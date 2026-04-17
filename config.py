# config.py — SnapYTube Ultimate (Render-Ready)

import os
import socket
from datetime import datetime

# ✅ نكتشف هل نحن على Render أو local
IS_PRODUCTION = bool(os.environ.get('RENDER') or os.environ.get('IS_RENDER'))

class Config:
    APP_NAME        = "SnapYTube Ultimate"
    APP_VERSION     = "4.0.0"
    APP_DESCRIPTION = "منصة متكاملة لتحميل الفيديوهات من جميع المنصات بجودة 4K"

    HOST  = '0.0.0.0'
    PORT  = int(os.environ.get('PORT', 5001))   # ✅ Render بيحدد PORT
    DEBUG = False

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # ✅ على Render نستخدم /tmp (مؤقت لكن كافي)
    if IS_PRODUCTION:
        USERS_FOLDER = '/tmp/snapytube/users'
        LOGS_FOLDER  = '/tmp/snapytube/logs'
        CACHE_FOLDER = '/tmp/snapytube/cache'
    else:
        USERS_FOLDER = os.path.join(BASE_DIR, 'users')
        LOGS_FOLDER  = os.path.join(BASE_DIR, 'logs')
        CACHE_FOLDER = os.path.join(BASE_DIR, 'cache')

    TEMPLATE_FOLDER  = os.path.join(BASE_DIR, 'templates')
    STATIC_FOLDER    = os.path.join(BASE_DIR, 'static')
    DOWNLOAD_FOLDER  = None

    MAX_FILE_SIZE_MB       = 2000
    MAX_CONCURRENT_DOWNLOADS = 2
    DOWNLOAD_TIMEOUT       = 600

    CACHE_ENABLED = True
    CACHE_TIMEOUT = 3600

    SUPPORTED_PLATFORMS = {
        'youtube': {
            'name': 'YouTube', 'icon': 'fab fa-youtube', 'color': '#FF0000',
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        },
        'tiktok':    {'name': 'TikTok',    'icon': 'fab fa-tiktok',    'color': '#000000', 'format': 'best[ext=mp4]/best'},
        'instagram': {'name': 'Instagram', 'icon': 'fab fa-instagram', 'color': '#E4405F', 'format': 'best[ext=mp4]/best'},
        'facebook':  {'name': 'Facebook',  'icon': 'fab fa-facebook',  'color': '#1877F2', 'format': 'best[ext=mp4]/best'},
        'twitter':   {'name': 'Twitter/X', 'icon': 'fab fa-twitter',   'color': '#1DA1F2', 'format': 'best[ext=mp4]/best'},
        'capcut':    {'name': 'CapCut',    'icon': 'fas fa-cut',       'color': '#00D4FF', 'format': 'best[ext=mp4]/best'},
        'vimeo':     {'name': 'Vimeo',     'icon': 'fab fa-vimeo',     'color': '#1AB7EA', 'format': 'best[ext=mp4]/best'},
    }

    MESSAGES = {
        'download_start':   '🎬 بدء تحميل الفيديو...',
        'download_success': '✅ تم التحميل! اضغط "احفظ على الهاتف"',
        'download_error':   '❌ فشل التحميل: {error}',
        'invalid_url':      '⚠️ الرابط غير صالح',
        'file_not_found':   '📁 الملف غير موجود',
        'server_start':     '🚀 السيرفر يعمل الآن',
        'server_stop':      '🛑 تم إيقاف السيرفر',
        'welcome':          '✨ مرحباً بك في SnapYTube Ultimate',
        'processing':       '⚙️ جاري المعالجة...'
    }

    @classmethod
    def get_client_ip(cls, request=None):
        if request:
            if request.headers.get('X-Forwarded-For'):
                return request.headers.get('X-Forwarded-For').split(',')[0].strip()
            elif request.headers.get('X-Real-IP'):
                return request.headers.get('X-Real-IP').strip()
            elif request.remote_addr:
                return request.remote_addr
        return 'local'

    @classmethod
    def get_user_folder(cls, client_ip):
        clean_ip = client_ip.replace('.', '_').replace(':', '_')
        return os.path.join(cls.USERS_FOLDER, f'device_{clean_ip}')

    @classmethod
    def setup_user_folders(cls, client_ip):
        user_folder = cls.get_user_folder(client_ip)
        downloads_folder = os.path.join(user_folder, 'downloads')
        logs_folder      = os.path.join(user_folder, 'logs')
        os.makedirs(downloads_folder, exist_ok=True)
        os.makedirs(logs_folder,      exist_ok=True)
        cls.DOWNLOAD_FOLDER = downloads_folder
        return user_folder

    @classmethod
    def setup_directories(cls):
        for folder in [cls.USERS_FOLDER, cls.LOGS_FOLDER, cls.CACHE_FOLDER]:
            os.makedirs(folder, exist_ok=True)
        return True

    @classmethod
    def get_local_ip(cls):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    @classmethod
    def get_banner(cls):
        mode = "☁️  Render (Production)" if IS_PRODUCTION else "💻 Local"
        return f"""
╔══════════════════════════════════════════════╗
║   SnapYTube Ultimate v{cls.APP_VERSION}                   ║
║   Mode: {mode:<36}║
║   PORT: {cls.PORT:<37}║
╚══════════════════════════════════════════════╝"""


Config.setup_directories()
