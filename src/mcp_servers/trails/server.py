"""TrailBear HTTP server: REST API + static UI in one process."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import make_api
from .repository import make_repository

# In Docker the image has:  WORKDIR /app  +  COPY ui ./ui  → /app/ui
# In dev (editable install): ui/ sits 3 levels above src/mcp_servers/trails/
_CANDIDATES = [
    Path(os.environ["UI_DIR"]) if "UI_DIR" in os.environ else None,
    Path("/app/ui"),
    Path(__file__).resolve().parents[3] / "ui",
]
_UI_DIR: Path | None = next((p for p in _CANDIDATES if p and p.exists()), None)


def _resolve_db_path() -> str:
    if env := os.environ.get("TRAILS_DB_PATH"):
        return env
    # Docker volume mount
    if Path("/data").exists():
        return "/data/trails.db"
    # Dev fallback: data/ at repo root
    return str(Path(__file__).resolve().parents[3] / "data" / "trails.db")


_DB_URL = f"sqlite:///{_resolve_db_path()}"


def make_app() -> FastAPI:
    repo = make_repository(_DB_URL)
    repo.init_schema()

    app = make_api(repo)

    if _UI_DIR:
        static_dir = _UI_DIR / "static"
        if static_dir.exists():
            app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(str(_UI_DIR / "index.html"))

    @app.get("/healthz", include_in_schema=False)
    def health():
        return {"ok": True, "db": _DB_URL}

    return app


app = make_app()


def run() -> None:
    uvicorn.run(
        "mcp_servers.trails.server:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        reload=False,
    )


if __name__ == "__main__":
    run()
