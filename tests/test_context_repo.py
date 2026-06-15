from pathlib import Path

from kb.core.config import KBConfig
from kb.core.context import AppContext
from kb.data.local_repository import LocalMarkdownRepository
from kb.core.open_targets import FileTarget


def test_context_exposes_repo_and_open_target(tmp_path: Path):
    (tmp_path / "notes").mkdir()
    cfg = KBConfig(vault_path=tmp_path)
    with AppContext.from_config(cfg, with_embedding=False, with_llm=False) as ctx:
        assert isinstance(ctx.repo, LocalMarkdownRepository)
        assert isinstance(ctx.open_target, FileTarget)  # obsidian disabled by default
