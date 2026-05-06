"""SQLite-backed chat session and message storage."""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ChatMessage:
    role: str       # "user" | "assistant" | "system"
    content: str
    timestamp: str = ""


@dataclass
class ChatSession:
    session_id: str
    title: str = ""
    created_at: str = ""
    updated_at: str = ""


class ChatHistory:
    """SQLite-backed chat history for multi-turn RAG conversations."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._path))
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
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chat_messages_session
                ON chat_messages(session_id, id);
        """)

    def create_session(self, title: str = "") -> ChatSession:
        """Create a new chat session."""
        now = datetime.now().isoformat(timespec="milliseconds")
        sid = uuid.uuid4().hex[:12]
        conn = self._connect()
        conn.execute(
            "INSERT INTO chat_sessions (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (sid, title, now, now),
        )
        conn.commit()
        return ChatSession(session_id=sid, title=title, created_at=now, updated_at=now)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to a session."""
        now = datetime.now().isoformat(timespec="milliseconds")
        conn = self._connect()
        conn.execute(
            "INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now),
        )
        conn.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        conn.commit()

    def get_messages(self, session_id: str, limit: int = 50) -> list[ChatMessage]:
        """Get messages for a session in chronological order."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT role, content, timestamp FROM chat_messages "
            "WHERE session_id = ? ORDER BY id ASC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [ChatMessage(role=r["role"], content=r["content"], timestamp=r["timestamp"]) for r in rows]

    def list_sessions(self, limit: int = 20) -> list[ChatSession]:
        """List sessions, most recent first."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT session_id, title, created_at, updated_at FROM chat_sessions "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            ChatSession(session_id=r["session_id"], title=r["title"],
                         created_at=r["created_at"], updated_at=r["updated_at"])
            for r in rows
        ]

    def delete_session(self, session_id: str) -> None:
        """Delete a session and its messages (CASCADE)."""
        conn = self._connect()
        conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
        conn.commit()
