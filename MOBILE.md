# PIL on your phone

Your PIL library can live on your phone as an installable app — the same
answer-first search, offline, with your data never leaving your control.

## How it works

Phones can't use the desktop launcher: a phone needs the PWA files on **https**
before it can install them. So you publish the generated PWA folder to hosting
*you* control (private to you), then install from that link. After the first
load the service worker caches everything on the phone, so the library works
fully offline — search, answers, citations, all on-device.

## 1. Publish (one command, on your computer)

```bash
bin/export_pwa.py /tmp/pil-pwa
bin/publish_pwa.py /tmp/pil-pwa --provider netlify
```

`publish_pwa.py` uploads the bundle to your own Netlify site (token from the
`publish` section of your local `pil.config.json`, or the `NETLIFY_TOKEN` env
var — never committed), then writes `phone.json` + `phone-qr.png` into the
bundle. Re-serve or re-zip the folder so those files are included; the desktop
PWA then shows a **Take PIL on your phone** panel with a QR code.

Already host the folder somewhere yourself? Skip the upload:

```bash
bin/publish_pwa.py /tmp/pil-pwa --provider manual --url https://your-private-url
```

## 2. Install on the phone

Scan the QR code on the desktop PWA (or open the link on the phone), using
wi-fi for the first load (~tens of MB, then cached):

- **Android:** open the link in Chrome → menu → **Install app** (or **Add to
  Home screen**). It runs standalone like a native app.
- **iPhone:** open the link in Safari → **Share** → **Add to Home Screen**.
  It runs fullscreen; offline works via the service worker cache.

## Privacy

Code is shared, data stays home — publishing just moves *your* bundle to
*your* hosting. The repo never sees your posts, captions, or account ID. Put
the site behind your host's access control (password or private URL) since the
bundle contains your personal library.
