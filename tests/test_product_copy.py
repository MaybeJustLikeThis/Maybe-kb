from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CRITICAL_FILES = [
    "README.md",
    "USER_GUIDE.md",
    "config.toml",
    "web/src/App.vue",
]
MOJIBAKE_FRAGMENTS = [
    "鍗氬",
    "娌夋",
    "鎵嬪",
    "鏈",
    "閺",
    "閸",
    "閹",
    "濞屽",
    "绯荤粺鍋",
    "蹇",
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_critical_user_facing_copy_has_no_known_mojibake() -> None:
    for path in CRITICAL_FILES:
        text = read(path)
        for fragment in MOJIBAKE_FRAGMENTS:
            assert fragment not in text, f"{path} contains mojibake fragment {fragment!r}"


def test_source_labels_and_defaults_are_readable_chinese() -> None:
    config = read("config.toml")
    app_vue = read("web/src/App.vue")

    for text in [config, app_vue]:
        assert "博客" in text
        assert "Agent 沉淀" in text
        assert "手动录入" in text

    assert 'description = "Hexo 博客文章"' in config
    assert 'description = "Agent 自动沉淀的知识"' in config
    assert 'description = "手动创建的知识笔记"' in config
    assert config.count('default_category = "未分类"') == 3


def test_first_use_docs_keep_core_positioning_and_trust_entry() -> None:
    readme = read("README.md")
    guide = read("USER_GUIDE.md")

    for text in [readme, guide]:
        assert "本地优先" in text
        assert "System Health" in text
        assert "系统健康" in text
        assert "kb init" in text
        assert "kb index --full" in text
        assert "kb serve" in text
        assert "博客" in text
        assert "Agent 沉淀" in text
        assert "手动录入" in text
        assert "未分类" in text
