#!/usr/bin/env python3
"""PIL step 3: programmatic tagging for posts lacking tags.

Tags come from caption/summary keywords plus normalized folder names.
Resume-safe: only touches posts with fewer than 3 tags.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pil_common import db_connect, load_config
from extract_content import gen_tags


def norm_folder(name):
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def main():
    cfg = load_config()
    db = db_connect(cfg)
    db.execute("DELETE FROM tags WHERE rowid NOT IN (SELECT MIN(rowid) FROM tags GROUP BY post_id, tag)")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tags_unique ON tags(post_id, tag)")
    folder_of = {}
    for pid, cname in db.execute(
        "SELECT pf.post_id, f.name FROM post_folders pf JOIN folders f ON f.collection_id=pf.collection_id"
    ):
        folder_of.setdefault(pid, set()).add(norm_folder(cname))
    rows = db.execute(
        """SELECT p.post_id, p.caption, p.media_type, p.author FROM posts p
           LEFT JOIN tags t ON t.post_id = p.post_id
           GROUP BY p.post_id HAVING COUNT(t.tag) < 3"""
    ).fetchall()
    print(f"[tags] {len(rows)} posts need tags", flush=True)
    n = 0
    for pid, caption, media_type, author in rows:
        tags = gen_tags(caption, "", media_type, author)
        for ft in folder_of.get(pid, ()):
            if ft and ft not in tags:
                tags.append(ft)
        db.executemany("INSERT OR IGNORE INTO tags(post_id,tag) VALUES (?,?)",
                       [(pid, t) for t in tags[:10]])
        n += 1
        if n % 500 == 0:
            db.commit()
            print(f"[tags] {n}/{len(rows)}", flush=True)
    db.commit()
    total = db.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    db.close()
    print(f"[done] tagged {n} posts ({total} tag rows total)", flush=True)


if __name__ == "__main__":
    main()
