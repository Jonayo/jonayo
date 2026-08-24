from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs

class handler(BaseHTTPRequestHandler):
    def _extract(self, url, clients):
        import yt_dlp
        ydl_opts = {
            'quiet': True, 'no_warnings': True, 'noplaylist': True,
            'skip_download': True, 'nocheckcertificate': True, 'socket_timeout': 10,
            'extractor_args': {'youtube': {'player_client': clients}},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
            # Probar con tv primero (da DASH hasta 1080p), luego android
            info = None
            last_err = None
            for clients in [['tv'], ['android'], ['ios']]:
                try:
                    info = self._extract(url, clients)
                    if info and info.get('formats'):
                        # verificar que hay al menos un video >=360
                        has_video = any(f.get('height') and int(f.get('height') or 0) >= 360 for f in info.get('formats', []))
                        if has_video or len(info.get('formats', [])) > 5:
                            break
                except Exception as e:
                    last_err = e
                    continue
            if not info:
                raise last_err or Exception('No se pudo extraer info')

            title = info.get('title','')
            # recolectar formatos de VIDEO con audio (progresivos) primero, luego DASH video-only
            progressive=[]
            dash_video=[]
            seen=set()
            for f in (info.get('formats') or []):
                h=f.get('height')
                ext=(f.get('ext') or '').lower()
                if ext in ('mhtml','jpg','webp','json'):  # storyboard, thumbs
                    continue
                if not h:
                    continue
                try: h=int(h)
                except: continue
                if h<144 or h in seen:
                    continue
                vc=str(f.get('vcodec') or 'none')
                ac=str(f.get('acodec') or 'none')
                if vc=='none':
                    continue  # solo audio, no es calidad de video
                # progresivo = tiene audio
                if ac!='none':
                    progressive.append({'quality':f'{h}p','height':h,'ext':ext,'vcodec':vc,'acodec':ac,'url':f.get('url') or ''})
                    seen.add(h)
                else:
                    # DASH video-only: guardar como fallback si no hay progresivo a esa altura
                    if h not in seen:
                        dash_video.append({'quality':f'{h}p','height':h,'ext':ext,'vcodec':vc,'acodec':ac,'url':f.get('url') or ''})
            # si no hay progresivos, usar DASH (el navegador no reproducirá sin audio, pero sirve para descargar)
            fmts = progressive if progressive else dash_video
            # si aun vacio, intentar con url directo
            if not fmts and info.get('url'):
                h=info.get('height') or 720
                try: h=int(h)
                except: h=720
                fmts.append({'quality':f'{h}p','height':h,'ext':info.get('ext') or 'mp4','vcodec':str(info.get('vcodec') or ''),'acodec':str(info.get('acodec') or ''),'url':info.get('url')})
            # deduplicar por altura y ordenar
            by_h={}
            for f in fmts:
                by_h[f['height']] = f
            fmts=list(by_h.values())
            fmts.sort(key=lambda x: x['height'], reverse=True)
            # agregar audio solo
            best=None
            for f in (info.get('formats') or []):
                if str(f.get('vcodec') or 'none')=='none' and f.get('acodec') not in (None,'none') and f.get('url'):
                    if not best or (f.get('abr') or 0)>(best.get('abr') or 0):
                        best=f
            if best:
                fmts.append({'quality':'Audio · MP3','height':0,'ext':'m4a','vcodec':'none','acodec':best.get('acodec'),'url':best.get('url')})
            # limitar
            video_fmts=[f for f in fmts if f['height']>0][:6]
            audio_fmts=[f for f in fmts if f['height']==0]
            fmts=video_fmts+audio_fmts
            self.wfile.write(json.dumps({'title':title,'formats':fmts}).encode())
        except Exception as e:
            import traceback
            self.wfile.write(json.dumps({'error': str(e)[:400], 'trace': traceback.format_exc()[:600]}).encode())
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
