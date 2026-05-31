"""CLI entry point for kb."""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from kb.core.config import load_config
from kb.core.context import AppContext
from kb.core.indexer import index_files
from kb.data.storage import parse_markdown_file, validate_vault_path
from kb.core import services
from kb.core.eval import EvalEngine, load_dataset, filter_queries, compare_results

app = typer.Typer(help="Local knowledge base CLI")
console = Console()
logger = logging.getLogger(__name__)


def _get_context(*, with_embedding: bool = False, with_llm: bool = False) -> AppContext:
    """Get AppContext for current working directory."""
    vault = Path.cwd()
    config = load_config(vault)
    return AppContext.from_config(
        config, vault=vault,
        with_embedding=with_embedding, with_llm=with_llm,
    )


@app.command()
def init(
    path: Path = typer.Option(Path("."), help="Project directory"),
    import_existing: bool = typer.Option(
        False, "--import-existing", help="Index existing .md files"
    ),
):
    """Initialize a new knowledge base project."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "notes").mkdir(exist_ok=True)
    (path / "attachments").mkdir(exist_ok=True)
    (path / ".gitignore").write_text(
        ".kb/\n__pycache__/\n*.pyc\n.pytest_cache/\n*.egg-info/\n",
        encoding="utf-8",
    )
    if not (path / "config.toml").exists():
        (path / "config.toml").write_text(
            '[general]\n'
            'vault_path = "."\n\n'
            '[search]\n'
            'max_results = 20\n\n'
            '[embedding]\n'
            'provider = "local"\n'
            'model = "BAAI/bge-small-zh-v1.5"\n\n'
            '[llm]\n'
            'provider = "ollama"\n'
            'model = "qwen2.5:7b"\n\n'
            '[rag]\n'
            'top_k = 5\n\n'
            '[server]\n'
            'host = "127.0.0.1"\n'
            'port = 8420\n'
            '# watch_dir = "~/blog/source/_posts"\n',
            encoding="utf-8",
        )

    console.print(f"[green]Initialized knowledge base at {path.resolve()}[/green]")

    if import_existing:
        ctx = _get_context(with_embedding=True)
        count, _ = index_files(path.resolve(), ctx.db, full=True, embedding_provider=ctx.embedding)
        ctx.close()
        console.print(f"[green]Indexed {count} existing notes[/green]")


@app.command("add")
def add_note(
    title: str = typer.Argument(help="Note title"),
    tags: str = typer.Option("", help="Comma-separated tags"),
    category: str = typer.Option("", help="Note category"),
    description: str = typer.Option("", help="Short description"),
    source_project: str = typer.Option(
        "manual", "--source-project", "-s",
        help="Source project (blog, agent, manual)",
    ),
    source_context: str = typer.Option(
        "", "--source-context", "-c",
        help="Source context (e.g., original URL, purpose)",
    ),
):
    """Create a new note."""
    from kb.core.ingest import ingest
    from kb.core.models import IngestRequest

    vault = Path.cwd()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    cat = category.strip() or None
    desc = description.strip() or None
    sctx = source_context.strip() or None
    config = load_config(vault)
    src_cfg = config.sources.get(source_project)

    ctx = _get_context()
    try:
        note = ingest(
            IngestRequest(
                title=title,
                content=f"# {title}\n\n",
                source_project=source_project,
                tags=tag_list,
                category=cat,
                description=desc,
                source_context=sctx,
            ),
            vault,
            ctx.db,
            source_config=src_cfg,
        )
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        ctx.close()

    console.print(f"[green]Created note:[/green] {note.file_id}")


@app.command("list")
def list_notes(
    category: str = typer.Option(None, help="Filter by category"),
    tag: str = typer.Option(None, help="Filter by tag"),
    limit: int = typer.Option(20, help="Max results"),
):
    """List notes in the knowledge base."""
    ctx = _get_context()
    rows = ctx.db.list_notes(category=category, tag=tag, limit=limit)
    ctx.close()

    if not rows:
        console.print("[dim]No notes found.[/dim]")
        return

    table = Table(title="Notes")
    table.add_column("Title", style="bold")
    table.add_column("Category", style="cyan")
    table.add_column("Tags", style="yellow")
    table.add_column("Updated", style="dim")

    for row in rows:
        table.add_row(
            row["title"],
            row["category"] or "",
            row["tags"] or "",
            row["updated_at"] or row["created_at"] or "",
        )

    console.print(table)


@app.command()
def search(
    query: str = typer.Argument(help="Search query"),
    limit: int = typer.Option(10, help="Max results"),
):
    """Full-text search across notes."""
    ctx = _get_context()
    results = ctx.db.search_fulltext(query, limit=limit)
    ctx.close()

    if not results:
        console.print("[dim]No results found.[/dim]")
        return

    for i, row in enumerate(results, 1):
        console.print(f"[bold]{i}. {row['title']}[/bold] [dim]({row['id']})[/dim]")
        if row["description"]:
            console.print(f"   {row['description']}")
        console.print()


@app.command()
def index(
    full: bool = typer.Option(False, "--full", help="Rebuild index from scratch"),
):
    """Build or update the search index."""
    vault = Path.cwd()
    config = load_config(vault)
    ctx = _get_context(with_embedding=True)

    external_sources = None
    if config.server.watch_dir:
        watch_path = Path(config.server.watch_dir).expanduser().resolve()
        if watch_path.is_dir():
            external_sources = [watch_path]

    fts5_count, vec_count = index_files(
        vault, ctx.db, full=full, embedding_provider=ctx.embedding,
        external_sources=external_sources, source_project="blog",
    )
    ctx.close()

    mode = "full rebuild" if full else "incremental update"
    console.print(f"[green]Index {mode}: {fts5_count} files indexed, {vec_count} vectors[/green]")


@app.command()
def delete(
    file_path: str = typer.Argument(help="Note file path (relative to vault)"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a note."""
    vault = Path.cwd()

    if not force:
        confirm = typer.confirm(f"Delete {file_path}?")
        if not confirm:
            raise typer.Abort()

    ctx = _get_context()
    try:
        services.delete_note(vault, ctx.db, file_path)
    except ValueError:
        console.print(f"[red]Path traversal blocked: {file_path}[/red]")
        raise typer.Exit(1)
    except FileNotFoundError:
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)
    finally:
        ctx.close()

    console.print(f"[green]Deleted: {file_path}[/green]")


