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

    # --- endpoints will be registered in Task 2 ---

    return app
