# PIL — Personal Instagram Library

Your Instagram saved posts, turned into a private knowledge base on your own
machine: searchable, deep-read by vision AI, and queryable live from your AI
coding tools.

**Core principle: code is shared, data stays home.** This package contains only
code, the database schema, config examples, and docs. Your saved posts, captions,
and account details never leave your computer — ingestion, extraction, search,
and the MCP server all run locally.

## What it does

1. **Ingest** your saved posts and collections into a local SQLite database.
2. **Deep-extract** each post with vision AI: a narrative summary, key points,
   how-to steps, and any URLs the post discusses — plus automatic tags.
3. **Query** the library two ways:
   - *Manual path:* a static JSON export you can upload into any AI tool.
   - *Live path:* a read-only local MCP server for Cursor, Claude Code, and
     Claude Desktop.

## Install

Prerequisites: `python3`, and `instagram-cli` with your Instagram account linked
(see the Instagram skill: run `instagram-cli accounts` — it must list your
account).

```bash
# 1. Get the code
git clone <repo-url> pil && cd pil

# 2. Configure (your data stays in data_dir, default ~/.local/share/pil)
cp pil.config.example.json ~/.config/pil/pil.config.json
# edit it: set account_id to your user_fbid from `instagram-cli accounts`

# 3. MCP server dependency
pip install "mcp<2"
```

## Build your library

```bash
cd bin
python3 ingest_saved.py      # step 1: collections + saved posts (resume-safe)
python3 extract_content.py   # step 2: vision-AI deep read (resume-safe, batches of 25)
python3 tag_all.py           # step 3: programmatic tags for untagged posts
python3 export_web.py        # step 4: static JSON export -> <data_dir>/web_data.json
```

Re-run `ingest_saved.py` any time to pick up newly saved posts; `extract_content.py`
only processes posts it hasn't seen (tracked in `<data_dir>/.understanding_done`).

## Query it live (MCP)

```bash
python3 bin/mcp_server.py    # read-only, stdio — Ctrl-C to stop
```

Wire it into your client — see [references/mcp_clients.md](references/mcp_clients.md)
for Claude Code, Claude Desktop, and Cursor configs. Available tools:

| Tool | What it does |
|---|---|
| `search_posts` | Text search over captions + deep-read knowledge, with optional folder/tag filters |
| `get_post` | Full record for one post: summary, key points, how-to, links, folders, tags |
| `list_folders` | Your saved collections with indexed counts |
| `list_tags` | Tags by usage |
| `library_stats` | Totals + deep-read coverage per field |

The server opens the database with SQLite `mode=ro` and exposes SELECT-only
tools — it cannot modify your library.

## Query it manually (static export)

`export_web.py` writes `<data_dir>/web_data.json`: every post with a
280-character caption snippet plus deep-read knowledge where available. Upload
that file into any AI chat tool to ask questions over your library.

## Layout

```
pil/
  SKILL.md                  # skill definition (for Muse)
  README.md                 # this file
  schema.sql                # the five tables: folders, posts, post_folders, knowledge, tags
  pil.config.example.json   # copy to pil.config.json and set your account_id
  bin/
    pil_common.py           # config resolution + DB helpers
    ingest_saved.py         # step 1: ingest
    extract_content.py      # step 2: vision-AI extraction
    tag_all.py              # step 3: tagging
    export_web.py           # step 4: static export
    mcp_server.py           # read-only MCP server
  references/
    mcp_clients.md          # Cursor / Claude Code / Claude Desktop wiring
```

## Troubleshooting

- `PIL account_id is not configured` → copy the example config and set
  `account_id` to your `user_fbid` from `instagram-cli accounts`.
- Extraction is slow on huge libraries — it's resume-safe; just re-run it.
- `429` rate limits are handled with backoff inside the scripts.
- The MCP server needs `mcp<2` in the Python that runs it (2.x renamed the API).
