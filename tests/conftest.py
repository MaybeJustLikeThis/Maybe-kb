"""Shared pytest fixtures for the kb test suite.

vault/db/local_repo cover the ~30 setup-boilerplate sites. Core-layer
Protocol tests import FakeRepository directly (decision 2B) — no fake_repo
fixture here.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from kb.data.database import Database
from kb.data.local_repository import LocalMarkdownRepository


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """tmp_path with notes/ and .kb/ pre-created."""
    (tmp_path / "notes").mkdir()
    (tmp_path / ".kb").mkdir()
    return tmp_path


@pytest.fixture
def db(vault: Path) -> Database:
    """Initialized Database at vault/.kb/kb.db (function-scoped)."""
    database = Database(vault / ".kb" / "kb.db")
    database.initialize()
    return database


@pytest.fixture
def local_repo(vault: Path) -> LocalMarkdownRepository:
    """LocalMarkdownRepository over the shared vault fixture."""
    return LocalMarkdownRepository(
        vault, notes_dir="notes", attachments_dir="attachments"
    )


@pytest.fixture(scope="session")
def embedding_provider():
    """Shared LocalEmbeddingProvider — loads the BGE model once per session.

    Cold-loading torch + the model is the dominant CI cost. Sharing one
    instance across the embedding/search/server tests avoids reloading it
    per test. (Tests verifying factory construction still build their own.)
    """
    from kb.data.embedding import LocalEmbeddingProvider
    return LocalEmbeddingProvider("BAAI/bge-small-zh-v1.5")
