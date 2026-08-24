from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
import re

def extract_id(url):
    m=re.search(r'(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})', url)
    return m.group(1) if m else None

class handler(BaseHTTPRequestHandler):
    def _try_yt_dlp(self, url, clients):
        import yt_dlp
        opts={'quiet':True,'no_warnings':True,'noplaylist':True,'skip_download':True,'nocheckcertificate':True,'socket_timeout':10,'extractor_args':{'youtube':{'player_client': clients}}}
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    def _try_invidious(self, video_id):
        import urllib.request
        # probar varias instancias publicas
        instances=[
            'https://invidious.io',
            'https://inv.riverside.rocks',
            'https://yewtu.be',
            'https://invidious.snopyta.org',
            'https://vid.puffyan.us',
        ]
        for base in instances:
            try:
                req=urllib.request.Request(f'{base}/api/v1/videos/{video_id}', headers={'User-Agent':'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=12) as r:
                    j=json.loads(r.read().decode())
                    fmts=[]
                    # formatStreams son progresivos con audio
                    for f in (j.get('formatStreams') or []):
                        url=f.get('url') or ''
                        if not url: continue
                        res=f.get('qualityLabel') or ''
                        # qualityLabel como "720p"
                        m=re.search(r'(\d+)p', res)
                        h=int(m.group(1)) if m else 0
                        if h<144: continue
                        fmts.append({'quality':f'{h}p','height':h,'ext':(f.get('container') or 'mp4'),'vcodec':'unknown','acodec':'mp4a','url':url})
                    # adaptiveFormats son DASH separados, los ignoramos para web simple (necesitan merge)
                    # pero si no hay progresivos, usar DASH video-only como fallback
                    if not fmts:
                        for f in (j.get('adaptiveFormats') or []):
                            if f.get('type','').startswith('video/') and f.get('url'):
                                h=int(re.search(r'(\d+)p', f.get('qualityLabel') or '0p').group(1)) if re.search(r'(\d+)p', f.get('qualityLabel') or '') else 0
                                if h>=144:
                                    fmts.append({'quality':f'{h}p','height':h,'ext':f.get('container') or 'mp4','vcodec':'unknown','acodec':'none','url':f['url']})
                                    if len(fmts)>=6: break
                    if fmts:
                        # deduplicar y ordenar
                        by_h={}
                        for f in fmts:
                            by_h[f['height']]=f
                        fmts=list(by_h.values())
                        fmts.sort(key=lambda x: x['height'], reverse=True)
                        # agregar audio
                        aud=None
                        for f in (j.get('adaptiveFormats') or []):
                            if f.get('type','').startswith('audio/') and f.get('url'):
                                if not aud or (f.get('bitrate') or 0)>(aud.get('bitrate') or 0):
                                    aud=f
                        if aud:
                            fmts.append({'quality':'Audio · MP3','height':0,'ext':'m4a','vcodec':'none','acodec':aud.get('audioSampleRate') and 'mp4a' or 'opus','url':aud['url']})
                        return {'title': j.get('title',''), 'formats': fmts[:7]}
            except Exception as e:
                continue
        return None

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        try:
            qs=parse_qs(urlparse(self.path).query)
            url=(qs.get('url') or [None])[0]
            if not url:
                self.wfile.write(json.dumps({'error':'Falta ?url='}).encode())
                return
            vid=extract_id(url)
            # intentar yt-dlp primero con varios clientes
            info=None
            last_err=None
            for clients in [['android'], ['tv'], ['ios'], ['web']]:
                try:
                    info=self._try_yt_dlp(url, clients)
                    if info and (info.get('formats') or info.get('url')):
                        break
                except Exception as e:
                    last_err=e
                    if 'not a bot' in str(e).lower() or 'sign in' in str(e).lower():
                        # probar siguiente cliente, si todos fallan probar invidious
                        continue
                    continue
            # si yt-dlp dio formatos, procesarlos
            if info and (info.get('formats') or info.get('url')):
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
                    ac=str(f.get('acodec') or 'none')
                    if vc=='none': continue
                    # priorizar progresivos con audio para web
                    if ac=='none' and len([x for x in fmts if x['height']==h])>0:
                        continue
                    seen.add(h)
                    fmts.append({'quality':f'{h}p','height':h,'ext':ext or 'mp4','vcodec':vc,'acodec':ac,'url':f.get('url') or ''})
                if not fmts and info.get('url'):
                    h=info.get('height') or 720
                    try: h=int(h)
                    except: h=720
                    fmts.append({'quality':f'{h}p','height':h,'ext':info.get('ext') or 'mp4','vcodec':str(info.get('vcodec') or ''),'acodec':str(info.get('acodec') or ''),'url':info.get('url')})
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
                if fmts:
                    video_fmts=[f for f in fmts if f['height']>0][:6]
                    audio_fmts=[f for f in fmts if f['height']==0]
                    self.wfile.write(json.dumps({'title':title,'formats':video_fmts+audio_fmts}).encode())
                    return
            # fallback a Invidious si yt-dlp fallo o no dio calidades
            if vid:
                inv=self._try_invidious(vid)
                if inv and inv.get('formats'):
                    self.wfile.write(json.dumps(inv).encode())
                    return
            raise last_err or Exception('No se pudieron obtener calidades. Probá con otro video.')
        except Exception as e:
            msg=str(e)
            if 'not a bot' in msg.lower() or 'sign in' in msg.lower():
                msg='YouTube bloqueó temporalmente las descargas desde la web. Intentando vía Invidious...'
            self.wfile.write(json.dumps({'error': msg[:500]}).encode())
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
