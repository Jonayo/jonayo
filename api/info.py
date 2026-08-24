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
                'extractor_args': {'youtube': {'player_client': ['android', 'tv']}},
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            title = info.get('title','')
            # recolectar formatos de VIDEO reales (con altura), sin filtrar demasiado
            fmts=[]; seen=set()
            for f in (info.get('formats') or []):
                h=f.get('height')
                if not h:
                    continue
                try: h=int(h)
                except: continue
                if h<144 or h in seen:
                    continue
                # si no tiene vcodec, igual puede ser video (algunos HLS no reportan vcodec)
                # solo excluir los que son claramente solo-audio (vcodec none + acodec set y sin height relevante)
                vc=str(f.get('vcodec') or '')
                # permitir si tiene altura, aunque vcodec sea none pero es formato combinado raro
                # excluir solo si es audio puro: height pequeño y vcodec none es audio (ya filtrado por h>=144, audio no tiene altura)
                seen.add(h)
                fmts.append({'quality':f'{h}p','height':h,'ext':f.get('ext') or 'mp4','vcodec':vc or 'unknown','acodec':str(f.get('acodec') or ''),'url':f.get('url') or ''})
            # si no hay nada, fallback: usar url directo de info
            if not fmts and info.get('url'):
                h=info.get('height') or 720
                try: h=int(h)
                except: h=720
                fmts.append({'quality':f'{h}p','height':h,'ext':info.get('ext') or 'mp4','vcodec':str(info.get('vcodec') or ''),'acodec':str(info.get('acodec') or ''),'url':info.get('url')})
            # mejor audio separado
            best=None
            for f in (info.get('formats') or []):
                if str(f.get('vcodec') or 'none')=='none' and f.get('acodec') not in (None,'none') and f.get('url'):
                    if not best or (f.get('abr') or 0)>(best.get('abr') or 0):
                        best=f
            if best:
                fmts.append({'quality':'Audio · MP3','height':0,'ext':'m4a','vcodec':'none','acodec':best.get('acodec'),'url':best.get('url')})
            # ordenar y deduplicar por quality, quedarnos con mejor url por altura
            by_h={}
            for f in fmts:
                by_h[f['height']] = f  # ultimo gana (suele ser mejor)
            fmts=list(by_h.values())
            fmts.sort(key=lambda x: x['height'], reverse=True)
            fmts=fmts[:8]
            self.wfile.write(json.dumps({'title':title,'formats':fmts, 'debug_heights': len(fmts)}).encode())
        except Exception as e:
            import traceback
            self.wfile.write(json.dumps({'error': str(e)[:500], 'trace': traceback.format_exc()[:500]}).encode())
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
