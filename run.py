# run.py — SnapYTube Ultimate (Render-Ready + PWA)

import os
import sys
import json
import uuid
import queue
import threading
import mimetypes
from urllib.parse import unquote
from flask import (Flask, request, jsonify, send_file,
                   Response, stream_with_context)
from flask_cors import CORS

from config import Config, IS_PRODUCTION
from downloader import downloader

app = Flask(__name__,
            template_folder=Config.TEMPLATE_FOLDER,
            static_folder=Config.STATIC_FOLDER)
app.config['SECRET_KEY'] = os.urandom(24)
CORS(app)

INDEX_HTML_PATH = os.path.join(Config.BASE_DIR, 'index.html')


# ══════════════════════════════════════════════
# MIDDLEWARE
# ══════════════════════════════════════════════

@app.before_request
def set_client_folder():
    client_ip = Config.get_client_ip(request)
    downloader.setup_for_client(client_ip)


# ══════════════════════════════════════════════
# PWA Routes
# ══════════════════════════════════════════════

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "SnapYTube Ultimate",
        "short_name": "SnapYTube",
        "description": "حمّل فيديوهاتك من يوتيوب وتيك توك وأكثر",
        "start_url": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0a0012",
        "theme_color": "#7c3aed",
        "lang": "ar",
        "dir": "rtl",
        "icons": [
            {
                "src": "https://cdn-icons-png.flaticon.com/512/2111/2111463.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": "https://cdn-icons-png.flaticon.com/512/2111/2111463.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable"
            }
        ],
        "screenshots": [],
        "categories": ["utilities", "productivity"]
    })


@app.route('/sw.js')
def service_worker():
    sw_code = """
const CACHE = 'snapytube-v1';
const OFFLINE_URLS = ['/'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(OFFLINE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(clients.claim());
});

self.addEventListener('fetch', e => {
  // لا نكاش API requests
  if (e.request.url.includes('/api/')) {
    e.respondWith(fetch(e.request));
    return;
  }
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
"""
    return Response(sw_code, mimetype='application/javascript',
                    headers={'Cache-Control': 'no-cache'})


# ══════════════════════════════════════════════
# Main Routes
# ══════════════════════════════════════════════

