import json
import os
import io
import subprocess
import socket
from datetime import datetime
from detection import detection, set_settings, fetch_image
from flask import Flask, render_template, jsonify, request, send_file
import cv2


# Set socket timeout for RTSP connections
socket.setdefaulttimeout(10)

app = Flask(__name__)

@app.context_processor
def inject_ingress_path():
    """Inject HA ingress base path into all templates so relative URLs work correctly."""
    ingress_path = request.headers.get('X-Ingress-Path', '').rstrip('/')
    return {'ingress_path': ingress_path}


last_result = ['?'] * 5

# Global settings state
SETTINGS_FILE = '/media/addon_settings.json'
DEFAULT_RTSP_URL = "rtsp://szentjozsef:KonyorogjErtunk@10.5.10.39/stream1"

# Default settings
DEFAULT_SETTINGS = {
    'rtsp_url': DEFAULT_RTSP_URL,
    'angle': -2,
    'roi_y_start': 560,
    'roi_y_end': 610,
    'x_start': 768,
    'x_end': 1005
}

# Current settings in memory
_current_settings = DEFAULT_SETTINGS.copy()

def load_settings():
    """Load settings from HOME ASSISTANT OPTIONS environment variable or settings file"""
    global _current_settings
    
    settings = DEFAULT_SETTINGS.copy()
    
    # Try to read from OPTIONS environment variable (Home Assistant addon config)
    options_json = os.environ.get('OPTIONS', '{}')
    try:
        options = json.loads(options_json)
        # Only update the non-RTSP settings from options
        if 'angle' in options:
            settings['angle'] = options['angle']
        if 'roi_y_start' in options:
            settings['roi_y_start'] = options['roi_y_start']
        if 'roi_y_end' in options:
            settings['roi_y_end'] = options['roi_y_end']
        if 'x_start' in options:
            settings['x_start'] = options['x_start']
        if 'x_end' in options:
            settings['x_end'] = options['x_end']
        if 'rtsp_url' in options:
            settings['rtsp_url'] = options['rtsp_url']
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error loading OPTIONS: {e}")
    
    # Try to load from settings file (persistent user settings)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                file_settings = json.load(f)
                settings.update(file_settings)
        except Exception as e:
            print(f"Error loading settings file: {e}")
    
    _current_settings = settings
    return settings

