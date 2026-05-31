"""
mqtt_publisher.py
-----------------
Publishes meter readings to Home Assistant via MQTT Discovery.

Each reader appears as a separate HA Device with these entities:
  - sensor: mérőállás (total_increasing, m³, device_class gas)
  - sensor: heti fogyasztás (measurement, m³, device_class gas)
  - sensor: havi fogyasztás (measurement, m³, device_class gas)
  - sensor: utolsó leolvasás (device_class timestamp)
  - sensor: snapshot URL  (string)
  - sensor: feldolgozott kép URL (string)

MQTT credentials are obtained in priority order:
  1. HA Supervisor services API  (automatic when mqtt:want is set in config.yaml)
  2. Addon options (mqtt_host / mqtt_port / mqtt_username / mqtt_password)
  3. Defaults (localhost:1883, no auth)

All publish calls are fire-and-forget; errors are logged but never raised.
"""

import json
import logging
import os
import threading
from typing import Optional

try:
    import paho.mqtt.client as _mqtt_module
    _PAHO_AVAILABLE = True
except ImportError:
    _mqtt_module = None  # type: ignore[assignment]
    _PAHO_AVAILABLE = False

logger = logging.getLogger(__name__)

_DISCOVERY_PREFIX = 'homeassistant'
_STATE_PREFIX = 'gazleolvaso'
_ADDON_SLUG = 'gazleolvaso'


