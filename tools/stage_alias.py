#!/usr/bin/env python3
"""Stage a public ULQF alias locally. Requires qrcode[pil]. No network writes."""
import argparse, hashlib, html, json, re, string
from pathlib import Path
from urllib.parse import urlsplit
import qrcode

ALPHABET = string.digits + string.ascii_uppercase
def base36(n, width):
    out = ""
    for _ in range(width):
        n, d = divmod(n, 36)
        out = ALPHABET[d] + out
    return out

def allocate(url, issuance, occupied):
    for width in (4, 6):
        for nonce in range(1 if width == 4 else 1000):
            digest = hashlib.sha256(json.dumps([url, issuance, nonce], ensure_ascii=False).encode()).digest()
            code = base36(int.from_bytes(digest, "big") % (36**width), width)
            if code.lower() not in occupied:
                return code
    raise ValueError("Alias space collision; reconcile registry.")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("url")
    p.add_argument("issuance_id")
    p.add_argument("--registry", type=Path, required=True, help="Current links.json from repo")
    p.add_argument("--reserved", type=Path, required=True, help="JSON array of ALL historical/reserved aliases from reconciled private registry")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    u = urlsplit(args.url)
    if u.scheme != "https" or not u.hostname or u.username or u.password or u.hostname.lower().rstrip(".") in {"ursua.cc","www.ursua.cc","bigstanleysausage-cloud.github.io"} or any(c.isspace() or ord(c)<32 for c in args.url):
        p.error("Only valid public HTTPS destinations; no credentials or resolver loops.")
    data = json.loads(args.registry.read_text())
    reserved = json.loads(args.reserved.read_text())
    if not isinstance(reserved, list) or not all(isinstance(x,str) for x in reserved):
        p.error("Reserved must be a JSON array of codes.")
    occupied = {k.lower() for k in data["links"]} | {k.lower() for k in reserved}
    code = allocate(args.url, args.issuance_id, occupied)
    short = "https://ursua.cc/" + code
    dest = html.escape(args.url, quote=True)
    args.out.mkdir(parents=True, exist_ok=False)
    folder = args.out / code
    folder.mkdir()
    page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><meta http-equiv="refresh" content="0;url='+dest+'"><title>ULQF</title></head><body><a href="'+dest+'">Continue</a></body></html>'
    (folder / "index.html").write_text(page, encoding="utf-8")
    data["links"][code.lower()] = args.url
    (args.out / "links.json").write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")
    qrcode.make(short).save(args.out / (code+".png"))
    print(json.dumps({"alias":code,"short_url":short,"status":"LOCAL_STAGED_NOT_ISSUED"}))
if __name__ == "__main__":
    main()
