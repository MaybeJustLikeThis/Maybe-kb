"""CLI entry point for kb."""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from kb.data.database import Database, _index_vectors
from kb.core.config import load_config
from kb.data.embedding import create_embedding_provider
from kb.data.storage import discover_notes, parse_markdown_file, validate_vault_path
from kb.core import services

app = typer.Typer(help="Local knowledge base CLI")
console = Console()
logger = logging.getLogger(__name__)


def _get_db() -> Database:
    """Get database instance for current project."""
    vault = Path.cwd()
    db_path = vault / ".kb" / "kb.db"
    db = Database(db_path)
    db.initialize()
    return db


def _index_files(
    vault: Path,
    db: Database,
    full: bool = False,
    embedding_provider: "EmbeddingProvider | None" = None,
) -> tuple[int, int]:
    """Index notes into database. Returns (fts5_count, vector_count)."""
    all_hashes = db.get_all_hashes()
    existing = {} if full else all_hashes
    files = discover_notes(vault)
    changed_ids: set[str] = set()
    indexed = 0

    for f in files:
        try:
            note = parse_markdown_file(f, vault)
        except Exception:
            logger.warning("Failed to parse %s, skipping", f, exc_info=True)
            continue

        fid = note.file_id
        if not full and existing.get(fid) == note.file_hash:
            continue

        db.upsert_note(note)
        indexed += 1
        changed_ids.add(fid)

    # Remove deleted files from index
    current_ids = {f.relative_to(vault).as_posix() for f in files}
    for file_id in all_hashes:
        if file_id not in current_ids:
            db.delete_note(file_id)
            changed_ids.add(file_id)

    vector_count = 0
    if embedding_provider is not None:
        vector_count = _index_vectors(vault, db, embedding_provider, changed_ids)

    return indexed, vector_count


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
            'port = 8420\n',
            encoding="utf-8",
        )

    console.print(f"[green]Initialized knowledge base at {path.resolve()}[/green]")

    if import_existing:
        db = _get_db()
        config = load_config(path.resolve())
        provider = create_embedding_provider(config.embedding)
        count, _ = _index_files(path.resolve(), db, full=True, embedding_provider=provider)
        db.close()
        console.print(f"[green]Indexed {count} existing notes[/green]")


@app.command("add")
def add_note(
    title: str = typer.Argument(help="Note title"),
    tags: str = typer.Option("", help="Comma-separated tags"),
    category: str = typer.Option("", help="Note category"),
    description: str = typer.Option("", help="Short description"),
):
    """Create a new note."""
    vault = Path.cwd()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    cat = category if category else None

    db = _get_db()
    try:
        note = services.create_note(
            vault, db, title, f"# {title}\n\n",
            cat, tag_list, description or None,
        )
    except ValueError:
        console.print("[red]Path traversal blocked in note path[/red]")
        raise typer.Exit(1)
    finally:
        db.close()

    console.print(f"[green]Created note:[/green] {note.file_id}")


@app.command("list")
def list_notes(
    category: str = typer.Option(None, help="Filter by category"),
    tag: str = typer.Option(None, help="Filter by tag"),
    limit: int = typer.Option(20, help="Max results"),
):
    """List notes in the knowledge base."""
    db = _get_db()
    rows = db.list_notes(category=category, tag=tag, limit=limit)
    db.close()

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
    db = _get_db()
    results = db.search_fulltext(query, limit=limit)
    db.close()

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
    db = _get_db()
    provider = create_embedding_provider(config.embedding)
    fts5_count, vec_count = _index_files(vault, db, full=full, embedding_provider=provider)
    db.close()

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

    db = _get_db()
    try:
        services.delete_note(vault, db, file_path)
    except ValueError:
        console.print(f"[red]Path traversal blocked: {file_path}[/red]")
        raise typer.Exit(1)
    except FileNotFoundError:
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)
    finally:
        db.close()

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
):
    """Start the web UI server."""
    import uvicorn
    vault = Path.cwd()
    config = load_config(vault)

    host = host or config.server.host
    port = port or config.server.port

    from kb.server import create_app
    web_app = create_app(config)

    console.print(f"[green]Starting kb server at http://{host}:{port}[/green]")
    uvicorn.run(web_app, host=host, port=port, log_level="info")


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
    db = _get_db()
    db.upsert_note(saved)
    db.close()

    console.print(f"[green]Updated tags: {saved.tags}[/green]")


@app.command()
def ask(
    query: str = typer.Argument(help="Question to ask your knowledge base"),
    top_k: int = typer.Option(5, help="Number of search results to include"),
    stream: bool = typer.Option(False, "--stream", "-s", help="Stream the response"),
):
    """Ask a question using RAG over your knowledge base."""
    vault = Path.cwd()
    config = load_config(vault)

    from kb.core.rag import rag_query, rag_query_stream
    from kb.data.llm import create_llm_provider
    from kb.data.vector import VectorStore

    db = _get_db()
    provider = create_embedding_provider(config.embedding)
    llm = create_llm_provider(config.llm)
    store = VectorStore(vault / ".kb" / "vectors.lance")

    try:
        if stream:
            for chunk in rag_query_stream(query, db, provider, store, llm, top_k=top_k):
                console.print(chunk.text, end="")
            console.print()
        else:
            with console.status("[bold green]Thinking..."):
                response = rag_query(query, db, provider, store, llm, top_k=top_k)
            console.print(response.text)
    finally:
        store.close()
        db.close()


@app.command()
def mcp():
    """Start MCP server for Claude Code integration."""
    vault = Path.cwd()
    config = load_config(vault)
    from kb.mcp_server import create_mcp_server
    server = create_mcp_server(config)
    server.run()
