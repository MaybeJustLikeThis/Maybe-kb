#!/usr/bin/env python3
"""Generate evaluation dataset from vault notes using LLM.

Standalone script -- not part of the kb package.
Run from the vault root directory.

Output: eval/dataset.json
"""

from __future__ import annotations

import json
import re
import sys
from itertools import combinations
from pathlib import Path
from random import sample as random_sample
from typing import Any

# ---------------------------------------------------------------------------
# Allow importing from the kb package (vault root)
# ---------------------------------------------------------------------------
_VAULT_ROOT = Path(__file__).resolve().parent.parent
if str(_VAULT_ROOT) not in sys.path:
    sys.path.insert(0, str(_VAULT_ROOT))

from kb.core.config import load_config
from kb.core.context import AppContext
from kb.data.storage import discover_notes, parse_markdown_file

# ---------------------------------------------------------------------------
# Prompt templates (module-level constants)
# ---------------------------------------------------------------------------

SINGLE_HOP_PROMPT = """\
You are a test dataset generator. Given a note from a knowledge base, generate {n} different questions that can be answered using the information in the note.

Note Title: {title}
Note Content:
{content}

Return only a valid JSON array of objects, each with:
- "query": the question string
- "expected_keywords": list of 3-5 key terms expected in an answer

Output format example:
[{{"query": "What is X?", "expected_keywords": ["X", "Y", "Z"]}}]

Return ONLY the JSON array, no other text."""

MULTI_HOP_PROMPT = """\
You are a test dataset generator. Given two notes from a knowledge base, generate 1 complex question that requires combining information from BOTH notes to answer correctly.

Note 1 Title: {title1}
Note 1 Content:
{content1}

Note 2 Title: {title2}
Note 2 Content:
{content2}

Return only a valid JSON object with:
- "query": the question string
- "expected_keywords": list of 3-5 key terms expected in an answer

Output format example:
{{"query": "How does X relate to Y?", "expected_keywords": ["X", "Y", "relation"]}}

Return ONLY the JSON object, no other text."""


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"(\[.*\]|\{.*\})", re.DOTALL)


def _extract_json(text: str) -> str:
    """Extract the first JSON array or object from LLM response text.

    Handles markdown code fences and stray surrounding text.
    """
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    match = _JSON_BLOCK_RE.search(text)
    if match:
        return match.group(0)
    return text


# ---------------------------------------------------------------------------
# Generation functions
# ---------------------------------------------------------------------------

def generate_single_hop(
    notes: list[dict[str, str]], llm: Any, n_per_note: int = 2
) -> list[dict[str, Any]]:
    """Generate single-hop queries from individual notes.

    Args:
        notes: List of dicts with file_id, title, content.
        llm: LLM provider with .generate(prompt) -> LLMResponse.
        n_per_note: Number of questions to generate per note.

    Returns:
        List of query dicts (without id field -- main() assigns sequential IDs).
    """
    queries: list[dict[str, Any]] = []

    for note in notes:
        title = note["title"]
        content = note["content"][:3000]
        file_id = note["file_id"]

        prompt = SINGLE_HOP_PROMPT.format(n=n_per_note, title=title, content=content)

        try:
            response = llm.generate(prompt)
            json_str = _extract_json(response.text)
            parsed = json.loads(json_str)
        except (json.JSONDecodeError, Exception) as exc:
            print(f"[WARN] Failed to generate single-hop for '{title}': {exc}")
            continue

        if not isinstance(parsed, list):
            print(
                f"[WARN] Expected JSON array for '{title}', "
                f"got {type(parsed).__name__}"
            )
            continue

        for item in parsed:
            if not isinstance(item, dict):
                continue
            queries.append({
                "query": item.get("query", ""),
                "expected_source": file_id,
                "expected_keywords": item.get("expected_keywords", []),
                "type": "single_hop",
                "difficulty": "easy",
            })

    return queries