@app.command()
def edit(
    file_path: str = typer.Argument(help="Note file path (relative to vault)"),
):
    """Open a note in the system's default editor."""
    vault = Path.cwd()
    try:
        full_path = validate_vault_path(vault, file_path)
    except ValueError:
        console.print(f"[red]Path traversal blocked: {file_path}[/red]")
        raise typer.Exit(1)

    if not full_path.is_file():
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)

    if sys.platform == "win32":
        import os as _os
        _os.startfile(str(full_path))
    elif sys.platform == "darwin":
        subprocess.run(["open", str(full_path)], check=False)
    else:
        subprocess.run(["xdg-open", str(full_path)], check=False)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Server host"),
    port: int = typer.Option(8420, help="Server port"),
    watch: Path | None = typer.Option(
        None, "--watch",
        help="Watch a directory for .md changes and auto-reindex",
    ),
    skip_watch: bool = typer.Option(
        False, "--skip-watch",
        help="Skip file watcher even if watch_dir is configured",
    ),
):
    """Start the web UI server."""
    import uvicorn
    vault = Path.cwd()
    config = load_config(vault)

    host = host or config.server.host
    port = port or config.server.port

    from kb.server import create_app
    web_app = create_app(config)

    observer = None
    if not skip_watch:
        watch_dir_path = watch.resolve() if watch else None
        if watch_dir_path is None and config.server.watch_dir:
            watch_dir_path = Path(config.server.watch_dir).expanduser().resolve()
        if watch_dir_path is not None:
            if not watch_dir_path.is_dir():
                console.print(
                    f"[yellow]Warning: watch directory not found: {watch_dir_path}[/yellow]"
                )
                console.print("[yellow]Skipping file watcher. API server will still start.[/yellow]")
            else:
                from kb.core.watcher import start_watcher

                ctx = _get_context(with_embedding=True)
                sources = [watch_dir_path]

                count, vec_count = index_files(
                    vault, ctx.db, full=False, embedding_provider=ctx.embedding,
                    external_sources=sources, source_project="blog",
                )
                console.print(f"[green]Initial index: {count} files, {vec_count} vectors[/green]")

                def on_change():
                    index_files(
                        vault, ctx.db, full=False, embedding_provider=ctx.embedding,
                        external_sources=sources, source_project="blog",
                    )

                observer = start_watcher(watch_dir_path, on_change, debounce_ms=200)
                console.print(f"[green]Watching {watch_dir_path} for .md changes[/green]")

    console.print(f"[green]Starting kb server at http://{host}:{port}[/green]")

    try:
        uvicorn.run(web_app, host=host, port=port, log_level="info")
    finally:
        if observer is not None:
            observer.stop()
            observer.join()


