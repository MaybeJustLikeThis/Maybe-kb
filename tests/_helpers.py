"""Small shared helpers for the test suite."""
from __future__ import annotations

import re

_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences (color/style codes) from text.

    Rich/typer render ``--help`` with ANSI styling that splits tokens like
    ``--host`` across escape sequences, so ``"--host" in stdout`` fails under
    a color-capable terminal. Strip before asserting on rendered CLI output.
    """
    return _ANSI.sub("", text)
