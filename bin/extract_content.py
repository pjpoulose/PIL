#!/usr/bin/env python3
"""PIL step 2: deep content extraction for posts lacking knowledge rows.

Uses instagram-cli media-understanding (vision AI) to watch/read each post and
produce a narrative summary + semantic breakdown, then extracts links and tags.

Resume-safe: completed media fbids are tracked in <data_dir>/.understanding_done.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pil_common import db_connect, load_config, require_account

BATCH = 25

URL_RE = re.compile(r"https?://[^\s\"')\]]+")
BARE_RE = re.compile(r"(?<!/)(?<!\w)((?:bit\.ly|tinyurl\.com|t\.co|lnk\.bio|linktr\.ee|ow\.ly|buff\.ly|goo\.gl|rb\.gy|is\.gd)/[^\s\"')\]]+)")


def run_cli(args):
    p = subprocess.run(["instagram-cli"] + args, capture_output=True, text=True, timeout=300)
    return p.stdout


def clean_url(u):
    return u.rstrip(".,;:!?'\"\\)").rstrip("/")


def extract_links(text):
    if not text:
        return []
    links = set()
    for u in URL_RE.findall(text):
        links.add(clean_url(u))
    for u in BARE_RE.findall(text):
        links.add("https://" + clean_url(u))
    return sorted(links)


STOPWORDS = {"the","a","an","and","or","of","to","in","for","on","with","is","are","it","this","that","how","why",
 "your","you","my","me","our","we","i","at","by","from","as","be","was","were","will","would","can","its","if","not",
 "all","more","new","just","but","about","into","than","them","their","has","have","had","do","does","did","when",
 "what","where","which","who","whom","these","those","then","so","out","up","no","yes","via","reel","reels",
 "post","video","photo","caption","like","share","follow","comment","link","bio","check","day","one","two",
 "best","get","got","make","made","using","use","used","top","free","pro","tips","tricks","hack","hacks"}


def gen_tags(caption, summary, media_type, author):
    text = f"{caption or ''} {summary or ''}".lower()
    text = re.sub(r"[^a-z0-9\s#-]", " ", text)
    words = re.findall(r"[a-z][a-z0-9-]{2,}", text)
    freq = {}
    for w in words:
        w = w.lstrip("#")
        if w in STOPWORDS or len(w) < 4:
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq, key=lambda w: -freq[w])
    tags = []
    seen = set()

    def _add(t):
        if t not in seen:
            tags.append(t)
            seen.add(t)

    for w in ranked:
        _add(w)
        if len(tags) >= 6:
            break
    fmt = (media_type or "").lower()
    if "video" in fmt or "reel" in fmt:
        _add("video")
    elif "photo" in fmt or "image" in fmt:
        _add("image")
    if "carousel" in fmt:
        _add("carousel")
    tags = tags[:8]
    for filler in ([author.lower()] if author else []) + ["instagram"]:
        if len(tags) >= 3:
            break
        _add(filler)
    return tags[:8]


def _normalize_labels(text):
    """Drop the word 'Cultural' from vision-model headings so sections read
    Context / Moment / Significance / Origin instead of Cultural Context etc."""
    for old, new in (
        ("Cultural Context", "Context"),
        ("Cultural Moment:", "Moment:"),
        ("Cultural Significance:", "Significance:"),
        ("Cultural Origin:", "Origin:"),
    ):
        text = text.replace(old, new)
    return text


def parse_understanding(d):
    """Response shape: {"media": [{"media_id","narrative_summary","semantic_understanding","error"}...]}."""
    out = {}
    items = d.get("media") or d.get("items") or d.get("results") or []
    if isinstance(items, dict):
        items = [items]
    for it in items:
        if not isinstance(it, dict):
            continue
        fid = str(it.get("media_id") or it.get("fbid") or it.get("id") or "")
        if it.get("error"):
            continue
        narr = _normalize_labels(str(it.get("narrative_summary") or ""))
        sem = _normalize_labels(str(it.get("semantic_understanding") or ""))
        summary = (narr + "\n\n" + sem).strip()[:4000]
        key_points = []
        for line in re.split(r"\n+", sem):
            s = line.strip().lstrip("-•*–—0123456789. ").strip()
            if len(s) > 30 and len(s) < 400:
                key_points.append(s)
            if len(key_points) >= 8:
                break
        howto = ""
        m = re.search(r"(?is)(?:how[- ]?to|steps?|instructions?|do this)[:\s]*(.+)", sem)
        if m:
            howto = m.group(1).strip()[:2000]
        if fid:
            out[fid] = {"summary": summary, "key_points": key_points, "howto": howto}
    return out


def main():
    cfg = load_config()
    account = require_account(cfg)
    progress = os.path.join(cfg["data_dir"], ".understanding_done")
    done = set()
    if os.path.exists(progress):
        done = set(x.strip() for x in open(progress) if x.strip())
    db = db_connect(cfg)
    rows = db.execute(
        "SELECT post_id, media_fbid, caption, media_type, author FROM posts "
        "WHERE post_id NOT IN (SELECT post_id FROM knowledge) ORDER BY post_id"
    ).fetchall()
    rows = [r for r in rows if r[1] and r[1] not in done]
    print(f"[understanding] {len(rows)} posts to process", flush=True)
    failures = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        ids = ",".join(r[1] for r in chunk)
        out = run_cli(["media-understanding", "--account-id", account, "--media-ids", ids])
        try:
            d = json.loads(out)
        except Exception:
            print(f"[ERROR] batch {i // BATCH}: unparseable; marking chunk failed", flush=True)
            failures += len(chunk)
            time.sleep(10)
            continue
        if d.get("error") and "429" in str(d["error"]):
            print("[429] sleeping 60s", flush=True)
            time.sleep(60)
            out = run_cli(["media-understanding", "--account-id", account, "--media-ids", ids])
            try:
                d = json.loads(out)
            except Exception:
                failures += len(chunk)
                continue
        parsed = parse_understanding(d)
        if not parsed:
            print(f"[warn] batch {i // BATCH}: no parseable understanding records", flush=True)
        for (post_id, fbid, caption, media_type, author) in chunk:
            rec = parsed.get(fbid, {})
            summary = rec.get("summary", "")
            key_points = rec.get("key_points", [])
            howto = rec.get("howto", "")
            if not summary and caption:
                summary = caption[:2000]
                key_points = []
            links = extract_links((caption or "") + " " + summary)
            db.execute(
                "INSERT OR IGNORE INTO knowledge(post_id,summary,key_points,howto,links) VALUES (?,?,?,?,?)",
                (post_id, summary, json.dumps(key_points), howto, json.dumps(links)),
            )
            tags = gen_tags(caption, summary, media_type, author)
            # INSERT OR IGNORE: posts may already carry tags from tag_all.py
            db.executemany("INSERT OR IGNORE INTO tags(post_id,tag) VALUES (?,?)",
                           [(post_id, t) for t in tags])
            done.add(fbid)
        db.commit()
        with open(progress, "w") as f:
            f.write("\n".join(sorted(done)))
        print(f"[understanding] batch {i // BATCH}: {len(chunk)} done ({i + len(chunk)}/{len(rows)})", flush=True)
        time.sleep(1)
    db.close()
    print(f"[done] understanding complete. failures: {failures}", flush=True)


if __name__ == "__main__":
    main()
