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

# Double-click launchers: start the local server and open the browser.
# No terminal skills needed: unzip -> double-click -> Install.
START_COMMAND = """#!/bin/bash
# PIL launcher (macOS / Linux) — just double-click this file.
cd "$(dirname "$0")"
PORT=8080
if command -v lsof >/dev/null 2>&1; then
  while lsof -i :$PORT >/dev/null 2>&1; do PORT=$((PORT+1)); done
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "PIL needs Python 3: https://www.python.org/downloads/"
  echo "Install it, then double-click this file again."
  read -p "Press Enter to close."
  exit 1
fi
echo "Starting your Personal Instagram Library on http://localhost:$PORT ..."
echo "A browser window will open. Keep this window open while you use PIL;"
echo "closing it stops the library."
sleep 1
(open "http://localhost:$PORT" 2>/dev/null || xdg-open "http://localhost:$PORT" 2>/dev/null || true) &
exec python3 -m http.server "$PORT"
"""

START_BAT = """@echo off
title PIL - Personal Instagram Library
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo PIL needs Python 3: https://www.python.org/downloads/
  echo Install it (tick "Add python.exe to PATH"), then double-click this file again.
  pause
  exit /b 1
)
echo Starting your Personal Instagram Library on http://localhost:8080 ...
echo A browser window will open. Keep this window open while you use PIL;
echo closing it stops the library.
timeout /t 1 /nobreak >nul
start "" "http://localhost:8080"
python -m http.server 8080
"""

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


def render_png(size):
    """Render the PIL icon (dark tile, red dot) as PNG bytes. No dependencies."""
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
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


def write_png(path, size):
    with open(path, "wb") as f:
        f.write(render_png(size))


def write_icns(path):
    """Minimal macOS .icns packing PNGs (ic07=128, ic08=256, ic09=512)."""
    parts = []
    for itype, size in ((b"ic07", 128), (b"ic08", 256), (b"ic09", 512)):
        data = render_png(size)
        parts.append(itype + struct.pack(">I", 8 + len(data)) + data)
    body = b"".join(parts)
    with open(path, "wb") as f:
        f.write(b"icns" + struct.pack(">I", 8 + len(body)) + body)


# ---------------------------------------------------------------------------
# Polished one-click launchers (no certificates, no fees, no terminal windows)
# ---------------------------------------------------------------------------

# macOS: AppleScript source. "Make Mac App.command" compiles it into
# Start PIL.app via osacompile (one double-click, on the Mac itself).
APPLESCRIPT = """-- Start PIL (macOS): launches your Personal Instagram Library.
-- No terminal window. If it's already running, just opens it.
on run
	tell application "Finder"
		set pwaDir to POSIX path of (container of (path to me) as alias)
	end tell
	try
		do shell script "command -v python3"
	on error
		display dialog "PIL needs Python 3." & return & "Get it at https://www.python.org/downloads, then try again." buttons {"OK"} default button 1 with icon caution
		return
	end try
	set pyScript to "import socket, subprocess, os, sys, urllib.request" & return & ¬
		"pwa = sys.argv[1]" & return & ¬
		"for p in range(8080, 8091):" & return & ¬
		"    try:" & return & ¬
		"        body = urllib.request.urlopen('http://127.0.0.1:%d/index.html' % p, timeout=1).read(4000).decode('utf8', 'ignore')" & return & ¬
		"        if 'Personal Instagram Library' in body:" & return & ¬
		"            print('OPEN %d' % p); raise SystemExit" & return & ¬
		"    except Exception:" & return & ¬
		"        pass" & return & ¬
		"port = 8080" & return & ¬
		"while True:" & return & ¬
		"    s = socket.socket()" & return & ¬
		"    try:" & return & ¬
		"        s.bind(('127.0.0.1', port)); s.close(); break" & return & ¬
		"    except OSError:" & return & ¬
		"        port += 1" & return & ¬
		"log = open(os.path.join(pwa, 'pil-server.log'), 'a')" & return & ¬
		"subprocess.Popen([sys.executable, '-m', 'http.server', str(port)], cwd=pwa, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)" & return & ¬
		"open(os.path.join(pwa, 'pil-server.port'), 'w').write(str(port))" & return & ¬
		"print('OPEN %d' % port)" & return
	set resultLine to do shell script "python3 - " & quoted form of pwaDir & " <<'PYEOF'" & return & pyScript & return & "PYEOF"
	set thePort to text 6 thru -1 of resultLine
	open location "http://localhost:" & thePort
end run
"""

