#!/usr/bin/env python3
"""Publish a generated PIL PWA folder to the user's own private static host.

One command: uploads the PWA bundle produced by export_pwa.py to hosting the
user controls, then writes phone.json + phone-qr.png into the bundle so the
desktop PWA shows a "Take PIL on your phone" panel with a QR code that the
phone can scan to install the app.

Providers:
  netlify  Deploy via the Netlify API. Token comes from the "publish" section
           of pil.config.json (netlify_token) or the NETLIFY_TOKEN env var.
           Creates a new site unless site_id / site name is given.
  manual   No upload. Use when you already host the folder somewhere; pass
           --url with the public https URL.

Code is shared, data stays home: the bundle is uploaded only to hosting the
user chose and authenticated. The token is never committed (it lives in the
local config, which is git-ignored).

Example:
  bin/export_pwa.py /tmp/pil-pwa
  bin/publish_pwa.py /tmp/pil-pwa --provider netlify
  # then re-serve /tmp/pil-pwa (or re-zip it) so phone.json is included
"""

import argparse
import datetime as dt
import io
import json
import os
import sys
import urllib.request
import urllib.error
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
try:
    from pil.pil_common import load_config
except ImportError:  # allow running as `python3 bin/publish_pwa.py`
    from pil.pil_common import load_config


def fail(msg):
    print(f"publish_pwa: error: {msg}", file=sys.stderr)
    sys.exit(1)


def zip_dir(path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(path):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, path)
                # skip phone assets from a previous publish; they are rewritten below
                if rel in ("phone.json", "phone-qr.png"):
                    continue
                zf.write(full, rel)
    return buf.getvalue()


def netlify_request(token, method, url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8")).get("message", "")
        except Exception:
            detail = ""
        fail(f"Netlify API {e.code}: {detail or e.reason}")


def netlify_deploy(pwa_dir, cfg):
    token = (cfg.get("publish", {}) or {}).get("netlify_token") or os.environ.get("NETLIFY_TOKEN")
    if not token:
        fail("no Netlify token: set publish.netlify_token in pil.config.json or NETLIFY_TOKEN env var")
    pub = cfg.get("publish", {}) or {}
    site_id = pub.get("site_id")
    if not site_id:
        name = pub.get("site_name")
        payload = {"name": name} if name else {}
        site = netlify_request(token, "POST", "https://api.netlify.com/api/v1/sites",
                               data=json.dumps(payload).encode("utf-8"),
                               headers={"Content-Type": "application/json"})
        site_id = site["site_id"]
        print(f"created Netlify site: {site.get('ssl_url') or site.get('url')} (site_id {site_id})")
        print("tip: save site_id under publish.site_id in pil.config.json to reuse this site")
    blob = zip_dir(pwa_dir)
    print(f"uploading {len(blob)/1e6:.1f} MB to Netlify...")
    deploy = netlify_request(token, "POST",
                             f"https://api.netlify.com/api/v1/sites/{site_id}/deploys",
                             data=blob, headers={"Content-Type": "application/zip"})
    url = deploy.get("ssl_url") or deploy.get("deploy_ssl_url") or deploy.get("url")
    if not url:
        fail("Netlify did not return a deploy URL")
    return url


def write_phone_assets(pwa_dir, url, provider):
    phone = {"url": url, "provider": provider,
             "published_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    with open(os.path.join(pwa_dir, "phone.json"), "w", encoding="utf-8") as f:
        json.dump(phone, f, indent=2)
    try:
        import qrcode
        img = qrcode.make(url)
        img.save(os.path.join(pwa_dir, "phone-qr.png"))
        print("wrote phone-qr.png")
    except ImportError:
        print('note: pip install "qrcode[pil]" to generate the QR code image; '
              "the phone panel will show the link without it")
    print("wrote phone.json")


def main():
    ap = argparse.ArgumentParser(description="Publish a PIL PWA folder for phone install")
    ap.add_argument("pwa_dir", help="PWA folder produced by export_pwa.py")
    ap.add_argument("--provider", choices=["netlify", "manual"], default="netlify")
    ap.add_argument("--url", help="public https URL (with --provider manual)")
    args = ap.parse_args()

    pwa_dir = os.path.abspath(args.pwa_dir)
    if not os.path.isdir(pwa_dir):
        fail(f"not a directory: {pwa_dir}")
    for needed in ("index.html", "manifest.json"):
        if not os.path.exists(os.path.join(pwa_dir, needed)):
            fail(f"{pwa_dir} does not look like a PIL PWA (missing {needed}); run export_pwa.py first")

    cfg = load_config()["config"]
    if args.provider == "manual":
        if not args.url:
            fail("--provider manual requires --url https://...")
        url = args.url.rstrip("/")
    else:
        url = netlify_deploy(pwa_dir, cfg)

    write_phone_assets(pwa_dir, url, args.provider)
    print()
    print(f"published: {url}")
    print("desktop PWA: re-serve this folder (or re-zip it) so phone.json is included;")
    print("  the 'Take PIL on your phone' panel appears automatically.")
    print("phone: scan the QR (or open the link) -> Android: Chrome > Install app |")
    print("  iPhone: Safari > Share > Add to Home Screen. First load on wi-fi, then offline.")


if __name__ == "__main__":
    main()
