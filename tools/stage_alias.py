#!/usr/bin/env python3
"""Prepare a public alias, redirect page, JSON binding and QR; no network writes."""
import argparse, hashlib, html, json, string, ipaddress
from pathlib import Path
from urllib.parse import urlsplit
import qrcode
import ulmi

ALPHABET = string.digits + string.ascii_uppercase
KNOWN_HOLDS = {'ab12', '26d001'}
CLEAN_START_ID = 'ULQF-CS-20261126-001'
SOURCES = ('glair', 'github')

def base36(n, width):
    out = ''
    for _ in range(width):
        n, d = divmod(n, 36)
        out = ALPHABET[d] + out
    return out

def allocate(url, issuance, occupied, purpose='AUTO'):
    occupied = {k.lower() for k in occupied}
    if purpose not in ('AUTO', 'PERSONAL', 'SOCIAL'):
        raise ValueError('Unsupported alias purpose.')
    host = (urlsplit(url).hostname or '').lower().rstrip('.')
    social_hosts = ('youtube.com', 'youtu.be', 'facebook.com', 'fb.watch', 'instagram.com', 'threads.net', 'threads.com', 'tiktok.com', 'x.com', 'twitter.com', 'linkedin.com', 'reddit.com', 'twitch.tv', 'bsky.app')
    is_social = purpose == 'SOCIAL' or any(host == h or host.endswith('.' + h) for h in social_hosts)
    for width in ((6,) if is_social else (4, 6)):
        for nonce in range(1 if width == 4 else 1000):
            digest = hashlib.sha256(json.dumps([url, issuance, nonce], ensure_ascii=False).encode()).digest()
            code = base36(int.from_bytes(digest, 'big') % (36**width), width)
            if code.lower() not in occupied:
                return code
    raise ValueError('Alias collision; reconcile registry.')

def load_inventory(path, fixture=False):
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get('schema') != 1 or data.get('complete') is not True:
        raise ValueError('Complete current-era reservation inventory required.')
    if bool(data.get('fixture_only')) != fixture:
        raise ValueError('Fixture inventory cannot authorize production; use --fixture-only for local testing.')
    if data.get('mode') != 'clean-start' or data.get('authorization') != CLEAN_START_ID:
        raise ValueError('Clean-start authorization required.')
    sources = data.get('sources', {})
    if not isinstance(sources, dict) or any(not isinstance(sources.get(k), str) or not sources[k].strip() for k in SOURCES):
        raise ValueError('Current GLAIR and GitHub source references required.')
    codes = data.get('codes')
    if not isinstance(codes, list) or not all(isinstance(k, str) and k.strip() and k == k.strip() for k in codes):
        raise ValueError('Inventory codes must be nonempty strings.')
    reserved = {k.lower() for k in codes}
    if not KNOWN_HOLDS.issubset(reserved):
        raise ValueError('Known historical holds missing: AB12 and/or 26D001.')
    return reserved

def validate_destination(url):
    u = urlsplit(url)
    host = (u.hostname or '').lower().rstrip('.')
    if (u.scheme != 'https' or not host or '.' not in host or u.username or u.password or
        host in {'ursua.cc','www.ursua.cc','bigstanleysausage-cloud.github.io'} or host.endswith(('.local','.localhost','.internal')) or
        any(c.isspace() or ord(c)<32 for c in url)):
        raise ValueError('Use an approved public HTTPS destination; no credentials or resolver loops.')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError('Nonpublic IP destination forbidden.')
    return url

def prepare(url, issuance, registry, inventory, out, fixture=False, metadata_mode='NONE', metadata=None, canonical='ALIAS', purpose='AUTO'):
    validate_destination(url)
    if not issuance.strip():
        raise ValueError('Issuance ID required.')
    data = json.loads(registry.read_text())
    if data.get('schema') != 1 or not isinstance(data.get('links'), dict):
        raise ValueError('Unsupported registry schema.')
    reserved = load_inventory(inventory, fixture)
    code = allocate(url, issuance, set(data['links']) | reserved, purpose)
    short = 'https://ursua.cc/' + code
    dest = html.escape(url, quote=True)
    if metadata_mode == 'NONE' and metadata is not None:
        raise ValueError('Metadata supplied for NONE mode')
    preview = None if metadata_mode == 'NONE' else ulmi.sanitize(metadata, url) if metadata_mode != 'PASSTHROUGH' else None
    if metadata_mode != 'NONE':
        preview_page = ulmi.render(code, url, metadata_mode, preview, canonical)
    out.mkdir(parents=True, exist_ok=False)
    folder = out / code
    folder.mkdir()
    page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><meta http-equiv="refresh" content="2;url='+dest+'"><title>ULQF</title><script defer src="/analytics/client.js?v=0.4.2" data-alias="'+code+'" data-target="'+dest+'"></script></head><body><a href="'+dest+'">Continue</a></body></html>'
    if metadata_mode != 'NONE':
        page = preview_page
        (out / 'preview-metadata.json').write_text(json.dumps(preview, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (folder / 'index.html').write_text(page, encoding='utf-8')
    data['links'][code.lower()] = url
    (out / 'links.json').write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    qrcode.make(short).save(out / (code+'.png'))
    manifest = {'alias':code,'short_url':short,'destination':url,'issuance_id':issuance,'status':'FIXTURE_ONLY_NOT_ISSUED' if fixture else 'LOCAL_STAGED_NOT_ISSUED','inventory_mode':'clean-start','authorization':CLEAN_START_ID,'registry_sha256':hashlib.sha256(registry.read_bytes()).hexdigest(),'inventory_sha256':hashlib.sha256(inventory.read_bytes()).hexdigest(),'qr_sha256':hashlib.sha256((out / (code+'.png')).read_bytes()).hexdigest()}
    manifest.update({'alias_purpose':purpose,'alias_length':len(code)})
    if metadata_mode != 'NONE':
        manifest.update({'metadata_mode':metadata_mode,'canonical_policy':canonical,'metadata_sha256':ulmi.fingerprint(preview)})
    (out / 'issuance.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('url'); p.add_argument('issuance_id')
    p.add_argument('--registry', type=Path, required=True)
    p.add_argument('--reserved', type=Path, required=True, help='Complete current-era inventory JSON, see tools/ISSUANCE.md')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--fixture-only', action='store_true')
    p.add_argument('--metadata-mode', choices=ulmi.MODES, default='NONE')
    p.add_argument('--metadata', type=Path, help='Private validated metadata JSON; never publish this file')
    p.add_argument('--canonical', choices=('ALIAS','DESTINATION'), default='ALIAS')
    p.add_argument('--purpose', choices=('AUTO','PERSONAL','SOCIAL'), default='AUTO', help='SOCIAL for public social distribution; known social hosts always use six characters')
    a = p.parse_args()
    try:
        print(json.dumps(prepare(a.url,a.issuance_id,a.registry,a.reserved,a.out,a.fixture_only,a.metadata_mode,json.loads(a.metadata.read_text()) if a.metadata else None,a.canonical,a.purpose)))
    except (ValueError, KeyError, OSError) as e:
        p.error(str(e))
if __name__ == '__main__':
    main()
