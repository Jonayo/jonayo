from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs

class handler(BaseHTTPRequestHandler):
    def _try(self, url, clients):
        import yt_dlp
        opts = {
            'quiet': True, 'no_warnings': True, 'noplaylist': True,
            'skip_download': True, 'nocheckcertificate': True, 'socket_timeout': 12,
            'extractor_args': {'youtube': {'player_client': clients}},
        }
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
            # Probar clientes en orden: android (estable para largos), tv, ios, web sin especificar
            for clients in [['android'], ['tv'], ['ios'], ['web']]:
                try:
                    info=self._try(url, clients)
                    if info and (info.get('formats') or info.get('url')):
                        break
                except Exception as e:
                    last_err=e
                    continue
            # ultimo intento sin cliente especificado
            if not info or not (info.get('formats') or info.get('url')):
                try:
                    import yt_dlp
                    with yt_dlp.YoutubeDL({'quiet':True,'no_warnings':True,'noplaylist':True,'skip_download':True,'nocheckcertificate':True,'socket_timeout':12}) as ydl:
                        info=ydl.extract_info(url, download=False)
                except Exception as e:
                    last_err=e
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
            # si aun vacio pero hay formatos, intentar tomar cualquier url con altura aunque vcodec none (fallback para vivos largos)
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
            # si sigue vacio, error explicito
            if not fmts:
                raise Exception(f'YouTube no devolvió calidades para este video (duración {info.get("duration") or "?"}s). Probá con otro video o usa el link directo.')
            video_fmts=[f for f in fmts if f['height']>0][:6]
            audio_fmts=[f for f in fmts if f['height']==0]
            fmts=video_fmts+audio_fmts
            self.wfile.write(json.dumps({'title':title,'formats':fmts}).encode())
        except Exception as e:
            import traceback
            self.wfile.write(json.dumps({'error': str(e)[:500]}).encode())
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
