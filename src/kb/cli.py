"""CLI entry point for kb."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from kb.indexer import Database
from kb.models import Note
from kb.storage import discover_notes, parse_markdown_file, write_markdown_file

app = typer.Typer(help="Local knowledge base CLI")
console = Console()


def _get_db() -> Database:
    """Get database instance for current project."""
    vault = Path.cwd()
    db_path = vault / ".kb" / "kb.db"
    db = Database(db_path)
    db.initialize()
    return db


def _index_files(vault: Path, db: Database, full: bool = False) -> int:
    """Index notes into database. Returns number of files indexed."""
    existing = {} if full else db.get_all_hashes()
    files = discover_notes(vault)
    indexed = 0

    for f in files:
        try:
            note = parse_markdown_file(f, vault)
        except Exception:
            continue

        if not full and existing.get(note.file_id) == note.file_hash:
            continue

        db.upsert_note(note)
        indexed += 1

    # Remove deleted files from index
    current_ids = {f.relative_to(vault).as_posix() for f in files}
    for file_id in list(existing.keys()):
        if file_id not in current_ids:
            db.delete_note(file_id)

    return indexed


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
            '[general]\nvault_path = "."\n\n[search]\nmax_results = 20\n',
            encoding="utf-8",
        )

    console.print(f"[green]Initialized knowledge base at {path.resolve()}[/green]")

    if import_existing:
        db = _get_db()
        count = _index_files(path.resolve(), db, full=True)
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
    now = datetime.now().isoformat(timespec="seconds")

    slug = title.lower().replace(" ", "-")[:50]
    # All notes live under notes/ directory
    file_path = f"notes/{cat}/{slug}.md" if cat else f"notes/{slug}.md"

    note = Note(
        file_id=file_path,
        title=title,
        tags=tag_list,
        category=cat,
        description=description or None,
        content=f"# {title}\n\n",
        created_at=now,
        updated_at=now,
    )

    full_path = vault / file_path
    write_markdown_file(full_path, note)

    # Auto-index the new note
    db = _get_db()
    parsed = parse_markdown_file(full_path, vault)
    db.upsert_note(parsed)
    db.close()

    console.print(f"[green]Created note:[/green] {file_path}")


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
    db = _get_db()
    count = _index_files(vault, db, full=full)
    db.close()

    mode = "full rebuild" if full else "incremental update"
    console.print(f"[green]Index {mode}: {count} files indexed[/green]")


@app.command()
def delete(
    file_path: str = typer.Argument(help="Note file path (relative to vault)"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a note."""
    vault = Path.cwd()
    full_path = vault / file_path

    if not full_path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Delete {file_path}?")
        if not confirm:
            raise typer.Abort()

    full_path.unlink()

    # file_id is path relative to vault
    db = _get_db()
    db.delete_note(file_path)
    db.close()

    console.print(f"[green]Deleted: {file_path}[/green]")


@app.command()
def tag(
    file_path: str = typer.Argument(help="Note file path"),
    action: str = typer.Argument(help="Action: add or remove"),
    tags: str = typer.Option(..., help="Comma-separated tags"),
):
    """Add or remove tags from a note."""
    vault = Path.cwd()
    full_path = vault / file_path

    if not full_path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)

    note = parse_markdown_file(full_path, vault)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    if action == "add":
        for t in tag_list:
            if t not in note.tags:
                note.tags.append(t)
    elif action == "remove":
        note.tags = [t for t in note.tags if t not in tag_list]
    else:
        console.print(f"[red]Unknown action: {action}. Use 'add' or 'remove'.[/red]")
        raise typer.Exit(1)

    note.updated_at = datetime.now().isoformat(timespec="seconds")
    write_markdown_file(full_path, note)

    db = _get_db()
    db.upsert_note(note)
    db.close()

    console.print(f"[green]Updated tags: {note.tags}[/green]")
