"""Tests for local Markdown image asset collection."""
from __future__ import annotations

from pathlib import Path

from kb.core.markdown_assets import collect_markdown_image_assets


def test_collect_relative_image_stores_attachment_and_rewrites_link(tmp_path: Path):
    """A relative Markdown image is copied to attachments and rewritten."""
    vault = tmp_path / "vault"
    source_root = tmp_path / "blog"
    post_dir = source_root / "posts"
    post_dir.mkdir(parents=True)
    image = post_dir / "diagram.png"
    image.write_bytes(b"png-bytes")
    post = post_dir / "post.md"
    post.write_text("![Diagram](./diagram.png)\n", encoding="utf-8")

    result = collect_markdown_image_assets(
        post.read_text(encoding="utf-8"),
        source_file=post,
        source_root=source_root,
        vault=vault,
    )

    assert result.attachments == [result.attachments[0]]
    rel = result.attachments[0]
    assert rel.startswith("attachments/")
    assert rel.endswith(".png")
    assert (vault / rel).read_bytes() == b"png-bytes"
    assert result.content == f"![Diagram]({rel})\n"
    assert result.warnings == []


def test_collect_hexo_bare_image_uses_post_asset_folder(tmp_path: Path):
    """A bare image filename can resolve through the Hexo same-stem asset folder."""
    vault = tmp_path / "vault"
    source_root = tmp_path / "blog"
    post_dir = source_root / "posts"
    asset_dir = post_dir / "my-post"
    asset_dir.mkdir(parents=True)
    (asset_dir / "cover.jpg").write_bytes(b"jpg-bytes")
    post = post_dir / "my-post.md"
    markdown = "![Cover](cover.jpg \"Hero\")\n"

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=source_root,
        vault=vault,
    )

    rel = result.attachments[0]
    assert rel.startswith("attachments/")
    assert rel.endswith(".jpg")
    assert result.content == f"![Cover]({rel} \"Hero\")\n"


def test_collect_existing_attachment_link_is_recorded_but_not_rewritten(tmp_path: Path):
    """Existing vault attachment links stay stable and are returned as attachments."""
    post = tmp_path / "post.md"
    markdown = "![Stored](attachments/2026/06/abc.png)\n"

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=tmp_path,
        vault=tmp_path / "vault",
    )

    assert result.content == markdown
    assert result.attachments == ["attachments/2026/06/abc.png"]
    assert result.warnings == []


def test_collect_ignores_remote_data_and_root_relative_links(tmp_path: Path):
    """Non-local image targets are ignored by this phase."""
    post = tmp_path / "post.md"
    markdown = "\n".join([
        "![Remote](https://example.com/a.png)",
        "![Data](data:image/png;base64,abc)",
        "![Root](/images/a.png)",
        "",
    ])

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=tmp_path,
        vault=tmp_path / "vault",
    )

    assert result.content == markdown
    assert result.attachments == []
    assert result.warnings == []


def test_collect_missing_local_image_keeps_link_and_warns(tmp_path: Path):
    """Missing images do not break sync; they leave the original link in place."""
    post = tmp_path / "post.md"
    markdown = "![Missing](missing.png)\n"

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=tmp_path,
        vault=tmp_path / "vault",
    )

    assert result.content == markdown
    assert result.attachments == []
    assert result.warnings == ["missing image: missing.png"]


def test_collect_blocks_paths_outside_source_root(tmp_path: Path):
    """Image paths resolving outside source_root are left unchanged with a warning."""
    source_root = tmp_path / "blog"
    source_root.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside")
    post = source_root / "post.md"
    markdown = "![Outside](../outside.png)\n"

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=source_root,
        vault=tmp_path / "vault",
    )

    assert result.content == markdown
    assert result.attachments == []
    assert result.warnings == ["blocked image outside source root: ../outside.png"]
