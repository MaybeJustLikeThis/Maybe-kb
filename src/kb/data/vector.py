"""LanceDB-backed vector storage for note embeddings."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import lancedb


@dataclass(frozen=True)
class VectorRecord:
    id: str
    chunk_id: int
    vector: list[float]
    text: str
    section_path: list[str] = field(default_factory=list)
    content_type: str = "paragraph"


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
        except ValueError:
            self._table = None

    def close(self) -> None:
        self._table = None
        self._db = None

    def upsert_chunks(self, file_id: str, chunks: list[VectorRecord]) -> None:
        self._connect()
        self.delete_note(file_id)
        if not chunks:
            return
        import json as _json
        data = [
            {
                "id": c.id,
                "chunk_id": c.chunk_id,
                "vector": c.vector,
                "text": c.text,
                "section_path": _json.dumps(c.section_path, ensure_ascii=False),
                "content_type": c.content_type,
            }
            for c in chunks
        ]
        if self._table is None:
            import pyarrow as pa
            self._table = self._db.create_table("chunks", data=data)
        else:
            self._table.add(data)

    def delete_note(self, file_id: str) -> None:
        """Delete all chunks for a note. Rejects file_id with single quotes."""
        self._connect()
        if self._table is not None:
            if "'" in file_id:
                raise ValueError(f"file_id contains invalid character: {file_id!r}")
            self._table.delete(f"id = '{file_id}'")

    def search(self, query_vector: list[float], limit: int = 20) -> list[VectorRecord]:
        self._connect()
        if self._table is None:
            return []
        results = (
            self._table
            .search(query_vector, vector_column_name="vector")
            .metric("cosine")
            .limit(limit)
            .to_list()
        )
        import json as _json
        records: list[VectorRecord] = []
        for r in results:
            sp = r.get("section_path")
            if isinstance(sp, str):
                try:
                    sp = _json.loads(sp)
                except (ValueError, TypeError):
                    sp = []
            elif not isinstance(sp, list):
                sp = []
            records.append(VectorRecord(
                id=r["id"],
                chunk_id=r["chunk_id"],
                vector=r["vector"],
                text=r["text"],
                section_path=sp,
                content_type=r.get("content_type", "paragraph"),
            ))
        return records

    def count(self) -> int:
        self._connect()
        if self._table is None:
            return 0
        return self._table.count_rows()

    def get_chunks_by_file_id(self, file_id: str) -> list[VectorRecord]:
        """Return all chunks for a given file_id."""
        self._connect()
        if self._table is None:
            return []
        import json as _json
        if "'" in file_id:
            raise ValueError(f"file_id contains invalid character: {file_id!r}")
        try:
            rows = self._table.search().where(f"id = '{file_id}'").to_list()
        except Exception:
            return []
        records: list[VectorRecord] = []
        for r in rows:
            sp = r.get("section_path")
            if isinstance(sp, str):
                try:
                    sp = _json.loads(sp)
                except (ValueError, TypeError):
                    sp = []
            elif not isinstance(sp, list):
                sp = []
            records.append(VectorRecord(
                id=r["id"],
                chunk_id=r["chunk_id"],
                vector=r.get("vector", []),
                text=r.get("text", ""),
                section_path=sp,
                content_type=r.get("content_type", "paragraph"),
            ))
        return records
