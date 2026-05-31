"""
history_service.py
------------------
Persists meter readings over time and calculates weekly / monthly consumption.

Storage: /data/{reader_id}_history.json
Format:  [{"ts": "2026-05-31T18:00:00", "value": 12345.0}, ...]

Rolling window: keeps the last MAX_ENTRIES records per reader.
"""

import json
import os
import threading
from datetime import datetime, timedelta
from typing import List, Optional

DATA_DIR = '/data'
MAX_ENTRIES = 500  # ~17 days at 30-second intervals


class HistoryService:
    """Thread-safe history store for meter readings."""

    def __init__(self, data_dir: str = DATA_DIR):
        self._data_dir = data_dir
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, reader_id: str, value_str: str) -> None:
        """Append a new reading.  Silently ignores unparseable values."""
        try:
            value = float(value_str)
        except (TypeError, ValueError):
            return

        ts = datetime.now().isoformat(timespec='seconds')
        entry = {'ts': ts, 'value': value}

        with self._lock:
            history = self._load(reader_id)
            history.append(entry)
            # Rolling window
            if len(history) > MAX_ENTRIES:
                history = history[-MAX_ENTRIES:]
            self._save(reader_id, history)

    def get_weekly(self, reader_id: str) -> Optional[float]:
        """Return consumption over the last 7 days, or None if not enough data."""
        return self._delta(reader_id, days=7)

    def get_monthly(self, reader_id: str) -> Optional[float]:
        """Return consumption over the last 30 days, or None if not enough data."""
        return self._delta(reader_id, days=30)

    def get_history(self, reader_id: str) -> List[dict]:
        """Return a copy of the full history list."""
        with self._lock:
            return list(self._load(reader_id))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _delta(self, reader_id: str, days: int) -> Optional[float]:
        """Compute (latest value) - (value N days ago)."""
        with self._lock:
            history = self._load(reader_id)

        if len(history) < 2:
            return None

        latest = history[-1]
        cutoff = datetime.now() - timedelta(days=days)

        # Find the closest entry at-or-before the cutoff
        reference = None
        for entry in history:
            try:
                ts = datetime.fromisoformat(entry['ts'])
            except (ValueError, KeyError):
                continue
            if ts <= cutoff:
                reference = entry
            else:
                break  # history is sorted ascending

        if reference is None:
            return None

        try:
            delta = float(latest['value']) - float(reference['value'])
            return round(delta, 4) if delta >= 0 else None
        except (TypeError, ValueError):
            return None

    def _path(self, reader_id: str) -> str:
        return os.path.join(self._data_dir, f'{reader_id}_history.json')

    def _load(self, reader_id: str) -> List[dict]:
        """Load history from disk.  Returns [] on any error.  Caller must hold _lock."""
        path = self._path(reader_id)
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception as e:
            print(f'[history_service] Error loading {path}: {e}')
        return []

    def _save(self, reader_id: str, history: List[dict]) -> None:
        """Persist history to disk.  Caller must hold _lock."""
        os.makedirs(self._data_dir, exist_ok=True)
        path = self._path(reader_id)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False)
        except Exception as e:
            print(f'[history_service] Error saving {path}: {e}')
