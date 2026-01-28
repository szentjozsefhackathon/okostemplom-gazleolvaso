#!/usr/bin/with-contenv bashio

echo "[INFO] Okostemplom Gázleolvasó indul..."

# Start the multi-camera service which reads /data/options.json from the addon UI
# python3 /app/multi_camera_service.py &

# Keep the container running by tailing logs (or you can run cli.py interactively)
# If you want the old behavior when running manually, uncomment the next line
# Run CLI unbuffered so prints appear immediately in container logsy
exec python3 -u /app/cli.py

# Wait indefinitely so the container doesn't exit
tail -f /dev/null
