"""Tests for evaluation engine scoring and dataset functions."""
from pathlib import Path

import pytest

from kb.core.eval import (
    load_dataset,
    filter_queries,
    score_hit,
    score_rank,
    compute_mrr,
    score_keywords,
)
from kb.core.search import ChunkSearchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_results(*file_ids: str) -> list[ChunkSearchResult]:
    """Build ChunkSearchResult list from file_ids with simple defaults."""
    return [
        ChunkSearchResult(
            file_id=fid,
            chunk_id=0,
            text=f"Content for {fid}",
            title=f"Title for {fid}",
            score=1.0 / (i + 1),
            source="fts5",
        )
        for i, fid in enumerate(file_ids)
    ]


# ============================================================================
# 1. load_dataset
# ============================================================================


def test_load_dataset(tmp_path: Path):
    """Parses a valid v1 dataset JSON and returns query dicts."""
    import json

    data = {
        "version": "1",
        "queries": [
            {
                "id": "q001",
                "query": "测试问题",
                "expected_source": "notes/test.md",
                "expected_keywords": ["关键词1", "关键词2"],
                "difficulty": "easy",
            }
        ],
    }
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    queries = load_dataset(path)

    assert len(queries) == 1
    assert queries[0]["id"] == "q001"
    assert queries[0]["query"] == "测试问题"
    assert queries[0]["expected_source"] == "notes/test.md"
    assert queries[0]["difficulty"] == "easy"


def test_load_dataset_bad_version(tmp_path: Path):
    """Raises ValueError when dataset version is not "1"."""
    import json

    data = {"version": "2", "queries": [{"id": "q1", "query": "test"}]}
    path = tmp_path / "bad_version.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    try:
        load_dataset(path)
        assert False, "Expected ValueError was not raised"
    except ValueError as exc:
        msg = str(exc).lower()
        assert "version" in msg
        assert "2" in msg


# ============================================================================
# 3. filter_queries – by subset
# ============================================================================


def test_filter_by_subset():
    """Filters queries by difficulty level."""
    queries = [
        {"id": "q1", "difficulty": "easy", "expected_source": "notes/a.md"},
        {"id": "q2", "difficulty": "hard", "expected_source": "notes/b.md"},
        {"id": "q3", "difficulty": "easy", "expected_source": "notes/c.md"},
    ]

    result = filter_queries(queries, subset="easy")

    assert len(result) == 2
    assert {r["id"] for r in result} == {"q1", "q3"}


# ============================================================================
# 4. filter_queries – by category (single source)
# ============================================================================


def test_filter_by_category_single_hop():
    """Filters queries where expected_source is a single string matching the
    category prefix."""
    queries = [
        {"id": "q1", "expected_source": "notes/a.md"},
        {"id": "q2", "expected_source": "notes/b.md"},
        {"id": "q3", "expected_source": "archive/a.md"},
    ]

    result = filter_queries(queries, category="notes/")

    assert len(result) == 2
    assert {r["id"] for r in result} == {"q1", "q2"}


# ============================================================================
# 5. filter_queries – by category (list source / multi-hop)
# ============================================================================


def test_filter_by_category_multi_hop():
    """Filters queries where expected_source is a list and any element
    starts with the category prefix."""
    queries = [
        {"id": "q1", "expected_source": ["notes/a.md", "notes/b.md"]},
        {"id": "q2", "expected_source": "archive/x.md"},
        {"id": "q3", "expected_source": ["archive/y.md", "notes/c.md"]},
    ]

    result = filter_queries(queries, category="notes/")

    assert len(result) == 2
    assert {r["id"] for r in result} == {"q1", "q3"}


# ============================================================================
# 6. filter_queries – no filters
# ============================================================================


def test_filter_queries_no_filters():
    """Returns all queries when no subset or category is specified."""
    queries = [
        {"id": "q1", "expected_source": "notes/a.md"},
        {"id": "q2", "expected_source": "notes/b.md"},
        {"id": "q3", "expected_source": "notes/c.md"},
    ]

    result = filter_queries(queries)

    assert len(result) == 3
    assert {r["id"] for r in result} == {"q1", "q2", "q3"}


# ============================================================================
# 7. filter_queries – both subset and category
# ============================================================================


def test_filter_queries_both_filters():
    """Applies both difficulty and category filters simultaneously."""
    queries = [
        {"id": "q1", "difficulty": "easy", "expected_source": "notes/a.md"},
        {"id": "q2", "difficulty": "hard", "expected_source": "notes/b.md"},
        {"id": "q3", "difficulty": "easy", "expected_source": "archive/x.md"},
    ]

    result = filter_queries(queries, subset="easy", category="notes/")

    assert len(result) == 1
    assert result[0]["id"] == "q1"


# ============================================================================
# 8. score_hit – single source (found + not found)
# ============================================================================


