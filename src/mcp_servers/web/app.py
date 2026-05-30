"""ASGI entry point exposing one direct MCP endpoint at /."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import logging
import os
import time
import uuid
from urllib.parse import urlencode

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from mcp_servers.driving_distance.mcp import mcp

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("mcp.access")

MCP_PUBLIC_BASE_URL = os.environ.get("MCP_PUBLIC_BASE_URL", "https://mcp.your-domain.example").rstrip("/")
MCP_TRUSTED_HOSTS = os.environ.get("MCP_TRUSTED_HOSTS", "mcp.your-domain.example,localhost,127.0.0.1")
MCP_DISABLE_DNS_REBINDING_PROTECTION = os.environ.get("MCP_DISABLE_DNS_REBINDING_PROTECTION", "0") == "1"
MCP_REQUIRE_BEARER_AUTH = os.environ.get("MCP_REQUIRE_BEARER_AUTH", "1") == "1"

AUTH_CODE_TTL_SECONDS = 300
REFRESH_TOKEN_TTL_SECONDS = 86400
AUTH_CODES: dict[str, dict[str, str | int]] = {}
REFRESH_TOKENS: dict[str, dict[str, str | int]] = {}
ACCESS_TOKENS: dict[str, dict[str, str | int]] = {}


def _configure_transport_security() -> None:
    transport_security = mcp.settings.transport_security
    if MCP_DISABLE_DNS_REBINDING_PROTECTION:
        transport_security.enable_dns_rebinding_protection = False
        return

    trusted_hosts = [h.strip() for h in MCP_TRUSTED_HOSTS.split(",") if h.strip()]
    allowed_hosts: list[str] = []
    for host in trusted_hosts:
        if ":" in host:
            allowed_hosts.append(host)
        else:
            allowed_hosts.append(host)
            allowed_hosts.append(f"{host}:*")

    transport_security.allowed_hosts = allowed_hosts
    transport_security.allowed_origins = [
        f"https://{h}" for h in trusted_hosts if h not in {"localhost", "127.0.0.1"}
    ] + [
        "http://localhost:*",
        "http://127.0.0.1:*",
    ]


_configure_transport_security()
mcp.settings.streamable_http_path = "/"


async def health(_: Request) -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "auth": "none",
            "mcp_url": f"{MCP_PUBLIC_BASE_URL}/",
        }
    )


async def oauth_protected_resource(_: Request) -> JSONResponse:
    return JSONResponse(
        {
            "resource": f"{MCP_PUBLIC_BASE_URL}/",
            "authorization_servers": [MCP_PUBLIC_BASE_URL],
            "bearer_methods_supported": ["header"],
        }
    )


async def oauth_authorization_server(_: Request) -> JSONResponse:
    return JSONResponse(
        {
            "issuer": MCP_PUBLIC_BASE_URL,
            "authorization_endpoint": f"{MCP_PUBLIC_BASE_URL}/authorize",
            "token_endpoint": f"{MCP_PUBLIC_BASE_URL}/token",
            "registration_endpoint": f"{MCP_PUBLIC_BASE_URL}/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["none"],
            "code_challenge_methods_supported": ["S256", "plain"],
        },
        headers={"cache-control": "no-store", "pragma": "no-cache"},
    )


async def openid_configuration(_: Request) -> JSONResponse:
    return await oauth_authorization_server(_)


async def oauth_register(request: Request) -> JSONResponse:
    payload = {}
    with contextlib.suppress(Exception):
        payload = await request.json()

    redirect_uris = payload.get("redirect_uris") if isinstance(payload, dict) else None
    if not isinstance(redirect_uris, list) or not redirect_uris:
        redirect_uris = ["https://claude.ai/api/mcp/auth_callback"]

    client_id = f"anon-{uuid.uuid4().hex[:16]}"
    return JSONResponse(
        {
            "client_id": client_id,
            "client_id_issued_at": int(time.time()),
            "client_secret_expires_at": 0,
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
        status_code=201,
        headers={"cache-control": "no-store", "pragma": "no-cache"},
    )


def _oauth_error(error: str, description: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        {"error": error, "error_description": description},
        status_code=status_code,
        headers={"cache-control": "no-store", "pragma": "no-cache"},
    )


def _pkce_s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _mcp_auth_challenge(error: str = "missing_token") -> Response:
    metadata_url = f"{MCP_PUBLIC_BASE_URL}/.well-known/oauth-protected-resource"
    challenge = (
        f'Bearer realm="{MCP_PUBLIC_BASE_URL}/", '
        f'resource_metadata="{metadata_url}", '
        f'error="{error}"'
    )
    return JSONResponse(
        {"error": error, "error_description": "Authentication required"},
        status_code=401,
        headers={"WWW-Authenticate": challenge},
    )


async def oauth_authorize(request: Request) -> Response:
    qp = request.query_params
    redirect_uri = qp.get("redirect_uri")
    state = qp.get("state")
    client_id = qp.get("client_id") or ""
    code_challenge = qp.get("code_challenge") or ""
    code_challenge_method = (qp.get("code_challenge_method") or "plain").upper()
    scope = qp.get("scope") or "mcp:read mcp:write"
    resource = qp.get("resource") or f"{MCP_PUBLIC_BASE_URL}/"
    if not redirect_uri:
        return _oauth_error("invalid_request", "missing redirect_uri")
    if code_challenge_method not in {"S256", "PLAIN"}:
        return _oauth_error("invalid_request", "unsupported code_challenge_method")

    code_seed = f"{uuid.uuid4().hex}:{time.time()}"
    code = hashlib.sha256(code_seed.encode("utf-8")).hexdigest()[:32]
    AUTH_CODES[code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "scope": scope,
        "resource": resource,
        "expires_at": int(time.time()) + AUTH_CODE_TTL_SECONDS,
    }

    params = {"code": code}
    if state:
        params["state"] = state
    location = f"{redirect_uri}?{urlencode(params)}"
    return Response(status_code=302, headers={"location": location})


async def oauth_token(request: Request) -> JSONResponse:
    form = await request.form()
    grant_type = str(form.get("grant_type") or "")

    if grant_type == "authorization_code":
        code = str(form.get("code") or "")
        client_id = str(form.get("client_id") or "")
        redirect_uri = str(form.get("redirect_uri") or "")
        code_verifier = str(form.get("code_verifier") or "")

        payload = AUTH_CODES.pop(code, None)
        if not payload:
            return _oauth_error("invalid_grant", "unknown or already-used authorization code")
        if int(payload["expires_at"]) < int(time.time()):
            return _oauth_error("invalid_grant", "authorization code expired")

        if payload["client_id"] and payload["client_id"] != client_id:
            return _oauth_error("invalid_grant", "client_id mismatch")
        if payload["redirect_uri"] != redirect_uri:
            return _oauth_error("invalid_grant", "redirect_uri mismatch")

        expected_challenge = str(payload["code_challenge"])
        challenge_method = str(payload["code_challenge_method"])
        if expected_challenge:
            if not code_verifier:
                return _oauth_error("invalid_request", "missing code_verifier")
            computed = _pkce_s256(code_verifier) if challenge_method == "S256" else code_verifier
            if computed != expected_challenge:
                return _oauth_error("invalid_grant", "pkce verification failed")

        access_token = f"tok_{uuid.uuid4().hex}"
        refresh_token = f"rtok_{uuid.uuid4().hex}"
        REFRESH_TOKENS[refresh_token] = {
            "client_id": client_id,
            "scope": str(payload["scope"]),
            "resource": str(payload["resource"]),
            "expires_at": int(time.time()) + REFRESH_TOKEN_TTL_SECONDS,
        }
        ACCESS_TOKENS[access_token] = {
            "client_id": client_id,
            "scope": str(payload["scope"]),
            "resource": str(payload["resource"]),
            "expires_at": int(time.time()) + 3600,
        }
        return JSONResponse(
            {
                "access_token": access_token,
                "token_type": "bearer",
                "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
                "expires_in": 3600,
                "refresh_token": refresh_token,
                "refresh_token_expires_in": REFRESH_TOKEN_TTL_SECONDS,
                "scope": str(payload["scope"]),
            },
            headers={"cache-control": "no-store", "pragma": "no-cache"},
        )

    if grant_type == "refresh_token":
        refresh_token = str(form.get("refresh_token") or "")
        payload = REFRESH_TOKENS.get(refresh_token)
        if not payload or int(payload["expires_at"]) < int(time.time()):
            return _oauth_error("invalid_grant", "invalid refresh_token")

        access_token = f"tok_{uuid.uuid4().hex}"
        ACCESS_TOKENS[access_token] = {
            "client_id": str(payload["client_id"]),
            "scope": str(payload["scope"]),
            "resource": str(payload["resource"]),
            "expires_at": int(time.time()) + 3600,
        }
        return JSONResponse(
            {
                "access_token": access_token,
                "token_type": "bearer",
                "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
                "expires_in": 3600,
                "scope": str(payload["scope"]),
            },
            headers={"cache-control": "no-store", "pragma": "no-cache"},
        )

    if grant_type:
        return _oauth_error("unsupported_grant_type", f"unsupported grant_type: {grant_type}")

    access_token = f"tok_{uuid.uuid4().hex}"
    ACCESS_TOKENS[access_token] = {
        "client_id": "",
        "scope": "mcp:read mcp:write",
        "resource": f"{MCP_PUBLIC_BASE_URL}/",
        "expires_at": int(time.time()) + 3600,
    }
    return JSONResponse(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "expires_in": 3600,
            "refresh_token": f"rtok_{uuid.uuid4().hex}",
            "refresh_token_expires_in": REFRESH_TOKEN_TTL_SECONDS,
            "scope": "mcp:read mcp:write",
        },
        headers={"cache-control": "no-store", "pragma": "no-cache"},
    )


async def access_log_middleware(request: Request, call_next):
    if request.method == "POST" and request.url.path in {"/", "/mcp"}:
        if MCP_REQUIRE_BEARER_AUTH:
            authz = request.headers.get("authorization", "")
            if not authz.lower().startswith("bearer "):
                return _mcp_auth_challenge("missing_token")

            token = authz.split(" ", 1)[1].strip()
            token_data = ACCESS_TOKENS.get(token)
            if not token_data or int(token_data["expires_at"]) < int(time.time()):
                return _mcp_auth_challenge("invalid_token")

        accept = request.headers.get("accept", "")
        if accept.strip() in {"", "*/*"}:
            headers = [(k, v) for (k, v) in request.scope["headers"] if k != b"accept"]
            headers.append((b"accept", b"application/json, text/event-stream"))
            request.scope["headers"] = headers

    if request.method == "OPTIONS" and request.url.path == "/":
        response = Response(status_code=204)
        response.headers["allow"] = "GET, POST, DELETE, OPTIONS"
        response.headers["access-control-allow-methods"] = "GET, POST, DELETE, OPTIONS"
        response.headers["access-control-allow-headers"] = "content-type, accept, authorization"
        response.headers["access-control-max-age"] = "600"
        return response

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


app = Starlette(
    routes=[
        Route("/healthz", endpoint=health, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource", endpoint=oauth_protected_resource, methods=["GET"]),
        Route("/.well-known/oauth-authorization-server", endpoint=oauth_authorization_server, methods=["GET"]),
        Route("/.well-known/openid-configuration", endpoint=openid_configuration, methods=["GET"]),
        Route("/register", endpoint=oauth_register, methods=["POST"]),
        Route("/oauth/register", endpoint=oauth_register, methods=["POST"]),
        Route("/authorize", endpoint=oauth_authorize, methods=["GET"]),
        Route("/token", endpoint=oauth_token, methods=["POST"]),
        Route("/oauth/authorize", endpoint=oauth_authorize, methods=["GET"]),
        Route("/oauth/token", endpoint=oauth_token, methods=["POST"]),
        Mount("/mcp", app=mcp.streamable_http_app()),
        Mount("/", app=mcp.streamable_http_app()),
    ],
    lifespan=lifespan,
)
app.add_middleware(BaseHTTPMiddleware, dispatch=access_log_middleware)


def run() -> None:
    import uvicorn

    uvicorn.run(
        "mcp_servers.web.app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=True,
    )


if __name__ == "__main__":
    run()
