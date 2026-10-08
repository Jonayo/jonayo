from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
import re

# NOTA (oct-2026): se usan los clientes por defecto de yt-dlp, que ya
# combinan formatos de varios players. Forzar una lista fija degradaba
# calidades. Solo se excluye 'configs'. Los reintentos van de a pares:
# primero defaults, luego tv (el más tolerante sin cuenta).
PLAYER_CLIENTS_FALLBACK = ['tv']

# Instancias Invidious públicas con mejor uptime (se prueban en orden).
INVIDIOUS = [
    'https://invidious.nerdvpn.de',
    'https://inv.nadeko.net',
    'https://invidious.jing.li',
    'https://yewtu.be',
]


def extract_id(url):
    m = re.search(r'(?:v=|youtu\.be/|shorts/|live/)([A-Za-z0-9_-]{11})', url or '')
    return m.group(1) if m else None


def ydl_extract(url, clients=None):
    import yt_dlp
    extra = {'player_skip': ['configs']}
    if clients:
        extra['player_client'] = clients
    opts = {
        'quiet': True, 'no_warnings': True, 'noplaylist': True,
        'skip_download': True, 'nocheckcertificate': True,
        'geo_bypass': True, 'socket_timeout': 8,
        'retries': 2, 'extractor_retries': 2,
        'extractor_args': {'youtube': extra},
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


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
            vid = extract_id(url)
            # yt-dlp: intento 1 con clientes por defecto, intento 2 solo tv
            info = None
            last_err = None
            for clients in (None, ['tv']):
                try:
                    info = ydl_extract(url, clients)
                    if info and (info.get('formats') or info.get('url')):
                        last_err = None
                        break
                except Exception as e:
                    last_err = e
                    continue

            if info and (info.get('formats') or info.get('url')):
                title = info.get('title', '')
                fmts = []
                seen = set()
                for f in (info.get('formats') or []):
                    h = f.get('height')
                    ext = (f.get('ext') or '').lower()
                    if ext in ('mhtml', 'jpg', 'webp'):
                        continue
                    if not h:
                        continue
                    try:
                        h = int(h)
                    except (TypeError, ValueError):
                        continue
                    if h < 144 or h in seen:
                        continue
                    vc = str(f.get('vcodec') or 'none')
                    if vc == 'none':
                        continue
                    seen.add(h)
                    fmts.append({'quality': f'{h}p', 'height': h,
                                 'ext': ext or 'mp4', 'vcodec': vc,
                                 'acodec': str(f.get('acodec') or ''),
                                 'url': f.get('url') or ''})
                if not fmts and info.get('url'):
                    h = info.get('height') or 720
                    try:
                        h = int(h)
                    except (TypeError, ValueError):
                        h = 720
                    fmts.append({'quality': f'{h}p', 'height': h,
                                 'ext': info.get('ext') or 'mp4',
                                 'vcodec': str(info.get('vcodec') or ''),
                                 'acodec': str(info.get('acodec') or ''),
                                 'url': info.get('url')})
                by_h = {}
                for f in fmts:
                    if f['url']:
                        by_h[f['height']] = f
                fmts = list(by_h.values())
                fmts.sort(key=lambda x: x['height'], reverse=True)
                best = None
                for f in (info.get('formats') or []):
                    if str(f.get('vcodec') or 'none') == 'none' and f.get('acodec') not in (None, 'none') and f.get('url'):
                        if not best or (f.get('abr') or 0) > (best.get('abr') or 0):
                            best = f
                if best:
                    fmts.append({'quality': 'Audio · MP3', 'height': 0,
                                 'ext': 'm4a', 'vcodec': 'none',
                                 'acodec': best.get('acodec'),
                                 'url': best.get('url')})
                if fmts:
                    video_fmts = [f for f in fmts if f['height'] > 0][:6]
                    audio_fmts = [f for f in fmts if f['height'] == 0]
                    self.wfile.write(json.dumps({'title': title, 'formats': video_fmts + audio_fmts}).encode())
                    return
            # fallback Invidious: varias instancias, timeout corto
            if vid:
                import urllib.request
                for base in INVIDIOUS:
                    try:
                        req = urllib.request.Request(
                            f'{base}/api/v1/videos/{vid}',
                            headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=6) as r:
                            j = json.loads(r.read().decode())
                            fmts = []
                            for f in (j.get('formatStreams') or []):
                                url2 = f.get('url') or ''
                                if not url2:
                                    continue
                                res = f.get('qualityLabel') or ''
                                m = re.search(r'(\d+)p', res)
                                h = int(m.group(1)) if m else 0
                                if h < 144:
                                    continue
                                fmts.append({'quality': f'{h}p', 'height': h,
                                             'ext': f.get('container') or 'mp4',
                                             'vcodec': 'unknown', 'acodec': 'mp4a',
                                             'url': url2})
                            if fmts:
                                by_h = {}
                                for f in fmts:
                                    by_h[f['height']] = f
                                fmts = list(by_h.values())
                                fmts.sort(key=lambda x: x['height'], reverse=True)
                                # audio
                                aud = None
                                for f in (j.get('adaptiveFormats') or []):
                                    if f.get('type', '').startswith('audio/') and f.get('url'):
                                        if not aud or (f.get('bitrate') or 0) > (aud.get('bitrate') or 0):
                                            aud = f
                                if aud:
                                    fmts.append({'quality': 'Audio · MP3', 'height': 0,
                                                 'ext': 'm4a', 'vcodec': 'none',
                                                 'acodec': aud.get('acodec') or 'mp4a',
                                                 'url': aud['url']})
                                self.wfile.write(json.dumps({'title': j.get('title', ''), 'formats': fmts[:7]}).encode())
                                return
                    except Exception:
                        continue
            raise last_err or Exception('No se pudieron obtener calidades.')
        except Exception as e:
            msg = str(e)
            if 'not a bot' in msg.lower() or 'sign in' in msg.lower():
                msg = 'YouTube bloqueó este video en la web. Probá con otro o usa la APK Android.'
            self.wfile.write(json.dumps({'error': msg[:400]}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
