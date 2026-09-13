#!/usr/bin/env python3
"""PIL step 6: export the library as an installable PWA bundle.

Writes a folder with everything a browser needs to offer "Install":
index.html (the dashboard, PWA-enabled), manifest.json, sw.js (offline
service worker), and app icons. Serve the folder over HTTP and the browser
takes it from there.

Usage:
    python3 export_pwa.py [output_dir]   # defaults to <data_dir>/pwa
    cd <output_dir> && python3 -m http.server 8080
    # open http://localhost:8080 -> install prompt (Chrome/Edge);
    # Safari/Firefox: add to Dock / Home Screen from the browser menu.

Cross-browser notes:
  - Chrome/Edge (desktop & Android): automatic install prompt once served.
  - Safari (macOS): File -> Add to Dock. iOS: Share -> Add to Home Screen
    (uses the apple-touch-icon + meta tags; no auto-prompt by design).
  - Firefox: Add to Home Screen (Android) or bookmark/dock the localhost
    page manually; no auto-prompt.
localhost counts as a secure context everywhere, so the service worker
(and therefore offline + installability) works without HTTPS.
"""
import json
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_html import gather_data, render_page
from pil_common import db_connect, load_config

CACHE_VERSION = "pil-v1"

MANIFEST = {
    "name": "PIL — Personal Instagram Library",
    "short_name": "PIL",
    "description": "Your Instagram saved posts — deep-read by AI, searchable forever, on your machine.",
    "start_url": "./index.html",
    "scope": "./",
    "display": "standalone",
    "orientation": "any",
    "background_color": "#141414",
    "theme_color": "#141414",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}

SW_JS = """const CACHE = "%s";
const ASSETS = ["./", "./index.html", "./manifest.json",
                "./icon-192.png", "./icon-512.png", "./icon-180.png"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS))
    .then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy));
      return res;
    }).catch(() => caches.match("./index.html")))
  );
});
""" % CACHE_VERSION


def write_png(path, size):
    """Minimal PNG writer (no dependencies): dark tile, red PIL dot."""
    bg, dot = (20, 20, 20), (224, 69, 58)
    cx = cy = size / 2.0
    r = size * 0.26
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter byte
        for x in range(size):
            dx, dy = x - cx + 0.5, y - cy + 0.5
            raw.extend(dot if dx * dx + dy * dy <= r * r else bg)

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def main():
    cfg = load_config()
    out_dir = (sys.argv[1] if len(sys.argv) > 1
               else os.path.join(os.path.expanduser(cfg["data_dir"]), "pwa"))
    os.makedirs(out_dir, exist_ok=True)

    db = db_connect(cfg, read_only=True)
    d = gather_data(db)
    db.close()

    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_page(d, pwa=True))
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(MANIFEST, f, indent=2)
    with open(os.path.join(out_dir, "sw.js"), "w", encoding="utf-8") as f:
        f.write(SW_JS)
    write_png(os.path.join(out_dir, "icon-192.png"), 192)
    write_png(os.path.join(out_dir, "icon-512.png"), 512)
    write_png(os.path.join(out_dir, "icon-180.png"), 180)  # apple-touch-icon

    files = sorted(os.listdir(out_dir))
    total = sum(os.path.getsize(os.path.join(out_dir, x)) for x in files)
    print(f"[done] {d['stats']['posts']} posts -> {out_dir}/ ({total / 1024 / 1024:.1f} MB)", flush=True)
    print("Next:", flush=True)
    print(f"  cd {out_dir} && python3 -m http.server 8080", flush=True)
    print("  Open http://localhost:8080 — Chrome/Edge will offer Install;", flush=True)
    print("  Safari: File -> Add to Dock (macOS) / Share -> Add to Home Screen (iOS).", flush=True)


if __name__ == "__main__":
    main()
