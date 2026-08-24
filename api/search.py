from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        try:
            qs = parse_qs(urlparse(self.path).query)
            q = (qs.get('q') or [None])[0]
            if not q:
                self.wfile.write(json.dumps({'error': 'Falta ?q='}).encode())
                return
            import yt_dlp
            ydl_opts = {
                'quiet': True, 'no_warnings': True, 'noplaylist': True,
                'extract_flat': True, 'playlistend': 12,
                'nocheckcertificate': True, 'socket_timeout': 12,
                'extractor_args': {'youtube': {'player_client': ['tv', 'android']}},
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                data = ydl.extract_info('ytsearch12:' + q, download=False)
            items=[]
            for e in (data.get('entries') or []):
                if not e or not e.get('id'):
                    continue
                vid = e.get('id')
                title = e.get('title') or 'Sin título'
                channel = e.get('uploader') or e.get('channel') or ''
                dur = e.get('duration') or 0
                dur_txt = f"{int(dur//60)}:{int(dur%60):02d}" if dur else ''
                thumb = f'https://i.ytimg.com/vi/{vid}/mqdefault.jpg'
                url = f'https://www.youtube.com/watch?v={vid}'
                items.append({'id': vid, 'title': title, 'channel': channel, 'duration': dur_txt, 'thumb': thumb, 'url': url})
            self.wfile.write(json.dumps({'items': items}).encode())
        except Exception as e:
            self.wfile.write(json.dumps({'error': str(e)[:400]}).encode())
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
