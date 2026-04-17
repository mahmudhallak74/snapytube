# downloader.py
# SnapYTube Ultimate - محرك تحميل مع دعم مجلدات المستخدمين

import os
import re
import time
import json
import threading
from datetime import datetime
import yt_dlp
from config import Config


class DownloadLogger:
    """نظام تسجيل التحميلات - لكل مستخدم سجل خاص"""
    
    def __init__(self, log_folder=None):
        self.log_folder = log_folder or Config.LOGS_FOLDER
        self.log_file = os.path.join(self.log_folder, 'downloads.json')
        self.history = []
        self.load_history()

    def load_history(self):
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
            except:
                self.history = []

    def save_history(self):
        try:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(self.history[-500:], f, ensure_ascii=False, indent=2)
        except:
            pass

    def add(self, data):
        data['timestamp'] = time.time()
        data['date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.history.insert(0, data)
        self.save_history()

    def get_all(self, limit=100):
        return self.history[:limit]

    def get_stats(self):
        stats = {
            'total': len(self.history),
            'by_platform': {},
            'today': 0,
            'this_week': 0,
            'total_size': 0
        }
        today = datetime.now().strftime('%Y-%m-%d')
        week_ago = time.time() - (7 * 24 * 3600)

        for item in self.history:
            platform = item.get('platform', 'other')
            stats['by_platform'][platform] = stats['by_platform'].get(platform, 0) + 1
            if item.get('date', '').startswith(today):
                stats['today'] += 1
            if item.get('timestamp', 0) > week_ago:
                stats['this_week'] += 1
            stats['total_size'] += item.get('filesize', 0)

        return stats


class MediaDownloader:
    """الفئة الرئيسية لتحميل الوسائط"""
    
    def __init__(self):
        self.download_folder = None  # بيتحدد حسب المستخدم
        self.log_folder = None       # بيتحدد حسب المستخدم
        self.logger = None           # بيتحدث بعد تحديد المجلدات
        self.active_downloads = {}
        self.download_lock = threading.Lock()
        self.progress_callbacks = {}
        
        # إعدادات yt-dlp
        self.base_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'noplaylist': True,
            'geo_bypass': True,
            'nocheckcertificate': True,
            'retries': 3,
            'fragment_retries': 3,
            'socket_timeout': 30,
            'sleep_requests': 0,
            'sleep_interval': 0,
            'concurrent_fragment_downloads': 16,
            'http_chunk_size': 10485760,
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        }

    def setup_for_client(self, client_ip):
        """إعداد المجلدات للمستخدم الحالي"""
        user_folder = Config.setup_user_folders(client_ip)
        self.download_folder = Config.DOWNLOAD_FOLDER
        self.log_folder = os.path.join(user_folder, 'logs')
        self.logger = DownloadLogger(self.log_folder)
        
        # التأكد من وجود مجلد التحميل
        os.makedirs(self.download_folder, exist_ok=True)
        
        return self.download_folder

    def detect_platform(self, url):
        """تحديد المنصة من الرابط"""
        url_lower = url.lower()
        domains = {
            'youtube':   ['youtube.com', 'youtu.be'],
            'tiktok':    ['tiktok.com', 'vt.tiktok', 'vm.tiktok'],
            'instagram': ['instagram.com', 'instagr.am'],
            'facebook':  ['facebook.com', 'fb.watch', 'fb.com'],
            'twitter':   ['twitter.com', 'x.com'],
            'capcut':    ['capcut.com', 'capcut.net'],
            'vimeo':     ['vimeo.com']
        }
        for platform, domain_list in domains.items():
            if any(d in url_lower for d in domain_list):
                return platform
        return 'other'

    def validate_url(self, url):
        """التحقق من صحة الرابط"""
        pattern = re.compile(
            r'^https?://'
            r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
            r'(/[^\s]*)?$'
        )
        return bool(pattern.match(url.strip()))

    def get_thumbnail(self, url, platform):
        """الحصول على صورة مصغرة للفيديو"""
        if platform == 'youtube':
            for pattern in [r'youtube\.com/watch\?v=([^&]+)', r'youtu\.be/([^?]+)']:
                match = re.search(pattern, url)
                if match:
                    return f"https://img.youtube.com/vi/{match.group(1)}/mqdefault.jpg"
        return None

    def _resolution_label(self, info):
        """تحديد تسمية الجودة"""
        height = info.get('height', 0) or 0
        if height >= 2160:
            return '4K (2160p)'
        elif height >= 1440:
            return '1440p (2K)'
        elif height >= 1080:
            return '1080p (FHD)'
        elif height >= 720:
            return '720p (HD)'
        elif height > 0:
            return f'{height}p'
        return 'Unknown'

    def download(self, url, progress_callback=None, download_id=None):
        """تحميل الفيديو مع شريط تقدم"""
        
        url = url.strip()
        
        if not self.validate_url(url):
            return {'success': False, 'error': Config.MESSAGES['invalid_url']}

        platform = self.detect_platform(url)
        platform_info = Config.SUPPORTED_PLATFORMS.get(
            platform,
            {'name': 'Other', 'format': 'best[ext=mp4]/best'}
        )

        if not download_id:
            download_id = str(int(time.time() * 1000))

        progress_data = {
            'percent': 0,
            'speed': 0,
            'speed_str': '0 B/s',
            'eta': '?',
            'status': 'starting'
        }

        if progress_callback:
            self.progress_callbacks[download_id] = progress_callback
            progress_callback(progress_data)

        print(f"🎬 [{platform_info['name']}] {url[:50]}...")

        def progress_hook(d):
            try:
                if d['status'] == 'downloading':
                    percent_str = d.get('_percent_str', '0%').strip().replace('%', '')
                    try:
                        percent = float(percent_str)
                    except:
                        percent = 0

                    speed_str = d.get('_speed_str', '0 B/s').strip()
                    eta_str = d.get('_eta_str', '?').strip()

                    speed_bytes = 0
                    if 'MiB' in speed_str:
                        speed_bytes = float(speed_str.replace('MiB/s', '').strip()) * 1024 * 1024
                    elif 'KiB' in speed_str:
                        speed_bytes = float(speed_str.replace('KiB/s', '').strip()) * 1024

                    progress_data.update({
                        'percent': round(percent, 1),
                        'speed': round(speed_bytes / 1024 / 1024, 2),
                        'speed_str': speed_str,
                        'eta': eta_str,
                        'status': 'downloading'
                    })

                    if progress_callback:
                        progress_callback(progress_data)

                elif d['status'] == 'finished':
                    progress_data['status'] = 'processing'
                    if progress_callback:
                        progress_callback(progress_data)

            except:
                pass

        opts = self.base_opts.copy()
        opts['format'] = platform_info.get('format', 'best[ext=mp4]/best')
        opts['progress_hooks'] = [progress_hook]
        opts['outtmpl'] = os.path.join(self.download_folder, '%(title).80s_%(id)s.%(ext)s')

        if platform == 'tiktok':
            opts['http_headers']['Referer'] = 'https://www.tiktok.com/'

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)

            if info is None:
                return {'success': False, 'error': 'فشل استخراج معلومات الفيديو'}

            # البحث عن الملف
            filepath = None
            try:
                filepath = ydl.prepare_filename(info)
            except:
                pass
            
            if not filepath or not os.path.exists(filepath):
                base = os.path.splitext(filepath)[0] if filepath else None
                if base:
                    for ext in ['.mp4', '.mkv', '.webm']:
                        if os.path.exists(base + ext):
                            filepath = base + ext
                            break
            
            if not filepath or not os.path.exists(filepath):
                files = [
                    os.path.join(self.download_folder, f)
                    for f in os.listdir(self.download_folder)
                    if f.lower().endswith(('.mp4', '.mkv', '.webm'))
                ]
                if files:
                    filepath = max(files, key=os.path.getmtime)

            if not filepath or not os.path.exists(filepath):
                return {'success': False, 'error': 'الملف غير موجود'}

            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)

            progress_data['status'] = 'completed'
            progress_data['percent'] = 100
            if progress_callback:
                progress_callback(progress_data)

            title = info.get('title', 'Unknown')
            quality = self._resolution_label(info)

            # تسجيل في السجل
            if self.logger:
                self.logger.add({
                    'filename': filename,
                    'title': title,
                    'platform': platform,
                    'url': url,
                    'filesize': filesize,
                    'quality': quality
                })

            return {
                'success': True,
                'filename': filename,
                'title': title,
                'platform': platform,
                'duration': info.get('duration', 0),
                'filesize': filesize,
                'filesize_mb': round(filesize / (1024 * 1024), 2),
                'quality': quality,
                'thumbnail': self.get_thumbnail(url, platform)
            }

        except Exception as e:
            error_msg = str(e)
            if 'ffmpeg' in error_msg.lower():
                error_msg = 'ffmpeg غير موجود — شغّل: pkg install ffmpeg'
            return {'success': False, 'error': error_msg}

    def get_stats(self):
        if self.logger:
            return self.logger.get_stats()
        return {'total': 0, 'by_platform': {}, 'today': 0, 'this_week': 0, 'total_size': 0}

    def get_history(self, limit=50):
        if self.logger:
            return self.logger.get_all(limit)
        return []


downloader = MediaDownloader()
