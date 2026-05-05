"""CLI entry point for kb."""
import typer

app = typer.Typer(help="Local knowledge base CLI")


@app.command()
def hello():
    """Test command to verify CLI works."""
    typer.echo("kb is ready!")


@app.command()
def version():
    """Show kb version."""
    from kb import __version__
    typer.echo(f"kb {__version__}")
