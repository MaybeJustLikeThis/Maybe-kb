"""First-run setup planning and application."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kb.core.config import _validate_vault_subpath, load_config
from kb.core.config_writer import render_toml_sections, write_toml_text
from kb.core.context import AppContext
from kb.core.indexer import index_files

SetupMode = Literal["obsidian", "markdown", "new"]


class SetupError(ValueError):
    """Raised when a setup request cannot be safely planned or applied."""


@dataclass(frozen=True)
class SetupRequest:
    project_path: Path
    mode: SetupMode
    source_path: Path
    build_index: bool = True


@dataclass(frozen=True)
class SetupPlan:
    project_path: Path
    mode: SetupMode
    vault_path: Path
    notes_dir: str
    attachments_dir: str
    index_dir: str
    config_updates: dict[str, dict[str, str | bool]]
    directories_to_create: tuple[Path, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SetupResult:
    plan: SetupPlan
    indexed_notes: int | None
    indexed_vectors: int | None


def _resolve(path: Path) -> Path:
    return path.expanduser().resolve()


def _require_existing_dir(path: Path) -> Path:
    resolved = _resolve(path)
    if not resolved.is_dir():
        raise SetupError(f"Source directory not found: {resolved}")
    return resolved


def _reject_file_target(path: Path) -> Path:
    resolved = _resolve(path)
    if resolved.exists() and not resolved.is_dir():
        raise SetupError(f"Setup target is not a directory: {resolved}")
    return resolved


def _common_updates(
    *,
    vault: Path,
    notes_dir: str,
    attachments_dir: str,
    index_dir: str,
    obsidian_enabled: bool,
    obsidian_vault_name: str = "",
    obsidian_vault_path: str = "",
) -> dict[str, dict[str, str | bool]]:
    _validate_vault_subpath("general.notes_dir", notes_dir)
    _validate_vault_subpath("general.attachments_dir", attachments_dir)
    _validate_vault_subpath("general.index_dir", index_dir)
    return {
        "general": {
            "vault_path": vault.as_posix(),
            "notes_dir": notes_dir,
            "attachments_dir": attachments_dir,
            "index_dir": index_dir,
        },
        "obsidian": {
            "enabled": obsidian_enabled,
            "vault_name": obsidian_vault_name,
            "vault_path": obsidian_vault_path,
            "open_uri_strategy": "file",
        },
    }


def _warnings_for_existing_source(vault: Path, *, mode: SetupMode) -> tuple[str, ...]:
    warnings: list[str] = []
    has_notes = any(vault.rglob("*.md")) or any(vault.rglob("*.pdf"))
    if not has_notes:
        warnings.append("No Markdown or PDF files were found in the selected folder.")
    if mode == "obsidian" and not vault.joinpath(".obsidian").is_dir():
        warnings.append("No .obsidian directory was found; this folder will still be indexed.")
    return tuple(warnings)


def build_setup_plan(request: SetupRequest) -> SetupPlan:
    project_path = _resolve(request.project_path)
    source_path = request.source_path
    attachments_dir = "attachments"
    index_dir = ".kb"

    if request.mode == "obsidian":
        vault = _require_existing_dir(source_path)
        notes_dir = "."
        directories = (
            vault / attachments_dir,
            vault / index_dir,
        )
        updates = _common_updates(
            vault=vault,
            notes_dir=notes_dir,
            attachments_dir=attachments_dir,
            index_dir=index_dir,
            obsidian_enabled=True,
            obsidian_vault_name=vault.name,
            obsidian_vault_path=vault.as_posix(),
        )
        warnings = _warnings_for_existing_source(vault, mode=request.mode)
    elif request.mode == "markdown":
        vault = _require_existing_dir(source_path)
        notes_dir = "."
        directories = (
            vault / attachments_dir,
            vault / index_dir,
        )
        updates = _common_updates(
            vault=vault,
            notes_dir=notes_dir,
            attachments_dir=attachments_dir,
            index_dir=index_dir,
            obsidian_enabled=False,
        )
        warnings = _warnings_for_existing_source(vault, mode=request.mode)
    elif request.mode == "new":
        vault = _reject_file_target(source_path)
        notes_dir = "notes"
        directories = (
            vault,
            vault / notes_dir,
            vault / attachments_dir,
            vault / index_dir,
        )
        updates = _common_updates(
            vault=vault,
            notes_dir=notes_dir,
            attachments_dir=attachments_dir,
            index_dir=index_dir,
            obsidian_enabled=False,
        )
        warnings = ()
    else:
        raise SetupError(f"Unknown setup mode: {request.mode}")

    config_path = project_path / "config.toml"
    render_toml_sections(config_path, updates)
    return SetupPlan(
        project_path=project_path,
        mode=request.mode,
        vault_path=vault,
        notes_dir=notes_dir,
        attachments_dir=attachments_dir,
        index_dir=index_dir,
        config_updates=updates,
        directories_to_create=tuple(path.resolve() for path in directories),
        warnings=warnings,
    )


def apply_setup_plan(plan: SetupPlan, *, build_index: bool) -> SetupResult:
    config_path = plan.project_path / "config.toml"
    rendered = render_toml_sections(config_path, plan.config_updates)
    for directory in plan.directories_to_create:
        directory.mkdir(parents=True, exist_ok=True)
    write_toml_text(config_path, rendered)

    indexed_notes: int | None = None
    indexed_vectors: int | None = None
    if build_index:
        config = load_config(plan.project_path)
        ctx = AppContext.from_config(config, with_embedding=True, with_llm=False)
        try:
            indexed_notes, indexed_vectors = index_files(
                ctx.repo,
                ctx.db,
                full=True,
                embedding_provider=ctx.embedding,
                vault=ctx.vault,
                index_dir=ctx.index_dir,
            )
        finally:
            ctx.close()

    return SetupResult(
        plan=plan,
        indexed_notes=indexed_notes,
        indexed_vectors=indexed_vectors,
    )
