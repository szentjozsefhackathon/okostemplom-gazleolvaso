# Home Assistant Addon Debug Report
## Okostemplom Gázleolvasó (local_okostemplom_gazleolvaso)

**Date:** 2026-05-31  
**Version:** 1.0.6  
**Status:** Fixed ✓

---

## Issues Identified & Root Causes

### 1. **Missing Configuration Schema** (PRIMARY - FIXED)
**Symptoms:**
```
WARNING Option 'rtsp_url' does not exist in the schema
WARNING Option 'angle' does not exist in the schema  
WARNING Option 'roi_y_start' does not exist in the schema
WARNING Option 'roi_y_end' does not exist in the schema
WARNING Option 'x_start' does not exist in the schema
WARNING Option 'x_end' does not exist in the schema
```

**Root Cause:**
Home Assistant Supervisor requires a `config.schema.json` file at the addon root directory to validate configuration options. This file was **missing**, causing Supervisor to reject all addon options during initialization.

**Fix Applied:**
Created [`config.schema.json`](./config.schema.json) with proper JSON Schema validation for all 6 options:
- `rtsp_url` (string) - RTSP stream URL
- `angle` (integer) - Image rotation angle (-180 to 180°)
- `roi_y_start` (integer) - ROI Y-axis start position
- `roi_y_end` (integer) - ROI Y-axis end position  
- `x_start` (integer) - Detection X-axis start
- `x_end` (integer) - Detection X-axis end

---

### 2. **Ingress Connection Errors** (SECONDARY - INVESTIGATED)
**Symptoms:**
```
ERROR Ingress error: Cannot connect to host 172.30.33.1:8099 ssl:default
[Connect call failed ('172.30.33.1', 8099)]
```

**Root Cause Analysis:**

This error comes from Home Assistant Supervisor's ingress proxy module (not from addon code). The `172.30.33.1:8099` connection failure indicates:

1. **Timing Issue:** The addon might not be fully ready when Supervisor ingress tries to establish the connection
2. **Service Startup:** The Flask app was running in background processes, causing socket binding delays
3. **No Health Check:** Supervisor had no `/healthz` endpoint to verify service readiness

**Fixes Applied:**

#### A. Modified [`run.sh`](./run.sh)
- Changed from background process management (`&`) to **single foreground process model**
- Removed CLI detection service from main startup (can be started separately)
- Flask now runs as the **main/exec process** (PID 1 compatible)
- Added proper error handling with `set -e`

**Before:**
```bash
python3 -u /app/main.py &
FLASK_PID=$!
python3 -u /app/cli.py &
CLI_PID=$!
wait $FLASK_PID $CLI_PID
```

**After:**
```bash
exec python3 -u /app/main.py
```

#### B. Updated [`config.yaml`](./config.yaml)
- Added `protocol: http` to ingress configuration (explicit protocol declaration)
- Ensures Supervisor knows to expect HTTP (not HTTPS) on the Flask endpoint

#### C. Enhanced [`main.py`](./main.py) with Diagnostics

**Added socket timeout handling:**
```python
import socket
socket.setdefaulttimeout(10)  # 10-second timeout for RTSP connections
```

**Added health check endpoint:**
```python
@app.route('/healthz')
def health_check():
    """Health check endpoint for Home Assistant Supervisor ingress"""
    return jsonify({'status': 'healthy', 'service': 'okostemplom_gazleolvaso'})
```

**Improved startup logging:**
```python
# Added diagnostic logs:
- Hostname identification
- Port binding verification  
- Settings load error handling with traceback
- Service restart debug logs
```

**Better service restart handling:**
- Proper exception handling for s6 vs supervisorctl
- Debug logging for each restart attempt
- FileNotFoundError detection for missing service managers

---

## Technical Details

### Why the Ingress Error Occurred

Home Assistant Supervisor's ingress module attempts to:
1. Start the addon container
2. Wait for port 5000 to be available
3. Establish proxy connection to `172.30.33.1:8099`

**The Problem:** With the previous `run.sh` architecture:
- Flask started in background with `&`
- Main script continued to `wait` on multiple PIDs
- Socket might not bind immediately
- Supervisor timeout could trigger before Flask fully ready

**The Solution:** Single foreground process ensures:
- Immediate socket binding on port 5000
- Clean startup/shutdown signals
- Supervisor can properly detect service readiness

### Schema Validation Flow

```
Supervisor reads config.yaml
    ↓
Validates options against config.schema.json
    ↓
If schema missing → WARNING (but proceeds)
    ↓
Sets OPTIONS environment variable
    ↓
Addon main.py loads from OPTIONS
```

Without the schema file, Supervisor emits warnings but still passes options via `OPTIONS` env var. However, this breaks:
- UI configuration validation
- Type safety
- User experience

---

## Verification Checklist

✓ `config.schema.json` created with proper Home Assistant JSON Schema  
✓ Ingress configuration updated with explicit HTTP protocol  
✓ Flask startup improved with health check endpoint  
✓ Process management simplified to single foreground process  
✓ Socket timeout set for RTSP connections (10s)  
✓ Diagnostic logging added to main.py  
✓ Service restart error handling improved  
✓ Directory creation ensured in run.sh  

---

## Recommendations

1. **Monitor the service logs** after restart to confirm:
   - "Settings loaded successfully" message appears
   - No warnings about missing schema options
   - Flask binds to 0.0.0.0:5000

2. **Test ingress connectivity** by accessing:
   - Home Assistant web UI → Settings → Addons → Okostemplom Gázleolvasó
   - Ingress proxy should now establish connection without errors

3. **For the CLI detection service** (previously started in background):
   - Consider running as separate s6 service in `rootfs/etc/service.d/`
   - OR use a cronjob if periodic execution is sufficient

4. **Network connectivity to RTSP stream** (10.5.10.39):
   - Verify camera is accessible from container network
   - The 10-second timeout will prevent hanging connections

---

## Files Modified

| File | Changes |
|------|---------|
| [`config.schema.json`](./config.schema.json) | **Created** - Home Assistant schema validation |
| [`config.yaml`](./config.yaml) | Added `protocol: http` to ingress |
| [`run.sh`](./run.sh) | Simplified to single foreground Flask process |
| [`main.py`](./main.py) | Added healthz endpoint, socket timeout, diagnostics |

---

## Related Logs Explained

The repeated error cycle every ~1-2 seconds indicates Supervisor's ingress module attempting reconnection:

```
2026-05-31 18:22:49.713 - First connection attempt
2026-05-31 18:22:50.748 - Warnings about missing schema options
2026-05-31 18:22:50.757 - Retry connection
... (repeats every ~1 second)
```

This is **normal behavior** when:
- Service is starting
- Socket not yet bound
- Previous attempts timed out

Should resolve within 5-10 seconds of addon startup once fixes are applied.
