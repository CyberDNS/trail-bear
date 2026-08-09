"""ASGI entry point: TrailBear REST API + web UI + one MCP endpoint (trails + driving-distance tools)."""

from __future__ import annotations

import contextlib
import logging
import os
import time
import uuid

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.routing import Mount, Route

from mcp_servers.driving_distance.mcp import mcp as driving_mcp
from mcp_servers.trails.mcp import mcp as trails_mcp
from mcp_servers.trails.server import make_app

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("mcp.access")

MCP_PATH = "/mcp"


def _merge_tools(target: FastMCP, *sources: FastMCP) -> None:
    # No public "compose servers" API in the mcp SDK, so we reuse the
    # already-built Tool objects from each source's tool manager directly.
    for source in sources:
        for tool in source._tool_manager.list_tools():
            target._tool_manager._tools[tool.name] = tool


mcp = FastMCP("trailbear", stateless_http=True, json_response=True)
_merge_tools(mcp, trails_mcp, driving_mcp)

# TrailBear sits behind an MCP aggregator/reverse proxy rather than being hit
# directly by browsers, so the Host-header DNS-rebinding check just rejects
# legitimate aggregator traffic without adding real protection here.
mcp.settings.transport_security.enable_dns_rebinding_protection = False
mcp.settings.streamable_http_path = "/"


async def access_log_middleware(request: Request, call_next):
    if request.method == "POST" and request.url.path == MCP_PATH:
        accept = request.headers.get("accept", "")
        if accept.strip() in {"", "*/*"}:
            headers = [(k, v) for (k, v) in request.scope["headers"] if k != b"accept"]
            headers.append((b"accept", b"application/json, text/event-stream"))
            request.scope["headers"] = headers

    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())[:8]
    started = time.monotonic()
    response = await call_next(request)

    duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "%s method=%s path=%s status=%s dur_ms=%s ua=%r accept=%r ctype=%r host=%r",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request.headers.get("user-agent", ""),
        request.headers.get("accept", ""),
        request.headers.get("content-type", ""),
        request.headers.get("host", ""),
    )
    response.headers["x-request-id"] = request_id
    return response


@contextlib.asynccontextmanager
async def lifespan(_: Starlette):
    async with mcp.session_manager.run():
        yield


async def _redirect_to_mcp_slash(request: Request) -> RedirectResponse:
    # Starlette's Mount only matches "/mcp/..." (trailing slash required), so
    # bare "/mcp" (no trailing slash) needs an explicit redirect; 307 keeps
    # the method and body intact for POST requests.
    return RedirectResponse(url=f"{MCP_PATH}/", status_code=307)


app = Starlette(
    routes=[
        Route(MCP_PATH, endpoint=_redirect_to_mcp_slash, methods=["GET", "POST"]),
        Mount(MCP_PATH, app=mcp.streamable_http_app()),
        Mount("/", app=make_app()),
    ],
    lifespan=lifespan,
)
app.add_middleware(BaseHTTPMiddleware, dispatch=access_log_middleware)


def run() -> None:
    import uvicorn

    uvicorn.run(
        "mcp_servers.web.app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        reload=False,
    )


if __name__ == "__main__":
    run()
