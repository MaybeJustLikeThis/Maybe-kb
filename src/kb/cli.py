"""CLI entry point for kb."""
from __future__ import annotations

import filecmp
import json
import logging
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from kb.core.config import load_config
from kb.core.config_writer import render_toml_sections, write_toml_text
from kb.core.context import AppContext
from kb.core.import_file import ImportFileError
from kb.core.indexer import index_files
from kb.data.storage import parse_markdown_file, validate_vault_path
from kb.core import services
from kb.core.eval import EvalEngine, load_dataset, filter_queries, compare_results

app = typer.Typer(help="Local knowledge base CLI")
obsidian_app = typer.Typer(help="Obsidian vault operations")
app.add_typer(obsidian_app, name="obsidian")
console = Console()
logger = logging.getLogger(__name__)


def _get_project_config(project_path: Path | None = None):
    """Load config from the project directory, defaulting to the current directory."""
    project = (project_path or Path.cwd()).resolve()
    return load_config(project)


def _get_context(
    *,
    with_embedding: bool = False,
    with_llm: bool = False,
    project_path: Path | None = None,
) -> AppContext:
    """Get AppContext from a project config without overriding its vault."""
    config = _get_project_config(project_path)
    return AppContext.from_config(
        config,
        with_embedding=with_embedding, with_llm=with_llm,
    )


def _index_context(ctx: AppContext, *, full: bool) -> tuple[int, int]:
    return index_files(
        ctx.vault,
        ctx.db,
        full=full,
        embedding_provider=ctx.embedding,
        notes_dir=ctx.notes_dir,
        attachments_dir=ctx.attachments_dir,
        index_dir=ctx.index_dir,
    )


@app.command()
def init(
    path: Path = typer.Option(Path("."), help="Project directory"),
    import_existing: bool = typer.Option(
        False, "--import-existing", help="Index existing .md files"
    ),
):
    """Initialize a new knowledge base project."""
    project_path = path.resolve()
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / ".gitignore").write_text(
        ".kb/\n__pycache__/\n*.pyc\n.pytest_cache/\n*.egg-info/\n",
        encoding="utf-8",
    )
    if not (project_path / "config.toml").exists():
        (project_path / "config.toml").write_text(
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

    config = _get_project_config(project_path)
    config.notes_path.mkdir(parents=True, exist_ok=True)
    config.attachments_path.mkdir(parents=True, exist_ok=True)

    console.print(f"[green]Initialized knowledge base at {project_path}[/green]")

    if import_existing:
        ctx = _get_context(with_embedding=True, project_path=project_path)
        try:
            count, _ = _index_context(ctx, full=True)
        finally:
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
    from kb.data.models import IngestRequest

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    cat = category.strip() or None
    desc = description.strip() or None
    sctx = source_context.strip() or None
    ctx = _get_context()
    src_cfg = ctx.config.sources.get(source_project) if ctx.config else None
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
            ctx.vault,
            ctx.db,
            source_config=src_cfg,
            notes_dir=ctx.notes_dir,
        )
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        ctx.close()

    console.print(f"[green]Created note:[/green] {note.file_id}")


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
    ctx = _get_context(with_embedding=True)
    try:
        fts5_count, vec_count = _index_context(ctx, full=full)
    finally:
        ctx.close()

    mode = "full rebuild" if full else "incremental update"
    console.print(f"[green]Index {mode}: {fts5_count} files indexed, {vec_count} vectors[/green]")


