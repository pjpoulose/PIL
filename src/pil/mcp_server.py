#!/usr/bin/env python3
"""PIL MCP server: READ-ONLY local access to a Personal Instagram Library.

Exposes the user's local SQLite database (pil.sqlite) to MCP clients
(Claude Code, Claude Desktop, Cursor, …) over stdio.

Read-only guarantee:
  - The SQLite connection is opened with mode=ro (SQLite enforces it).
  - Every tool below issues SELECT statements only. There is no write path.

Run:
    python3 mcp_server.py
Config is resolved exactly like the other PIL scripts (see pil_common.py):
PIL_CONFIG env var, ./pil.config.json, or ~/.config/pil/pil.config.json.
"""
import json
import os
import sys

from pil.pil_common import db_connect, load_config

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pil")

_cfg = load_config()
if not os.path.exists(_cfg["db_path"]):
    print(
        f"PIL database not found at {_cfg['db_path']}.\n"
        "Run the pipeline first: bin/ingest_saved.py, then bin/extract_content.py.",
        file=sys.stderr,
    )
    sys.exit(1)
_db = db_connect(_cfg, read_only=True)


def _like_esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _tags_for(post_id: str) -> list:
    return [r["tag"] for r in _db.execute(
        "SELECT tag FROM tags WHERE post_id=? ORDER BY tag", (post_id,))]


def _folders_for(post_id: str) -> list:
    return [{"id": r["collection_id"], "name": r["name"]} for r in _db.execute(
        """SELECT f.collection_id, f.name FROM post_folders pf
           JOIN folders f ON f.collection_id = pf.collection_id
           WHERE pf.post_id=? ORDER BY f.name""", (post_id,))]


@mcp.tool()
def search_posts(query: str, folder: str = "", tag: str = "", limit: int = 10) -> list:
    """Search the library. Matches query text against captions and deep-read
    knowledge (summaries, key points, how-to). Optionally restrict to one
    folder (collection id or folder name) and/or one tag. Returns up to `limit`
    matches (1-50) as compact cards with a `has_knowledge` flag."""
    limit = max(1, min(int(limit or 10), 50))
    q = f"%{_like_esc(query)}%"
    sql = """SELECT DISTINCT p.post_id, p.url, p.author, p.media_type,
                    substr(p.caption, 1, 200) AS snippet,
                    CASE WHEN k.post_id IS NOT NULL THEN 1 ELSE 0 END AS has_knowledge
             FROM posts p
             LEFT JOIN knowledge k ON k.post_id = p.post_id
             LEFT JOIN post_folders pf ON pf.post_id = p.post_id
             LEFT JOIN folders f ON f.collection_id = pf.collection_id
             LEFT JOIN tags t ON t.post_id = p.post_id
             WHERE (p.caption LIKE ? ESCAPE '\\' OR k.summary LIKE ? ESCAPE '\\'
                    OR k.key_points LIKE ? ESCAPE '\\' OR k.howto LIKE ? ESCAPE '\\')"""
    params: list = [q, q, q, q]
    if folder:
        sql += " AND (pf.collection_id = ? OR f.name = ?)"
        params += [folder, folder]
    if tag:
        sql += " AND t.tag = ?"
        params += [tag]
    sql += " ORDER BY p.saved_at DESC LIMIT ?"
    params.append(limit)
    out = []
    for r in _db.execute(sql, params):
        out.append({
            "id": r["post_id"],
            "author": r["author"],
            "url": r["url"],
            "media_type": r["media_type"],
            "snippet": r["snippet"],
            "has_knowledge": bool(r["has_knowledge"]),
            "folders": [f["name"] for f in _folders_for(r["post_id"])],
            "tags": _tags_for(r["post_id"]),
        })
    return out


@mcp.tool()
def get_post(post_id: str) -> dict:
    """Return everything PIL knows about one post: metadata, deep-read
    knowledge (summary, key_points, howto, links), folders, and tags."""
    r = _db.execute("SELECT * FROM posts WHERE post_id=?", (post_id,)).fetchone()
    if not r:
        return {"error": f"no post with id {post_id}"}
    k = _db.execute("SELECT summary, key_points, howto, links FROM knowledge WHERE post_id=?",
                    (post_id,)).fetchone()
    knowledge = None
    if k:
        try:
            key_points = json.loads(k["key_points"] or "[]")
        except Exception:
            key_points = []
        try:
            links = json.loads(k["links"] or "[]")
        except Exception:
            links = []
        knowledge = {
            "summary": k["summary"],
            "key_points": key_points,
            "howto": k["howto"],
            "links": links,
        }
    return {
        "id": r["post_id"],
        "url": r["url"],
        "author": r["author"],
        "media_type": r["media_type"],
        "caption": r["caption"],
        "saved_at": r["saved_at"],
        "knowledge": knowledge,
        "folders": _folders_for(post_id),
        "tags": _tags_for(post_id),
    }


@mcp.tool()
def list_folders() -> list:
    """List the user's saved-post collections (rooms). `item_count` is the
    count Instagram reports; `mapped_posts` is how many are actually indexed."""
    out = []
    for r in _db.execute("SELECT collection_id, name, item_count FROM folders ORDER BY name"):
        mapped = _db.execute("SELECT COUNT(*) AS c FROM post_folders WHERE collection_id=?",
                             (r["collection_id"],)).fetchone()["c"]
        out.append({
            "id": r["collection_id"],
            "name": r["name"],
            "item_count": r["item_count"],
            "mapped_posts": mapped,
        })
    return out


@mcp.tool()
def list_tags(limit: int = 100) -> list:
    """List tags by usage, most-used first."""
    limit = max(1, min(int(limit or 100), 500))
    return [{"tag": r["tag"], "count": r["c"]} for r in _db.execute(
        "SELECT tag, COUNT(*) AS c FROM tags GROUP BY tag ORDER BY c DESC LIMIT ?", (limit,))]


@mcp.tool()
def library_stats() -> dict:
    """Totals for the library plus deep-read coverage per field."""
    q = lambda sql: _db.execute(sql).fetchone()[0]
    return {
        "posts": q("SELECT COUNT(*) FROM posts"),
        "folders": q("SELECT COUNT(*) FROM folders"),
        "distinct_tags": q("SELECT COUNT(DISTINCT tag) FROM tags"),
        "knowledge_rows": q("SELECT COUNT(*) FROM knowledge"),
        "coverage": {
            "with_summary": q("SELECT COUNT(*) FROM knowledge WHERE summary IS NOT NULL AND summary != ''"),
            "with_key_points": q("SELECT COUNT(*) FROM knowledge WHERE key_points IS NOT NULL AND key_points != '[]'"),
            "with_howto": q("SELECT COUNT(*) FROM knowledge WHERE howto IS NOT NULL AND howto != ''"),
            "with_links": q("SELECT COUNT(*) FROM knowledge WHERE links IS NOT NULL AND links != '[]'"),
        },
    }


def main():
    """Entry point: run the read-only PIL MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
