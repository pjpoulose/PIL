#!/usr/bin/env python3
"""PIL step 4: export the library to a JSON file for manual use with any AI tool.

Captions are truncated to snippets (never reproduced verbatim). Deep-read
knowledge (summary, key points, how-to, links) is included for extracted posts.

Usage:
    python3 export_web.py [output_path]   # defaults to <data_dir>/web_data.json
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pil_common import db_connect, load_config

SNIPPET_LEN = 280


def main():
    cfg = load_config()
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(cfg["data_dir"], "web_data.json")
    db = db_connect(cfg, read_only=True)

    folders = [{"id": r["collection_id"], "name": r["name"], "count": r["item_count"]}
               for r in db.execute("SELECT collection_id, name, item_count FROM folders")]

    post_folders = {}
    for r in db.execute("SELECT post_id, collection_id FROM post_folders"):
        post_folders.setdefault(r["post_id"], []).append(r["collection_id"])

    tags = {}
    for r in db.execute("SELECT post_id, tag FROM tags"):
        tags.setdefault(r["post_id"], []).append(r["tag"])

    knowledge = {}
    for r in db.execute("SELECT post_id, summary, key_points, howto, links FROM knowledge"):
        try:
            kp = json.loads(r["key_points"] or "[]")
        except Exception:
            kp = []
        try:
            links = json.loads(r["links"] or "[]")
        except Exception:
            links = []
        knowledge[r["post_id"]] = {
            "summary": (r["summary"] or "")[:1500],
            "key_points": kp[:8],
            "howto": (r["howto"] or "")[:1200],
            "links": links[:10],
        }

    posts = []
    for r in db.execute("SELECT post_id, url, author, media_type, caption, saved_at FROM posts"):
        cap = (r["caption"] or "").strip()
        snippet = cap[:SNIPPET_LEN] + ("…" if len(cap) > SNIPPET_LEN else "")
        p = {
            "id": r["post_id"],
            "url": r["url"],
            "author": r["author"],
            "media_type": r["media_type"],
            "snippet": snippet,
            "tags": sorted(set(tags.get(r["post_id"], []))),
            "folders": sorted(set(post_folders.get(r["post_id"], []))),
            "saved_at": r["saved_at"],
        }
        if r["post_id"] in knowledge:
            p["knowledge"] = knowledge[r["post_id"]]
        posts.append(p)

    payload = {
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "post_count": len(posts),
        "folders": folders,
        "posts": posts,
        "schema_note": ("posts[].folders holds folder ids resolving via folders[].id. "
                        "posts[].knowledge is present only for posts with deep extraction. "
                        "snippet is a truncated caption; link out to url for the full post."),
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    size = os.path.getsize(out_path)
    print(f"[done] {len(posts)} posts -> {out_path} ({size / 1024 / 1024:.1f} MB)", flush=True)
    db.close()


if __name__ == "__main__":
    main()
