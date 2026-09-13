# PIL MCP server (read-only, stdio).
#
# Used for registry health checks (e.g. Glama) and by anyone who wants the
# server containerized. Ships with an empty schema-only database so the
# server starts and answers MCP introspection out of the box.
#
# Serve a real library by mounting your PIL data dir at /data:
#   docker build -t pil-mcp .
#   docker run -i --rm -v ~/.local/share/pil:/data pil-mcp
#
# Wire the container into any MCP client as a stdio server with
# command "docker", args ["run", "-i", "--rm", "-v", "<data_dir>:/data", "pil-mcp"].
FROM python:3.11-slim

WORKDIR /app
COPY bin/ ./bin/
COPY schema.sql ./
COPY LICENSE ./

RUN pip install --no-cache-dir "mcp<2"

# Seed an empty (schema-only) database so the read-only server can start.
RUN mkdir -p /data && python3 -c "import sqlite3; \
    db = sqlite3.connect('/data/pil.sqlite'); \
    db.executescript(open('/app/schema.sql').read()); \
    db.commit(); db.close()" \
 && echo '{"data_dir": "/data"}' > /app/pil.docker.json

ENV PIL_CONFIG=/app/pil.docker.json

ENTRYPOINT ["python3", "/app/bin/mcp_server.py"]
