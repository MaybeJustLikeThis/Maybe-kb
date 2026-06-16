"""Shared in-memory test doubles for the NoteRepository contract.

Imported by any core-layer test that wants to exercise logic against the
NoteRepository Protocol without touching the filesystem.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace

from kb.data.embedding import EmbeddingProvider, EmbeddingResult
from kb.data.llm import LLMProvider, LLMResponse
from kb.data.models import Note
from kb.data.vector import VectorRecord


class FakeRepository:
    """In-memory NoteRepository — lets core-layer tests run without a filesystem."""

    def __init__(self) -> None:
        self._notes: dict[str, Note] = {}

    @property
    def supports_write(self) -> bool:
        return True

    def discover(self) -> list[str]:
        return sorted(self._notes)

    def read(self, file_id: str) -> Note:
        if file_id not in self._notes:
            raise FileNotFoundError(file_id)
        return self._notes[file_id]

    def write(self, note: Note) -> Note:
        file_id = note.file_id or f"notes/{note.title.strip() or 'untitled'}.md"
        digest = hashlib.sha256(note.content.encode("utf-8")).hexdigest()
        committed = replace(note, file_id=file_id, file_hash=digest)
        self._notes[file_id] = committed
        return committed

    def delete(self, file_id: str) -> None:
        if file_id not in self._notes:
            raise FileNotFoundError(file_id)
        del self._notes[file_id]

    def hash(self, file_id: str) -> str:
        return self.read(file_id).file_hash or ""

    def validate(self, file_id: str) -> None:
        return None


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding — vector derived from text length, fixed dim."""

    def __init__(self, dimension: int = 8) -> None:
        self._dim = dimension

    def embed(self, text: str) -> EmbeddingResult:
        vec = [float(len(text))] + [1.0] * (self._dim - 1)
        return EmbeddingResult(vector=vec[: self._dim], dimension=self._dim, tokens_used=len(text))

    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        return [self.embed(t) for t in texts]

    @property
    def dimension(self) -> int:
        return self._dim


class FakeLLM(LLMProvider):
    """Configurable LLM stub: fixed response, optional failure, call recording.

    response_text: returned by generate() and (by default) each stream chunk.
    stream_chunks: if given, generate_stream yields these as separate chunks.
    raises: exception instance or class; generate/generate_stream raise it.
    """

    def __init__(
        self,
        *,
        response_text: str = "fake-llm-response",
        stream_chunks: list[str] | None = None,
        raises: BaseException | type[BaseException] | None = None,
        model: str = "fake-llm",
    ) -> None:
        self._response_text = response_text
        self._stream_chunks = stream_chunks
        self._raises = raises
        self._model = model
        self.recorded_prompts: list[str] = []

    def _maybe_raise(self) -> None:
        if self._raises is not None:
            raise self._raises if isinstance(self._raises, BaseException) else self._raises()

    def generate(self, prompt: str, *, system_prompt: str = "") -> LLMResponse:
        self.recorded_prompts.append(prompt)
        self._maybe_raise()
        return LLMResponse(text=self._response_text, tokens_used=0, model=self._model)

    def generate_stream(self, prompt: str, *, system_prompt: str = ""):
        self.recorded_prompts.append(prompt)
        self._maybe_raise()
        chunks = self._stream_chunks if self._stream_chunks is not None else [self._response_text]
        for c in chunks:
            yield LLMResponse(text=c, tokens_used=0, model=self._model)

    @property
    def model_name(self) -> str:
        return self._model


class FakeVectorStore:
    """In-memory VectorStore — records writes, serves reads. No LanceDB.

    Implements the full surface used across tests: write side
    (upsert_chunks/delete_note) and read side (search/get_chunks_by_file_id).
    """

    def __init__(self, path=None) -> None:
        self.records: dict[str, list[VectorRecord]] = {}
        self.deleted: list[str] = []
        self.closed = False

    def upsert_chunks(self, file_id: str, chunks: list[VectorRecord]) -> None:
        self.records[file_id] = list(chunks)

    def delete_note(self, file_id: str) -> None:
        self.deleted.append(file_id)
        self.records.pop(file_id, None)

    def search(self, query_vector: list[float], limit: int = 20) -> list[VectorRecord]:
        all_recs = [r for recs in self.records.values() for r in recs]
        return all_recs[:limit]

    def get_chunks_by_file_id(self, file_id: str) -> list[VectorRecord]:
        return list(self.records.get(file_id, []))

    def count(self) -> int:
        return sum(len(r) for r in self.records.values())

    def close(self) -> None:
        self.closed = True