@app.command()
def migrate(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview changes without moving files"
    ),
):
    """Migrate root-level notes into category subdirectories."""
    vault = Path.cwd()
    notes_dir = vault / "notes"
    if not notes_dir.is_dir():
        console.print("[red]notes/ directory not found[/red]")
        raise typer.Exit(1)

    root_files = sorted(notes_dir.glob("*.md"))
    if not root_files:
        console.print("[dim]No root-level notes to migrate.[/dim]")
        return

    ctx = _get_context(with_embedding=True)
    try:
        moved = 0

        for src in root_files:
            try:
                note = parse_markdown_file(src, vault)
            except Exception:
                logger.warning("Failed to parse %s, skipping", src, exc_info=True)
                continue

            cat_raw = note.category or "未分类"
            cat = cat_raw.replace("/", "-").replace("\\", "-")
            slug = src.stem

            target = notes_dir / cat / src.name
            counter = 2
            while target.exists():
                target = notes_dir / cat / f"{slug}-{counter}{src.suffix}"
                counter += 1

            if dry_run:
                console.print(
                    f"[dim]Would move: {src.name} → {target.relative_to(vault).as_posix()}[/dim]"
                )
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                src.rename(target)
                console.print(
                    f"[green]Moved: {src.name} → {target.relative_to(vault).as_posix()}[/green]"
                )
            moved += 1

        if dry_run:
            console.print(f"\n[bold]Would migrate {moved} note(s).[/bold]")
            return

        console.print(f"\n[bold]Migrated {moved} note(s).[/bold]")

        count, vec_count = index_files(vault, ctx.db, full=True, embedding_provider=ctx.embedding)
        console.print(f"[green]Reindexed {count} notes, {vec_count} vectors.[/green]")
    finally:
        ctx.close()


@app.command()
def tag(
    file_path: str = typer.Argument(help="Note file path"),
    action: str = typer.Argument(help="Action: add or remove"),
    tags: str = typer.Option(..., help="Comma-separated tags"),
):
    """Add or remove tags from a note."""
    vault = Path.cwd()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    try:
        _, note = services.resolve_note(vault, file_path)
    except ValueError:
        console.print(f"[red]Path traversal blocked: {file_path}[/red]")
        raise typer.Exit(1)
    except FileNotFoundError:
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)

    if action == "add":
        existing = set(note.tags)
        new_tags = [t for t in tag_list if t not in existing]
        note.tags = [*note.tags, *new_tags]
    elif action == "remove":
        note.tags = [t for t in note.tags if t not in tag_list]
    else:
        console.print(f"[red]Unknown action: {action}. Use 'add' or 'remove'.[/red]")
        raise typer.Exit(1)

    saved = services.save_note_file(vault, note)
    ctx = _get_context()
    ctx.db.upsert_note(saved)
    ctx.close()

    console.print(f"[green]Updated tags: {saved.tags}[/green]")


@app.command()
def ask(
    query: str = typer.Argument(help="Question to ask your knowledge base"),
    top_k: int = typer.Option(5, help="Number of search results to include"),
    stream: bool = typer.Option(False, "--stream", "-s", help="Stream the response"),
):
    """Ask a question using RAG over your knowledge base."""
    from kb.core.rag import rag_query, rag_query_stream

    ctx = _get_context(with_embedding=True, with_llm=True)

    try:
        if stream:
            for chunk in rag_query_stream(query, ctx.db, ctx.embedding, ctx.vector_store, ctx.llm, top_k=top_k):
                console.print(chunk.text, end="")
            console.print()
        else:
            with console.status("[bold green]Thinking..."):
                response = rag_query(query, ctx.db, ctx.embedding, ctx.vector_store, ctx.llm, top_k=top_k)
            console.print(response.text)
    finally:
        ctx.close()


def _reconstruct_result(data: dict) -> EvalResult:
    """Reconstruct EvalResult from JSON dict for comparison."""
    from kb.core.eval import EvalResult, EvalSummary, EvalDetail

    summary_data = data["summary"]
    summary = EvalSummary(
        total=summary_data["total"],
        hit_rate=summary_data["hit_rate"],
        avg_rank=summary_data["avg_rank"],
        mrr=summary_data["mrr"],
        keyword_score=summary_data["keyword_score"],
        llm_judge_avg=summary_data.get("llm_judge_avg"),
        overall=summary_data["overall"],
    )

    details = [
        EvalDetail(
            id=d["id"],
            hit=d["hit"],
            rank=d["rank"],
            keyword_score=d["keyword_score"],
            llm_judge=d.get("llm_judge"),
            llm_judge_reason=d.get("llm_judge_reason"),
        )
        for d in data["details"]
    ]

    return EvalResult(
        timestamp=data["timestamp"],
        config=data["config"],
        summary=summary,
        details=details,
    )


