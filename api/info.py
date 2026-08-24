from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs

class handler(BaseHTTPRequestHandler):
    def _try(self, url, extra_args):
        import yt_dlp
        opts = {
            'quiet': True, 'no_warnings': True, 'noplaylist': True,
            'skip_download': True, 'nocheckcertificate': True, 'socket_timeout': 12,
        }
        if extra_args:
            opts['extractor_args'] = extra_args
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

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
            info=None
            last_err=None
            # Probar varios clientes, empezando por los que mejor evaden el bot-check
            attempts = [
                {'youtube': {'player_client': ['android']}},
                {'youtube': {'player_client': ['android', 'web']}},
                {'youtube': {'player_client': ['mweb']}},
                {'youtube': {'player_client': ['ios']}},
                None,  # sin especificar cliente (default)
            ]
            for extra in attempts:
                try:
                    info=self._try(url, extra)
                    if info and (info.get('formats') or info.get('url')):
                        break
                except Exception as e:
                    last_err=e
                    # si es bot-check, probar siguiente cliente
                    if 'not a bot' in str(e).lower() or 'sign in' in str(e).lower():
                        continue
                    continue
            if not info:
                raise last_err or Exception('No se pudo obtener info del video')
            title=info.get('title','')
            fmts=[]; seen=set()
            for f in (info.get('formats') or []):
                h=f.get('height')
                ext=(f.get('ext') or '').lower()
                if ext in ('mhtml','jpg','webp'): continue
                if not h: continue
                try: h=int(h)
                except: continue
                if h<144 or h in seen: continue
                vc=str(f.get('vcodec') or 'none')
                if vc=='none': continue
                seen.add(h)
                fmts.append({'quality':f'{h}p','height':h,'ext':ext or 'mp4','vcodec':vc,'acodec':str(f.get('acodec') or ''),'url':f.get('url') or ''})
            if not fmts and info.get('url'):
                h=info.get('height') or 720
                try: h=int(h)
                except: h=720
                fmts.append({'quality':f'{h}p','height':h,'ext':info.get('ext') or 'mp4','vcodec':str(info.get('vcodec') or ''),'acodec':str(info.get('acodec') or ''),'url':info.get('url')})
            if not fmts:
                for f in (info.get('formats') or []):
                    h=f.get('height')
                    if h:
                        try: h=int(h)
                        except: continue
                        if h>=144 and h not in seen and f.get('url'):
                            seen.add(h)
                            fmts.append({'quality':f'{h}p','height':h,'ext':f.get('ext') or 'mp4','vcodec':str(f.get('vcodec') or ''),'acodec':str(f.get('acodec') or ''),'url':f.get('url')})
                            if len(fmts)>=3: break
            by_h={}
            for f in fmts:
                if f['url']:
                    by_h[f['height']]=f
            fmts=list(by_h.values())
            fmts.sort(key=lambda x: x['height'], reverse=True)
            best=None
            for f in (info.get('formats') or []):
                if str(f.get('vcodec') or 'none')=='none' and f.get('acodec') not in (None,'none') and f.get('url'):
                    if not best or (f.get('abr') or 0)>(best.get('abr') or 0):
                        best=f
            if best:
                fmts.append({'quality':'Audio · MP3','height':0,'ext':'m4a','vcodec':'none','acodec':best.get('acodec'),'url':best.get('url')})
            if not fmts:
                # detectar bot-check para dar mensaje útil
                raise Exception('YouTube bloqueó la descarga desde el servidor web (verificación anti-bots). Probá con otro video o usa la APK Android — desde el celular funciona sin ese bloqueo.')
            video_fmts=[f for f in fmts if f['height']>0][:6]
            audio_fmts=[f for f in fmts if f['height']==0]
            fmts=video_fmts+audio_fmts
            self.wfile.write(json.dumps({'title':title,'formats':fmts}).encode())
        except Exception as e:
            msg=str(e)
            # Mensaje amigable para bot-check
            if 'not a bot' in msg.lower() or 'sign in' in msg.lower():
                msg='YouTube bloqueó temporalmente las descargas desde la web (anti-bots). Probá con otro video o usa la app Android — ahí funciona sin este límite.'
            self.wfile.write(json.dumps({'error': msg[:400]}).encode())
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
