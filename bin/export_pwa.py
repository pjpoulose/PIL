#!/usr/bin/env python3
"""PIL step 6: export the library as an installable PWA bundle.

Writes a folder with everything a browser needs to offer "Install":
index.html (the dashboard, PWA-enabled), manifest.json, sw.js (offline
service worker), and app icons. Serve the folder over HTTP and the browser
takes it from there.

Usage:
    python3 export_pwa.py [output_dir]   # defaults to <data_dir>/pwa
    # then double-click the launcher for your OS (see README) - it serves
    # the folder and opens http://127.0.0.1:8080 for you.

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
echo "Starting your Personal Instagram Library on http://127.0.0.1:$PORT ..."
echo "A browser window will open. Keep this window open while you use PIL;"
echo "closing it stops the library."
sleep 1
(open "http://127.0.0.1:$PORT" 2>/dev/null || xdg-open "http://127.0.0.1:$PORT" 2>/dev/null || true) &
exec python3 -c "from http.server import ThreadingHTTPServer as S, SimpleHTTPRequestHandler as H; S(('127.0.0.1', $PORT), H).serve_forever()"
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
echo Starting your Personal Instagram Library on http://127.0.0.1:8080 ...
echo A browser window will open. Keep this window open while you use PIL;
echo closing it stops the library.
timeout /t 1 /nobreak >nul
start "" "http://127.0.0.1:8080"
python -c "from http.server import ThreadingHTTPServer as S, SimpleHTTPRequestHandler as H; S(('127.0.0.1', 8080), H).serve_forever()"
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
		"subprocess.Popen([sys.executable, '-c', 'from http.server import ThreadingHTTPServer as S, SimpleHTTPRequestHandler as H; S(('127.0.0.1', %d), H).serve_forever()' % port], cwd=pwa, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)" & return & ¬
		"open(os.path.join(pwa, 'pil-server.port'), 'w').write(str(port))" & return & ¬
		"print('OPEN %d' % port)" & return
	set resultLine to do shell script "python3 - " & quoted form of pwaDir & " <<'PYEOF'" & return & pyScript & return & "PYEOF"
	set thePort to text 6 thru -1 of resultLine
	open location "http://127.0.0.1:" & thePort
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
# window), Stop kills it via the PID file. Start diagnoses the common failure
# modes (ran from inside the zip, Store stub instead of real Python) itself.
START_VBS = """' Start PIL (Windows) - double-click to launch. No console window.
Option Explicit
Dim fso, sh, pwaDir, pidFile, logFile
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
pwaDir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = pwaDir
pidFile = fso.BuildPath(pwaDir, "pil-server.pid")
logFile = fso.BuildPath(pwaDir, "pil-launcher.log")

Sub Log(msg)
  On Error Resume Next
  Dim t : Set t = fso.OpenTextFile(logFile, 8, True)
  t.WriteLine Now & "  " & msg
  t.Close
  On Error GoTo 0
End Sub

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

Function WaitForPil(p)
  Dim i
  For i = 1 To 20
    If PilOnPort(p) Then WaitForPil = True : Exit Function
    WScript.Sleep 500
  Next
  WaitForPil = False
End Function

Log "--- Start PIL launched ---"

' Must run from the extracted folder, not from inside the zip.
If Not fso.FileExists(fso.BuildPath(pwaDir, "index.html")) Then
  MsgBox "Please extract the whole pil-pwa folder from the zip first," & vbCrLf & _
         "then double-click Start PIL inside the extracted folder.", 48, "PIL"
  WScript.Quit 1
End If

' Already running? Just open it.
Dim p
For p = 8080 To 8090
  If PilOnPort(p) Then
    Log "already running on " & p
    sh.Run "http://127.0.0.1:" & p, 1, False
    WScript.Quit
  End If
Next

' Find a real Python 3 (not the Microsoft Store stub).
Dim oExec, pyPath, ver
pyPath = "" : ver = ""
On Error Resume Next
Set oExec = sh.Exec("cmd /c where python 2>nul")
If Err.Number = 0 Then
  If Not oExec.StdOut.AtEndOfStream Then pyPath = Trim(oExec.StdOut.ReadLine())
End If
On Error GoTo 0
Log "where python -> " & pyPath
If InStr(LCase(pyPath), "windowsapps") > 0 Then
  Log "ignoring Microsoft Store stub"
  pyPath = ""
End If
If pyPath <> "" Then
  On Error Resume Next
  Set oExec = sh.Exec("cmd /c python --version 2>&1")
  If Err.Number = 0 Then ver = Trim(oExec.StdOut.ReadAll())
  On Error GoTo 0
  Log "python --version -> " & ver
End If
If Left(ver, 8) <> "Python 3" Then
  Log "no usable Python 3"
  MsgBox "PIL couldn't find Python 3 on this computer." & vbCrLf & vbCrLf & _
         "Install it from https://www.python.org/downloads/" & vbCrLf & _
         "(on the first install screen, tick ""Add python.exe to PATH"")," & vbCrLf & _
         "then double-click Start PIL again.", 48, "PIL"
  WScript.Quit 1
End If

' Start the server on the first free port and wait until it answers.
' Threaded server bound to 127.0.0.1: the browser opens the exact address
' that was verified, so localhost/IPv6/proxy quirks can't get in the way.
Dim started, proc, tried, srvCmd
started = False : tried = ""
For Each p In Array(8080, 8081, 8082)
  tried = tried & p & " "
  Log "trying port " & p
  srvCmd = "python -c " & Chr(34) & "from http.server import ThreadingHTTPServer as S, SimpleHTTPRequestHandler as H; S(('127.0.0.1'," & p & "),H).serve_forever()" & Chr(34)
  On Error Resume Next
  Set proc = sh.Exec(srvCmd)
  If Err.Number <> 0 Then
    Log "Exec failed: " & Err.Description
    On Error GoTo 0
  Else
    On Error GoTo 0
    If WaitForPil(p) Then
      fso.CreateTextFile(pidFile, True).Write proc.ProcessID & ":" & p
      Log "serving on 127.0.0.1:" & p & " (pid " & proc.ProcessID & ")"
      sh.Run "http://127.0.0.1:" & p, 1, False
      started = True
      Exit For
    Else
      Log "no answer on " & p & ", killing"
      On Error Resume Next : proc.Terminate : On Error GoTo 0
    End If
  End If
Next

If Not started Then
  Log "FAILED on ports " & tried
  MsgBox "PIL couldn't start its local server." & vbCrLf & vbCrLf & _
         "Python was found (" & ver & "), but the library didn't answer" & vbCrLf & _
         "on ports " & Trim(tried) & "." & vbCrLf & vbCrLf & _
         "If you're on a work network, a proxy or firewall may be blocking" & vbCrLf & _
         "local connections. Details were saved to pil-launcher.log next" & vbCrLf & _
         "to this file.", 16, "PIL"
End If
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
