"""Collect local image assets referenced from Markdown content."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from kb.data.attachments import store_attachment


@dataclass(frozen=True)
class CollectedMarkdownAssets:
    """Markdown content plus collected attachment metadata."""

    content: str
    attachments: list[str]
    warnings: list[str]


_IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<body>[^)]*)\)")
_TARGET_RE = re.compile(r"^(?P<target>.+?)(?P<title>\s+\"[^\"]*\")?$")
_IGNORED_PREFIXES = ("http://", "https://", "data:", "/")


def collect_markdown_image_assets(
    markdown: str,
    *,
    source_file: Path,
    source_root: Path,
    vault: Path,
) -> CollectedMarkdownAssets:
    """Store local Markdown images in the vault and rewrite their links."""
    attachments: list[str] = []
    warnings: list[str] = []
    root = source_root.resolve()

    def rewrite(match: re.Match[str]) -> str:
        alt = match.group("alt")
        body = match.group("body")
        parsed = _TARGET_RE.match(body)
        if parsed is None:
            return match.group(0)

        target = parsed.group("target")
        title = parsed.group("title") or ""

        if target.startswith(_IGNORED_PREFIXES):
            return match.group(0)

        if target.startswith("attachments/"):
            _append_unique(attachments, target)
            return match.group(0)

        resolved = _resolve_image(target, source_file, source_root, root)
        if resolved is None:
            warnings.append(f"missing image: {target}")
            return match.group(0)

        if not _is_relative_to(resolved, root):
            warnings.append(f"blocked image outside source root: {target}")
            return match.group(0)

        rel_path = store_attachment(resolved, vault)
        _append_unique(attachments, rel_path)
        return f"![{alt}]({rel_path}{title})"

    content = _IMAGE_RE.sub(rewrite, markdown)
    return CollectedMarkdownAssets(
        content=content,
        attachments=attachments,
        warnings=warnings,
    )


def _resolve_image(
    target: str,
    source_file: Path,
    source_root: Path,
    resolved_root: Path,
) -> Path | None:
    primary = (source_file.parent / target).resolve()
    if not _is_relative_to(primary, resolved_root):
        return primary
    if primary.is_file():
        return primary

    hexo_asset = (source_file.parent / source_file.stem / target).resolve()
    if not _is_relative_to(hexo_asset, source_root.resolve()):
        return hexo_asset
    if hexo_asset.is_file():
        return hexo_asset

    return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _append_unique(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)
