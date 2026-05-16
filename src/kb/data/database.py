"""SQLite database with FTS5 full-text search."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import jieba

from kb.core.models import Note

# Suppress jieba startup logs
jieba.setLogLevel(20)


def _tokenize(text: str) -> str:
    """Segment Chinese text with jieba, joining with spaces."""
    if not text:
        return ""
    return " ".join(jieba.cut(text))


def _sanitize_fts5_query(query: str) -> str:
    """Remove FTS5 special characters to prevent query injection."""
    return query.replace('*', '').replace('"', '').replace('(', '').replace(')', '').replace('?', '')


class Database:
    """SQLite database with FTS5 for note metadata and full-text search."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def initialize(self) -> None:
        """Create tables if they don't exist."""
        conn = self._connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                content TEXT,
                tags TEXT,
                category TEXT,
                created_at TEXT,
                updated_at TEXT,
                status TEXT DEFAULT 'published',
                file_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS note_tags (
                note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
                tag TEXT,
                PRIMARY KEY (note_id, tag)
            );

            CREATE INDEX IF NOT EXISTS idx_note_tags_tag ON note_tags(tag);

            CREATE TABLE IF NOT EXISTS note_attachments (
                note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
                attachment_path TEXT,
                PRIMARY KEY (note_id, attachment_path)
            );
        """)

        try:
            conn.execute("""
                CREATE VIRTUAL TABLE notes_fts USING fts5(
                    note_id,
                    title,
                    content,
                    tags,
                    tokenize='unicode61'
                )
            """)
        except sqlite3.OperationalError:
            pass  # already exists

        # Migration: add new columns for multi-source support
        new_columns = {
            "entry_type": "TEXT",
            "source_project": "TEXT",
            "source_path": "TEXT",
            "source_context": "TEXT",
            "content_type": "TEXT DEFAULT 'markdown'",
        }
        existing_cols = {
            row[1] for row in
            conn.execute("PRAGMA table_info(notes)").fetchall()
        }
        for col_name, col_def in new_columns.items():
            if col_name not in existing_cols:
                conn.execute(
                    f"ALTER TABLE notes ADD COLUMN {col_name} {col_def}"
                )

        conn.commit()

    def upsert_note(self, note: Note) -> None:
        """Insert or update a note and its tags."""
        conn = self._connect()

        conn.execute(
            """
            INSERT INTO notes (id, title, description, content, tags,
                               category, created_at, updated_at, status, file_hash,
                               entry_type, source_project, source_path, source_context, content_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                description=excluded.description,
                content=excluded.content,
                tags=excluded.tags,
                category=excluded.category,
                created_at=excluded.created_at,
                updated_at=excluded.updated_at,
                status=excluded.status,
                file_hash=excluded.file_hash,
                entry_type=excluded.entry_type,
                source_project=excluded.source_project,
                source_path=excluded.source_path,
                source_context=excluded.source_context,
                content_type=excluded.content_type
            """,
            (
                note.file_id,
                note.title,
                note.description,
                note.content,
                note.tags_text,
                note.category,
                note.created_at,
                note.updated_at,
                note.status,
                note.file_hash,
                note.entry_type,
                note.source_project,
                note.source_path,
                note.source_context,
                note.content_type,
            ),
        )

        # Sync tags
        conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note.file_id,))
        for tag in note.tags:
            conn.execute(
                "INSERT INTO note_tags (note_id, tag) VALUES (?, ?)",
                (note.file_id, tag),
            )

        # Sync attachments
        conn.execute("DELETE FROM note_attachments WHERE note_id = ?", (note.file_id,))
        for att in note.attachments:
            conn.execute(
                "INSERT INTO note_attachments (note_id, attachment_path) VALUES (?, ?)",
                (note.file_id, att),
            )

        # Update FTS5 index
        conn.execute(
            "DELETE FROM notes_fts WHERE note_id = ?",
            (note.file_id,),
        )
        conn.execute(
            "INSERT INTO notes_fts (note_id, title, content, tags) VALUES (?, ?, ?, ?)",
            (
                note.file_id,
                _tokenize(note.title),
                _tokenize(note.content),
                _tokenize(note.tags_text),
            ),
        )

        conn.commit()

    def get_note(self, file_id: str) -> sqlite3.Row | None:
        """Get note metadata by file_id."""
        conn = self._connect()
        return conn.execute("SELECT * FROM notes WHERE id = ?", (file_id,)).fetchone()

    def get_tags(self, file_id: str) -> list[str]:
        """Get tags for a note."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT tag FROM note_tags WHERE note_id = ?", (file_id,)
        ).fetchall()
        return [r["tag"] for r in rows]

    def list_notes(
        self,
        category: str | None = None,
        tag: str | None = None,
        source_project: str | None = None,
        status: str = "published",
        limit: int = 100,
        sort: str | None = None,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        """List notes with optional filters."""
        conn = self._connect()
        query = "SELECT n.* FROM notes n"
        conditions = ["n.status = ?"]
        params: list[Any] = [status]

        if tag:
            query += " JOIN note_tags t ON n.id = t.note_id"
            conditions.append("t.tag = ?")
            params.append(tag)

        if category:
            conditions.append("n.category = ?")
            params.append(category)

        if source_project:
            conditions.append("n.source_project = ?")
            params.append(source_project)

        query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY n.updated_at DESC, n.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        return conn.execute(query, params).fetchall()

    def count_notes(
        self,
        category: str | None = None,
        tag: str | None = None,
        source_project: str | None = None,
        status: str = "published",
    ) -> int:
        """Count notes with the same filters as list_notes."""
        conn = self._connect()
        query = "SELECT COUNT(DISTINCT n.id) as cnt FROM notes n"
        conditions = ["n.status = ?"]
        params: list[Any] = [status]

        if tag:
            query += " JOIN note_tags t ON n.id = t.note_id"
            conditions.append("t.tag = ?")
            params.append(tag)

        if category:
            conditions.append("n.category = ?")
            params.append(category)

        if source_project:
            conditions.append("n.source_project = ?")
            params.append(source_project)

        query += " WHERE " + " AND ".join(conditions)
        row = conn.execute(query, params).fetchone()
        return int(row["cnt"])

    def search_fulltext(self, query: str, limit: int = 20) -> list[sqlite3.Row]:
        """Full-text search using FTS5."""
        conn = self._connect()
        tokenized = _tokenize(_sanitize_fts5_query(query))
        return conn.execute(
            """
            SELECT n.* FROM notes_fts fts
            JOIN notes n ON n.id = fts.note_id
            WHERE notes_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (tokenized, limit),
        ).fetchall()

    def delete_note(self, file_id: str) -> None:
        """Delete a note and its related data."""
        conn = self._connect()
        conn.execute(
            "DELETE FROM notes_fts WHERE note_id = ?",
            (file_id,),
        )
        conn.execute("DELETE FROM note_tags WHERE note_id = ?", (file_id,))
        conn.execute("DELETE FROM note_attachments WHERE note_id = ?", (file_id,))
        conn.execute("DELETE FROM notes WHERE id = ?", (file_id,))
        conn.commit()

    def get_all_hashes(self) -> dict[str, str]:
        """Return {file_id: file_hash} for all notes."""
        conn = self._connect()
        rows = conn.execute("SELECT id, file_hash FROM notes").fetchall()
        return {r["id"]: r["file_hash"] for r in rows if r["file_hash"]}

    def list_all_tags(self) -> list[str]:
        """Return all unique tags sorted alphabetically."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT DISTINCT tag FROM note_tags ORDER BY tag"
        ).fetchall()
        return [r["tag"] for r in rows]

    def list_all_categories(self) -> list[str]:
        """Return all unique non-empty categories sorted alphabetically."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT DISTINCT category FROM notes "
            "WHERE category IS NOT NULL AND category != '' ORDER BY category"
        ).fetchall()
        return [r["category"] for r in rows]

    def count_notes_by_category(self, category: str) -> int:
        """Return the number of notes in a category."""
        conn = self._connect()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM notes WHERE category = ? AND status = 'published'",
            (category,),
        ).fetchone()
        return row["cnt"]

    def count_notes_by_entry_type(self) -> list[dict]:
        """Return [{entry_type, count}] for all published notes."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT entry_type, COUNT(*) as cnt FROM notes "
            "WHERE status = 'published' AND entry_type IS NOT NULL "
            "GROUP BY entry_type ORDER BY cnt DESC"
        ).fetchall()
        return [{"entry_type": r["entry_type"], "count": r["cnt"]} for r in rows]

    def list_source_projects(self) -> list[dict]:
        """Return [{source_project, count}] for all published notes."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT source_project, COUNT(*) as cnt FROM notes "
            "WHERE status = 'published' AND source_project IS NOT NULL "
            "GROUP BY source_project ORDER BY cnt DESC"
        ).fetchall()
        return [{"source_project": r["source_project"], "count": r["cnt"]} for r in rows]

    def count_notes_by_content_type(self) -> list[dict]:
        """Return [{content_type, count}] for all published notes."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT content_type, COUNT(*) as cnt FROM notes "
            "WHERE status = 'published' "
            "GROUP BY content_type ORDER BY cnt DESC"
        ).fetchall()
        return [{"content_type": r["content_type"], "count": r["cnt"]} for r in rows]
