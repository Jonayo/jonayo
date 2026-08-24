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
            url = (qs.get('url') or [None])[0]
            if not url:
                self.wfile.write(json.dumps({'error': 'Falta ?url='}).encode())
                return
            import yt_dlp
            ydl_opts = {
                'quiet': True, 'no_warnings': True, 'noplaylist': True,
                'skip_download': True, 'nocheckcertificate': True, 'socket_timeout': 12,
                'extractor_args': {'youtube': {'player_client': ['tv', 'android', 'ios']}},
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            title = info.get('title','')
            fmts=[]; seen=set()
            for f in (info.get('formats') or []):
                h=f.get('height'); vc=str(f.get('vcodec') or 'none')
                if h and vc!='none':
                    try:
                        h=int(h)
                        if h>=144 and h not in seen:
                            seen.add(h)
                            fmts.append({'quality':f'{h}p','height':h,'ext':f.get('ext') or 'mp4','vcodec':vc,'acodec':str(f.get('acodec') or 'none'),'url':f.get('url') or ''})
                    except: pass
            # mejor audio
            best=None
            for f in (info.get('formats') or []):
                if str(f.get('vcodec') or 'none')=='none' and f.get('acodec')!='none' and f.get('url'):
                    if not best or (f.get('abr') or 0)>(best.get('abr') or 0):
                        best=f
            if best:
                fmts.append({'quality':'Audio · MP3','height':0,'ext':'m4a','vcodec':'none','acodec':best.get('acodec'),'url':best.get('url')})
            fmts.sort(key=lambda x: x['height'], reverse=True)
            fmts=fmts[:7]
            self.wfile.write(json.dumps({'title':title,'formats':fmts}).encode())
        except Exception as e:
            self.wfile.write(json.dumps({'error': str(e)[:300]}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
