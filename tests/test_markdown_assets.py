"""Tests for local Markdown image asset collection."""
from __future__ import annotations

from pathlib import Path

import pytest

import kb.core.markdown_assets as markdown_assets
from kb.core.markdown_assets import collect_markdown_image_assets


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as exc:
        if isinstance(exc, PermissionError) or getattr(exc, "winerror", None) == 1314:
            pytest.skip(f"symlink creation is not permitted: {exc}")
        raise


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


def test_collect_url_encoded_relative_image_decodes_before_resolution(tmp_path: Path):
    """URL-encoded local image names resolve to their decoded filesystem names."""
    vault = tmp_path / "vault"
    source_root = tmp_path / "blog"
    source_root.mkdir()
    image = source_root / "my image.png"
    image.write_bytes(b"png-bytes")
    post = source_root / "post.md"
    markdown = "![Alt](my%20image.png)\n"

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=source_root,
        vault=vault,
    )

    rel = result.attachments[0]
    assert rel.startswith("attachments/")
    assert rel.endswith(".png")
    assert (vault / rel).read_bytes() == b"png-bytes"
    assert result.content == f"![Alt]({rel})\n"
    assert result.warnings == []


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


def test_collect_existing_attachment_link_records_normalized_safe_path(tmp_path: Path):
    """Existing attachment metadata is normalized while Markdown stays unchanged."""
    post = tmp_path / "post.md"
    markdown = "![Stored](attachments/2026/../06/abc.png)\n"

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=tmp_path,
        vault=tmp_path / "vault",
    )

    assert result.content == markdown
    assert result.attachments == ["attachments/06/abc.png"]
    assert result.warnings == []


def test_collect_existing_attachment_link_rejects_traversal(tmp_path: Path):
    """Existing attachment links cannot escape the attachments namespace."""
    post = tmp_path / "post.md"
    markdown = "\n".join([
        "![Traversal](attachments/../secret.png)",
        "![EncodedTraversal](attachments/%2e%2e/secret.png)",
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
    assert result.warnings == [
        "unsafe attachment path: attachments/../secret.png",
        "unsafe attachment path: attachments/%2e%2e/secret.png",
    ]


def test_collect_uses_configured_attachment_dir_for_storage_and_existing_links(
    tmp_path: Path,
):
    vault = tmp_path / "vault"
    source_root = tmp_path / "blog"
    source_root.mkdir()
    (source_root / "diagram.png").write_bytes(b"diagram")
    post = source_root / "post.md"
    markdown = (
        "![New](diagram.png)\n"
        "![Stored](files/2026/06/existing.png)\n"
        "![Traversal](files/../secret.png)\n"
    )

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=source_root,
        vault=vault,
        attachments_dir="files",
    )

    assert len(result.attachments) == 2
    assert result.attachments[0].startswith("files/")
    assert result.attachments[1] == "files/2026/06/existing.png"
    assert (vault / result.attachments[0]).read_bytes() == b"diagram"
    assert "![New](files/" in result.content
    assert result.warnings == ["unsafe attachment path: files/../secret.png"]


def test_collect_rejects_existing_configured_attachment_symlink_outside_vault(
    tmp_path: Path,
):
    vault = tmp_path / "vault"
    configured = vault / "files"
    configured.mkdir(parents=True)
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside")
    unsafe_link = configured / "outside.png"
    _symlink_or_skip(unsafe_link, outside)
    source_root = tmp_path / "blog"
    source_root.mkdir()
    post = source_root / "post.md"
    markdown = "![Stored](files/outside.png)\n"

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=source_root,
        vault=vault,
        attachments_dir="files",
    )

    assert result.content == markdown
    assert result.attachments == []
    assert result.warnings == ["unsafe attachment path: files/outside.png"]


def test_collect_recognizes_existing_attachment_when_attachment_dir_is_dot(
    tmp_path: Path,
):
    vault = tmp_path / "vault"
    existing = vault / "2026" / "06" / "existing.png"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing")
    source_root = tmp_path / "blog"
    source_root.mkdir()
    post = source_root / "post.md"
    markdown = "![Stored](2026/06/existing.png)\n"

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=source_root,
        vault=vault,
        attachments_dir=".",
    )

    assert result.content == markdown
    assert result.attachments == ["2026/06/existing.png"]
    assert result.warnings == []


