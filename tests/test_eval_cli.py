"""Tests for kb eval CLI command."""
import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers – reusable mock providers
# ---------------------------------------------------------------------------


class _FakeEmbedding:
    """Returns a fixed 512-dim vector for any input."""

    def embed(self, text: str):
        from kb.data.embedding import EmbeddingResult

        return EmbeddingResult(vector=[0.1] * 512, dimension=512, tokens_used=0)

    def embed_batch(self, texts: list[str]):
        return [self.embed(t) for t in texts]

    @property
    def dimension(self) -> int:
        return 512


class _FakeLLM:
    """Returns a stub LLM response."""

    def generate(self, prompt: str, *, system_prompt: str = ""):
        from kb.data.llm import LLMResponse

        return LLMResponse(text="mock answer", tokens_used=5, model="mock")

    def generate_stream(self, prompt: str, *, system_prompt: str = ""):
        yield None

    @property
    def model_name(self) -> str:
        return "mock"


def _mock_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch provider factories so init / index / eval run without real models."""
    monkeypatch.setattr(
        "kb.core.context.create_embedding_provider",
        lambda c: _FakeEmbedding(),
    )
    monkeypatch.setattr(
        "kb.core.context.create_llm_provider",
        lambda c: _FakeLLM(),
    )


# ---------------------------------------------------------------------------
# Fixture: fully wired kb project with notes, index, and eval dataset
# ---------------------------------------------------------------------------

@pytest.fixture
def kb_with_dataset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create kb project with notes and eval dataset.  Mocks embedding + LLM."""
    from kb.cli import app

    os.chdir(tmp_path)
    _mock_providers(monkeypatch)

    runner.invoke(app, ["init"])

    # Two categories so filtering tests have distinct targets
    notes_tech = tmp_path / "notes" / "tech"
    notes_tech.mkdir(parents=True)
    (notes_tech / "docker.md").write_text(
        "---\ntitle: Docker 基础\ntags: docker, container\ncategory: tech\n---\n\n"
        "Docker 是一个容器化平台，用于打包和运行应用。",
        encoding="utf-8",
    )

    notes_life = tmp_path / "notes" / "life"
    notes_life.mkdir(parents=True)
    (notes_life / "reading.md").write_text(
        "---\ntitle: 阅读习惯\ntags: reading, life\ncategory: life\n---\n\n"
        "每天阅读一小时是保持知识更新的好习惯。",
        encoding="utf-8",
    )

    runner.invoke(app, ["index", "--full"])

    # Create eval dataset with three queries covering two difficulties and
    # two categories.
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir(exist_ok=True)
    results_dir = eval_dir / "results"
    results_dir.mkdir(exist_ok=True)

    dataset = {
        "version": "1",
        "queries": [
            {
                "id": "q001",
                "query": "Docker 是什么？",
                "expected_source": "notes/tech/docker.md",
                "expected_keywords": ["Docker", "容器化", "打包"],
                "type": "single_hop",
                "difficulty": "easy",
            },
            {
                "id": "q002",
                "query": "如何养成阅读习惯？",
                "expected_source": "notes/life/reading.md",
                "expected_keywords": ["阅读", "习惯"],
                "type": "single_hop",
                "difficulty": "easy",
            },
            {
                "id": "q003",
                "query": "Kubernetes 集群怎么管理？",
                "expected_source": "notes/tech/docker.md",
                "expected_keywords": ["集群", "管理", "编排"],
                "type": "single_hop",
                "difficulty": "hard",
            },
        ],
    }
    (eval_dir / "dataset.json").write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return tmp_path


# ============================================================================
# 1. Error when dataset.json is missing
# ============================================================================


