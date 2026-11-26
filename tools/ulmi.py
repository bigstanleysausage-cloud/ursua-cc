"""ULMI: opt-in preview capture and static redirect rendering (no network writes).
Capture from bounded, operator-fetched public HTML; never fetch on visitor requests.
"""
import argparse, hashlib, html, json, re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

MODES = ('NONE', 'SNAPSHOT', 'LIVE-SYNC', 'CUSTOM', 'PASSTHROUGH')
FIELDS = {'og:title': 300, 'og:description': 1000, 'og:image': 2048,
          'og:image:alt': 300, 'og:url': 2048, 'og:type': 100,
          'og:site_name': 200, 'twitter:card': 60, 'twitter:title': 300,
          'twitter:description': 1000, 'twitter:image': 2048, 'twitter:image:alt': 300}
URL_FIELDS = {'og:image', 'og:url', 'twitter:image'}
MAX_HTML = 512 * 1024
MAX_METADATA = 8192


def public_url(value, base=''):
    if not isinstance(value, str) or not value or any(ord(c) < 32 or c.isspace() for c in value):
        raise ValueError('invalid URL')
    value = urljoin(base, value)
    u = urlsplit(value)
    if u.scheme != 'https' or not u.hostname or '.' not in u.hostname or u.username or u.password or u.port not in (None, 443):
        raise ValueError('public HTTPS URL required')
    # URL syntax only. Network fetcher must separately verify DNS, redirects and authorization.
    return value


class Head(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags, self.title = {}, []
        self.done = self.in_title = False
    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        if tag == 'body':
            self.done = True
        if tag == 'title':
            self.in_title = True
        if tag == 'meta':
            a = dict(attrs)
            key = (a.get('property') or a.get('name') or '').lower()
            val = a.get('content') or ''
            if key in FIELDS or key == 'description':
                self.tags.setdefault(key, val)
    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag == 'head':
            self.done = True
    def handle_data(self, data):
        if self.in_title and not self.done:
            self.title.append(data)


def sanitize(tags, source):
    public_url(source)
    if not isinstance(tags, dict):
        raise ValueError('metadata object required')
    result = {}
    for key, size in FIELDS.items():
        value = tags.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        if key in URL_FIELDS:
            try:
                value = public_url(value.strip(), source)
            except ValueError:
                continue
            if len(value) > size:
                continue
        else:
            value = ' '.join(value.split())[:size]
        result[key] = value
    if len(json.dumps(result, ensure_ascii=False).encode()) > MAX_METADATA:
        raise ValueError('metadata too large')
    return result


def capture(raw, source):
    if len(raw) > MAX_HTML:
        raise ValueError('HTML exceeds capture limit; supply bounded head only')
    parser = Head()
    parser.feed(raw.decode('utf-8', errors='replace'))
    tags = parser.tags
    tags.setdefault('og:title', ''.join(parser.title))
    tags.setdefault('og:description', tags.get('description', ''))
    return sanitize(tags, source)


def render(code, target, mode='NONE', tags=None, canonical='ALIAS'):
    if not re.fullmatch(r'[A-Za-z0-9]{4}(?:[A-Za-z0-9]{2})?', code):
        raise ValueError('invalid alias')
    public_url(target)
    if mode not in MODES:
        raise ValueError('unknown mode')
    if mode == 'PASSTHROUGH':
        raise ValueError('native HTTP passthrough unavailable on GitHub Pages')
    if canonical not in ('ALIAS', 'DESTINATION'):
        raise ValueError('invalid canonical policy')
    m = {} if mode == 'NONE' else sanitize(tags, target)
    if mode != 'NONE' and not m.get('og:title') and not m.get('twitter:title'):
        raise ValueError('preview title missing; do not silently publish incomplete preview')
    if m:
        m['og:url'] = ('https://ursua.cc/' + code.upper()) if canonical == 'ALIAS' else m.get('og:url', target)
    esc = lambda s: html.escape(s, quote=True)
    meta = ''.join('<meta '+('name' if k.startswith('twitter:') else 'property')+'="'+esc(k)+'" content="'+esc(v)+'">' for k,v in m.items())
    dest = esc(target)
    title = esc(m.get('og:title', m.get('twitter:title','ULQF')))
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer">'+meta+'<meta http-equiv="refresh" content="2;url='+dest+'"><title>'+title+'</title><script defer src="/analytics/client.js?v=0.4.3" data-alias="'+code.upper()+'" data-target="'+dest+'"></script></head><body><a href="'+dest+'">Continue</a></body></html>'


def fingerprint(tags):
    return hashlib.sha256(json.dumps(tags, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('capture'); c.add_argument('html', type=Path); c.add_argument('source'); c.add_argument('output', type=Path)
    r = sub.add_parser('render'); r.add_argument('code'); r.add_argument('target'); r.add_argument('mode', choices=MODES); r.add_argument('output', type=Path); r.add_argument('--metadata', type=Path); r.add_argument('--canonical', choices=('ALIAS','DESTINATION'), default='ALIAS')
    a = p.parse_args()
    if a.cmd == 'capture':
        tags = capture(a.html.read_bytes(), a.source)
        a.output.write_text(json.dumps(tags, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(fingerprint(tags))
    else:
        tags = json.loads(a.metadata.read_text()) if a.metadata else None
        a.output.write_text(render(a.code, a.target, a.mode, tags, a.canonical), encoding='utf-8')

if __name__ == '__main__':
    main()