def test_collect_stores_local_image_when_attachment_dir_is_dot(tmp_path: Path):
    vault = tmp_path / "vault"
    source_root = tmp_path / "blog"
    source_root.mkdir()
    (source_root / "diagram.png").write_bytes(b"diagram")
    post = source_root / "post.md"

    result = collect_markdown_image_assets(
        "![Diagram](diagram.png)\n",
        source_file=post,
        source_root=source_root,
        vault=vault,
        attachments_dir=".",
    )

    assert len(result.attachments) == 1
    assert (vault / result.attachments[0]).read_bytes() == b"diagram"
    assert result.content == f"![Diagram]({result.attachments[0]})\n"
    assert result.warnings == []


def test_collect_rejects_traversal_when_attachment_dir_is_dot(tmp_path: Path):
    source_root = tmp_path / "blog"
    source_root.mkdir()
    post = source_root / "post.md"
    markdown = "![Traversal](../secret.png)\n"

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=source_root,
        vault=tmp_path / "vault",
        attachments_dir=".",
    )

    assert result.content == markdown
    assert result.attachments == []
    assert result.warnings == ["unsafe attachment path: ../secret.png"]


def test_collect_existing_attachment_link_normalizes_windows_separators_for_metadata(
    tmp_path: Path,
):
    """Existing attachment links with backslashes are recorded with slash metadata."""
    post = tmp_path / "post.md"
    markdown = r"![Stored](attachments\2026\06\abc.png)" "\n"

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


def test_collect_ignores_remote_data_schemes_case_insensitively(tmp_path: Path):
    """Ignored URL/data schemes are matched regardless of case."""
    post = tmp_path / "post.md"
    markdown = "\n".join([
        "![Remote](HTTPS://example.com/a.png)",
        "![Data](DATA:image/png;base64,abc)",
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


def test_collect_store_failure_keeps_link_and_warns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Attachment storage failures do not abort collection or rewrite links."""
    vault = tmp_path / "vault"
    source_root = tmp_path / "blog"
    source_root.mkdir()
    image = source_root / "diagram.png"
    image.write_bytes(b"png-bytes")
    post = source_root / "post.md"
    markdown = "![Diagram](diagram.png)\n"

    def fail_store(
        _source: Path,
        _vault: Path,
        *,
        attachments_dir: str = "attachments",
    ) -> str:
        raise OSError("disk full")

    monkeypatch.setattr(markdown_assets, "store_attachment", fail_store)

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=source_root,
        vault=vault,
    )

    assert result.content == markdown
    assert result.attachments == []
    assert result.warnings == ["failed to store image diagram.png: disk full"]


def test_collect_ignores_images_inside_fenced_code_blocks(tmp_path: Path):
    """Image-looking Markdown in fenced code blocks is preserved as code."""
    vault = tmp_path / "vault"
    source_root = tmp_path / "blog"
    source_root.mkdir()
    (source_root / "real.png").write_bytes(b"real")
    (source_root / "code.png").write_bytes(b"code")
    post = source_root / "post.md"
    markdown = (
        "```markdown\n"
        "![Code](code.png)\n"
        "```\n\n"
        "![Real](real.png)\n"
    )

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=source_root,
        vault=vault,
    )

    assert "![Code](code.png)" in result.content
    assert result.content.count("attachments/") == 1
    assert result.content.startswith(
        "```markdown\n![Code](code.png)\n```\n\n![Real](attachments/"
    )
    assert len(result.attachments) == 1
    assert (vault / result.attachments[0]).read_bytes() == b"real"
    assert result.warnings == []


def test_collect_does_not_close_fence_on_info_string_inside_code(tmp_path: Path):
    """Fence-like code with an info string does not close an open fence."""
    vault = tmp_path / "vault"
    source_root = tmp_path / "blog"
    source_root.mkdir()
    (source_root / "real.png").write_bytes(b"real")
    (source_root / "code.png").write_bytes(b"code")
    post = source_root / "post.md"
    markdown = (
        "```\n"
        "```js\n"
        "![Code](code.png)\n"
        "```\n\n"
        "![Real](real.png)\n"
    )

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=source_root,
        vault=vault,
    )

    assert "```js\n![Code](code.png)" in result.content
    assert result.content.count("attachments/") == 1
    assert result.content.endswith("![Real](" + result.attachments[0] + ")\n")
    assert (vault / result.attachments[0]).read_bytes() == b"real"
    assert result.warnings == []
