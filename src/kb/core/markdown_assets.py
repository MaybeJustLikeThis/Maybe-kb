"""Collect local image assets referenced from Markdown content."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from pathlib import Path
import posixpath
import re
from urllib.parse import unquote

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
_FENCE_RE = re.compile(r"^(?P<fence>`{3,}|~{3,})")


def collect_markdown_image_assets(
    markdown: str,
    *,
    source_file: Path,
    source_root: Path,
    vault: Path,
    attachments_dir: str = "attachments",
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

        if _is_ignored_target(target):
            return match.group(0)

        attachment_path = _normalize_attachment_path(
            target,
            attachments_dir=attachments_dir,
        )
        if attachment_path is not None:
            if not attachment_path:
                warnings.append(f"unsafe attachment path: {target}")
                return match.group(0)
            vault_root = vault.resolve()
            attachments_root = (vault / attachments_dir).resolve()
            candidate = (vault / attachment_path).resolve()
            if (
                not attachments_root.is_relative_to(vault_root)
                or not candidate.is_relative_to(vault_root)
                or not candidate.is_relative_to(attachments_root)
            ):
                warnings.append(f"unsafe attachment path: {target}")
                return match.group(0)
            if attachments_dir == ".":
                if not candidate.is_file():
                    attachment_path = None
            else:
                _append_unique(attachments, attachment_path)
                return match.group(0)
            if attachment_path is not None:
                _append_unique(attachments, attachment_path)
                return match.group(0)

        resolved = _resolve_image(unquote(target), source_file, source_root, root)
        if resolved is None:
            warnings.append(f"missing image: {target}")
            return match.group(0)

        if not _is_relative_to(resolved, root):
            warnings.append(f"blocked image outside source root: {target}")
            return match.group(0)

        try:
            rel_path = store_attachment(
                resolved,
                vault,
                attachments_dir=attachments_dir,
            )
        except Exception as exc:
            warnings.append(f"failed to store image {target}: {exc}")
            return match.group(0)
        _append_unique(attachments, rel_path)
        return f"![{alt}]({rel_path}{title})"

    content = _rewrite_images_outside_fences(markdown, rewrite)
    return CollectedMarkdownAssets(
        content=content,
        attachments=attachments,
        warnings=warnings,
    )


def _rewrite_images_outside_fences(
    markdown: str,
    rewrite: Callable[[re.Match[str]], str],
) -> str:
    lines = markdown.splitlines(keepends=True)
    rewritten: list[str] = []
    fence: tuple[str, int] | None = None

    for line in lines:
        stripped = line.lstrip()
        fence_match = _FENCE_RE.match(stripped)

        if fence is None:
            if fence_match is not None:
                fence_marker = fence_match.group("fence")
                fence = (fence_marker[0], len(fence_marker))
                rewritten.append(line)
            else:
                rewritten.append(_IMAGE_RE.sub(rewrite, line))
            continue

        rewritten.append(line)
        if _is_closing_fence(stripped, fence):
            fence = None

    return "".join(rewritten)


def _is_closing_fence(line: str, fence: tuple[str, int]) -> bool:
    fence_char, fence_len = fence
    body = line.rstrip("\r\n")
    marker_match = re.match(rf"^{re.escape(fence_char)}{{{fence_len},}}", body)
    if marker_match is None:
        return False

    return body[marker_match.end():].strip() == ""


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


def _is_ignored_target(target: str) -> bool:
    return target.lower().startswith(_IGNORED_PREFIXES)


def _normalize_attachment_path(
    target: str,
    *,
    attachments_dir: str = "attachments",
) -> str | None:
    decoded = unquote(target).replace("\\", "/")
    namespace = posixpath.normpath(attachments_dir.replace("\\", "/"))
    if namespace != "." and not decoded.startswith(f"{namespace}/"):
        return None

    normalized = posixpath.normpath(decoded)
    if normalized == ".":
        return ""

    normalized = normalized.replace("\\", "/")
    if normalized.startswith("../") or normalized == "..":
        return ""
    if namespace != "." and not normalized.startswith(f"{namespace}/"):
        return ""

    return normalized


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _append_unique(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)
