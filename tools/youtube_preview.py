"""YouTube oEmbed-first snapshot adapter. No image downloads or periodic jobs."""
import argparse, json, re, socket, ipaddress
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

LIMIT = 64 * 1024

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def watch_url(video_id):
    if not isinstance(video_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        raise ValueError('invalid YouTube video ID')
    return 'https://www.youtube.com/watch?v=' + video_id

def endpoint(video_id):
    return 'https://www.youtube.com/oembed?' + urlencode({'url': watch_url(video_id), 'format': 'json'})

def tags(video_id, data, source='oembed'):
    target = watch_url(video_id)
    if not isinstance(data, dict):
        raise ValueError('JSON object required')
    if source == 'vidiq':
        if data.get('id') != video_id:
            raise ValueError('video ID mismatch')
        title, image, description = data.get('title'), data.get('thumbnail'), data.get('description')
    elif source == 'oembed':
        if data.get('provider_name') != 'YouTube' or data.get('type') != 'video':
            raise ValueError('unexpected provider/type')
        title, image, description = data.get('title'), data.get('thumbnail_url'), None
    else:
        raise ValueError('unknown source')
    if not isinstance(title, str) or not title.strip() or not isinstance(image, str):
        raise ValueError('missing required preview fields')
    u = urlsplit(image)
    if (u.scheme != 'https' or u.hostname != 'i.ytimg.com' or u.username or u.password or
        u.port not in (None,443) or not re.fullmatch(r'/vi(?:_webp)?/'+re.escape(video_id)+r'/[A-Za-z0-9_-]+\.(?:jpg|webp)',u.path)):
        raise ValueError('thumbnail not verified for exact video ID')
    out = {'og:title': ' '.join(title.split())[:300], 'og:image': image,
           'og:url': target, 'og:type': 'video.other', 'og:site_name': 'YouTube',
           'twitter:card': 'summary_large_image', 'twitter:title': ' '.join(title.split())[:300], 'twitter:image': image}
    if isinstance(description,str) and description.strip():
        out['og:description'] = out['twitter:description'] = ' '.join(description.split())[:280]
    return out

def fetch(video_id):
    url = endpoint(video_id)
    addresses = socket.getaddrinfo('www.youtube.com',443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('nonpublic DNS result')
    with build_opener(NoRedirect()).open(Request(url,headers={'Accept':'application/json'}), timeout=10) as r:
        if r.geturl() != url or r.headers.get_content_type() != 'application/json':
            raise ValueError('unexpected endpoint or media type')
        raw = r.read(LIMIT+1)
    if len(raw) > LIMIT:
        raise ValueError('response too large')
    return json.loads(raw)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('video_id'); p.add_argument('output',type=Path)
    p.add_argument('--vidiq-json',type=Path,help='Explicit fallback: verified video object, not entire response')
    a=p.parse_args()
    if a.vidiq_json:
        raw=a.vidiq_json.read_bytes()
        if len(raw)>LIMIT: raise ValueError('fallback too large')
        data=json.loads(raw); source='vidiq'
    else:
        data=fetch(a.video_id); source='oembed'
    a.output.write_text(json.dumps(tags(a.video_id,data,source),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(source)

if __name__=='__main__': main()
