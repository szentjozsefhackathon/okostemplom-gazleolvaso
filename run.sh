#!/bin/bash

set -e

echo "[INFO] Okostemplom Gázleolvasó service starting..."
echo "[INFO] Home Assistant version: ${HOMEASSISTANT_VERSION:-unknown}"
echo "[INFO] Addon version: 2.0.0"

# Ensure /media and /data directories exist with proper permissions
mkdir -p /media
mkdir -p /data

# Start the Flask web server for the settings dashboard (MAIN PROCESS - must stay in foreground)
echo "[INFO] Starting Flask web server on port 8099..."
echo "[INFO] Ingress endpoint available at: http://localhost:8099"

# Flask in foreground - this is the main process for Home Assistant Supervisor
exec python3 -u /app/main.py
