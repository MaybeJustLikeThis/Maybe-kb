"""Tests for LanceDB vector store."""
import pytest
from pathlib import Path
from kb.data.vector import VectorStore, VectorRecord


def test_vector_store_creates_table_on_first_upsert(tmp_path: Path):
    store = VectorStore(tmp_path / "vectors.lance")
    store._connect()
    assert store._table is None  # no table until first data
    store.upsert_chunks("note.md", [
        VectorRecord(id="note.md", chunk_id=0, vector=[1.0, 0.0], text="hello"),
    ])
    assert store._table is not None
    assert store.count() == 1
    store.close()


def test_upsert_and_search(tmp_path: Path):
    store = VectorStore(tmp_path / "vectors.lance")
    store.upsert_chunks("note-a.md", [
        VectorRecord(id="note-a.md", chunk_id=0, vector=[1.0, 0.0, 0.0], text="about python"),
    ])
    store.upsert_chunks("note-b.md", [
        VectorRecord(id="note-b.md", chunk_id=0, vector=[0.0, 1.0, 0.0], text="about golang"),
    ])
    results = store.search([1.0, 0.0, 0.0], limit=2)
    assert results[0].id == "note-a.md"
    store.close()


def test_upsert_replaces_old_vectors(tmp_path: Path):
    store = VectorStore(tmp_path / "vectors.lance")
    store.upsert_chunks("note.md", [
        VectorRecord(id="note.md", chunk_id=0, vector=[1.0, 0.0], text="old"),
    ])
    store.upsert_chunks("note.md", [
        VectorRecord(id="note.md", chunk_id=0, vector=[0.0, 1.0], text="new"),
    ])
    assert store.count() == 1
    results = store.search([0.0, 1.0], limit=1)
    assert results[0].text == "new"
    store.close()


def test_delete_note_removes_vectors(tmp_path: Path):
    store = VectorStore(tmp_path / "vectors.lance")
    store.upsert_chunks("note.md", [
        VectorRecord(id="note.md", chunk_id=0, vector=[1.0], text="chunk 0"),
        VectorRecord(id="note.md", chunk_id=1, vector=[2.0], text="chunk 1"),
    ])
    assert store.count() == 2
    store.delete_note("note.md")
    assert store.count() == 0
    store.close()


def test_search_empty_store(tmp_path: Path):
    store = VectorStore(tmp_path / "vectors.lance")
    results = store.search([1.0, 0.0], limit=10)
    assert results == []
    store.close()


def test_delete_note_rejects_quote_in_file_id(tmp_path: Path):
    """delete_note raises ValueError when file_id contains single quote."""
    store = VectorStore(tmp_path / "test.lance")
    # Initialize a table so delete_note doesn't return early
    store.upsert_chunks("seed.md", [
        VectorRecord(id="seed.md", chunk_id=0, vector=[1.0], text="seed"),
    ])
    with pytest.raises(ValueError, match="invalid character"):
        store.delete_note("notes/bad'id.md")
