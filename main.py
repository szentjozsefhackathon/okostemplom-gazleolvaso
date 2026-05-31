import io
import os
import socket

import cv2
from flask import Flask, jsonify, render_template, request, send_file

from detection import fetch_image
from reader_service import ReaderService

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

socket.setdefaulttimeout(10)

app = Flask(__name__)

# Global ReaderService instance – started once at module load
service = ReaderService()
service.start()


@app.context_processor
def inject_ingress_path():
    """Inject HA ingress base path into all templates so relative URLs work."""
    ingress_path = request.headers.get('X-Ingress-Path', '').rstrip('/')
    return {'ingress_path': ingress_path}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.route('/healthz')
def health_check():
    try:
        readers = service.get_all_readers()
        return jsonify({
            'status': 'healthy',
            'service': 'okostemplom_gazleolvaso',
            'version': '2.0.0',
            'readers_count': len(readers),
        }), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Pages (HTML)
# ---------------------------------------------------------------------------

@app.route('/')
def dashboard():
    """Main dashboard – list of all readers."""
    return render_template('index.html')


@app.route('/reader/<reader_id>/settings')
def reader_settings_page(reader_id: str):
    """Per-reader settings page."""
    reader = service.get_reader(reader_id)
    if reader is None:
        return 'Leolvasó nem található', 404
    return render_template('reader_settings.html', reader_id=reader_id)


# ---------------------------------------------------------------------------
# REST API – readers CRUD
# ---------------------------------------------------------------------------

@app.route('/api/readers', methods=['GET'])
def api_get_readers():
    """Return all readers with live state."""
    return jsonify(service.get_all_readers())


@app.route('/api/readers', methods=['POST'])
def api_add_reader():
    """Create a new reader."""
    data = request.get_json(force=True) or {}
    reader = service.add_reader(data)
    return jsonify({'success': True, 'reader': reader}), 201


@app.route('/api/readers/<reader_id>', methods=['GET'])
def api_get_reader(reader_id: str):
    """Return a single reader config + state."""
    reader = service.get_reader(reader_id)
    if reader is None:
        return jsonify({'error': 'Leolvasó nem található'}), 404
    return jsonify(reader)


@app.route('/api/readers/<reader_id>', methods=['PUT'])
def api_update_reader(reader_id: str):
    """Update a reader's config and restart its worker."""
    data = request.get_json(force=True) or {}
    updated = service.update_reader(reader_id, data)
    if updated is None:
        return jsonify({'error': 'Leolvasó nem található'}), 404
    return jsonify({'success': True, 'reader': updated})


@app.route('/api/readers/<reader_id>', methods=['DELETE'])
def api_delete_reader(reader_id: str):
    """Delete a reader and clean up its files."""
    removed = service.delete_reader(reader_id)
    if not removed:
        return jsonify({'error': 'Leolvasó nem található'}), 404
    return jsonify({'success': True})


@app.route('/api/readers/<reader_id>/trigger', methods=['POST'])
def api_trigger_reader(reader_id: str):
    """Manually trigger an immediate detection run for a reader."""
    ok = service.trigger_now(reader_id)
    if not ok:
        return jsonify({'error': 'Leolvasó nem található'}), 404
    return jsonify({'success': True, 'message': 'Leolvasás elindítva'})


# ---------------------------------------------------------------------------
# REST API – snapshot helpers
# ---------------------------------------------------------------------------

@app.route('/api/readers/<reader_id>/snapshot')
def api_reader_snapshot(reader_id: str):
    """Return a fresh live snapshot from the reader's RTSP stream (color PNG)."""
    reader = service.get_reader(reader_id)
    if reader is None:
        return jsonify({'error': 'Leolvasó nem található'}), 404

    rtsp_url = reader.get('rtsp_url', '')
    img = fetch_image(rtsp_url, grayscale=False)
    if img is None:
        return jsonify({'error': 'Nem sikerült képet lekérni az RTSP streamből'}), 500

    success, buffer = cv2.imencode('.png', img)
    if not success:
        return jsonify({'error': 'Nem sikerült a képet kódolni'}), 500

    return send_file(io.BytesIO(buffer.tobytes()), mimetype='image/png')


@app.route('/api/snapshot')
def api_generic_snapshot():
    """Legacy / settings-preview endpoint: fetch snapshot for any rtsp_url query param."""
    rtsp_url = request.args.get('rtsp_url', '')
    if not rtsp_url:
        return jsonify({'error': 'rtsp_url paraméter szükséges'}), 400

    img = fetch_image(rtsp_url, grayscale=False)
    if img is None:
        return jsonify({'error': 'Nem sikerült képet lekérni'}), 500

    success, buffer = cv2.imencode('.png', img)
    if not success:
        return jsonify({'error': 'Nem sikerült a képet kódolni'}), 500

    return send_file(io.BytesIO(buffer.tobytes()), mimetype='image/png')


# ---------------------------------------------------------------------------
# Static media files (saved snapshots / processed images)
# ---------------------------------------------------------------------------

@app.route('/media/<path:filename>')
def serve_media(filename: str):
    """Serve files from /media (snapshots, processed images)."""
    media_path = f'/media/{filename}'
    if not os.path.exists(media_path):
        return jsonify({'error': 'Fájl nem található'}), 404
    # Determine MIME type
    if filename.endswith('.png'):
        mimetype = 'image/png'
    elif filename.endswith('.txt'):
        mimetype = 'text/plain; charset=utf-8'
    else:
        mimetype = 'application/octet-stream'
    return send_file(media_path, mimetype=mimetype)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("Starting Okostemplom Gázleolvasó v2 Flask app...")
    logger.info(f"Hostname: {socket.gethostname()}")
    logger.info("Binding to 0.0.0.0:8099")
    app.run(host='0.0.0.0', port=8099, debug=False, use_reloader=False)