MAKE_MAC_APP = """#!/bin/bash
# PIL one-time Mac setup: builds the polished "Start PIL.app". Just double-click.
cd "$(dirname "$0")"
if ! command -v osacompile >/dev/null 2>&1; then
  echo "This setup needs to run on a Mac (osacompile not found)."
  read -p "Press Enter to close."
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "PIL needs Python 3: https://www.python.org/downloads/"
  echo "Install it, then double-click this file again."
  read -p "Press Enter to close."
  exit 1
fi
echo "Building Start PIL.app ..."
rm -rf "Start PIL.app"
osacompile -o "Start PIL.app" "Start PIL.applescript" || {
  echo "Build failed."
  read -p "Press Enter to close."
  exit 1
}
if [ -f "pil.icns" ]; then
  cp "pil.icns" "Start PIL.app/Contents/Resources/applet.icns"
fi
echo ""
echo "Done! From now on, double-click 'Start PIL.app' to launch your library."
echo "(First launch: right-click the app -> Open, to clear Apple's one-time check.)"
read -p "Press Enter to close."
"""

# Windows: hidden-console launchers. Start finds/starts the server (no console
# window), Stop kills it via the PID file.
START_VBS = """' Start PIL (Windows) - double-click to launch. No console window.
Option Explicit
Dim fso, sh, pwaDir, pidFile, port, proc, started, p
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
pwaDir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = pwaDir
pidFile = fso.BuildPath(pwaDir, "pil-server.pid")

Function PilOnPort(p)
  On Error Resume Next
  Dim h, body
  Set h = CreateObject("MSXML2.XMLHTTP")
  h.open "GET", "http://127.0.0.1:" & p & "/index.html", False
  h.send
  If Err.Number <> 0 Then PilOnPort = False : Exit Function
  On Error GoTo 0
  body = Mid(h.responseText, 1, 4000)
  PilOnPort = (InStr(body, "Personal Instagram Library") > 0)
End Function

' Already running? Just open it.
For p = 8080 To 8090
  If PilOnPort(p) Then
    sh.Run "http://localhost:" & p, 1, False
    WScript.Quit
  End If
Next

' Need Python 3 on PATH.
Dim hasPy
On Error Resume Next
sh.Run "cmd /c where python >nul 2>nul", 0, True
hasPy = (Err.Number = 0)
On Error GoTo 0
If Not hasPy Then
  MsgBox "PIL needs Python 3: https://www.python.org/downloads/" & vbCrLf & _
         "Install it (tick ""Add python.exe to PATH""), then try again.", 48, "PIL"
  WScript.Quit 1
End If

' Start on the first free port, verify it answers, remember the PID.
started = False
For Each port In Array(8080, 8081, 8082)
  Set proc = sh.Exec("python -m http.server " & port)
  WScript.Sleep 1500
  If PilOnPort(port) Then
    fso.CreateTextFile(pidFile, True).Write proc.ProcessID & ":" & port
    sh.Run "http://localhost:" & port, 1, False
    started = True
    Exit For
  Else
    On Error Resume Next : proc.Terminate : On Error GoTo 0
  End If
Next
If Not started Then MsgBox "Couldn't start the PIL server.", 16, "PIL"
"""

STOP_VBS = """' Stop PIL (Windows) - double-click to stop the background server.
Option Explicit
Dim fso, pidFile, parts, sh
Set fso = CreateObject("Scripting.FileSystemObject")
pidFile = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "pil-server.pid")
If fso.FileExists(pidFile) Then
  parts = Split(fso.OpenTextFile(pidFile).ReadAll(), ":")
  Set sh = CreateObject("WScript.Shell")
  sh.Run "taskkill /PID " & Trim(parts(0)) & " /F", 0, True
  fso.DeleteFile pidFile
  MsgBox "PIL server stopped.", 64, "PIL"
Else
  MsgBox "The PIL server isn't running.", 64, "PIL"
End If
"""


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
    write_icns(os.path.join(out_dir, "pil.icns"))          # mac app icon
    cmd_path = os.path.join(out_dir, "Start PIL.command")
    with open(cmd_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(START_COMMAND)
    os.chmod(cmd_path, 0o755)
    with open(os.path.join(out_dir, "Start PIL.bat"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(START_BAT)
    # Polished launchers: mac .app (built on first run), hidden-console Windows pair
    with open(os.path.join(out_dir, "Start PIL.applescript"), "w", encoding="utf-8", newline="\n") as f:
        f.write(APPLESCRIPT)
    mac_path = os.path.join(out_dir, "Make Mac App.command")
    with open(mac_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(MAKE_MAC_APP)
    os.chmod(mac_path, 0o755)
    with open(os.path.join(out_dir, "Start PIL.vbs"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(START_VBS)
    with open(os.path.join(out_dir, "Stop PIL.vbs"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(STOP_VBS)

    files = sorted(os.listdir(out_dir))
    total = sum(os.path.getsize(os.path.join(out_dir, x)) for x in files)
    print(f"[done] {d['stats']['posts']} posts -> {out_dir}/ ({total / 1024 / 1024:.1f} MB)", flush=True)
    print("One-click: unzip the folder and double-click 'Start PIL' "
          "(.command on Mac, .bat on Windows).", flush=True)


if __name__ == "__main__":
    main()
