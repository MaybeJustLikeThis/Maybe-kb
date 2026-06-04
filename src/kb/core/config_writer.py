"""Focused, comment-preserving updates for top-level TOML sections."""
from __future__ import annotations

import json
import os
import re
import tempfile
import tomllib
from pathlib import Path

TomlValue = str | bool

_SECTION_RE = re.compile(r"^\s*\[([^\[\]]+)\]\s*(?:#.*)?$")
_TABLE_RE = re.compile(r"^\s*\[\[?[^\[\]]+\]?\]\s*(?:#.*)?$")
_KEY_VALUE_RE = re.compile(
    r"^(\s*)((?:\"(?:\\.|[^\"\\])*\"|'[^']*'|[A-Za-z0-9_-]+))(\s*)=(.*)$"
)
_ASSIGNMENT_RE = re.compile(r"^(\s*)(.+?)(\s*)=(.*)$")


def _render_value(value: TomlValue) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"Unsupported TOML value: {type(value).__name__}")


def _find_inline_comment(value: str) -> str:
    quote = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quote == '"' and char == "\\":
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
            continue
        if char == "#" and quote is None:
            return value[index:].rstrip()
    return ""


def _section_bounds(lines: list[str], section: str) -> tuple[int, int] | None:
    start = None
    for index, line in enumerate(lines):
        match = _SECTION_RE.match(line)
        if match and match.group(1).strip() == section:
            start = index
            break
    if start is None:
        return None

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if _TABLE_RE.match(lines[index]):
            end = index
            break
    return start, end


def _toml_key_name(token: str) -> str | None:
    try:
        parsed = tomllib.loads(f"{token} = true")
    except tomllib.TOMLDecodeError:
        return None
    if len(parsed) != 1:
        return None
    key = next(iter(parsed))
    return key if isinstance(key, str) else None


def _key_token(name: str) -> str:
    if re.match(r"^[A-Za-z0-9_-]+$", name):
        return name
    return json.dumps(name, ensure_ascii=False)


def _single_toml_path(data: dict) -> list[str] | None:
    path: list[str] = []
    current = data
    while isinstance(current, dict) and len(current) == 1:
        key = next(iter(current))
        if not isinstance(key, str):
            return None
        path.append(key)
        current = current[key]
    return path if current is True else None


def _top_level_dotted_path(key_expr: str, section: str) -> list[str] | None:
    try:
        parsed = tomllib.loads(f"{key_expr} = true")
    except tomllib.TOMLDecodeError:
        return None
    path = _single_toml_path(parsed)
    if path is None or len(path) < 2 or path[0] != section:
        return None
    return path[1:]


def _normalize_top_level_dotted_section(
    lines: list[str],
    section: str,
    updates: dict[str, TomlValue],
) -> None:
    moved: list[tuple[str, str]] = []
    for index, line in enumerate(lines):
        if _TABLE_RE.match(line):
            break
        match = _ASSIGNMENT_RE.match(line)
        if match is None:
            continue
        key_path = _top_level_dotted_path(match.group(2).strip(), section)
        if key_path is None:
            continue
        key_expr = ".".join(_key_token(part) for part in key_path)
        if len(key_path) == 1 and key_path[0] in updates:
            value = updates[key_path[0]]
            comment = _find_inline_comment(match.group(4))
            suffix = f" {comment}" if comment else ""
            moved.append((key_path[0], f"{key_expr} = {_render_value(value)}{suffix}"))
        else:
            moved.append(("", f"{key_expr} = {match.group(4).lstrip()}"))
        lines[index] = ""

    if not moved:
        return

    bounds = _section_bounds(lines, section)
    if bounds is None:
        insertion = len(lines)
        lines[insertion:insertion] = [
            f"[{section}]",
            *(line for _key, line in moved),
            "",
        ]
    else:
        start, _end = bounds
        lines[start + 1:start + 1] = [line for _key, line in moved]

    for key_name, _line in moved:
        if key_name:
            updates.pop(key_name, None)


def _update_section(lines: list[str], section: str, updates: dict[str, TomlValue]) -> None:
    updates = dict(updates)
    _normalize_top_level_dotted_section(lines, section, updates)
    bounds = _section_bounds(lines, section)
    if bounds is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([f"[{section}]", *(f"{key} = {_render_value(value)}" for key, value in updates.items())])
        return

    start, end = bounds
    missing = dict(updates)
    for index in range(start + 1, end):
        line = lines[index]
        match = _KEY_VALUE_RE.match(line)
        if match is None:
            continue
        key_name = _toml_key_name(match.group(2))
        if key_name not in missing:
            continue
        comment = _find_inline_comment(match.group(4))
        suffix = f" {comment}" if comment else ""
        lines[index] = (
            f"{match.group(1)}{match.group(2)}{match.group(3)}= "
            f"{_render_value(missing[key_name])}{suffix}"
        )
        del missing[key_name]

    if missing:
        insertion = end
        while insertion > start + 1 and not lines[insertion - 1].strip():
            insertion -= 1
        lines[insertion:insertion] = [
            f"{key} = {_render_value(value)}" for key, value in missing.items()
        ]


def render_toml_sections(
    config_path: Path,
    updates: dict[str, dict[str, TomlValue]],
) -> str:
    """Render selected section updates without writing the file."""
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    had_trailing_newline = text.endswith("\n")
    lines = text.splitlines()

    for section, section_updates in updates.items():
        _update_section(lines, section, section_updates)

    rendered = "\n".join(lines)
    if rendered and (had_trailing_newline or not text):
        rendered += "\n"
    tomllib.loads(rendered)
    return rendered


def write_toml_text(config_path: Path, rendered: str) -> None:
    """Atomically write TOML text after validating it."""
    tomllib.loads(rendered)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        dir=config_path.parent,
        prefix=f".{config_path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as temp_file:
            temp_file.write(rendered)
        os.replace(temp_name, config_path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def update_toml_sections(
    config_path: Path,
    updates: dict[str, dict[str, TomlValue]],
) -> None:
    """Update selected keys while preserving unrelated TOML text."""
    write_toml_text(config_path, render_toml_sections(config_path, updates))