@app.command("eval")
def eval_cmd(
    subset: str = typer.Option(None, "--subset", help="Filter by difficulty (easy/medium/hard)"),
    category: str = typer.Option(None, "--category", help="Filter by category path prefix"),
    search_mode: str = typer.Option("hybrid", "--search-mode", help="Search mode: hybrid, semantic, fts5"),
    top_k: int = typer.Option(5, "--top-k", help="Number of search results"),
    rag: bool = typer.Option(False, "--rag", help="Run RAG and score answers"),
    baseline: bool = typer.Option(False, "--baseline", help="Save as baseline.json"),
    compare: str = typer.Option(None, "--compare", help="Baseline name to compare against"),
):
    """Evaluate search and RAG quality against a test dataset."""
    vault = Path.cwd()

    # 1. Load dataset
    dataset_path = vault / "eval" / "dataset.json"
    if not dataset_path.is_file():
        console.print(f"[red]Dataset not found: {dataset_path}[/red]")
        raise typer.Exit(1)

    queries = load_dataset(dataset_path)

    # 2. Filter queries
    queries = filter_queries(queries, subset=subset, category=category)

    # 3. Handle empty results
    if not queries:
        console.print("[dim]No queries match the given filters.[/dim]")
        return

    # 4. Create context
    ctx = _get_context(with_embedding=True, with_llm=True)

    try:
        # 5. Create EvalEngine
        engine = EvalEngine(
            db=ctx.db,
            embedding=ctx.embedding,
            vector_store=ctx.vector_store,
            llm=ctx.llm,
            search_mode=search_mode,
            top_k=top_k,
            with_rag=rag,
        )

        # 6. Run evaluation
        result = engine.run(queries)

        # 7. Save results
        results_dir = vault / "eval" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).isoformat().replace(":", "")
        filename = f"{ts}.json"

        if baseline:
            filename = "baseline.json"
            filepath = results_dir / filename
        else:
            filepath = results_dir / filename

        filepath.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if baseline:
            console.print(f"[green]Baseline saved to {filepath}[/green]")
        else:
            console.print(f"[green]Results saved to {filepath}[/green]")

        # 8. Print summary table
        s = result.summary
        table = Table(title="Evaluation Results")
        table.add_column("Metric", style="bold")
        table.add_column("Value", style="cyan")

        table.add_row("Total Queries", str(s.total))
        table.add_row("Hit Rate", f"{s.hit_rate:.4f}")
        table.add_row("Avg Rank", f"{s.avg_rank:.2f}" if s.avg_rank > 0 else "N/A")
        table.add_row("MRR", f"{s.mrr:.4f}")
        table.add_row("Keyword Score", f"{s.keyword_score:.4f}")
        if s.llm_judge_avg is not None:
            table.add_row("LLM Judge Avg", f"{s.llm_judge_avg:.2f}")
        table.add_row("Overall", f"{s.overall:.4f}")

        console.print(table)

        # 9. Handle --compare
        if compare:
            compare_path = results_dir / f"{compare}.json"
            if not compare_path.is_file():
                console.print(f"[red]Baseline not found: {compare_path}[/red]")
            else:
                baseline_data = json.loads(compare_path.read_text(encoding="utf-8"))
                baseline_result = _reconstruct_result(baseline_data)
                diff = compare_results(result, baseline_result)

                # Print diff table
                diff_table = Table(title=f"Comparison vs {compare}")
                diff_table.add_column("Metric", style="bold")
                diff_table.add_column("Delta", style="cyan")

                for metric, delta in diff["summary_diffs"].items():
                    if delta is not None:
                        color = "green" if delta >= 0 else "red"
                        sign = "+" if delta > 0 else ""
                        diff_table.add_row(metric, f"[{color}]{sign}{delta:.4f}[/{color}]")
                    else:
                        diff_table.add_row(metric, "N/A")

                console.print(diff_table)

                # Print degraded queries
                if diff["degraded"]:
                    console.print("\n[bold yellow]Degraded Queries:[/bold yellow]")
                    deg_table = Table()
                    deg_table.add_column("ID", style="bold")
                    deg_table.add_column("Metric", style="cyan")
                    deg_table.add_column("Before")
                    deg_table.add_column("After", style="red")

                    for deg in diff["degraded"]:
                        deg_table.add_row(
                            deg["id"],
                            deg["metric"],
                            str(deg["before"]),
                            str(deg["after"]),
                        )

                    console.print(deg_table)

    finally:
        ctx.close()


@app.command()
def mcp(
    path: Path = typer.Option(
        Path.cwd(),
        help="Knowledge base project directory",
    ),
):
    """Start MCP server for Claude Code integration."""
    vault = path.resolve()
    config = load_config(vault)
    from kb.mcp_server import create_mcp_server
    server = create_mcp_server(config)
    server.run()
