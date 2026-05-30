# mcp-servers

Collection of MCP servers with a modern `src/` Python package layout and `uv` project metadata.

## Repository layout

```text
.
├── pyproject.toml
├── src/
│   └── mcp_servers/
│       ├── driving_distance/
│       │   └── mcp.py
│       ├── trails/
│       │   ├── mcp.py
│       │   └── repository.py
│       ├── web/
│       │   └── app.py
│       └── runners/
│           ├── stdio_driving.py
│           └── stdio_trails.py
├── smoke_test.sh
├── Dockerfile
└── assets/
```

## Install (uv)

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

## Run servers

HTTP MCP server (driving distance):

```bash
mcp-http
```

Driving distance stdio server:

```bash
mcp-driving-stdio
```

Trails stdio server:

```bash
mcp-trails-stdio
```

## Driving distance MCP tools

- `get_driving_info`
- `compare_routes`

The MCP Streamable HTTP endpoint is served directly at `/`.

## Trails MCP tools

- `import_trails_from_asset`
- `list_trails`
- `get_trail`
- `add_trail`
- `edit_trail`
- `add_execution`
- `edit_execution`
- `delete_execution`
- `add_impression`
- `edit_impression`
- `delete_impression`
- `list_executions`
- `list_impressions`
- `set_trail_garmin_course` (Garmin URL only)

`add_impression` requires an existing `execution_id`.
Use `add_execution` first when needed.

Default DB URL:

- `sqlite:////Users/david/repos/mcp-servers/data/trails.db` (repo-local)

Override with env var:

```bash
TRAILS_DB_URL=sqlite:///absolute/path/to/trails.db
```

## Smoke test

```bash
chmod +x smoke_test.sh
./smoke_test.sh http://127.0.0.1:8000
```

## Docker

```bash
docker build -t mcp-servers .
docker run --rm -p 8000:8000 mcp-servers
```

Container command uses `mcp-http`.

## Claude Custom Connector URL

Use exactly:

`https://mcp.your-domain.example/`