def _get_supervisor_mqtt() -> Optional[dict]:
    """Try to fetch MQTT credentials from the HA Supervisor API."""
    try:
        import urllib.request
        token = os.environ.get('SUPERVISOR_TOKEN', '')
        if not token:
            return None
        req = urllib.request.Request(
            'http://supervisor/services/mqtt',
            headers={'Authorization': f'Bearer {token}'},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        if data.get('result') == 'ok':
            svc = data.get('data', {})
            return {
                'host': svc.get('host', 'core-mosquitto'),
                'port': int(svc.get('port', 1883)),
                'username': svc.get('username', ''),
                'password': svc.get('password', ''),
            }
    except Exception as e:
        logger.debug(f'[mqtt_publisher] Supervisor MQTT lookup failed: {e}')
    return None


def _load_addon_options() -> dict:
    """Read /data/options.json (HA addon runtime options)."""
    try:
        with open('/data/options.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


class MqttPublisher:
    """Thread-safe MQTT client for HA Discovery publishing."""

    def __init__(self):
        self._lock = threading.Lock()
        self._client = None  # paho mqtt.Client instance or None
        self._connected = False
        self._connect()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def publish_discovery(self, reader_id: str, reader_name: str) -> None:
        """Send MQTT Discovery config messages for all entities of a reader."""
        if not self._connected:
            return
        device = self._device_info(reader_id, reader_name)
        state_topic = self._state_topic(reader_id)

        entities = [
            # (entity_type, object_suffix, name, value_template, extra)
            ('sensor', 'value', f'{reader_name} Mérőállás',
             '{{ value_json.value }}',
             {'unit_of_measurement': 'm³', 'device_class': 'gas',
              'state_class': 'total_increasing', 'icon': 'mdi:meter-gas'}),

            ('sensor', 'weekly', f'{reader_name} Heti fogyasztás',
             '{{ value_json.weekly }}',
             {'unit_of_measurement': 'm³', 'device_class': 'gas',
              'state_class': 'measurement', 'icon': 'mdi:calendar-week'}),

            ('sensor', 'monthly', f'{reader_name} Havi fogyasztás',
             '{{ value_json.monthly }}',
             {'unit_of_measurement': 'm³', 'device_class': 'gas',
              'state_class': 'measurement', 'icon': 'mdi:calendar-month'}),

            ('sensor', 'last_run', f'{reader_name} Utolsó leolvasás',
             '{{ value_json.last_run }}',
             {'device_class': 'timestamp', 'icon': 'mdi:clock-check'}),

            ('sensor', 'snapshot_url', f'{reader_name} Snapshot URL',
             '{{ value_json.snapshot_url }}',
             {'icon': 'mdi:camera'}),

            ('sensor', 'processed_url', f'{reader_name} Feldolgozott kép URL',
             '{{ value_json.processed_url }}',
             {'icon': 'mdi:image-filter-center-focus'}),
        ]

        for entity_type, suffix, name, value_template, extra in entities:
            unique_id = f'gazleolvaso_{reader_id}_{suffix}'
            config_topic = (
                f'{_DISCOVERY_PREFIX}/{entity_type}/{unique_id}/config'
            )
            payload = {
                'name': name,
                'unique_id': unique_id,
                'state_topic': state_topic,
                'value_template': value_template,
                'device': device,
                **extra,
            }
            self._publish(config_topic, json.dumps(payload, ensure_ascii=False), retain=True)

        logger.info(f'[mqtt_publisher] Discovery published for reader {reader_id} ({reader_name})')

    def publish_state(
        self,
        reader_id: str,
        reader_name: str,
        value: str,
        last_run: str,
        weekly: Optional[float],
        monthly: Optional[float],
        snapshot_url: str = '',
        processed_url: str = '',
    ) -> None:
        """Publish a JSON state payload to the reader's state topic."""
        if not self._connected:
            return

        payload = {
            'value': value,
            'weekly': weekly if weekly is not None else 'unknown',
            'monthly': monthly if monthly is not None else 'unknown',
            'last_run': last_run,
            'snapshot_url': snapshot_url,
            'processed_url': processed_url,
        }
        self._publish(
            self._state_topic(reader_id),
            json.dumps(payload, ensure_ascii=False),
            retain=True,
        )
        logger.debug(f'[mqtt_publisher] State published for {reader_id}: {payload}')

    def remove_discovery(self, reader_id: str) -> None:
        """Remove all discovery entries for a deleted reader (empty retained payload)."""
        if not self._connected:
            return
        suffixes = ['value', 'weekly', 'monthly', 'last_run', 'snapshot_url', 'processed_url']
        for suffix in suffixes:
            unique_id = f'gazleolvaso_{reader_id}_{suffix}'
            for entity_type in ('sensor',):
                config_topic = f'{_DISCOVERY_PREFIX}/{entity_type}/{unique_id}/config'
                self._publish(config_topic, '', retain=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _state_topic(self, reader_id: str) -> str:
        return f'{_STATE_PREFIX}/{reader_id}/state'

    def _device_info(self, reader_id: str, reader_name: str) -> dict:
        return {
            'identifiers': [f'gazleolvaso_{reader_id}'],
            'name': reader_name,
            'manufacturer': 'Okostemplom',
            'model': 'Gázleolvasó OCR',
            'sw_version': '2.0.0',
        }

    def _publish(self, topic: str, payload: str, retain: bool = False) -> None:
        if not self._connected or self._client is None:
            return
        try:
            with self._lock:
                self._client.publish(topic, payload, qos=1, retain=retain)
        except Exception as e:
            logger.warning(f'[mqtt_publisher] Publish failed ({topic}): {e}')
            self._connected = False

    def _connect(self) -> None:
        """Resolve MQTT credentials and connect.  Fails silently."""
        if not _PAHO_AVAILABLE:
            logger.warning('[mqtt_publisher] paho-mqtt not installed; MQTT disabled.')
            return

        creds = _get_supervisor_mqtt()
        if creds is None:
            opts = _load_addon_options()
            host = opts.get('mqtt_host', '').strip()
            if not host:
                logger.info('[mqtt_publisher] No MQTT config found; MQTT disabled.')
                return
            creds = {
                'host': host,
                'port': int(opts.get('mqtt_port', 1883)),
                'username': opts.get('mqtt_username', ''),
                'password': opts.get('mqtt_password', ''),
            }

        try:
            client = _mqtt_module.Client(client_id='gazleolvaso_addon', clean_session=True)  # type: ignore[union-attr]
            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect

            if creds.get('username'):
                client.username_pw_set(creds['username'], creds.get('password', ''))

            client.connect(creds['host'], creds['port'], keepalive=60)
            client.loop_start()
            self._client = client
            # _connected is set to True in on_connect callback
            logger.info(
                f"[mqtt_publisher] Connecting to {creds['host']}:{creds['port']} ..."
            )
        except Exception as e:
            logger.warning(f'[mqtt_publisher] Connection failed: {e}')

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            logger.info('[mqtt_publisher] Connected to MQTT broker.')
        else:
            self._connected = False
            logger.warning(f'[mqtt_publisher] MQTT connect error rc={rc}')

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            logger.warning(f'[mqtt_publisher] Unexpected MQTT disconnect rc={rc}')
