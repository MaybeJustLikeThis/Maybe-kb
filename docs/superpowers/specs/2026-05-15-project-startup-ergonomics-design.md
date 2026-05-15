# Project Startup Ergonomics

**Date:** 2026-05-15
**Status:** implemented

## Problem

Starting kb requires multiple manual steps every time:
- Python not on PATH, need full path
- PYTHONPATH=src must be set manually
- SentenceTransformer model loads slowly from HF Hub
- watch_dir absence crashes the server
- Frontend + backend need separate terminals and commands
- Port conflicts cause hard failures

## Design

### 1. Unified startup scripts

`scripts/start.ps1` (Windows) and `scripts/start.sh` (macOS/Linux):

1. Auto-detect Python (walk common install paths)
2. Verify required packages, prompt install if missing
3. Kill stale processes on ports 8420 / 3030
4. Start backend (`kb serve`) in background, log to `.kb/logs/server.log`
5. Start frontend (`vite dev`) in background, log to `.kb/logs/vite.log`
6. Health-check both ports, print URL when ready
7. `-OpenBrowser` flag to auto-open browser

### 2. Graceful watch_dir handling

`cli.py serve`: watch_dir missing → `[yellow] Warning[/yellow]`, skip watcher, continue starting API.
New `--skip-watch` flag for explicit dev-mode skip.

### 3. Logging

Both services log to `.kb/logs/` (already gitignored).

### 4. Documentation

Update README.md and USER_GUIDE.md with the new startup flow.

### Future: Docker Compose (方案 B)

When project stabilizes, add `docker-compose.yml` with pre-built model volume.
