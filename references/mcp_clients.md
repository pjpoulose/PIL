# Connecting MCP clients to PIL

All three clients talk to the same local server over stdio — nothing leaves the
user's machine. The server command is:

```
python3 /path/to/pil/bin/mcp_server.py
```

with `PIL_CONFIG` pointing at the user's config file (or `pil.config.json`
discoverable in the working directory / `~/.config/pil/`). The client needs
`mcp<2` installed in the Python that runs the server.

## Claude Code

```bash
claude mcp add pil -e PIL_CONFIG=/home/<user>/.config/pil/pil.config.json \
  -- python3 /path/to/pil/bin/mcp_server.py
```

Verify with `claude mcp list`. The five tools (`search_posts`, `get_post`,
`list_folders`, `list_tags`, `library_stats`) become available in that project.

## Claude Desktop

Edit `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "pil": {
      "command": "python3",
      "args": ["/path/to/pil/bin/mcp_server.py"],
      "env": { "PIL_CONFIG": "/home/<user>/.config/pil/pil.config.json" }
    }
  }
}
```

Restart Claude Desktop. PIL's tools appear under the hammer/search menu.

## Cursor

Settings → MCP → Add new global MCP server (or project `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "pil": {
      "command": "python3",
      "args": ["/path/to/pil/bin/mcp_server.py"],
      "env": { "PIL_CONFIG": "/home/<user>/.config/pil/pil.config.json" }
    }
  }
}
```

## Notes

- The server opens the database with SQLite `mode=ro`: even a buggy client
  cannot write to the library through these tools.
- The server needs an existing database — run `bin/ingest_saved.py` (step 1)
  first. If the DB is missing, the server exits with a clear message instead
  of starting empty.
- Keep the `mcp` Python package pinned to 1.x (`pip install "mcp<2"`): in the
  2.x SDK, `FastMCP` was renamed to `MCPServer` and the v1 import path raises
  `ModuleNotFoundError`, so this server requires the 1.x API.
