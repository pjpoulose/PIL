---
name: "pil"
description: "Build and query a Personal Instagram Library: ingest your saved Instagram posts into a local SQLite database, run vision-AI deep extraction over them, and query the library live through a read-only local MCP server. Use when the user wants to index, search, or ask questions over their Instagram saved posts."
---

# PIL — Personal Instagram Library

## Purpose
Turn a user's Instagram saved posts into a private, queryable knowledge base that
lives entirely on their own machine: ingest → deep-extract → tag → export, plus a
read-only MCP server so Cursor, Claude Code, or Claude Desktop can query it live.

## Tooling
Helpers live in `bin/` and share config through `bin/pil_common.py`. Config resolves
from `PIL_CONFIG` env var, `./pil.config.json`, then `~/.config/pil/pil.config.json`
(copy `pil.config.example.json` to start). The DB is `<data_dir>/pil.sqlite`;
`schema.sql` is applied automatically on first run.

- `bin/ingest_saved.py [collection_id]` — step 1: saved collections → `folders`,
  saved posts → `posts`/`post_folders`. Resume-safe via cursor files.
- `bin/extract_content.py` — step 2: vision-AI deep read (`instagram-cli
  media-understanding`) → `knowledge` rows (summary, key points, how-to, links)
  plus tags. Resume-safe; batches of 25.
- `bin/tag_all.py` — step 3: programmatic tags (caption keywords + folder names)
  for posts with fewer than 3 tags.
- `bin/export_web.py [output_path]` — step 4: static JSON export for manual use
  with any AI tool. Captions are truncated to snippets, never verbatim.
- `bin/export_html.py [output_path]` — step 5: self-contained HTML dashboard
  (`pil_library.html`): search, rooms, tags, sorting, read-notes. Works offline
  from disk; the user can keep it on their Desktop as a web app.
- `bin/mcp_server.py` — read-only MCP server over stdio. Tools: `search_posts`,
  `get_post`, `list_folders`, `list_tags`, `library_stats`.

Requires: `python3`, `instagram-cli` (see the Instagram skill), `pip install "mcp<2"`.

## Auth
The user links their own Instagram account themselves. `instagram-cli accounts`
must list it; the `user_fbid` from that output goes into `pil.config.json` as
`account_id`. Never ask for, handle, or store passwords, tokens, or session data.
The pipeline only reads the user's own saved posts.

## Operating Rules
1. **Code is shared, data stays home.** Never copy, upload, or commit a user's
   `pil.sqlite`, exports, captions, or account ID. The package holds code,
   schema, config examples, and docs only.
2. The MCP server is read-only by construction (SQLite `mode=ro`, SELECT-only
   tools). Never add a write tool.
3. Run the pipeline in order: ingest → extract → tag. Export any time after ingest.
4. Deep-extraction headings are normalized in `extract_content.py`
   (`_normalize_labels`): sections read Context / Moment / Significance / Origin.
   Do not reintroduce the word "Cultural".
5. Keep this file lean. Install/usage docs live in `README.md`; per-client MCP
   wiring lives in `references/mcp_clients.md`.
