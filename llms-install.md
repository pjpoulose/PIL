# llms-install.md — agent install guide for PIL's MCP server

## What this is

PIL (Personal Instagram Library) ships a read-only local MCP server
(`bin/mcp_server.py`) over stdio. Tools: `search_posts`, `get_post`,
`list_folders`, `list_tags`, `library_stats`. It reads the user's own
`pil.sqlite` — SELECT-only, `mode=ro`. It never writes, never uploads,
never leaves the machine.

## Install the MCP server

Option A — PyPI (recommended):

1. `pip install personal-instagram-library` (needs Python 3.10+)
2. Register it with the MCP client:
   ```json
   {
     "mcpServers": {
       "pil": { "command": "pil-mcp", "args": [] }
     }
   }
   ```
   (`uvx personal-instagram-library` / `pipx run` also work; the entry point is `pil-mcp`.)

Option B — from source:

1. `git clone https://github.com/pjpoulose/PIL.git && cd PIL`
2. `pip install "mcp<2"` (needs Python 3.10+)
3. Register it with the MCP client:
   ```json
   {
     "mcpServers": {
       "pil": {
         "command": "python3",
         "args": ["bin/mcp_server.py"],
         "cwd": "/path/to/PIL"
       }
     }
   }
   ```
   Optional: set `PIL_CONFIG` to a JSON config file with `data_dir`
   (defaults to `~/.local/share/pil`). Copy `pil.config.example.json` to start.
4. If no library database exists yet, the server exits with a message
   telling the user to run the pipeline below first.

## Building the library (the data behind the server)

The server is an empty shell until the user builds their personal library.
That part is interactive and driven by `SKILL.md`:

1. Link Instagram: `instagram-cli accounts` must list the user's account
   (the user links it themselves in their browser — never handle passwords
   or tokens). Put the `user_fbid` in the config as `account_id`.
2. `python3 bin/ingest_saved.py` — saved collections → folders, saved posts → DB.
3. `python3 bin/extract_content.py` — vision-AI deep read into summaries,
   key points, how-tos, links. Slow on large libraries; run in background.
4. `python3 bin/tag_all.py` — programmatic tags for thinly-tagged posts.

Every step is resume-safe (cursor files / idempotent writes).

## Operating rules (do not skip)

- **Code is shared, data stays home.** Never copy, upload, or commit a user's
  `pil.sqlite`, exports, captions, or account ID. The repo holds code, schema,
  config examples, and docs only.
- The MCP server is read-only by construction. There is no write path.