@app.route('/')
def index():
    if os.path.exists(INDEX_HTML_PATH):
        with open(INDEX_HTML_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    return f"<h1>{Config.APP_NAME} — السيرفر يعمل ✅</h1>"


@app.route('/api/download', methods=['POST'])
def api_download():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'بيانات غير صالحة'}), 400
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'status': 'error', 'message': Config.MESSAGES['invalid_url']}), 400

        result = downloader.download(url)
        if result['success']:
            return jsonify({
                'status': 'success',
                'message': Config.MESSAGES['download_success'],
                **{k: result.get(k) for k in ['filename','title','platform','duration',
                                               'filesize','filesize_mb','quality','thumbnail']},
                'download_url': f"/api/video/{result['filename']}"
            })
        return jsonify({'status': 'error', 'message': result['error']}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/download/progress', methods=['POST'])
def api_download_progress():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'بيانات غير صالحة'}), 400
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'status': 'error', 'message': Config.MESSAGES['invalid_url']}), 400

        download_id  = str(uuid.uuid4())[:8]
        progress_queue = queue.Queue()

        def progress_callback(pd):
            try:
                progress_queue.put({
                    'type': 'progress',
                    'download_id': download_id,
                    'data': {
                        'percent':   pd.get('percent', 0),
                        'speed':     pd.get('speed', 0),
                        'speed_str': pd.get('speed_str', '0 B/s'),
                        'eta':       pd.get('eta', '?'),
                        'status':    pd.get('status', 'downloading')
                    }
                })
            except:
                pass

        def generate():
            def do_download():
                try:
                    result = downloader.download(url, progress_callback, download_id)
                    if result.get('success'):
                        result['message']      = Config.MESSAGES['download_success']
                        result['download_url'] = f"/api/video/{result['filename']}"
                        result['original_url'] = url   # ✅ نرجعه للـ frontend
                    progress_queue.put({'type': 'complete', 'data': result})
                except Exception as ex:
                    progress_queue.put({'type': 'complete',
                                        'data': {'success': False, 'error': str(ex)}})

            t = threading.Thread(target=do_download, daemon=True)
            t.start()

            while True:
                try:
                    msg = progress_queue.get(timeout=60)
                    yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                    if msg.get('type') == 'complete':
                        break
                except queue.Empty:
                    yield f"data: {json.dumps({'type':'heartbeat'})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control':         'no-cache',
                'X-Accel-Buffering':     'no',
                'Access-Control-Allow-Origin': '*'
            }
        )
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/video/<path:filename>')
def api_video(filename):
    """إرسال الملف ثم حذفه تلقائياً (يوفر مساحة على Render)"""
    try:
        filename = os.path.basename(unquote(filename))
        folder   = downloader.download_folder
        filepath = os.path.join(folder, filename)

        # بحث جزئي إذا ما وُجد المسار المباشر
        if not os.path.exists(filepath):
            for f in os.listdir(folder):
                if filename in f:
                    filepath = os.path.join(folder, f)
                    filename = f
                    break

        if not os.path.exists(filepath):
            return jsonify({'error': 'الملف غير موجود'}), 404

        # ✅ على Render: احذف الملف بعد الإرسال لتوفير المساحة
        def delete_after_send():
            import time
            time.sleep(30)   # انتظر 30 ثانية بعد بدء الإرسال
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"🗑️  حُذف: {filename}")
            except:
                pass

        if IS_PRODUCTION:
            threading.Thread(target=delete_after_send, daemon=True).start()

        return send_file(filepath, as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/videos', methods=['GET'])
def api_videos():
    try:
        videos = []
        folder = downloader.download_folder
        if folder and os.path.exists(folder):
            for f in os.listdir(folder):
                if f.lower().endswith(('.mp4', '.webm', '.mkv')):
                    fp   = os.path.join(folder, f)
                    size = os.path.getsize(fp)
                    videos.append({
                        'name':     f,
                        'url':      f'/api/video/{f}',
                        'size':     size,
                        'size_mb':  round(size / (1024*1024), 1),
                        'created':  os.path.getctime(fp)
                    })
        videos.sort(key=lambda x: x['created'], reverse=True)
        return jsonify({'status':'success','videos':videos,'count':len(videos)})
    except Exception as e:
        return jsonify({'status':'error','message':str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def api_stats():
    try:
        stats      = downloader.get_stats()
        total_size = 0
        videos     = []
        folder     = downloader.download_folder
        if folder and os.path.exists(folder):
            for f in os.listdir(folder):
                if f.lower().endswith(('.mp4', '.webm', '.mkv')):
                    total_size += os.path.getsize(os.path.join(folder, f))
                    videos.append(f)
        return jsonify({
            'status':       'success',
            'total':        len(videos),
            'total_size_mb': round(total_size/(1024*1024), 1),
            'today':        stats.get('today', 0),
            'download_folder': folder
        })
    except Exception as e:
        return jsonify({'status':'error','message':str(e)}), 500


@app.route('/api/health')
def api_health():
    return jsonify({
        'status':  'ok',
        'app':     Config.APP_NAME,
        'version': Config.APP_VERSION,
        'mode':    'production' if IS_PRODUCTION else 'local',
        'supported_platforms': list(Config.SUPPORTED_PLATFORMS.keys())
    })


# ══════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════

def main():
    print(Config.get_banner())
    print(f"🌐 http://localhost:{Config.PORT}")
    if not IS_PRODUCTION:
        print(f"🌍 http://{Config.get_local_ip()}:{Config.PORT}")
    print(f"🔴 Ctrl+C لإيقاف\n")

    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
        threaded=True
    )


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n🛑 {Config.MESSAGES['server_stop']}")
        sys.exit(0)
