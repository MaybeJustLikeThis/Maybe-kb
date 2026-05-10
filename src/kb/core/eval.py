"""Evaluation engine for search and RAG quality measurement."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from kb.core.search import SearchResult, hybrid_search
from kb.data.database import Database
from kb.data.embedding import EmbeddingProvider
from kb.data.llm import LLMProvider
from kb.data.vector import VectorStore

# ---------------------------------------------------------------------------
# LLM Judge Prompt
# ---------------------------------------------------------------------------

LLM_JUDGE_PROMPT = """你是一个严格的中文搜索质量评估专家。请根据以下标准对 AI 回答的质量进行评分（1-5 分）。

评分标准：
- **1 分**：回答完全无关，未涉及用户问题，或包含严重事实错误。
- **2 分**：回答部分相关，但核心问题未得到解答，或存在明显不准确之处。
- **3 分**：回答基本相关，覆盖了主要问题，但回答较为笼统，缺乏具体细节。
- **4 分**：回答准确且相关，覆盖了大部分要点，但仍有少量遗漏或不精确之处。
- **5 分**：回答完全准确、全面且具体，直接命中问题核心，引用了相关知识库内容。

请以 JSON 格式输出评分结果，格式为：
{"score": <1-5 整数>, "reason": "<简短的中文评分理由>"}"""


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvalDetail:
    """Per-query evaluation result."""

    id: str
    hit: bool
    rank: int
    keyword_score: float
    llm_judge: int | None = None
    llm_judge_reason: str | None = None


@dataclass(frozen=True)
class EvalSummary:
    """Aggregate evaluation scores."""

    total: int
    hit_rate: float
    avg_rank: float
    mrr: float
    keyword_score: float
    llm_judge_avg: float | None = None
    overall: float = 0.0


@dataclass(frozen=True)
class EvalResult:
    """Complete evaluation result with timestamp, config, summary, and details."""

    timestamp: str
    config: dict[str, object]
    summary: EvalSummary
    details: list[EvalDetail]

    def to_dict(self) -> dict[str, object]:
        """Serialize to a plain dict for JSON output."""
        return {
            "timestamp": self.timestamp,
            "config": dict(self.config),
            "summary": {
                "total": self.summary.total,
                "hit_rate": self.summary.hit_rate,
                "avg_rank": self.summary.avg_rank,
                "mrr": self.summary.mrr,
                "keyword_score": self.summary.keyword_score,
                "llm_judge_avg": self.summary.llm_judge_avg,
                "overall": self.summary.overall,
            },
            "details": [
                {
                    "id": d.id,
                    "hit": d.hit,
                    "rank": d.rank,
                    "keyword_score": d.keyword_score,
                    "llm_judge": d.llm_judge,
                    "llm_judge_reason": d.llm_judge_reason,
                }
                for d in self.details
            ],
        }


# ---------------------------------------------------------------------------
# Dataset I/O
# ---------------------------------------------------------------------------


def load_dataset(path: Path) -> list[dict]:
    """Load and validate a v1 evaluation dataset.

    Args:
        path: Path to a JSON dataset file.

    Returns:
        List of query dicts from the dataset.

    Raises:
        ValueError: If the dataset version is not "1" or the format is invalid.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))

    version = raw.get("version")
    if version != "1":
        raise ValueError(
            f"Unsupported dataset version: {version!r}. "
            f"Only version '1' is supported."
        )

    queries = raw.get("queries")
    if not isinstance(queries, list):
        raise ValueError("Dataset must contain a 'queries' array.")

    return queries


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def filter_queries(
    queries: list[dict],
    subset: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Filter queries by difficulty level and/or category path prefix.

    Args:
        queries: Raw query dicts from the dataset.
        subset: Difficulty filter ("easy", "medium", "hard").
        category: Category path prefix matched against expected_source.

    Returns:
        Filtered list of query dicts.
    """
    result = queries

    if subset is not None:
        result = [q for q in result if q.get("difficulty") == subset]

    if category is not None:
        filtered: list[dict] = []
        for q in result:
            expected = q.get("expected_source")
            sources = (
                expected if isinstance(expected, list) else [expected]
            )
            if any(
                isinstance(s, str) and s.startswith(category)
                for s in sources
            ):
                filtered.append(q)
        result = filtered

    return result


# ---------------------------------------------------------------------------
# Scoring Functions
# ---------------------------------------------------------------------------


def score_hit(
    expected_source: str | list[str], results: list[SearchResult]
) -> bool:
    """Check whether any expected source appears in the search results.

    Args:
        expected_source: A single file_id or a list of file_ids.
        results: Ordered search results.

    Returns:
        True if any expected source was found in results.
    """
    sources = (
        [expected_source]
        if isinstance(expected_source, str)
        else expected_source
    )
    result_ids = {r.file_id for r in results}
    return any(s in result_ids for s in sources)


def score_rank(
    expected_source: str | list[str], results: list[SearchResult]
) -> int:
    """Find the 1-indexed rank of the first matching expected source.

    Args:
        expected_source: A single file_id or a list of file_ids.
        results: Ordered search results.

    Returns:
        1-indexed rank of the first match, or -1 if not found.
    """
    sources = (
        [expected_source]
        if isinstance(expected_source, str)
        else expected_source
    )
    for i, r in enumerate(results, start=1):
        if r.file_id in sources:
            return i
    return -1


def compute_mrr(details: list[dict]) -> float:
    """Compute Mean Reciprocal Rank from detail records.

    Args:
        details: List of dicts each containing a "rank" key
                 (1-indexed, -1 if miss).

    Returns:
        MRR score in [0, 1].
    """
    if not details:
        return 0.0
    reciprocal_sum = 0.0
    for d in details:
        rank = d["rank"]
        if rank > 0:
            reciprocal_sum += 1.0 / rank
    return reciprocal_sum / len(details)


def score_keywords(answer: str, expected_keywords: list[str]) -> float:
    """Compute the fraction of expected keywords found in the answer.

    Match is case-insensitive substring search.

    Args:
        answer: The text to search within.
        expected_keywords: Keywords that should appear in the answer.

    Returns:
        Fraction of keywords found, in [0, 1].
    """
    if not expected_keywords:
        return 1.0
    answer_lower = answer.lower()
    found = sum(
        1 for kw in expected_keywords if kw.lower() in answer_lower
    )
    return found / len(expected_keywords)


def llm_judge(
    query: str, answer: str, context: str, llm: LLMProvider
) -> tuple[int, str]:
    """Use an LLM to score the answer quality on a 1-5 scale.

    Args:
        query: The original user query.
        answer: The generated answer to evaluate.
        context: Retrieved context used for the answer.
        llm: LLM provider to use for judging.

    Returns:
        A tuple of (score: int 1-5, reason: str).
    """
    prompt = (
        f"{LLM_JUDGE_PROMPT}\n\n"
        f"用户问题：{query}\n\n"
        f"检索到的上下文：\n{context}\n\n"
        f"AI 回答：\n{answer}\n\n"
        f"请根据以上信息给出评分。"
    )

    response = llm.generate(prompt)
    text = response.text.strip()

    # Try JSON parse first
    try:
        data = json.loads(text)
        score = int(data["score"])
        reason = str(data.get("reason", ""))
        return (score, reason)
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        pass

    # Fallback: regex extraction
    score_match = (
        re.search(r'"score"\s*[:=]\s*(\d)', text)
        or re.search(r"评分[：:]\s*(\d)", text)
        or re.search(r"(\d)\s*分", text)
    )
    reason_match = (
        re.search(r'"reason"\s*[:=]\s*"([^"]*)"', text)
        or re.search(r"理由[：:]\s*(.+?)(?:\n|$)", text)
    )

    score = int(score_match.group(1)) if score_match else 3
    reason = (
        reason_match.group(1).strip()
        if reason_match
        else text[:200]
    )

    # Clamp score to 1-5
    score = max(1, min(5, score))
    return (score, reason)


def summarize_details(
    details: list[EvalDetail],
    keyword_score_sum: float,
    judge_scores: list[int],
) -> EvalSummary:
    """Aggregate per-query details and scores into an EvalSummary.

    Weighted overall score:
      hit_rate 25%, avg_rank 15%, mrr 15%, keyword 15%, judge 30%.

    If any component is not applicable (e.g. no LLM judge scores),
    its weight is redistributed proportionally to the remaining components.

    Args:
        details: Per-query evaluation details.
        keyword_score_sum: Sum of keyword scores across all queries.
        judge_scores: List of LLM judge scores (1-5).

    Returns:
        Aggregated EvalSummary.
    """
    total = len(details)
    if total == 0:
        return EvalSummary(
            total=0,
            hit_rate=0.0,
            avg_rank=-1.0,
            mrr=0.0,
            keyword_score=0.0,
            llm_judge_avg=None,
            overall=0.0,
        )

    # Hit rate
    hits = sum(1 for d in details if d.hit)
    hit_rate = hits / total

    # Average rank (only valid ranks, i.e. > 0)
    ranks = [d.rank for d in details]
    valid_ranks = [r for r in ranks if r > 0]
    avg_rank = (
        sum(valid_ranks) / len(valid_ranks) if valid_ranks else -1.0
    )

    # MRR
    mrr = compute_mrr([{"rank": d.rank} for d in details])

    # Keyword score average
    keyword_score_avg = keyword_score_sum / total if total > 0 else 0.0

    # LLM judge average
    llm_judge_avg: float | None = (
        sum(judge_scores) / len(judge_scores) if judge_scores else None
    )

    # --- Weighted overall score ---
    # All components should be in [0, 1].

    hit_component = hit_rate  # already [0, 1]

    # Normalize avg_rank: 1 - (avg_rank / max_rank_cap)
    max_rank = 20
    if valid_ranks:
        max_rank = max(max_rank, max(valid_ranks))
    normalized_ranks = [
        (r if r > 0 else max_rank) / max_rank for r in ranks
    ]
    rank_component = 1.0 - (sum(normalized_ranks) / len(normalized_ranks))
    rank_component = max(0.0, rank_component)

    mrr_component = mrr  # already [0, 1]

    keyword_component = keyword_score_avg  # already [0, 1]

    # Judge: scale 1-5 → [0, 1]
    judge_component: float | None = (
        (llm_judge_avg - 1.0) / 4.0
        if llm_judge_avg is not None
        else None
    )

    weights: dict[str, float] = {
        "hit": 0.25,
        "rank": 0.15,
        "mrr": 0.15,
        "keyword": 0.15,
        "judge": 0.30,
    }
    components: dict[str, float] = {
        "hit": hit_component,
        "rank": rank_component,
        "mrr": mrr_component,
        "keyword": keyword_component,
    }

    if judge_component is not None:
        components["judge"] = judge_component
    else:
        # Redistribute judge weight proportionally
        redist = sum(w for k, w in weights.items() if k != "judge")
        if redist > 0:
            for k in weights:
                if k != "judge":
                    weights[k] += weights["judge"] * (weights[k] / redist)
        weights["judge"] = 0.0

    overall = sum(
        weights[k] * components[k] for k in components
    )

    return EvalSummary(
        total=total,
        hit_rate=round(hit_rate, 4),
        avg_rank=round(avg_rank, 2) if avg_rank > 0 else avg_rank,
        mrr=round(mrr, 4),
        keyword_score=round(keyword_score_avg, 4),
        llm_judge_avg=(
            round(llm_judge_avg, 2)
            if llm_judge_avg is not None
            else None
        ),
        overall=round(overall, 4),
    )


def compare_results(
    current: EvalResult, baseline: EvalResult
) -> dict:
    """Diff two EvalResult instances and produce a comparison report.

    Args:
        current: The newer evaluation result.
        baseline: The older evaluation result to compare against.

    Returns:
        A dict with:
        - summary_diffs: metric name → delta.
        - degraded: list of dicts with id, metric, before, after.
    """
    s_cur = current.summary
    s_base = baseline.summary

    summary_diffs: dict[str, float | None] = {
        "total": s_cur.total - s_base.total,
        "hit_rate": round(s_cur.hit_rate - s_base.hit_rate, 4),
        "avg_rank": (
            round(s_cur.avg_rank - s_base.avg_rank, 2)
            if s_cur.avg_rank > 0 and s_base.avg_rank > 0
            else None
        ),
        "mrr": round(s_cur.mrr - s_base.mrr, 4),
        "keyword_score": round(
            s_cur.keyword_score - s_base.keyword_score, 4
        ),
        "overall": round(s_cur.overall - s_base.overall, 4),
    }

    if (
        s_cur.llm_judge_avg is not None
        and s_base.llm_judge_avg is not None
    ):
        summary_diffs["llm_judge_avg"] = round(
            s_cur.llm_judge_avg - s_base.llm_judge_avg, 2
        )
    else:
        summary_diffs["llm_judge_avg"] = None

    # Build lookup of baseline details by id
    base_lookup: dict[str, EvalDetail] = {
        d.id: d for d in baseline.details
    }

    degraded: list[dict] = []
    for cur_d in current.details:
        base_d = base_lookup.get(cur_d.id)
        if base_d is None:
            continue

        # Hit degradation
        if base_d.hit and not cur_d.hit:
            degraded.append({
                "id": cur_d.id,
                "metric": "hit",
                "before": True,
                "after": False,
            })

        # Rank degradation (was found, now worse or missing)
        if base_d.rank > 0 and (
            cur_d.rank < 0 or cur_d.rank > base_d.rank
        ):
            degraded.append({
                "id": cur_d.id,
                "metric": "rank",
                "before": base_d.rank,
                "after": cur_d.rank,
            })

        # Keyword degradation (> 10% drop)
        if cur_d.keyword_score < base_d.keyword_score - 0.1:
            degraded.append({
                "id": cur_d.id,
                "metric": "keyword_score",
                "before": round(base_d.keyword_score, 4),
                "after": round(cur_d.keyword_score, 4),
            })

        # Judge score degradation
        if (
            cur_d.llm_judge is not None
            and base_d.llm_judge is not None
            and cur_d.llm_judge < base_d.llm_judge
        ):
            degraded.append({
                "id": cur_d.id,
                "metric": "llm_judge",
                "before": base_d.llm_judge,
                "after": cur_d.llm_judge,
            })

    return {
        "summary_diffs": summary_diffs,
        "degraded": degraded,
    }


# ---------------------------------------------------------------------------
# EvalEngine
# ---------------------------------------------------------------------------


class EvalEngine:
    """Orchestrates search and RAG evaluation over a query dataset."""

    def __init__(
        self,
        db: Database,
        embedding: EmbeddingProvider,
        vector_store: VectorStore,
        llm: LLMProvider | None = None,
        search_mode: str = "hybrid",
        top_k: int = 5,
        with_rag: bool = False,
    ) -> None:
        self._db = db
        self._embedding = embedding
        self._vector_store = vector_store
        self._llm = llm
        self._search_mode = search_mode
        self._top_k = top_k
        self._with_rag = with_rag

    def run(self, queries: list[dict]) -> EvalResult:
        """Run evaluation over a list of query dicts.

        For each query:
          1. Run search via _run_search.
          2. Score hit / rank against expected_source.
          3. Optionally run RAG via the LLM.
          4. Score keywords in the RAG answer.
          5. Optionally run LLM judge on the RAG answer.

        Args:
            queries: List of query dicts with at least "query" and
                     "expected_source" keys.

        Returns:
            An EvalResult with summary and per-query details.
        """
        details: list[EvalDetail] = []
        keyword_score_sum = 0.0
        judge_scores: list[int] = []

        for q in queries:
            query_text = q["query"]
            expected_source = q.get("expected_source", "")
            expected_keywords = q.get("expected_keywords", [])

            # Identify this query
            qid = q.get("id", query_text[:40])

            # 1. Search
            results = self._run_search(query_text)

            # 2. Hit & rank
            hit = score_hit(expected_source, results)
            rank = score_rank(expected_source, results)

            # 3. Format context (reused by RAG and LLM judge)
            from kb.core.rag import format_context
            context_text = format_context(results[: self._top_k], self._db)

            # 4. RAG (optional)
            answer = ""
            if self._with_rag and self._llm is not None:
                from kb.core.rag import build_rag_prompt, RAG_SYSTEM_PROMPT
                prompt = build_rag_prompt(query_text, context_text)
                response = self._llm.generate(
                    prompt, system_prompt=RAG_SYSTEM_PROMPT,
                )
                answer = response.text

            # 5. Keyword scoring
            kw_score = score_keywords(answer, expected_keywords)
            keyword_score_sum += kw_score

            # 6. LLM judge (optional)
            judge_score: int | None = None
            judge_reason: str | None = None
            if self._llm is not None and answer:
                judge_score, judge_reason = llm_judge(
                    query_text, answer, context_text, self._llm
                )
                judge_scores.append(judge_score)

            details.append(
                EvalDetail(
                    id=qid,
                    hit=hit,
                    rank=rank,
                    keyword_score=kw_score,
                    llm_judge=judge_score,
                    llm_judge_reason=judge_reason,
                )
            )

        summary = summarize_details(
            details, keyword_score_sum, judge_scores
        )

        config: dict[str, object] = {
            "search_mode": self._search_mode,
            "top_k": self._top_k,
            "with_rag": self._with_rag,
            "total_queries": len(queries),
            "llm_judge_enabled": self._llm is not None,
        }

        return EvalResult(
            timestamp=datetime.now(timezone.utc).isoformat(),
            config=config,
            summary=summary,
            details=details,
        )

    def _run_search(self, query: str) -> list[SearchResult]:
        """Dispatch to the appropriate search method based on search_mode.

        Args:
            query: The search query text.

        Returns:
            Ordered list of SearchResult.

        Raises:
            ValueError: If search_mode is unrecognized.
        """
        mode = self._search_mode.lower()
        limit = self._top_k

        if mode == "fts5":
            rows = self._db.search_fulltext(query, limit=limit)
            return [
                SearchResult(
                    file_id=row["id"],
                    title=row["title"],
                    score=1.0 / (i + 1),
                    source="fts5",
                )
                for i, row in enumerate(rows)
            ]

        if mode == "semantic":
            embed_result = self._embedding.embed(query)
            records = self._vector_store.search(
                embed_result.vector, limit=limit
            )
            results: list[SearchResult] = []
            for i, rec in enumerate(records):
                note = self._db.get_note(rec.id)
                title = note["title"] if note else rec.id
                results.append(
                    SearchResult(
                        file_id=rec.id,
                        title=title,
                        score=1.0 / (i + 1),
                        source="semantic",
                    )
                )
            return results

        if mode == "hybrid":
            return hybrid_search(
                query,
                self._db,
                self._embedding,
                self._vector_store,
                limit=limit,
            )

        raise ValueError(
            f"Unknown search_mode: {mode!r}. "
            f"Expected one of: hybrid, semantic, fts5."
        )
