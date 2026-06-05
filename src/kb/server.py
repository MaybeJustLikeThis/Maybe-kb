"""FastAPI server for kb Web UI."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from kb.api.v1 import create_v1_router
from kb.core.config import KBConfig
from kb.core.context import AppContext
from kb.routes import create_api_router


def _resolve_static_path(static_dir: Path, full_path: str) -> Path:
    """Resolve a static file path, blocking path traversal outside static_dir."""
    resolved = (static_dir / full_path).resolve()
    static_resolved = static_dir.resolve()
    try:
        resolved.relative_to(static_resolved)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal blocked")
    return resolved


def create_app(kb_config: KBConfig) -> FastAPI:
    """Create the FastAPI application with all endpoints."""
    ctx = AppContext.from_config(
        kb_config,
        with_embedding=False,
        with_llm=False,
        allow_lazy_embedding=True,
        allow_lazy_llm=True,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        ctx.close()

    app = FastAPI(title="kb", version="0.1.0", lifespan=lifespan)

    router = create_api_router(ctx)
    app.include_router(router, prefix="/api")
    v1_router = create_v1_router(ctx)
    app.include_router(v1_router, prefix="/api/v1")

    # Serve vault files (notes, attachments) for image/asset resolution
    vault_path = kb_config.vault_path
    app.mount("/vault", StaticFiles(directory=str(vault_path)), name="vault")

    # Serve frontend static files (production mode — built files in web/dist/)
    static_dir = Path(__file__).parent.parent.parent / "web" / "dist"
    if static_dir.exists() and (static_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            """Serve frontend SPA — fallback to index.html for client-side routing."""
            if full_path.startswith("api") or full_path.startswith("vault"):
                raise HTTPException(status_code=404)
            file_path = _resolve_static_path(static_dir, full_path)
            if file_path.is_file():
                return FileResponse(file_path)
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            return PlainTextResponse(
                "Frontend not built. Run: cd web && npm run build",
                status_code=404,
            )

    return app
