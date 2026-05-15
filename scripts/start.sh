#!/usr/bin/env bash
# Start kb — backend (FastAPI) and frontend (Vite) with one command.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/.kb/logs"
mkdir -p "$LOG_DIR"

BACKEND_PORT="${KB_BACKEND_PORT:-8420}"
FRONTEND_PORT="${KB_FRONTEND_PORT:-3030}"
SKIP_WATCH="${KB_SKIP_WATCH:-}"

# ── 1. Find Python ──────────────────────────────────────────────
find_python() {
    for candidate in python3 python python3.13 python3.12 python3.11; do
        if command -v "$candidate" &>/dev/null; then
            echo "$candidate"
            return
        fi
    done
    echo ""
}

PYTHON="$(find_python)"
if [[ -z "$PYTHON" ]]; then
    echo "[kb] ERROR: Python not found in PATH" >&2
    exit 1
fi
echo "[kb] Python: $($PYTHON --version 2>&1)"

# ── 2. Verify packages ──────────────────────────────────────────
REQUIRED=("uvicorn" "fastapi" "typer" "rich")
MISSING=()
for pkg in "${REQUIRED[@]}"; do
    if ! "$PYTHON" -c "import $pkg" 2>/dev/null; then
        MISSING+=("$pkg")
    fi
done
if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "[kb] WARNING: Missing packages: ${MISSING[*]}"
    echo "[kb] Run: pip install -r requirements.txt"
fi

# ── 3. Kill stale processes on target ports ─────────────────────
free_port() {
    local port="$1"
    local pids
    pids="$(lsof -ti tcp:"$port" 2>/dev/null)" || true
    if [[ -n "$pids" ]]; then
        for pid in $pids; do
            local name
            name="$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")"
            echo "[kb] Port $port occupied by $name (PID $pid). Killing..."
            kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
        done
        sleep 0.5
    fi
}

free_port "$BACKEND_PORT"
free_port "$FRONTEND_PORT"

# ── 4. Start backend ────────────────────────────────────────────
export PYTHONPATH="$PROJECT_ROOT/src"
echo "[kb] Starting backend on port ${BACKEND_PORT}..."

BACKEND_ARGS=(-m kb.cli serve --host 127.0.0.1 --port "$BACKEND_PORT")
[[ -n "$SKIP_WATCH" ]] && BACKEND_ARGS+=(--skip-watch)

nohup "$PYTHON" "${BACKEND_ARGS[@]}" \
    > "$LOG_DIR/server.log" 2> "$LOG_DIR/server-error.log" &
BACKEND_PID=$!

# ── 5. Start frontend ───────────────────────────────────────────
echo "[kb] Starting frontend on port ${FRONTEND_PORT}..."

nohup npx vite --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort \
    > "$LOG_DIR/vite.log" 2> "$LOG_DIR/vite-error.log" &
FRONTEND_PID=$!

# ── 6. Health check ─────────────────────────────────────────────
echo "[kb] Waiting for services..."
BACKEND_UP=false
FRONTEND_UP=false
TIMEOUT=60
ELAPSED=0

while { [[ "$BACKEND_UP" == false || "$FRONTEND_UP" == false ]]; } && [[ $ELAPSED -lt $TIMEOUT ]]; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))

    if [[ "$BACKEND_UP" == false ]]; then
        if curl -s "http://127.0.0.1:${BACKEND_PORT}" &>/dev/null; then
            BACKEND_UP=true
            echo "[kb] Backend ready (${ELAPSED}s)"
        fi
    fi
    if [[ "$FRONTEND_UP" == false ]]; then
        if curl -s "http://127.0.0.1:${FRONTEND_PORT}" &>/dev/null; then
            FRONTEND_UP=true
            echo "[kb] Frontend ready (${ELAPSED}s)"
        fi
    fi

    # Check if either process died
    if [[ "$BACKEND_UP" == false ]] && ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "[kb] Backend failed to start. Check $LOG_DIR/server.log" >&2
        break
    fi
    if [[ "$FRONTEND_UP" == false ]] && ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo "[kb] Frontend failed to start. Check $LOG_DIR/vite.log" >&2
        break
    fi
done

# ── 7. Report ────────────────────────────────────────────────────
if [[ "$BACKEND_UP" == true && "$FRONTEND_UP" == true ]]; then
    echo ""
    echo "  kb is running!"
    echo "  Frontend : http://127.0.0.1:${FRONTEND_PORT}"
    echo "  Backend  : http://127.0.0.1:${BACKEND_PORT}"
    echo "  Logs     : $LOG_DIR"
    echo ""
elif [[ "$BACKEND_UP" == true ]]; then
    echo "[kb] Backend running, frontend did not start." >&2
elif [[ "$FRONTEND_UP" == true ]]; then
    echo "[kb] Frontend running, backend did not start." >&2
else
    echo "[kb] Neither service started. Check logs in $LOG_DIR" >&2
    exit 1
fi
