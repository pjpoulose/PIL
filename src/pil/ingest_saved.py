#!/usr/bin/env python3
"""PIL step 1: ingest saved posts (and their collections) into the local SQLite DB.

Usage:
    python3 ingest_saved.py                 # ingest collections, then all saved posts
    python3 ingest_saved.py <collection_id> # ingest one collection only

Resume-safe: pagination cursors are stored under <data_dir>/.cursors/.
Run `instagram-cli accounts` first to find your user_fbid for pil.config.json.
"""
import json
import os
import re
import subprocess
import sys
import time

from pil.pil_common import db_connect, load_config, require_account

AUTO_COLLECTIONS = {"ALL_MEDIA_AUTO_COLLECTION", "SAVED_ENTRYPOINT_COLLECTION"}


def run_cli(args):
    p = subprocess.run(["instagram-cli"] + args, capture_output=True, text=True, timeout=300)
    return p.stdout


def norm_post(p):
    """Normalize the two response shapes: global saved-posts and per-collection."""
    pid = str(p.get("media_id") or p.get("post_id") or p.get("id") or "")
    fbid = pid.split("_")[0]
    url = p.get("url") or p.get("media_permalink") or p.get("permalink")
    author = None
    ai = p.get("author_info")
    if isinstance(ai, dict):
        author = ai.get("username")
    u = p.get("user")
    if not author:
        if isinstance(u, dict):
            author = u.get("username")
        elif isinstance(u, str):
            author = u
    media_type = p.get("media_type") or p.get("post_type") or p.get("product_type")
    cap = p.get("post_caption_text")
    if cap is None:
        cap = p.get("caption")
    if isinstance(cap, dict):
        cap = cap.get("text")
    saved_at = p.get("post_creation_time") or p.get("timestamp")
    return pid, fbid, url, author, media_type, cap, saved_at


def sync_collections(cfg, account):
    """Populate the folders table from the user's saved collections."""
    out = run_cli(["saved-collections", "--account-id", account, "--limit", "100"])
    try:
        d = json.loads(out)
    except Exception:
        print(f"[collections] unparseable output: {out[:200]}", flush=True)
        return
    cols = d.get("collections", [])
    db = db_connect(cfg)
    n = 0
    for c in cols:
        cid = c.get("collection_id")
        if not cid or cid in AUTO_COLLECTIONS:
            continue
        db.execute(
            "INSERT INTO folders(collection_id,name,item_count) VALUES (?,?,?) "
            "ON CONFLICT(collection_id) DO UPDATE SET name=excluded.name, item_count=excluded.item_count",
            (cid, c.get("collection_name"), c.get("collection_media_count")),
        )
        n += 1
    db.commit()
    db.close()
    print(f"[collections] synced {n} folders", flush=True)


def fetch_all(cfg, account, collection_id=None):
    key = re.sub(r"[^A-Za-z0-9_-]", "_", collection_id or "all")
    cursor_dir = os.path.join(cfg["data_dir"], ".cursors")
    os.makedirs(cursor_dir, exist_ok=True)
    cursor_file = os.path.join(cursor_dir, f"{key}.cursor")
    after = None
    if os.path.exists(cursor_file):
        after = open(cursor_file).read().strip() or None
        if after:
            print(f"[resume] {key} from cursor {after[:20]}...", flush=True)
    total = 0
    pages = 0
    db = db_connect(cfg)
    while True:
        args = ["saved-posts", "--account-id", account, "--limit", "200"]
        if collection_id:
            args += ["--collection-id", collection_id]
        if after:
            args += ["--after", after]
        out = run_cli(args)
        try:
            d = json.loads(out)
        except Exception:
            print(f"[ERROR] {key} page {pages}: unparseable output", flush=True)
            time.sleep(10)
            continue
        if d.get("error"):
            err = str(d["error"])
            if "429" in err or "rate" in err.lower():
                print(f"[429] {key}: sleeping 60s", flush=True)
                time.sleep(60)
                continue
            print(f"[ERROR] {key} page {pages}: {err[:200]}", flush=True)
            time.sleep(10)
            continue
        posts = d.get("posts", [])
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        for p in posts:
            media_id, fbid, url, author, media_type, caption, saved_at = norm_post(p)
            if not media_id:
                continue
            db.execute(
                """INSERT INTO posts(post_id,media_fbid,url,author,media_type,caption,saved_at,indexed_at)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(post_id) DO UPDATE SET url=excluded.url, author=excluded.author,
                     media_type=excluded.media_type, caption=excluded.caption, saved_at=excluded.saved_at""",
                (media_id, fbid, url, author, media_type, caption, saved_at, now),
            )
            if collection_id:
                db.execute(
                    "INSERT OR IGNORE INTO post_folders(post_id,collection_id) VALUES (?,?)",
                    (media_id, collection_id),
                )
        db.commit()
        total += len(posts)
        pages += 1
        pi = d.get("page_info") or {}
        after = pi.get("end_cursor") or d.get("end_cursor")
        has_next = pi.get("has_next_page")
        if has_next is None:
            has_next = d.get("has_next_page")
        print(f"[{key}] page {pages}: +{len(posts)} (total {total})", flush=True)
        with open(cursor_file, "w") as f:
            f.write(after or "")
        if not has_next or not after:
            break
        time.sleep(1)
    db.close()
    if os.path.exists(cursor_file):
        os.remove(cursor_file)
    print(f"[done] {key}: {total} items over {pages} pages", flush=True)


def main():
    cfg = load_config()
    account = require_account(cfg)
    coll = sys.argv[1] if len(sys.argv) > 1 else None
    if not coll:
        sync_collections(cfg, account)
    fetch_all(cfg, account, coll)


if __name__ == "__main__":
    main()
