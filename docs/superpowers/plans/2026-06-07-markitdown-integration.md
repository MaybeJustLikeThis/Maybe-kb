# MarkItDown Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Microsoft markitdown as the sole file converter, enabling `kb import` for PDF/DOCX/CSV and other formats.

**Architecture:** markitdown converts files → Markdown. A new `import_file()` function orchestrates: store original as attachment → convert via markitdown → assemble IngestRequest → call existing `ingest()`. No new service classes. CLI and API are thin wrappers around `import_file()`.

**Tech Stack:** markitdown[all] (optional dependency), existing kb ingest pipeline, typer (CLI), FastAPI (API)

---

### Task 1: Add markitdown optional dependency

**Files:**
- Modify: `pyproject.toml:26-30`

- [ ] **Step 1: Add markitdown to optional dependencies**

```toml
[project.optional-dependencies]
markitdown = ["markitdown[all]"]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]
```

- [ ] **Step 2: Install markitdown in development environment**

Run: `pip install 'markitdown[all]'`
Expected: Successfully installed

- [ ] **Step 3: Verify markitdown import works**

Run: `python -c "from markitdown import MarkItDown; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add markitdown optional dependency"
```

---

### Task 2: Delete existing parsers and clean up tests

**Files:**
- Delete: `src/kb/parsers/pdf.py`
- Delete: `src/kb/parsers/docx.py`
- Delete: `src/kb/parsers/image.py`
- Modify: `tests/test_parsers.py:62-219`

- [ ] **Step 1: Delete parser files**

```bash
rm src/kb/parsers/pdf.py src/kb/parsers/docx.py src/kb/parsers/image.py
```

- [ ] **Step 2: Remove PDF/DOCX/Image test cases from test_parsers.py**

Delete everything from line 62 (the `# --- PDF Parser tests ---` comment) through the end of the file. The remaining file should contain only:

```python
"""Tests for parser registry and MarkdownParser."""
import pytest
from pathlib import Path
from kb.core.parsers import Parser, ParsedContent, ParserRegistry, MarkdownParser


def test_parsed_content_is_frozen():
    """ParsedContent is immutable."""
    pc = ParsedContent(text="hello", metadata={"pages": 1}, attachments=[])
    assert pc.text == "hello"
    assert pc.metadata == {"pages": 1}


def test_markdown_parser_parses_file(tmp_path: Path):
    """MarkdownParser extracts frontmatter and body."""
    md = tmp_path / "test.md"
    md.write_text("---\ntitle: Hello\ntags: [a, b]\n---\n\n# Content\n\nBody text.", encoding="utf-8")

    parser = MarkdownParser()
    result = parser.parse(md)

    assert "# Content" in result.text
    assert "Body text" in result.text
    assert result.metadata["title"] == "Hello"
    assert result.metadata["tags"] == ["a", "b"]


def test_markdown_parser_no_frontmatter(tmp_path: Path):
    """MarkdownParser handles files without frontmatter."""
    md = tmp_path / "plain.md"
    md.write_text("# Just a heading\n\nSome content.", encoding="utf-8")

    parser = MarkdownParser()
    result = parser.parse(md)

    assert "Just a heading" in result.text
    assert "Some content" in result.text


def test_parser_registry_returns_correct_parser():
    """ParserRegistry returns parser by extension."""
    assert isinstance(ParserRegistry.get(".md"), MarkdownParser)
    assert isinstance(ParserRegistry.get(".MD"), MarkdownParser)


def test_parser_registry_raises_for_unknown_extension():
    """ParserRegistry raises KeyError for unregistered extensions."""
    with pytest.raises(KeyError):
        ParserRegistry.get(".xyz")


def test_parser_registry_register_custom_parser():
    """Custom parsers can be registered."""
    class FakeParser:
        def parse(self, path, *, context_bound=False):
            return ParsedContent(text="fake", metadata={}, attachments=[])

    ParserRegistry.register(".fake", FakeParser())
    assert isinstance(ParserRegistry.get(".fake"), FakeParser)
```