def test_score_hit_single_source():
    """Detects whether a single expected source file_id appears in results."""
    results = _make_results("notes/a.md", "notes/b.md", "notes/c.md")

    assert score_hit("notes/a.md", results) is True
    assert score_hit("notes/z.md", results) is False


# ============================================================================
# 9. score_hit – list source
# ============================================================================


def test_score_hit_multi_source():
    """Detects whether any of a list of expected sources appears in results."""
    results = _make_results("notes/a.md", "notes/b.md", "notes/c.md")

    # One of the list sources appears in results.
    assert score_hit(["notes/x.md", "notes/a.md"], results) is True

    # None of the list sources appear in results.
    assert score_hit(["notes/x.md", "notes/y.md"], results) is False


# ============================================================================
# 11. score_rank – first position
# ============================================================================


def test_score_rank_first_position():
    """Returns 1 when the expected source is the first result."""
    results = _make_results("notes/a.md", "notes/b.md", "notes/c.md")

    assert score_rank("notes/a.md", results) == 1


# ============================================================================
# 12. score_rank – not found
# ============================================================================


def test_score_rank_not_found():
    """Returns -1 when no expected source matches any result."""
    results = _make_results("notes/a.md", "notes/b.md", "notes/c.md")

    assert score_rank("notes/z.md", results) == -1


# ============================================================================
# 13. score_rank – list source
# ============================================================================


def test_score_rank_multi_source():
    """Finds the 1-indexed rank of the first match among a list of sources."""
    results = _make_results("notes/a.md", "notes/b.md", "notes/c.md")

    # "notes/b.md" is at rank 2 and is in the source list.
    assert score_rank(["notes/x.md", "notes/b.md"], results) == 2

    # "notes/c.md" is at rank 3; "notes/z.md" is not present.
    assert score_rank(["notes/z.md", "notes/c.md"], results) == 3


# ============================================================================
# 14. compute_mrr – all hits
# ============================================================================


def test_compute_mrr_all_hits():
    """Computes MRR correctly when all queries have a hit."""
    details = [{"rank": 1}, {"rank": 2}, {"rank": 3}]
    # (1/1 + 1/2 + 1/3) / 3
    expected = (1.0 + 0.5 + 1.0 / 3) / 3

    assert compute_mrr(details) == pytest.approx(expected)


# ============================================================================
# 15. compute_mrr – some misses
# ============================================================================


def test_compute_mrr_some_misses():
    """Misses (rank -1) contribute zero to the reciprocal sum."""
    details = [{"rank": 1}, {"rank": -1}, {"rank": 3}]
    # Only ranks 1 and 3 contribute; denominator is always len(details).
    expected = (1.0 / 1 + 0 + 1.0 / 3) / 3

    assert compute_mrr(details) == pytest.approx(expected)


# ============================================================================
# 16. compute_mrr – all misses
# ============================================================================


def test_compute_mrr_all_misses():
    """Returns 0.0 when every query is a miss, and handles edge cases."""
    assert compute_mrr([{"rank": -1}, {"rank": -1}]) == 0.0

    # rank=0 is also treated as a miss (only rank > 0 counts).
    assert compute_mrr([{"rank": 0}]) == 0.0

    # Empty list yields 0.0.
    assert compute_mrr([]) == 0.0


# ============================================================================
# 17. score_keywords – full match
# ============================================================================


def test_score_keywords_full_match():
    """Returns 1.0 when every expected keyword is found in the answer."""
    answer = "This is a test answer about Python programming language."
    keywords = ["python", "test", "language"]

    assert score_keywords(answer, keywords) == 1.0


# ============================================================================
# 18. score_keywords – partial match
# ============================================================================


def test_score_keywords_partial_match():
    """Returns the fraction of expected keywords found."""
    answer = "This is a test answer about Python programming."

    # 1 out of 3 found
    assert score_keywords(answer, ["python", "java", "rust"]) == pytest.approx(1.0 / 3)

    # 2 out of 3 found
    assert score_keywords(answer, ["python", "test", "rust"]) == pytest.approx(2.0 / 3)


# ============================================================================
# 19. score_keywords – no match
# ============================================================================


def test_score_keywords_no_match():
    """Returns 0.0 when no keywords are found in the answer."""
    assert score_keywords("No relevant text.", ["python", "java"]) == 0.0


# ============================================================================
# 20. score_keywords – empty keywords
# ============================================================================


def test_score_keywords_empty():
    """Returns 1.0 when the expected keywords list is empty."""
    assert score_keywords("Any text.", []) == 1.0
    assert score_keywords("", []) == 1.0


# ============================================================================
# 21. score_keywords – case insensitive
# ============================================================================


def test_score_keywords_case_insensitive():
    """Keyword matching is case-insensitive substring search."""
    answer = "The CAT sat on the MAT."
    keywords = ["cat", "mat", "DOG"]

    # "cat" and "mat" are found via case-insensitive substring; "DOG" is not.
    assert score_keywords(answer, keywords) == pytest.approx(2.0 / 3)
