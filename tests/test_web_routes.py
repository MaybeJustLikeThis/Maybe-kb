from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_page_routes_are_lazy_loaded() -> None:
    """Vue page components should be loaded with dynamic imports."""
    main_ts = (ROOT / "web/src/main.ts").read_text(encoding="utf-8")

    pages = [
        "OverviewPage",
        "SourcePage",
        "NoteDetail",
        "SearchPage",
        "ChatPage",
        "ManagePage",
    ]

    for page in pages:
        assert f"import {page} from './pages/" not in main_ts

    for path in [
        "./pages/OverviewPage.vue",
        "./pages/SourcePage.vue",
        "./pages/NoteDetail.vue",
        "./pages/SearchPage.vue",
        "./pages/ChatPage.vue",
        "./pages/ManagePage.vue",
    ]:
        assert f"() => import('{path}')" in main_ts


def test_markdown_rendering_uses_highlight_core() -> None:
    """Markdown rendering should not import the full highlight.js bundle."""
    note_detail = (ROOT / "web/src/pages/NoteDetail.vue").read_text(encoding="utf-8")
    editor = (ROOT / "web/src/components/MarkdownEditor.vue").read_text(encoding="utf-8")
    markdown = (ROOT / "web/src/markdown.ts").read_text(encoding="utf-8")

    assert "from 'highlight.js'" not in note_detail
    assert "from 'highlight.js'" not in editor
    assert "highlight.js/lib/core" in markdown
