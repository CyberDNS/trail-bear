from __future__ import annotations

import os
import sys

from mcp_servers.trails.mcp import mcp


def main() -> None:
    db_url = os.environ.get("TRAILS_DB_URL", "(not set)")
    proxy_vars = {k: v for k, v in os.environ.items() if "proxy" in k.lower()}
    sys.stderr.write(f"[trails-mcp] TRAILS_DB_URL={db_url}\n")
    sys.stderr.write(f"[trails-mcp] proxy env vars: {proxy_vars or 'none'}\n")
    sys.stderr.write(f"[trails-mcp] python={sys.executable} v{sys.version.split()[0]}\n")
    sys.stderr.flush()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