@app.command()
def delete(
    file_path: str = typer.Argument(help="Note file path (relative to vault)"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a note."""
    if not force:
        confirm = typer.confirm(f"Delete {file_path}?")
        if not confirm:
            raise typer.Abort()

    ctx = _get_context()
    try:
        services.delete_note(ctx.vault, ctx.db, file_path)
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
    vault = _get_project_config().vault_path
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
        help="Skip the file watcher even if watching is enabled",
    ),
):
    """Start the web UI server."""
    import uvicorn
    config = _get_project_config()

    host = host or config.server.host
    port = port or config.server.port

    from kb.server import create_app
    web_app = create_app(config)

    observer = None
    ctx = None
    if not skip_watch:
        watch_dir_path = watch.resolve() if watch else None
        if watch_dir_path is None and config.server.watch_enabled:
            watch_dir_path = config.notes_path.resolve()
        if watch_dir_path is not None:
            if not watch_dir_path.is_dir():
                console.print(
                    f"[yellow]Warning: watch directory not found: {watch_dir_path}[/yellow]"
                )
                console.print("[yellow]Skipping file watcher. API server will still start.[/yellow]")
            else:
                from kb.core.watcher import start_watcher

                ctx = _get_context(with_embedding=True)
                count, vec_count = _index_context(ctx, full=False)
                console.print(f"[green]Initial index: {count} files, {vec_count} vectors[/green]")

                def on_change():
                    _index_context(ctx, full=False)

                observer = start_watcher(watch_dir_path, on_change, debounce_ms=200)
                console.print(f"[green]Watching {watch_dir_path} for .md changes[/green]")

    console.print(f"[green]Starting kb server at http://{host}:{port}[/green]")

    try:
        uvicorn.run(web_app, host=host, port=port, log_level="info")
    finally:
        if observer is not None:
            observer.stop()
            observer.join()
        if ctx is not None:
            ctx.close()


@app.command()
def migrate(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview changes without moving files"
    ),
):
    """Migrate root-level notes into category subdirectories."""
    config = _get_project_config()
    notes_dir = config.notes_path
    if not notes_dir.is_dir():
        console.print(f"[red]Configured notes directory not found: {notes_dir}[/red]")
        raise typer.Exit(1)

    root_files = sorted(notes_dir.glob("*.md"))
    if not root_files:
        console.print("[dim]No root-level notes to migrate.[/dim]")
        return

    ctx = _get_context(with_embedding=True)
    vault = ctx.vault
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
                    f"[dim]Would move: {src.name} -> {target.relative_to(vault).as_posix()}[/dim]"
                )
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                src.rename(target)
                console.print(
                    f"[green]Moved: {src.name} -> {target.relative_to(vault).as_posix()}[/green]"
                )
            moved += 1

        if dry_run:
            console.print(f"\n[bold]Would migrate {moved} note(s).[/bold]")
            return

        console.print(f"\n[bold]Migrated {moved} note(s).[/bold]")

        count, vec_count = _index_context(ctx, full=True)
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
    ctx = _get_context()
    vault = ctx.vault
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    try:
        _, note = services.resolve_note(vault, file_path)
    except ValueError:
        ctx.close()
        console.print(f"[red]Path traversal blocked: {file_path}[/red]")
        raise typer.Exit(1)
    except FileNotFoundError:
        ctx.close()
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)

    if action == "add":
        existing = set(note.tags)
        new_tags = [t for t in tag_list if t not in existing]
        note.tags = [*note.tags, *new_tags]
    elif action == "remove":
        note.tags = [t for t in note.tags if t not in tag_list]
    else:
        ctx.close()
        console.print(f"[red]Unknown action: {action}. Use 'add' or 'remove'.[/red]")
        raise typer.Exit(1)

    saved = services.save_note_file(vault, note)
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


def _ensure_directory_available(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ValueError(f"Conflicting destination path: {path}")


def _ensure_destination_parents_available(root: Path, destination_file: Path) -> None:
    parent = destination_file.parent
    stop = root.parent
    while True:
        if parent.exists() and not parent.is_dir():
            raise ValueError(f"Conflicting destination path: {parent}")
        if parent == stop:
            break
        next_parent = parent.parent
        if next_parent == parent:
            break
        parent = next_parent


def _ensure_target_outside_sources(target: Path, sources: list[Path]) -> None:
    for source in sources:
        if target == source or target.is_relative_to(source):
            raise ValueError(f"Target vault must not be inside source directory: {source}")


def _copy_planned_files(copies: list[tuple[Path, Path]]) -> None:
    created: list[Path] = []
    try:
        for source_file, destination_file in copies:
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            created.append(destination_file)
            shutil.copy2(source_file, destination_file)
    except Exception:
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        raise


def _build_copy_plan(source: Path, destination: Path) -> tuple[list[tuple[Path, Path]], int]:
    if not source.is_dir():
        raise ValueError(f"Source directory not found: {source}")
    _ensure_directory_available(destination)

    copies: list[tuple[Path, Path]] = []
    unchanged = 0
    for source_file in sorted(path for path in source.rglob("*") if path.is_file()):
        relative = source_file.relative_to(source)
        if ".kb" in relative.parts:
            continue
        destination_file = destination / relative
        _ensure_destination_parents_available(destination, destination_file)
        if destination_file.exists():
            if not destination_file.is_file() or not filecmp.cmp(
                source_file,
                destination_file,
                shallow=False,
            ):
                raise ValueError(f"Conflicting destination file: {destination_file}")
            unchanged += 1
            continue
        copies.append((source_file, destination_file))
    return copies, unchanged


@obsidian_app.command("init-vault")
def obsidian_init_vault(
    target: Path = typer.Option(..., "--target", help="New Obsidian vault path"),
    from_notes: Path = typer.Option(..., "--from-notes", help="Existing notes directory"),
    from_attachments: Path = typer.Option(
        ...,
        "--from-attachments",
        help="Existing attachments directory",
    ),
    skip_index: bool = typer.Option(
        False,
        "--skip-index",
        help="Skip rebuilding the knowledge index",
    ),
):
    """Copy existing knowledge into a safe Obsidian vault and update config."""
    project_path = Path.cwd().resolve()
    target_path = target.expanduser().resolve()
    notes_source = from_notes.expanduser().resolve()
    attachments_source = from_attachments.expanduser().resolve()
    config_path = project_path / "config.toml"
    target_posix = target_path.as_posix()
    config_updates = {
        "general": {
            "vault_path": target_posix,
            "notes_dir": "notes",
            "attachments_dir": "attachments",
            "index_dir": ".kb",
        },
        "obsidian": {
            "enabled": True,
            "vault_name": target_path.name,
            "vault_path": target_posix,
            "open_uri_strategy": "file",
        },
    }

    try:
        _ensure_target_outside_sources(target_path, [notes_source, attachments_source])
        _ensure_directory_available(target_path)
        _ensure_directory_available(target_path / "notes")
        _ensure_directory_available(target_path / "attachments")
        _ensure_directory_available(target_path / ".obsidian")
        note_copies, unchanged_notes = _build_copy_plan(
            notes_source,
            target_path / "notes",
        )
        attachment_copies, unchanged_attachments = _build_copy_plan(
            attachments_source,
            target_path / "attachments",
        )
        rendered_config = render_toml_sections(config_path, config_updates)
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    target_path.mkdir(parents=True, exist_ok=True)
    (target_path / "notes").mkdir(parents=True, exist_ok=True)
    (target_path / "attachments").mkdir(parents=True, exist_ok=True)
    (target_path / ".obsidian").mkdir(parents=True, exist_ok=True)

    copies = [*note_copies, *attachment_copies]
    try:
        _copy_planned_files(copies)
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    write_toml_text(config_path, rendered_config)

    indexed = None
    if not skip_index:
        ctx = _get_context(with_embedding=True, project_path=project_path)
        try:
            indexed = _index_context(ctx, full=True)
        finally:
            ctx.close()

    unchanged = unchanged_notes + unchanged_attachments
    console.print(f"[green]Obsidian vault ready at {target_path}[/green]")
    console.print(
        f"[green]Copied {len(copies)} files; {unchanged} identical files unchanged.[/green]"
    )
    console.print(f"[green]Updated {config_path}[/green]")
    if indexed is not None:
        console.print(
            f"[green]Indexed {indexed[0]} notes, {indexed[1]} vectors.[/green]"
        )
    else:
        console.print("[yellow]Skipped index rebuild.[/yellow]")


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
    project_path = Path.cwd()

    # 1. Load dataset
    dataset_path = project_path / "eval" / "dataset.json"
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
        results_dir = project_path / "eval" / "results"
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
    project_path = path.resolve()
    config = _get_project_config(project_path)
    from kb.mcp_server import create_mcp_server
    server = create_mcp_server(config)
    server.run()