- [ ] **Step 3: Run parser tests to verify nothing is broken**

Run: `pytest tests/test_parsers.py -v`
Expected: 7 passed

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: remove PDF/DOCX/Image parsers (replaced by markitdown)"
```

---

### Task 3: Create markitdown converter

**Files:**
- Create: `src/kb/parsers/markitdown_converter.py`
- Create: `tests/test_markitdown_converter.py`

- [ ] **Step 1: Write tests for the converter**

Create `tests/test_markitdown_converter.py`:

```python
"""Tests for markitdown converter."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kb.parsers.markitdown_converter import (
    ConversionError,
    MarkItDownNotInstalledError,
    convert_file,
)


def test_convert_file_returns_text(tmp_path: Path) -> None:
    """convert_file returns Markdown text from a file."""
    fake_result = MagicMock()
    fake_result.text_content = "# Converted\n\nHello from PDF."

    with patch("kb.parsers.markitdown_converter._get_converter") as mock_get:
        mock_converter = MagicMock()
        mock_converter.convert.return_value = fake_result
        mock_get.return_value = mock_converter

        result = convert_file(tmp_path / "test.pdf")

    assert result.text == "# Converted\n\nHello from PDF."
    assert result.metadata["converter"] == "markitdown"
    assert result.metadata["source_file"] == "test.pdf"


def test_convert_file_extracts_source_filename(tmp_path: Path) -> None:
    """Metadata contains the original filename."""
    fake_result = MagicMock()
    fake_result.text_content = "content"

    with patch("kb.parsers.markitdown_converter._get_converter") as mock_get:
        mock_converter = MagicMock()
        mock_converter.convert.return_value = fake_result
        mock_get.return_value = mock_converter

        result = convert_file(tmp_path / "my-report.docx")

    assert result.metadata["source_file"] == "my-report.docx"


def test_convert_file_raises_on_empty_content(tmp_path: Path) -> None:
    """Empty conversion result raises ConversionError."""
    fake_result = MagicMock()
    fake_result.text_content = "   "

    with patch("kb.parsers.markitdown_converter._get_converter") as mock_get:
        mock_converter = MagicMock()
        mock_converter.convert.return_value = fake_result
        mock_get.return_value = mock_converter

        with pytest.raises(ConversionError, match="empty"):
            convert_file(tmp_path / "blank.pdf")


def test_convert_file_raises_on_converter_exception(tmp_path: Path) -> None:
    """markitdown exceptions are wrapped in ConversionError."""
    with patch("kb.parsers.markitdown_converter._get_converter") as mock_get:
        mock_converter = MagicMock()
        mock_converter.convert.side_effect = RuntimeError("boom")
        mock_get.return_value = mock_converter

        with pytest.raises(ConversionError, match="boom"):
            convert_file(tmp_path / "broken.pdf")


def test_convert_file_raises_not_installed(tmp_path: Path) -> None:
    """Missing markitdown package raises MarkItDownNotInstalledError."""
    with patch(
        "kb.parsers.markitdown_converter._get_converter",
        side_effect=MarkItDownNotInstalledError(),
    ):
        with pytest.raises(MarkItDownNotInstalledError):
            convert_file(tmp_path / "test.pdf")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_markitdown_converter.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement the converter**

Create `src/kb/parsers/markitdown_converter.py`:

```python
"""MarkItDown-based file converter for kb import."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConversionResult:
    """Output from markitdown conversion."""
    text: str
    metadata: dict[str, str]


class MarkItDownNotInstalledError(Exception):
    """Raised when markitdown package is not installed."""

    def __init__(self) -> None:
        super().__init__(
            "markitdown is not installed. "
            "Install it with: pip install 'kb[markitdown]'"
        )


class ConversionError(Exception):
    """Raised when file conversion fails."""


def _get_converter() -> object:
    """Lazily import and return a MarkItDown instance.

    Raises MarkItDownNotInstalledError if the package is missing.
    """
    try:
        from markitdown import MarkItDown
    except ImportError:
        raise MarkItDownNotInstalledError()
    return MarkItDown(enable_plugins=False)


