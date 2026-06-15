"""Local filesystem NoteRepository — Markdown + PDF files under a vault.

Encapsulates the existing storage.py file functions behind the
NoteRepository Protocol. File-specific side effects (dedup, external
source sync) live here as methods, NOT on the Protocol — only the
local backend has these semantics.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from kb.data.models import Note
from kb.data.storage import (
    _compute_hash,
    discover_notes,
    make_slug,
    parse_markdown_file,
    parse_pdf_file,
    validate_vault_path,
    write_markdown_file,
)

_log = logging.getLogger(__name__)


class LocalMarkdownRepository:
    """NoteRepository backed by a local vault directory."""

    def __init__(
        self,
        vault_path: Path,
        notes_dir: str = "notes",
        attachments_dir: str = "attachments",
    ) -> None:
        # Resolve once so discover/read/write agree on an absolute root;
        # parse_markdown_file does file_path.relative_to(vault) and a mixed
        # absolute/relative pair raises ValueError.
        self._vault = vault_path.resolve()
        self._notes_dir = notes_dir
        self._attachments_dir = attachments_dir

    @property
    def supports_write(self) -> bool:
        return True

    def discover(self) -> list[str]:
        self._dedupe()
        paths = discover_notes(self._vault, notes_dir=self._notes_dir)
        return [p.relative_to(self._vault).as_posix() for p in paths]

    def read(self, file_id: str) -> Note:
        full = self.validate(file_id)
        if full is None or not full.is_file():
            raise FileNotFoundError(file_id)
        if full.suffix.lower() == ".pdf":
            return parse_pdf_file(full, self._vault)
        return parse_markdown_file(full, self._vault)

    def write(self, note: Note) -> Note:
        if not note.file_id:
            note = replace(note, file_id=self._allocate_file_id(note))
        full = self.validate(note.file_id)
        if full is None:
            raise ValueError(note.file_id)
        write_markdown_file(full, note)
        return parse_markdown_file(full, self._vault)

    def delete(self, file_id: str) -> None:
        full = self.validate(file_id)
        if full is None or not full.is_file():
            raise FileNotFoundError(file_id)
        full.unlink()

    def hash(self, file_id: str) -> str:
        full = self.validate(file_id)
        if full is None or not full.is_file():
            raise FileNotFoundError(file_id)
        return _compute_hash(full)

    def validate(self, file_id: str) -> Path | None:
        try:
            return validate_vault_path(self._vault, file_id)
        except ValueError:
            return None

    # -- file-specific helpers (not on the Protocol) --

    def _allocate_file_id(self, note: Note) -> str:
        """Pick a notes_dir-relative path for a new note (slug + collision check)."""
        slug, cat = make_slug(note.title, note.category)
        vault_root = self._vault.resolve()
        notes_root = (self._vault / self._notes_dir).resolve()
        if not notes_root.is_relative_to(vault_root):
            raise ValueError(f"notes_dir escapes vault: {self._notes_dir}")

        def resolve_path(suffix: str) -> tuple[str, Path]:
            full = (notes_root / cat / f"{slug}{suffix}.md").resolve()
            if not (full.is_relative_to(vault_root) and full.is_relative_to(notes_root)):
                raise ValueError("allocated path escapes notes dir")
            return full.relative_to(vault_root).as_posix(), full

        file_id, full = resolve_path("")
        counter = 2
        while full.exists():
            file_id, full = resolve_path(f"-{counter}")
            counter += 1
        return file_id

    def _dedupe(self) -> None:
        """Remove files with identical content but different paths."""
        seen: dict[str, Path] = {}
        for p in discover_notes(self._vault, notes_dir=self._notes_dir):
            try:
                h = _compute_hash(p)
            except Exception:
                continue
            if h in seen:
                p.unlink()
                _log.info("Removed duplicate %s (same content as %s)", p, seen[h])
            else:
                seen[h] = p

    def sync_external_sources(
        self,
        external_sources: list[Path],
        source_project: str | None,
    ) -> None:
        """Copy .md files from external dirs into notes_dir (local-only).

        For each external .md file: resolve its category (from frontmatter,
        falling back to the default), collect local image assets, inject
        source_project + merged attachments into the frontmatter, and write
        it under notes_dir/<category>/<name>. Stale copies under a different
        category are removed first.
        """
        from kb.core.markdown_assets import collect_markdown_image_assets
        from kb.data.storage import _merge_external_frontmatter, parse_markdown_file

        vault_root = self._vault.resolve()
        notes_root = (self._vault / self._notes_dir).resolve()
        if not notes_root.is_relative_to(vault_root):
            raise ValueError(f"notes_dir escapes vault: {self._notes_dir}")
        notes_root.mkdir(parents=True, exist_ok=True)

        cat_default = "未分类"
        for src_dir in external_sources:
            if not src_dir.is_dir():
                continue
            for f in sorted(src_dir.rglob("*.md")):
                try:
                    note = parse_markdown_file(f, src_dir)
                    cat = note.category or cat_default
                except Exception:
                    cat = cat_default
                cat = cat.replace("/", "-").replace("\\", "-")
                if cat in {".", ".."}:
                    cat = cat_default
                category_dir = notes_root / cat
                resolved_category_dir = category_dir.resolve()
                if not _is_within(resolved_category_dir, notes_root, vault_root):
                    raise ValueError(f"External source category escapes notes root: {cat}")
                category_dir.mkdir(exist_ok=True)
                dest = category_dir / f.name
                resolved_dest = dest.resolve()
                if not _is_within(resolved_dest, notes_root, vault_root):
                    raise ValueError(f"External source destination escapes notes root: {dest}")
                # Remove stale copies of this file that ended up in a different category.
                for existing in notes_root.rglob(f.name):
                    resolved_existing = existing.resolve()
                    if not _is_within(resolved_existing, notes_root, vault_root):
                        continue
                    if resolved_existing != resolved_dest:
                        existing.unlink()
                src_content = f.read_text(encoding="utf-8")
                collected = collect_markdown_image_assets(
                    src_content,
                    source_file=f,
                    source_root=src_dir,
                    vault=self._vault,
                    attachments_dir=self._attachments_dir,
                )
                for warning in collected.warnings:
                    _log.warning("Image asset warning for %s: %s", f, warning)
                src_content = _merge_external_frontmatter(
                    collected.content,
                    source_project=source_project,
                    attachments=collected.attachments,
                )
                if not dest.exists() or dest.read_text(encoding="utf-8") != src_content:
                    dest.write_text(src_content, encoding="utf-8")


def _is_within(path: Path, *roots: Path) -> bool:
    """True if path is inside every given root."""
    return all(path.is_relative_to(root) for root in roots)
