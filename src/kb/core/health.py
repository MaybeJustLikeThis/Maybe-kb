"""Read-only system health checks for setup readiness."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from kb.core.context import AppContext


HealthStatus = Literal["ready", "warning", "error"]


def _check(
    check_id: str,
    label: str,
    status: HealthStatus,
    message: str,
    action: str | None = None,
) -> dict:
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "message": message,
        "action": action,
    }


def _overall_status(checks: list[dict]) -> HealthStatus:
    if any(check["status"] == "error" for check in checks):
        return "error"
    if any(check["status"] == "warning" for check in checks):
        return "warning"
    return "ready"


def _database_path(ctx: AppContext) -> Path:
    return ctx.vault / ctx.index_dir / "kb.db"


def _vector_store_path(ctx: AppContext) -> Path:
    return ctx.vault / ctx.index_dir / "vectors.lance"


def _note_count(ctx: AppContext) -> int:
    if not _database_path(ctx).exists():
        return 0
    try:
        return ctx.db.count_notes()
    except Exception:
        return 0


def _vector_count(ctx: AppContext) -> int:
    vector_path = _vector_store_path(ctx)
    if ctx.vector_store is None or not vector_path.exists():
        return 0
    try:
        return ctx.vector_store.count()
    except Exception:
        return 0


def get_system_health(ctx: AppContext) -> dict:
    """Return setup readiness without initializing external providers."""
    notes_count = _note_count(ctx)
    vectors_count = _vector_count(ctx)
    coverage = 1.0 if notes_count == 0 else (1.0 if vectors_count > 0 else 0.0)

    notes_path = ctx.vault / ctx.notes_dir
    attachments_path = ctx.vault / ctx.attachments_dir
    index_path = ctx.vault / ctx.index_dir
    vault_ready = ctx.vault.is_dir()

    checks = [
        _check(
            "vault",
            "Vault",
            "ready" if vault_ready else "error",
            "Vault is initialized" if vault_ready else "Vault is not initialized",
            None if vault_ready else "Run kb init or check config.toml",
        ),
        _check(
            "notes_dir",
            "Notes directory",
            "ready" if notes_path.is_dir() else "error",
            "Notes directory exists" if notes_path.is_dir() else "Notes directory is missing",
            None if notes_path.is_dir() else "Create notes directory",
        ),
        _check(
            "attachments_dir",
            "Attachments directory",
            "ready" if attachments_path.is_dir() else "warning",
            (
                "Attachments directory exists"
                if attachments_path.is_dir()
                else "Attachments directory is missing"
            ),
            None if attachments_path.is_dir() else "Create attachments directory",
        ),
        _check(
            "index_dir",
            "Index directory",
            "ready" if index_path.is_dir() else "warning",
            "Index directory exists" if index_path.is_dir() else "Index directory is missing",
            None if index_path.is_dir() else "Rebuild index",
        ),
        _check(
            "fulltext_index",
            "Full-text index",
            "ready",
            f"{notes_count} note records indexed",
        ),
        _check(
            "vector_index",
            "Vector index",
            "ready" if coverage > 0 else "warning",
            f"{vectors_count} vectors indexed" if coverage > 0 else "No vectors indexed yet",
            None if coverage > 0 else "Rebuild index",
        ),
    ]

    config = ctx.config
    obsidian = config.obsidian if config else None
    obsidian_path = obsidian.vault_path if obsidian and obsidian.vault_path else ctx.vault
    obsidian_ready = bool(obsidian and obsidian.enabled and obsidian_path.is_dir())
    checks.append(_check(
        "obsidian",
        "Obsidian",
        "ready" if obsidian_ready else "warning",
        (
            "Obsidian vault is configured"
            if obsidian_ready
            else "Obsidian integration is not ready"
        ),
        None if obsidian_ready else "Check Obsidian config",
    ))
    checks.append(_check(
        "embedding_config",
        "Embedding provider",
        "ready" if config and config.embedding else "warning",
        (
            "Embedding provider is configured"
            if config and config.embedding
            else "Embedding provider is not configured"
        ),
        None if config and config.embedding else "Configure embedding",
    ))
    checks.append(_check(
        "llm_config",
        "LLM provider",
        "ready" if config and config.llm else "warning",
        "LLM provider is configured" if config and config.llm else "LLM provider is not configured",
        None if config and config.llm else "Configure LLM",
    ))

    if config and config.sources:
        for name, source in config.sources.items():
            checks.append(_check(
                f"source:{name}",
                source.label or name,
                "ready",
                source.description or "Source is configured",
            ))

    return {
        "status": _overall_status(checks),
        "checks": checks,
        "summary": {
            "notes_count": notes_count,
            "vectors_count": vectors_count,
            "coverage": coverage,
        },
    }