def convert_file(path: Path) -> ConversionResult:
    """Convert a file to Markdown using markitdown.

    Args:
        path: Absolute path to the source file.

    Returns:
        ConversionResult with Markdown text and metadata.

    Raises:
        MarkItDownNotInstalledError: markitdown package not installed.
        ConversionError: conversion failed or produced empty output.
    """
    converter = _get_converter()

    try:
        result = converter.convert(str(path))
    except Exception as exc:
        raise ConversionError(f"Conversion failed: {exc}") from exc

    text = result.text_content or ""
    if not text.strip():
        raise ConversionError(
            f"Conversion produced empty content: {path.name}"
        )

    return ConversionResult(
        text=text,
        metadata={
            "converter": "markitdown",
            "source_file": path.name,
        },
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_markitdown_converter.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/kb/parsers/markitdown_converter.py tests/test_markitdown_converter.py
git commit -m "feat: add markitdown converter module"
```

---

### Task 4: Create import_file() function

**Files:**
- Create: `src/kb/core/import_file.py`
- Create: `tests/test_import_file.py`

- [ ] **Step 1: Write tests for import_file**

Create `tests/test_import_file.py`:

```python
"""Tests for import_file function."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kb.core.import_file import (
    ImportFileError,
    import_file,
)


@pytest.fixture
def mock_ctx() -> MagicMock:
    """Create a mock AppContext with all needed attributes."""
    ctx = MagicMock()
    ctx.vault = Path("/vault")
    ctx.db = MagicMock()
    ctx.notes_dir = "notes"
    ctx.attachments_dir = "attachments"
    ctx.config = MagicMock()
    ctx.config.sources = {}
    return ctx


def _write_pdf(path: Path) -> Path:
    """Create a minimal PDF file for testing."""
    pdf_path = path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF")
    return pdf_path


def test_import_file_success(tmp_path: Path, mock_ctx: MagicMock) -> None:
    """Successful import stores attachment and creates a note."""
    pdf_path = _write_pdf(tmp_path)

    mock_note = MagicMock()
    mock_note.file_id = "notes/未分类/test.md"

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
        patch("kb.core.import_file.ingest") as mock_ingest,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        mock_convert.return_value = MagicMock(
            text="# Converted\n\nContent",
            metadata={"converter": "markitdown", "source_file": "test.pdf"},
        )
        mock_ingest.return_value = mock_note

        result = import_file(
            pdf_path,
            vault=mock_ctx.vault,
            db=mock_ctx.db,
            notes_dir=mock_ctx.notes_dir,
            attachments_dir=mock_ctx.attachments_dir,
        )

    assert result.file_id == "notes/未分类/test.md"

    # Verify IngestRequest was assembled correctly
    call_args = mock_ingest.call_args
    req = call_args[0][0]
    assert req.title == "test"
    assert req.source_project == "imported"
    assert req.content_type == "pdf"
    assert req.source_path == "attachments/2026/06/abc123.pdf"
    assert req.attachments == ["attachments/2026/06/abc123.pdf"]
    assert req.extra_frontmatter["source_file"] == "test.pdf"


def test_import_file_custom_title_and_category(tmp_path: Path, mock_ctx: MagicMock) -> None:
    """Title and category can be overridden."""
    pdf_path = _write_pdf(tmp_path)

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
        patch("kb.core.import_file.ingest") as mock_ingest,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        mock_convert.return_value = MagicMock(
            text="content", metadata={"converter": "markitdown", "source_file": "test.pdf"},
        )
        mock_ingest.return_value = MagicMock(file_id="notes/AI/paper.md")

        import_file(
            pdf_path,
            vault=mock_ctx.vault,
            db=mock_ctx.db,
            notes_dir=mock_ctx.notes_dir,
            attachments_dir=mock_ctx.attachments_dir,
            title="My Paper",
            category="AI",
        )

    req = mock_ingest.call_args[0][0]
    assert req.title == "My Paper"
    assert req.category == "AI"


def test_import_file_stores_attachment_before_convert(tmp_path: Path, mock_ctx: MagicMock) -> None:
    """Attachment is stored even if conversion fails."""
    pdf_path = _write_pdf(tmp_path)

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        mock_convert.side_effect = Exception("conversion crashed")

        with pytest.raises(ImportFileError, match="conversion crashed"):
            import_file(
                pdf_path,
                vault=mock_ctx.vault,
                db=mock_ctx.db,
                notes_dir=mock_ctx.notes_dir,
                attachments_dir=mock_ctx.attachments_dir,
            )

    # Attachment was stored
    mock_store.assert_called_once()


def test_import_file_not_installed(tmp_path: Path, mock_ctx: MagicMock) -> None:
    """Clear error when markitdown is not installed."""
    pdf_path = _write_pdf(tmp_path)

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        from kb.parsers.markitdown_converter import MarkItDownNotInstalledError
        mock_convert.side_effect = MarkItDownNotInstalledError()

        with pytest.raises(ImportFileError, match="markitdown"):
            import_file(
                pdf_path,
                vault=mock_ctx.vault,
                db=mock_ctx.db,
                notes_dir=mock_ctx.notes_dir,
                attachments_dir=mock_ctx.attachments_dir,
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_import_file.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement import_file**

Create `src/kb/core/import_file.py`:

```python
"""Single-file import: convert via markitdown, store attachment, create note."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from kb.core.ingest import ingest
from kb.core.models import IngestRequest, Note
from kb.data.attachments import store_attachment
from kb.data.database import Database
from kb.parsers.markitdown_converter import (
    ConversionError,
    MarkItDownNotInstalledError,
    convert_file,
)


class ImportFileError(Exception):
    """Raised when file import fails."""


def import_file(
    source: Path,
    *,
    vault: Path,
    db: Database,
    notes_dir: str = "notes",
    attachments_dir: str = "attachments",
    title: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    source_config: Any = None,
) -> Note:
    """Import a file into the knowledge base.

    1. Store the original file as an attachment.
    2. Convert to Markdown via markitdown.
    3. Assemble IngestRequest and call ingest().

    Args:
        source: Absolute path to the file to import.
        vault: Vault root path.
        db: Database instance.
        notes_dir: Notes subdirectory name.
        attachments_dir: Attachments subdirectory name.
        title: Override title (default: filename without extension).
        category: Override category (default: "未分类").
        tags: Optional tags.
        source_config: Optional SourceConfig for ingest().

    Returns:
        The created Note.

    Raises:
        ImportFileError: import failed (conversion, empty content, etc.)
    """
    if not source.is_file():
        raise ImportFileError(f"File not found: {source}")

    # 1. Store original as attachment
    attachment_path = store_attachment(
        source, vault, attachments_dir=attachments_dir,
    )

    # 2. Convert to Markdown
    try:
        result = convert_file(source)
    except MarkItDownNotInstalledError as exc:
        raise ImportFileError(str(exc)) from exc
    except ConversionError as exc:
        raise ImportFileError(str(exc)) from exc

    # 3. Determine metadata
    stem = source.stem
    ext = source.suffix.lstrip(".")
    resolved_title = title or stem
    resolved_category = category or "未分类"

    # 4. Assemble IngestRequest
    request = IngestRequest(
        title=resolved_title,
        content=result.text,
        source_project="imported",
        category=resolved_category,
        tags=list(tags) if tags else [],
        content_type=ext,
        source_path=attachment_path,
        attachments=[attachment_path],
        extra_frontmatter={
            "source_file": result.metadata.get("source_file", source.name),
        },
    )

    # 5. Ingest
    return ingest(
        request,
        vault=vault,
        db=db,
        source_config=source_config,
        notes_dir=notes_dir,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_import_file.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/kb/core/import_file.py tests/test_import_file.py
git commit -m "feat: add import_file function for markitdown-based file import"
```

---

### Task 5: Add CLI `kb import` command

**Files:**
- Modify: `src/kb/cli.py:24-28` (imports), `src/kb/cli.py:114-161` (after add_note)
- Create: `tests/test_cli_import.py`

- [ ] **Step 1: Write test for CLI import command**

Create `tests/test_cli_import.py`:

```python
"""Tests for kb import CLI command."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kb.cli import app

runner = CliRunner()


@pytest.fixture
def kb_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a kb project directory and cd into it."""
    monkeypatch.chdir(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "notes").mkdir()
    (vault / "attachments").mkdir()
    (vault / ".kb").mkdir()

    tmp_path.joinpath("config.toml").write_text(
        f'[general]\nvault_path = "{vault.as_posix()}"\n',
        encoding="utf-8",
    )
    return tmp_path


def _write_pdf(path: Path) -> Path:
    """Create a minimal PDF file."""
    pdf_path = path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF")
    return pdf_path


def test_kb_import_success(kb_dir: Path) -> None:
    """kb import creates a note from a PDF file."""
    pdf_path = _write_pdf(kb_dir)

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        mock_convert.return_value = MagicMock(
            text="# Paper Title\n\nContent here.",
            metadata={"converter": "markitdown", "source_file": "paper.pdf"},
        )

        result = runner.invoke(app, ["import", str(pdf_path)])

    assert result.exit_code == 0, result.output
    assert "Created note" in result.output
    assert "paper.pdf" in result.output


def test_kb_import_with_options(kb_dir: Path) -> None:
    """kb import respects --title, --category, --tags."""
    pdf_path = _write_pdf(kb_dir)

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        mock_convert.return_value = MagicMock(
            text="content",
            metadata={"converter": "markitdown", "source_file": "paper.pdf"},
        )

        result = runner.invoke(app, [
            "import", str(pdf_path),
            "--title", "My Paper",
            "--category", "AI",
            "--tags", "ml,research",
        ])

    assert result.exit_code == 0, result.output


def test_kb_import_file_not_found(kb_dir: Path) -> None:
    """kb import reports error for missing file."""
    result = runner.invoke(app, ["import", str(kb_dir / "nonexistent.pdf")])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_import.py -v`
Expected: FAIL — no such command "import"

- [ ] **Step 3: Add import command to CLI**

In `src/kb/cli.py`, add the following import at the top alongside the other `from kb.core` imports (after line 23):

```python
from kb.core.import_file import ImportFileError
```

Then add the `import_cmd` function after the `add_note` function (after line 161). Note: `import` is a Python keyword, so the command must be registered with an explicit name:

```python
@app.command("import")
def import_cmd(
    file_path: Path = typer.Argument(help="File to import (PDF, DOCX, CSV, etc.)"),
    title: str = typer.Option("", help="Note title (default: filename)"),
    category: str = typer.Option("", help="Note category"),
    tags: str = typer.Option("", help="Comma-separated tags"),
):
    """Import a file into the knowledge base."""
    from kb.core.import_file import import_file

    if not file_path.is_file():
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    override_title = title.strip() or None
    override_category = category.strip() or None

    ctx = _get_context()
    src_cfg = ctx.config.sources.get("imported") if ctx.config else None
    try:
        note = import_file(
            file_path,
            vault=ctx.vault,
            db=ctx.db,
            notes_dir=ctx.notes_dir,
            attachments_dir=ctx.attachments_dir,
            title=override_title,
            category=override_category,
            tags=tag_list,
            source_config=src_cfg,
        )
    except ImportFileError as e:
        console.print(f"[red]Import failed: {e}[/red]")
        raise typer.Exit(1)
    finally:
        ctx.close()

    console.print(f"[green]Created note:[/green] {note.file_id}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_import.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/kb/cli.py tests/test_cli_import.py
git commit -m "feat: add kb import CLI command for file import"
```

---

### Task 6: Add API `POST /api/v1/import` endpoint

**Files:**
- Modify: `src/kb/api/v1.py:220-247` (after upload_attachment)
- Modify: `tests/test_api_v1.py` (append tests at end)

- [ ] **Step 1: Write test for API import endpoint**

Append to `tests/test_api_v1.py`:

```python
# --- Import endpoint tests ---


def test_v1_import_pdf(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/v1/import converts and ingests a PDF file."""
    from unittest.mock import patch, MagicMock

    # Create a minimal PDF
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF")

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        mock_convert.return_value = MagicMock(
            text="# Test PDF\n\nContent.",
            metadata={"converter": "markitdown", "source_file": "test.pdf"},
        )

        with open(pdf_path, "rb") as f:
            response = client.post(
                "/api/v1/import",
                files={"file": ("test.pdf", f, "application/pdf")},
            )

    assert response.status_code == 200
    payload = response.json()
    assert_success_envelope(payload)
    assert payload["data"]["title"] == "test"
    assert payload["data"]["content_type"] == "pdf"


def test_v1_import_with_options(client: TestClient, tmp_path: Path) -> None:
    """POST /api/v1/import accepts title, category, tags."""
    from unittest.mock import patch, MagicMock

    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        mock_convert.return_value = MagicMock(
            text="content",
            metadata={"converter": "markitdown", "source_file": "report.pdf"},
        )

        with open(pdf_path, "rb") as f:
            response = client.post(
                "/api/v1/import",
                files={"file": ("report.pdf", f, "application/pdf")},
                data={"title": "My Report", "category": "AI", "tags": "ml,research"},
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["title"] == "My Report"


def test_v1_import_failure(client: TestClient, tmp_path: Path) -> None:
    """POST /api/v1/import returns error on conversion failure."""
    from unittest.mock import patch
    from kb.parsers.markitdown_converter import ConversionError

    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(b"not a pdf")

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        mock_convert.side_effect = ConversionError("Conversion failed: bad file")

        with open(pdf_path, "rb") as f:
            response = client.post(
                "/api/v1/import",
                files={"file": ("broken.pdf", f, "application/pdf")},
            )

    assert response.status_code == 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_v1.py::test_v1_import_pdf -v`
Expected: FAIL — 404 (route not found)

- [ ] **Step 3: Implement API import endpoint**

In `src/kb/api/v1.py`, add the import endpoint after the `upload_attachment` route (after the `return responses.ok({"path": rel_path})` line). Insert:

```python
    @router.post("/import")
    async def import_file_endpoint(
        file: UploadFile = File(...),
        title: str = "",
        category: str = "",
        tags: str = "",
    ):
        """Import a file (PDF, DOCX, CSV, etc.) into the knowledge base."""
        import tempfile
        from kb.core.import_file import import_file, ImportFileError

        tmp_path: Path | None = None
        try:
            suffix = Path(file.filename or ".bin").suffix
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix,
            ) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = Path(tmp.name)

            tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
            override_title = title.strip() or None
            override_category = category.strip() or None
            src_cfg = ctx.config.sources.get("imported") if ctx.config else None

            note = import_file(
                tmp_path,
                vault=ctx.vault,
                db=ctx.db,
                notes_dir=ctx.notes_dir,
                attachments_dir=ctx.attachments_dir,
                title=override_title,
                category=override_category,
                tags=tag_list,
                source_config=src_cfg,
            )
            _index_note_if_possible(note.file_id)
        except ImportFileError as exc:
            return responses.operation_failed(
                "IMPORT_FAILED",
                str(exc),
            )
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

        return responses.ok({
            "file_id": note.file_id,
            "title": note.title,
            "category": note.category,
            "content_type": note.content_type,
            "source_project": note.source_project,
        })
```

Also add the `import_file` name to the function to avoid conflict with the Python keyword. The endpoint function is named `import_file_endpoint` to avoid shadowing the import.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api_v1.py -v -k import`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/kb/api/v1.py tests/test_api_v1.py
git commit -m "feat: add POST /api/v1/import endpoint for file import"
```

---

### Task 7: Final verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass (no regressions)

- [ ] **Step 2: Verify CLI help**

Run: `kb import --help`
Expected: Shows usage with `--title`, `--category`, `--tags` options

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete markitdown integration for file import"
```
