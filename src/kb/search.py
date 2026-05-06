"""Hybrid search with Reciprocal Rank Fusion (FTS5 + semantic)."""
from __future__ import annotations

from dataclasses import dataclass

from kb.indexer import Database
from kb.embedding import EmbeddingProvider
from kb.vector import VectorStore


@dataclass(frozen=True)
class SearchResult:
    file_id: str
    title: str
    score: float
    source: str  # "fts5" | "semantic" | "hybrid"


def hybrid_search(
    query: str,
    db: Database,
    provider: EmbeddingProvider,
    store: VectorStore,
    limit: int = 20,
    rrf_k: int = 60,
) -> list[SearchResult]:
    """FTS5 + semantic search with Reciprocal Rank Fusion.

    1. Run both searches (each gets limit*2 candidates)
    2. For each result, compute RRF score: 1 / (k + rank)
    3. If a note appears in both result sets, sum its RRF scores
    4. Sort by fused score descending, return top 'limit'
    """
    fts5_rows = db.search_fulltext(query, limit=limit * 2)
    embed_result = provider.embed(query)
    semantic_records = store.search(embed_result.vector, limit=limit * 2)

    fused: dict[str, float] = {}
    sources: dict[str, str] = {}

    for rank, row in enumerate(fts5_rows):
        fid = row["id"]
        fused[fid] = fused.get(fid, 0.0) + 1.0 / (rrf_k + rank + 1)
        sources[fid] = "hybrid" if fid in sources else "fts5"

    for rank, rec in enumerate(semantic_records):
        fused[rec.id] = fused.get(rec.id, 0.0) + 1.0 / (rrf_k + rank + 1)
        sources[rec.id] = "hybrid" if rec.id in sources else "semantic"

    sorted_ids = sorted(fused, key=lambda k: fused[k], reverse=True)[:limit]

    results: list[SearchResult] = []
    for fid in sorted_ids:
        note = db.get_note(fid)
        if note is None:
            continue
        results.append(SearchResult(
            file_id=fid,
            title=note["title"],
            score=fused[fid],
            source=sources[fid],
        ))
    return results
