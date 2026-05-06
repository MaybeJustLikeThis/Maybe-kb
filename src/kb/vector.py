"""LanceDB-backed vector storage for note embeddings."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import lancedb


@dataclass(frozen=True)
class VectorRecord:
    id: str
    chunk_id: int
    vector: list[float]
    text: str


class VectorStore:
    """LanceDB-backed vector storage for note embeddings.

    Follows Database class pattern from indexer.py:
    - Lazy connection (connect on first operation)
    - Explicit close()
    - Table auto-created on first upsert (schema inferred from data)
    """

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._db: lancedb.DBConnection | None = None
        self._table: lancedb.table.Table | None = None

    def _connect(self) -> None:
        if self._db is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self._path))
        try:
            self._table = self._db.open_table("chunks")
        except Exception:
            self._table = None

    def close(self) -> None:
        self._table = None
        self._db = None

    def upsert_chunks(self, file_id: str, chunks: list[VectorRecord]) -> None:
        self._connect()
        self.delete_note(file_id)
        if not chunks:
            return
        data = [
            {"id": c.id, "chunk_id": c.chunk_id, "vector": c.vector, "text": c.text}
            for c in chunks
        ]
        if self._table is None:
            import pyarrow as pa
            self._table = self._db.create_table("chunks", data=data)
        else:
            self._table.add(data)

    def delete_note(self, file_id: str) -> None:
        self._connect()
        if self._table is not None:
            safe_id = file_id.replace("'", "''")
            self._table.delete(f"id = '{safe_id}'")

    def search(self, query_vector: list[float], limit: int = 20) -> list[VectorRecord]:
        self._connect()
        if self._table is None:
            return []
        try:
            results = (
                self._table
                .search(query_vector, vector_column_name="vector")
                .metric("cosine")
                .limit(limit)
                .to_list()
            )
        except (ValueError, RuntimeError, OSError):
            return []
        return [
            VectorRecord(
                id=r["id"],
                chunk_id=r["chunk_id"],
                vector=r["vector"],
                text=r["text"],
            )
            for r in results
        ]

    def count(self) -> int:
        self._connect()
        if self._table is None:
            return 0
        try:
            return self._table.count_rows()
        except (ValueError, RuntimeError, OSError):
            return 0
