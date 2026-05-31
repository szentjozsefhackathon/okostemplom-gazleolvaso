"""
reader_service.py
-----------------
Background service that manages one detection thread per reader.
Readers are defined in /data/readers.json (managed via WebUI).

Each reader thread:
  - runs detection() at the configured poll_interval (seconds)
  - stores last_value, last_run, last_error in an in-memory state dict
  - writes output files to /media/{reader_id}_snapshot.png,
    /media/{reader_id}_processed.png, /media/{reader_id}_result.txt
  - records readings in HistoryService and publishes to HA via MqttPublisher
"""

import json
import os
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Optional

from detection import detection

READERS_FILE = '/data/readers.json'
MEDIA_DIR = '/media'

DEFAULT_READER = {
    'id': '',
    'name': 'Új leolvasó',
    'rtsp_url': '',
    'angle': -2,
    'roi_y_start': 560,
    'roi_y_end': 610,
    'x_start': 768,
    'x_end': 1005,
    'num_segments': 5,
    'poll_interval': 30,
}


def _new_id() -> str:
    """Generate a short unique reader ID."""
    return 'reader_' + uuid.uuid4().hex[:8]


def load_readers() -> List[Dict]:
    """Load the readers list from READERS_FILE.
    Returns an empty list if the file does not exist or is malformed.
    """
    if not os.path.exists(READERS_FILE):
        return []
    try:
        with open(READERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        print(f"[reader_service] Unexpected readers.json format: {type(data)}")
        return []
    except Exception as e:
        print(f"[reader_service] Error loading {READERS_FILE}: {e}")
        return []


def save_readers(readers: List[Dict]) -> bool:
    """Persist the readers list to READERS_FILE."""
    try:
        os.makedirs(os.path.dirname(READERS_FILE), exist_ok=True)
        with open(READERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(readers, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[reader_service] Error saving {READERS_FILE}: {e}")
        return False


class ReaderService:
    """Manages background detection threads for multiple readers."""

    def __init__(self, mqtt_publisher=None, history_service=None):
        self._mqtt = mqtt_publisher
        self._history = history_service
        self._lock = threading.Lock()
        # Dict[reader_id -> thread]
        self._threads: Dict[str, threading.Thread] = {}
        # Dict[reader_id -> threading.Event] – set to stop the thread
        self._stop_events: Dict[str, threading.Event] = {}
        # Dict[reader_id -> state dict]
        self._state: Dict[str, Dict] = {}
        # Persisted reader configs (list of dicts)
        self._readers: List[Dict] = []
        # Dict[reader_id -> last_result list] for sticky digits
        self._last_digits: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Load readers from disk and start all worker threads."""
        readers = load_readers()
        with self._lock:
            self._readers = readers
        for reader in readers:
            self._start_worker(reader)
            # Publish MQTT discovery for existing readers on startup
            if self._mqtt:
                try:
                    self._mqtt.publish_discovery(reader['id'], reader.get('name', reader['id']))
                except Exception as e:
                    print(f"[reader_service] MQTT discovery error for {reader['id']}: {e}")
        print(f"[reader_service] Started with {len(readers)} reader(s).")

    def stop(self):
        """Signal all worker threads to stop and wait for them."""
        with self._lock:
            ids = list(self._stop_events.keys())
        for rid in ids:
            self._stop_worker(rid)
        print("[reader_service] All workers stopped.")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get_all_readers(self) -> List[Dict]:
        """Return a deep copy of all reader configs with live state merged in."""
        with self._lock:
            result = []
            for r in self._readers:
                rd = deepcopy(r)
                state = self._state.get(r['id'], {})
                rd['last_value'] = state.get('last_value', None)
                rd['last_run'] = state.get('last_run', None)
                rd['last_error'] = state.get('last_error', None)
                rd['running'] = r['id'] in self._threads and self._threads[r['id']].is_alive()
                # Check if output files exist
                rid = r['id']
                rd['has_snapshot'] = os.path.exists(f"{MEDIA_DIR}/{rid}_snapshot.png")
                rd['has_processed'] = os.path.exists(f"{MEDIA_DIR}/{rid}_processed.png")
                result.append(rd)
        return result

    def get_reader(self, reader_id: str) -> Optional[Dict]:
        """Return config + state for a single reader, or None."""
        with self._lock:
            for r in self._readers:
                if r['id'] == reader_id:
                    rd = deepcopy(r)
                    state = self._state.get(reader_id, {})
                    rd['last_value'] = state.get('last_value', None)
                    rd['last_run'] = state.get('last_run', None)
                    rd['last_error'] = state.get('last_error', None)
                    rd['running'] = reader_id in self._threads and self._threads[reader_id].is_alive()
                    return rd
        return None

    def add_reader(self, data: Dict) -> Dict:
        """Create a new reader, persist, and start its worker thread.
        Returns the new reader dict (with generated id).
        """
        reader = {**DEFAULT_READER, **data}
        reader['id'] = _new_id()
        with self._lock:
            self._readers.append(reader)
            save_readers(self._readers)
        self._start_worker(reader)
        # Publish MQTT discovery for the new reader
        if self._mqtt:
            try:
                self._mqtt.publish_discovery(reader['id'], reader.get('name', reader['id']))
            except Exception as e:
                print(f"[reader_service] MQTT discovery error for {reader['id']}: {e}")
        return deepcopy(reader)

    def update_reader(self, reader_id: str, data: Dict) -> Optional[Dict]:
        """Update an existing reader config, restart its worker thread.
        Returns the updated reader dict or None if not found.
        """
        with self._lock:
            for i, r in enumerate(self._readers):
                if r['id'] == reader_id:
                    # Preserve id; merge new values
                    updated = {**r, **data, 'id': reader_id}
                    self._readers[i] = updated
                    save_readers(self._readers)
                    reader_copy = deepcopy(updated)
                    break
            else:
                return None

        # Restart worker with new config
        self._stop_worker(reader_id)
        self._start_worker(reader_copy)
        return reader_copy

    def delete_reader(self, reader_id: str) -> bool:
        """Stop the worker, remove config, delete output files.
        Returns True if the reader existed.
        """
        self._stop_worker(reader_id)
        with self._lock:
            before = len(self._readers)
            self._readers = [r for r in self._readers if r['id'] != reader_id]
            removed = len(self._readers) < before
            if removed:
                save_readers(self._readers)
                # Clean state
                self._state.pop(reader_id, None)
                self._last_digits.pop(reader_id, None)

        if removed:
            # Remove MQTT discovery entries
            if self._mqtt:
                try:
                    self._mqtt.remove_discovery(reader_id)
                except Exception as e:
                    print(f"[reader_service] MQTT remove_discovery error for {reader_id}: {e}")
            # Delete output files
            for suffix in ('_snapshot.png', '_processed.png', '_result.txt'):
                path = f"{MEDIA_DIR}/{reader_id}{suffix}"
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    print(f"[reader_service] Could not delete {path}: {e}")

        return removed

    def trigger_now(self, reader_id: str) -> bool:
        """Signal the worker for *reader_id* to run detection immediately.
        Returns True if the reader exists.
        """
        with self._lock:
            event = self._stop_events.get(reader_id)
        if event is None:
            return False
        # We can't directly wake a wait() on the stop_event without stopping it.
        # Instead we use a separate per-reader "run_now" event.
        run_now = self._run_now_events.get(reader_id)
        if run_now:
            run_now.set()
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    # Dict[reader_id -> threading.Event] – set to trigger immediate run
    _run_now_events: Dict[str, threading.Event] = {}

    def _start_worker(self, reader: Dict):
        rid = reader['id']
        stop_event = threading.Event()
        run_now_event = threading.Event()
        with self._lock:
            self._stop_events[rid] = stop_event
            self._run_now_events[rid] = run_now_event
            self._state.setdefault(rid, {})
            self._last_digits[rid] = ['?'] * int(reader.get('num_segments', 5))

        t = threading.Thread(
            target=self._worker,
            args=(reader, stop_event, run_now_event),
            daemon=True,
            name=f"reader-{rid}",
        )
        with self._lock:
            self._threads[rid] = t
        t.start()
        print(f"[reader_service] Worker started: {rid} ({reader.get('name', '')})")

    def _stop_worker(self, reader_id: str):
        with self._lock:
            stop_event = self._stop_events.pop(reader_id, None)
            run_now = self._run_now_events.pop(reader_id, None)
            thread = self._threads.pop(reader_id, None)
        if stop_event:
            stop_event.set()
        if run_now:
            run_now.set()
        if thread and thread.is_alive():
            thread.join(timeout=5)
        print(f"[reader_service] Worker stopped: {reader_id}")

    def _worker(self, reader: Dict, stop_event: threading.Event,
                run_now_event: threading.Event):
        """Worker loop: run detection, then sleep poll_interval seconds."""
        rid = reader['id']
        # Re-read config from live _readers so that updates are picked up after restart
        while not stop_event.is_set():
            # Fetch latest config
            with self._lock:
                cfg = next((deepcopy(r) for r in self._readers if r['id'] == rid), None)
            if cfg is None:
                break  # Reader was deleted

            poll_interval = int(cfg.get('poll_interval', 30))
            num_segments = int(cfg.get('num_segments', 5))

            try:
                digits = detection(reader_id=rid, config=cfg)

                # Sticky digits: replace '!' or '?' with last known good value
                with self._lock:
                    prev = self._last_digits.get(rid, ['?'] * num_segments)
                    if len(prev) != num_segments:
                        prev = ['?'] * num_segments

                sticky = []
                for i, d in enumerate(digits):
                    if d not in ('!', '?', '\n', ''):
                        sticky.append(d)
                    else:
                        sticky.append(prev[i] if i < len(prev) else '?')

                value_str = ''.join(sticky)
                last_run_iso = datetime.now().isoformat(timespec='seconds')
                with self._lock:
                    self._last_digits[rid] = sticky
                    self._state[rid] = {
                        'last_value': value_str,
                        'last_run': last_run_iso,
                        'last_error': None,
                    }

                # Record in history and publish to MQTT
                weekly = None
                monthly = None
                if self._history:
                    try:
                        self._history.record(rid, value_str)
                        weekly = self._history.get_weekly(rid)
                        monthly = self._history.get_monthly(rid)
                    except Exception as e:
                        print(f"[reader_service] History error for {rid}: {e}")

                if self._mqtt:
                    try:
                        snapshot_url = f'/media/{rid}_snapshot.png'
                        processed_url = f'/media/{rid}_processed.png'
                        self._mqtt.publish_state(
                            reader_id=rid,
                            reader_name=cfg.get('name', rid),
                            value=value_str,
                            last_run=last_run_iso,
                            weekly=weekly,
                            monthly=monthly,
                            snapshot_url=snapshot_url,
                            processed_url=processed_url,
                        )
                    except Exception as e:
                        print(f"[reader_service] MQTT publish error for {rid}: {e}")

            except Exception as e:
                print(f"[reader_service] Detection error for {rid}: {e}")
                with self._lock:
                    self._state[rid] = {
                        **self._state.get(rid, {}),
                        'last_error': str(e),
                        'last_run': datetime.now().isoformat(timespec='seconds'),
                    }

            # Sleep, but wake up early if stop or run_now is set
            run_now_event.clear()
            # Wait up to poll_interval; stop_event or run_now_event will wake us
            end = time.monotonic() + poll_interval
            while not stop_event.is_set() and not run_now_event.is_set():
                remaining = end - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(1.0, remaining))
