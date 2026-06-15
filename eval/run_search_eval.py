#!/usr/bin/env python3
"""Quick search eval with manual dataset (corrected paths)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb.core.config import load_config
from kb.core.context import AppContext
from kb.core.eval import EvalEngine

DATASET = {
    "version": "1",
    "queries": [
        {
            "id": "q001",
            "query": "ARIMA模型是什么",
            "expected_source": "notes/量化金融/arima模型与向量自回归（var）.md",
            "expected_keywords": ["ARIMA", "自回归", "移动平均"],
            "difficulty": "easy",
        },
        {
            "id": "q002",
            "query": "ETS指数平滑模型",
            "expected_source": "notes/量化金融/ets指数平滑状态空间模型.md",
            "expected_keywords": ["ETS", "指数平滑", "状态空间"],
            "difficulty": "easy",
        },
        {
            "id": "q003",
            "query": "Agent工程化 ReAct",
            "expected_source": "notes/AI/Agent工程化（一）从React到Harness.md",
            "expected_keywords": ["ReAct", "Harness", "Agent"],
            "difficulty": "easy",
        },
        {
            "id": "q004",
            "query": "MCP Server搭建踩坑",
            "expected_source": "notes/AI/mcp-server-搭建踩坑记录.md",
            "expected_keywords": ["MCP", "Server", "搭建"],
            "difficulty": "easy",
        },
        {
            "id": "q005",
            "query": "为什么选LanceDB作为向量存储",
            "expected_source": "notes/未分类/选择-lancedb-作为向量存储的设计决策.md",
            "expected_keywords": ["LanceDB", "向量", "存储"],
            "difficulty": "easy",
        },
        {
            "id": "q006",
            "query": "TypeScript类型体操",
            "expected_source": "notes/技术/typescript-类型体操实战.md",
            "expected_keywords": ["TypeScript", "类型"],
            "difficulty": "easy",
        },
        {
            "id": "q007",
            "query": "Rust所有权和借用检查",
            "expected_source": "notes/编程语言/rust-所有权与借用检查.md",
            "expected_keywords": ["Rust", "所有权", "借用"],
            "difficulty": "easy",
        },
        {
            "id": "q008",
            "query": "Python内存泄漏Celery OOM",
            "expected_source": "notes/未分类/python-内存泄漏排查：celery-worker-oom-问题.md",
            "expected_keywords": ["Python", "内存泄漏", "OOM", "Celery"],
            "difficulty": "easy",
        },
        {
            "id": "q009",
            "query": "React学习笔记",
            "expected_source": ["notes/前端/react学习日记(三).md", "notes/前端/react学习日记(二期).md", "notes/前端/react学习日记.md"],
            "expected_keywords": ["React"],
            "difficulty": "easy",
        },
        {
            "id": "q010",
            "query": "时间序列分解X11 STL",
            "expected_source": "notes/量化金融/时间序列分解：x11与stl.md",
            "expected_keywords": ["X11", "STL", "时间序列"],
            "difficulty": "easy",
        },
    ],
}


def main():
    config = load_config(Path("."))
    ctx = AppContext.from_config(config, with_llm=False, with_embedding=True)

    queries = DATASET["queries"]

    engine = EvalEngine(
        db=ctx.db,
        embedding=ctx.embedding,
        vector_store=ctx.vector_store,
        search_mode="hybrid",
        top_k=10,
        with_rag=False,
    )

    result = engine.run(queries)

    print(f"\n=== Search Eval Results (After Optimization) ===")
    print(f"Total queries: {result.summary.total}")
    print(f"Hit rate: {result.summary.hit_rate:.2%}")
    print(f"MRR: {result.summary.mrr:.4f}")
    print(f"Avg rank: {result.summary.avg_rank:.2f}")
    print(f"Overall: {result.summary.overall:.4f}")

    print(f"\n=== Per-Query Details ===")
    for d in result.details:
        status = "HIT" if d.hit else "MISS"
        print(f"  [{status}] {d.id} — rank={d.rank}")

    # Save results
    output = {
        "timestamp": result.timestamp,
        "summary": {
            "total": result.summary.total,
            "hit_rate": result.summary.hit_rate,
            "mrr": result.summary.mrr,
            "avg_rank": result.summary.avg_rank,
            "overall": result.summary.overall,
        },
        "details": [
            {"id": d.id, "hit": d.hit, "rank": d.rank}
            for d in result.details
        ],
    }
    out_path = Path("eval/results/search_eval_after.json")
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResults saved to {out_path}")

    ctx.close()


if __name__ == "__main__":
    main()
