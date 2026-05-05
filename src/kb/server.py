"""FastAPI server for kb Web UI."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from kb.config import KBConfig
from kb.indexer import Database
from kb.models import Note
from kb.storage import parse_markdown_file, write_markdown_file
from kb.attachments import store_attachment


class NoteResponse(BaseModel):
    file_id: str
    title: str
    description: str | None = None
    content: str = ""
    category: str | None = None
    tags: list[str] = []
    attachments: list[str] = []
    created_at: str | None = None
    updated_at: str | None = None
    status: str = "published"


class NoteCreate(BaseModel):
    title: str
    content: str = ""
    category: str | None = None
    tags: list[str] = []
    description: str | None = None


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    description: str | None = None
    status: str | None = None


def _note_to_response(note: Note) -> NoteResponse:
    """Convert internal Note to API response model."""
    return NoteResponse(
        file_id=note.file_id,
        title=note.title,
        description=note.description,
        content=note.content,
        category=note.category,
        tags=note.tags,
        attachments=note.attachments,
        created_at=note.created_at,
        updated_at=note.updated_at,
        status=note.status,
    )


def create_app(kb_config: KBConfig) -> FastAPI:
    """Create the FastAPI application with all endpoints."""
    app = FastAPI(title="kb", version="0.1.0")

    vault_path = kb_config.vault_path
    db_path = vault_path / ".kb" / "kb.db"

    def get_db() -> Database:
        db = Database(db_path)
        db.initialize()
        return db

    @app.get("/api/notes")
    def list_notes(
        category: str | None = Query(None),
        tag: str | None = Query(None),
        limit: int = Query(50),
    ):
        db = get_db()
        try:
            rows = db.list_notes(category=category, tag=tag, limit=limit)
            result = []
            for row in rows:
                tags = db.get_tags(row["id"])
                result.append({
                    "file_id": row["id"],
                    "title": row["title"],
                    "description": row["description"],
                    "category": row["category"],
                    "tags": tags,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "status": row["status"],
                })
            return result
        finally:
            db.close()

    @app.post("/api/notes")
    def create_note(body: NoteCreate):
        vault = vault_path
        now = datetime.now().isoformat(timespec="seconds")
        slug = body.title.lower().replace(" ", "-")[:50]
        cat = body.category

        file_path = f"notes/{cat}/{slug}.md" if cat else f"notes/{slug}.md"
        full_path = vault / file_path
        counter = 2
        while full_path.exists():
            suffix = f"-{counter}"
            file_path = f"notes/{cat}/{slug}{suffix}.md" if cat else f"notes/{slug}{suffix}.md"
            full_path = vault / file_path
            counter += 1

        note = Note(
            file_id=file_path,
            title=body.title,
            content=body.content,
            category=body.category,
            tags=body.tags,
            description=body.description,
            created_at=now,
            updated_at=now,
        )

        write_markdown_file(full_path, note)
        parsed = parse_markdown_file(full_path, vault)

        db = get_db()
        try:
            db.upsert_note(parsed)
        finally:
            db.close()

        return _note_to_response(parsed)

    @app.get("/api/notes/{file_id:path}")
    def get_note(file_id: str):
        full_path = vault_path / file_id
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Note not found")

        note = parse_markdown_file(full_path, vault_path)
        return _note_to_response(note)

    @app.put("/api/notes/{file_id:path}")
    def update_note(file_id: str, body: NoteUpdate):
        full_path = vault_path / file_id
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Note not found")

        note = parse_markdown_file(full_path, vault_path)
        now = datetime.now().isoformat(timespec="seconds")

        if body.title is not None:
            note.title = body.title
        if body.content is not None:
            note.content = body.content
        if body.category is not None:
            note.category = body.category
        if body.tags is not None:
            note.tags = body.tags
        if body.description is not None:
            note.description = body.description
        if body.status is not None:
            note.status = body.status

        note.updated_at = now
        write_markdown_file(full_path, note)

        db = get_db()
        try:
            db.upsert_note(note)
        finally:
            db.close()

        return _note_to_response(note)

    @app.delete("/api/notes/{file_id:path}")
    def delete_note(file_id: str):
        full_path = vault_path / file_id
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Note not found")

        full_path.unlink()

        db = get_db()
        try:
            db.delete_note(file_id)
        finally:
            db.close()

        return {"ok": True}

    @app.get("/api/search")
    def search_notes(q: str = Query(..., min_length=1), limit: int = Query(20)):
        db = get_db()
        try:
            rows = db.search_fulltext(q, limit=limit)
            result = []
            for row in rows:
                tags = db.get_tags(row["id"])
                result.append({
                    "file_id": row["id"],
                    "title": row["title"],
                    "description": row["description"],
                    "category": row["category"],
                    "tags": tags,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "status": row["status"],
                })
            return result
        finally:
            db.close()

    @app.get("/api/tags")
    def get_tags():
        conn = get_db()._connect()
        rows = conn.execute("SELECT DISTINCT tag FROM note_tags ORDER BY tag").fetchall()
        return {"tags": [r["tag"] for r in rows]}

    @app.get("/api/categories")
    def get_categories():
        conn = get_db()._connect()
        rows = conn.execute(
            "SELECT DISTINCT category FROM notes WHERE category IS NOT NULL AND category != '' ORDER BY category"
        ).fetchall()
        return {"categories": [r["category"] for r in rows]}

    @app.post("/api/attachments")
    async def upload_attachment(file: UploadFile = File(...)):
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        rel_path = store_attachment(tmp_path, vault_path)
        tmp_path.unlink()
        return {"path": rel_path}

    @app.get("/api/index")
    def get_index_status():
        db = get_db()
        try:
            hashes = db.get_all_hashes()
            return {"notes_count": len(hashes)}
        finally:
            db.close()

    @app.post("/api/index")
    def trigger_index():
        from kb.cli import _index_files
        db = get_db()
        try:
            count = _index_files(vault_path, db, full=True)
            return {"indexed": count}
        finally:
            db.close()

    # Serve frontend static files (production mode — built files in web/dist/)
    static_dir = Path(__file__).parent.parent.parent / "web" / "dist"
    if static_dir.exists() and (static_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            """Serve frontend SPA — fallback to index.html for client-side routing."""
            file_path = static_dir / full_path
            if file_path.is_file() and not full_path.startswith("api"):
                from fastapi.responses import FileResponse
                return FileResponse(file_path)
            index_path = static_dir / "index.html"
            if index_path.exists():
                from fastapi.responses import FileResponse
                return FileResponse(index_path)
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(
                "Frontend not built. Run: cd web && npm run build",
                status_code=404,
            )

    return app