def generate_multi_hop(
    notes: list[dict[str, str]], llm: Any, total: int = 5
) -> list[dict[str, Any]]:
    """Generate multi-hop queries from pairs of notes.

    Args:
        notes: List of dicts with file_id, title, content.
        llm: LLM provider with .generate(prompt) -> LLMResponse.
        total: Target number of multi-hop queries to generate.

    Returns:
        List of query dicts (without id field -- main() assigns sequential IDs).
    """
    if len(notes) < 2:
        print("[WARN] Not enough notes for multi-hop generation (need at least 2)")
        return []

    # Generate all pair combinations
    all_pairs = list(combinations(notes, 2))

    # Sample up to total * 3, then generate up to total
    max_pairs = total * 3
    if len(all_pairs) > max_pairs:
        pairs = random_sample(all_pairs, max_pairs)
    else:
        pairs = all_pairs

    queries: list[dict[str, Any]] = []

    for note1, note2 in pairs:
        if len(queries) >= total:
            break

        title1, content1 = note1["title"], note1["content"][:2000]
        title2, content2 = note2["title"], note2["content"][:2000]
        file_ids = [note1["file_id"], note2["file_id"]]

        prompt = MULTI_HOP_PROMPT.format(
            title1=title1,
            content1=content1,
            title2=title2,
            content2=content2,
        )

        try:
            response = llm.generate(prompt)
            json_str = _extract_json(response.text)
            parsed = json.loads(json_str)
        except (json.JSONDecodeError, Exception) as exc:
            print(
                f"[WARN] Failed to generate multi-hop for "
                f"'{title1}' + '{title2}': {exc}"
            )
            continue

        if not isinstance(parsed, dict):
            print(
                f"[WARN] Expected JSON object for "
                f"'{title1}' + '{title2}', got {type(parsed).__name__}"
            )
            continue

        queries.append({
            "query": parsed.get("query", ""),
            "expected_source": file_ids,
            "expected_keywords": parsed.get("expected_keywords", []),
            "type": "multi_hop",
            "difficulty": "hard",
        })

    return queries


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Discover vault notes, generate single/multi-hop queries, save dataset."""
    vault = Path.cwd()

    config = load_config(vault)
    ctx = AppContext.from_config(config, with_llm=True, with_embedding=False)

    try:
        # Discover and parse all notes
        note_paths = discover_notes(vault)
        if not note_paths:
            print("[WARN] No notes found in vault. Exiting.")
            return

        print(f"Found {len(note_paths)} note(s) in vault.")

        notes: list[dict[str, str]] = []
        for file_path in note_paths:
            note = parse_markdown_file(file_path, vault)
            notes.append({
                "file_id": note.file_id,
                "title": note.title,
                "content": note.content,
            })

        # Generate queries
        print("Generating single-hop queries ...")
        single_queries = generate_single_hop(notes, ctx.llm)
        print(f"  Generated {len(single_queries)} single-hop queries.")

        print("Generating multi-hop queries ...")
        multi_queries = generate_multi_hop(notes, ctx.llm)
        print(f"  Generated {len(multi_queries)} multi-hop queries.")

        all_queries = single_queries + multi_queries

        # Assign sequential IDs in "q001" format
        output_queries: list[dict[str, Any]] = []
        for i, q in enumerate(all_queries, 1):
            output_queries.append({
                "id": f"q{i:03d}",
                "query": q["query"],
                "expected_source": q["expected_source"],
                "expected_keywords": q["expected_keywords"],
                "type": q["type"],
                "difficulty": q["difficulty"],
            })

        # Write dataset
        dataset: dict[str, Any] = {"version": "1", "queries": output_queries}
        output_path = vault / "eval" / "dataset.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(dataset, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"\nDataset written: {output_path}")
        print(f"  {len(single_queries)} single-hop + {len(multi_queries)} multi-hop")
        print(f"  = {len(output_queries)} total queries")

    finally:
        ctx.close()


if __name__ == "__main__":
    main()