def test_eval_missing_dataset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Exits with code 1 when eval/dataset.json does not exist."""
    from kb.cli import app

    os.chdir(tmp_path)
    _mock_providers(monkeypatch)

    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["eval"])
    assert result.exit_code == 1
    output_lower = result.output.lower()
    assert "dataset" in output_lower or "not found" in output_lower


# ============================================================================
# 2. Runs queries and shows summary table
# ============================================================================


def test_eval_runs_queries(kb_with_dataset: Path):
    """Eval prints an Evaluation Results table with key metrics."""
    from kb.cli import app

    result = runner.invoke(app, ["eval"])
    assert result.exit_code == 0
    assert "Hit Rate" in result.output
    assert "MRR" in result.output
    assert "Overall" in result.output


# ============================================================================
# 3. --subset filters by difficulty
# ============================================================================


def test_eval_subset_filter(kb_with_dataset: Path):
    """Only queries matching --subset difficulty are evaluated."""
    from kb.cli import app

    result = runner.invoke(app, ["eval", "--subset", "medium"])
    assert result.exit_code == 0
    assert "No queries match" in result.output


# ============================================================================
# 4. --category filters by category path
# ============================================================================


def test_eval_category_filter(kb_with_dataset: Path):
    """Only queries whose expected_source starts with the category prefix run."""
    from kb.cli import app

    result = runner.invoke(app, ["eval", "--category", "notes/tech/"])
    assert result.exit_code == 0
    assert "Hit Rate" in result.output

    result = runner.invoke(app, ["eval", "--category", "nonexistent"])
    assert result.exit_code == 0
    assert "No queries match" in result.output


# ============================================================================
# 5. --baseline saves result + --compare loads it
# ============================================================================


def test_eval_baseline_save_and_compare(kb_with_dataset: Path):
    """--baseline writes baseline.json ; --compare diffs against it."""
    from kb.cli import app

    # Save baseline
    result1 = runner.invoke(app, ["eval", "--baseline"])
    assert result1.exit_code == 0
    baseline_path = kb_with_dataset / "eval" / "results" / "baseline.json"
    assert baseline_path.is_file()

    # Compare against the saved baseline
    result2 = runner.invoke(app, ["eval", "--compare", "baseline"])
    assert result2.exit_code == 0
    assert "baseline" in result2.output.lower()
    assert "Delta" in result2.output


# ============================================================================
# 6. --compare with missing baseline shows error
# ============================================================================


def test_eval_compare_missing_baseline(kb_with_dataset: Path):
    """--compare against a non-existent baseline prints an error message."""
    from kb.cli import app

    result = runner.invoke(app, ["eval", "--compare", "nonexistent"])
    assert result.exit_code == 0  # command itself succeeds
    output_lower = result.output.lower()
    assert "not found" in output_lower or "nonexistent" in output_lower


# ============================================================================
# 7. Results JSON saved with correct structure
# ============================================================================


def test_eval_results_saved(kb_with_dataset: Path):
    """Evaluating writes a JSON results file with expected top-level keys."""
    from kb.cli import app

    result = runner.invoke(app, ["eval"])
    assert result.exit_code == 0

    results_dir = kb_with_dataset / "eval" / "results"
    json_files = sorted(results_dir.glob("*.json"))
    non_baseline = [f for f in json_files if f.name != "baseline.json"]
    assert len(non_baseline) == 1, f"Expected 1 result file, got {non_baseline}"

    data = json.loads(non_baseline[0].read_text(encoding="utf-8"))

    # Top-level keys
    assert "timestamp" in data
    assert "config" in data
    assert "summary" in data
    assert "details" in data

    # Summary keys
    summary = data["summary"]
    assert "total" in summary
    assert "hit_rate" in summary
    assert "avg_rank" in summary
    assert "mrr" in summary
    assert "keyword_score" in summary
    assert "overall" in summary

    # Details list
    assert isinstance(data["details"], list)
    assert len(data["details"]) == 3

    detail = data["details"][0]
    for key in ("id", "hit", "rank", "keyword_score"):
        assert key in detail, f"detail missing key {key!r}"


# ============================================================================
# 8. --search-mode respects the selected mode
# ============================================================================


def test_eval_search_mode_option(kb_with_dataset: Path):
    """Eval accepts --search-mode hybrid | semantic | fts5 without error."""
    from kb.cli import app

    for mode in ("hybrid", "semantic", "fts5"):
        result = runner.invoke(app, ["eval", "--search-mode", mode])
        assert result.exit_code == 0, f"eval --search-mode {mode} failed"
        assert "Hit Rate" in result.output
        assert "MRR" in result.output




