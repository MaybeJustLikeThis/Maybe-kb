"""FastAPI server for kb Web UI."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from kb.config import KBConfig
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
    app = FastAPI(title="kb", version="0.1.0")

    vault_path = kb_config.vault_path
    db_path = vault_path / ".kb" / "kb.db"

    router = create_api_router(vault_path, db_path, kb_config.embedding)
    app.include_router(router, prefix="/api")

    # Serve frontend static files (production mode — built files in web/dist/)
    static_dir = Path(__file__).parent.parent.parent / "web" / "dist"
    if static_dir.exists() and (static_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            """Serve frontend SPA — fallback to index.html for client-side routing."""
            if full_path.startswith("api"):
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
