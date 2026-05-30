from __future__ import annotations

from mcp_servers.driving_distance.mcp import mcp


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
