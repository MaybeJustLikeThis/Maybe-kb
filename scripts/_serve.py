"""Thin wrapper to start kb serve — used by start.ps1 / start.sh."""
import sys
from pathlib import Path

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Reconstruct argv: sys.argv[0] is this script's path,
# remaining args are the CLI subcommand and flags.
if len(sys.argv) > 1:
    sys.argv = ["kb"] + sys.argv[1:]
else:
    sys.argv = ["kb", "serve"]

from kb.cli import app
app()