def save_settings(settings):
    """Save settings to file and environment"""
    global _current_settings
    
    try:
        # Save to file
        os.makedirs('/media', exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        
        # Update Home Assistant OPTIONS environment variable
        # Note: In a Docker container, we can't directly modify the environment,
        # but we can write a script that Home Assistant can read
        options_file = '/data/options.json'
        os.makedirs('/data', exist_ok=True)
        with open(options_file, 'w') as f:
            json.dump({
                'angle': settings['angle'],
                'roi_y_start': settings['roi_y_start'],
                'roi_y_end': settings['roi_y_end'],
                'x_start': settings['x_start'],
                'x_end': settings['x_end'],
                'rtsp_url': settings['rtsp_url']
            }, f, indent=2)
        
        _current_settings = settings
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def restart_service():
    """Restart the service to apply new settings"""
    try:
        # Try s6 service manager (common in Home Assistant addons)
        print("[DEBUG] Attempting to restart service with s6...")
        subprocess.run(['s6-rc-service-down', 'gazleolvaso'], timeout=5)
        subprocess.run(['s6-rc-service-up', 'gazleolvaso'], timeout=5)
        print("[INFO] Service restarted successfully with s6")
        return True
    except FileNotFoundError:
        print("[DEBUG] s6 service manager not found, trying supervisorctl...")
        try:
            # Fallback: Try supervisorctl
            subprocess.run(['supervisorctl', 'restart', 'gazleolvaso'], timeout=5)
            print("[INFO] Service restarted successfully with supervisorctl")
            return True
        except Exception as e2:
            print(f"[ERROR] Error restarting service with supervisorctl: {e2}")
            return False
    except Exception as e:
        print(f"[ERROR] Error restarting service with s6: {e}")
        try:
            # Fallback: Try supervisorctl
            subprocess.run(['supervisorctl', 'restart', 'gazleolvaso'], timeout=5)
            print("[INFO] Service restarted successfully with supervisorctl (fallback)")
            return True
        except Exception as e2:
            print(f"[ERROR] Error restarting service with supervisorctl: {e2}")
            return False

# Load settings on startup with error handling
try:
    load_settings()
    set_settings(**_current_settings)
    print("[INFO] Settings loaded successfully")
except Exception as e:
    print(f"[ERROR] Failed to load settings on startup: {e}")
    import traceback
    traceback.print_exc()

@app.route('/healthz')
def health_check():
    """Health check endpoint for Home Assistant Supervisor ingress"""
    try:
        return jsonify({
            'status': 'healthy',
            'service': 'okostemplom_gazleolvaso',
            'version': '1.0.6',
            'settings': _current_settings
        }), 200
    except Exception as e:
        print(f"[ERROR] Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.route('/')
def result():
    result = detection(rtsp_url=_current_settings['rtsp_url'])

    for idx, c in enumerate(result):
        if c != '?': last_result[idx] = c
        else: result[idx] = last_result[idx]
    result = ''.join(result)

    return render_template('index.html', number=result)

@app.route('/settings')
def settings_page():
    """Render the settings page"""
    return render_template('settings.html')

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Return current settings as JSON"""
    return jsonify(_current_settings)

@app.route('/api/snapshot', methods=['GET'])
def get_snapshot():
    """Return a snapshot from the RTSP stream as PNG"""
    rtsp_url = request.args.get('rtsp_url', _current_settings['rtsp_url'])
    
    # Fetch color image (not grayscale)
    img = fetch_image(rtsp_url, grayscale=False)
    
    if img is None:
        return jsonify({'error': 'Failed to fetch image from RTSP stream'}), 500
    
    # Encode as PNG
    success, buffer = cv2.imencode('.png', img)
    if not success:
        return jsonify({'error': 'Failed to encode image'}), 500
    
    return send_file(
        io.BytesIO(buffer.tobytes()),
        mimetype='image/png',
        as_attachment=False
    )

@app.route('/api/settings', methods=['POST'])
def save_settings_endpoint():
    """Save new settings and restart service"""
    try:
        data = request.get_json()
        
        # Validate settings
        new_settings = _current_settings.copy()
        
        if 'angle' in data:
            angle = int(data['angle'])
            if -180 <= angle <= 180:
                new_settings['angle'] = angle
        
        if 'roi_y_start' in data:
            new_settings['roi_y_start'] = int(data['roi_y_start'])
        
        if 'roi_y_end' in data:
            new_settings['roi_y_end'] = int(data['roi_y_end'])
        
        if 'x_start' in data:
            new_settings['x_start'] = int(data['x_start'])
        
        if 'x_end' in data:
            new_settings['x_end'] = int(data['x_end'])
        
        if 'rtsp_url' in data:
            new_settings['rtsp_url'] = str(data['rtsp_url']).strip()
        
        # Save settings
        if save_settings(new_settings):
            # Update in-memory settings
            set_settings(
                angle=new_settings['angle'],
                roi_y_start=new_settings['roi_y_start'],
                roi_y_end=new_settings['roi_y_end'],
                x_start=new_settings['x_start'],
                x_end=new_settings['x_end']
            )
            
            # Try to restart service
            restart_success = restart_service()
            
            if restart_success:
                return jsonify({
                    'success': True,
                    'message': 'Beállítások mentve és szolgáltatás újraindítva',
                    'settings': new_settings
                }), 200
            else:
                return jsonify({
                    'success': True,
                    'warning': 'Beállítások mentve, de a szolgáltatás újraindítása sikertelen. Kérjük, indítsa újra manuálisan.',
                    'settings': new_settings
                }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Hiba a beállítások mentése során'
            }), 500
    
    except Exception as e:
        print(f"Error in save_settings_endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Run Flask app on all interfaces (needed for Home Assistant ingress)
    import logging
    import socket
    
    # Add diagnostic logging for ingress connectivity
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    # Log startup details
    logger.info("Starting Okostemplom Gázleolvasó Flask app...")
    logger.info(f"Hostname: {socket.gethostname()}")
    logger.info(f"Binding to 0.0.0.0:8099 for Home Assistant ingress")
    
    try:
        # Verify socket can bind before starting Flask
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.bind(('0.0.0.0', 8099))
        test_socket.close()
        logger.info("Port 8099 is available for binding")
    except Exception as e:
        logger.error(f"Failed to bind to port 8099: {e}")
    
    app.run(host='0.0.0.0', port=8099, debug=False, use_reloader=False)
