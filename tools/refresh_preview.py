"""Stage a LIVE-SYNC preview update without changing the permanent binding.
Inputs are private, operator-verified registry and metadata snapshots. No network writes.
"""
import argparse, json, re
from pathlib import Path
import ulmi

def refresh(registry, record, new_tags):
    code = record['code_exact'].upper()
    if not re.fullmatch(r'[A-Z0-9]{4}(?:[A-Z0-9]{2})?', code):
        raise ValueError('invalid alias')
    if record.get('mode') != 'LIVE-SYNC' or record.get('status') != 'ACTIVE':
        raise ValueError('only ACTIVE LIVE-SYNC aliases can refresh')
    target = registry['links'][code.lower()]
    if target != record['bound_destination']:
        raise ValueError('binding mismatch')
    old = ulmi.sanitize(record['metadata'], target)
    if ulmi.fingerprint(old) != record['metadata_sha256']:
        raise ValueError('previous metadata fingerprint mismatch')
    source = record['source_url']
    tags = ulmi.sanitize(new_tags, source)
    # Do not replace a known-good card with a partial/blocked scrape.
    for key in ('og:title','og:description','og:image','twitter:card','twitter:image','og:url'):
        if key in old and key not in tags:
            raise ValueError('previous field missing; retain last known valid metadata')
    if ulmi.fingerprint(tags) == ulmi.fingerprint(old):
        return None
    return {'code':code,'bound_destination':target,'metadata':tags,
            'metadata_sha256':ulmi.fingerprint(tags),
            'page':ulmi.render(code,target,'LIVE-SYNC',tags,record['canonical_policy'])}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('registry',type=Path); p.add_argument('record',type=Path)
    p.add_argument('new_metadata',type=Path); p.add_argument('output',type=Path)
    a=p.parse_args()
    result=refresh(json.loads(a.registry.read_text()),json.loads(a.record.read_text()),json.loads(a.new_metadata.read_text()))
    if result is None:
        print('UNCHANGED')
        return
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'index.html').write_text(result.pop('page'),encoding='utf-8')
    (a.output/'refresh.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('STAGED_NOT_PUBLISHED')

if __name__ == '__main__':
    main()
