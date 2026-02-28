#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY_ENV_MODE="${PY_ENV_MODE:-conda}"
CONDA_ENV="${CONDA_ENV:-quarkagent}"
VENV_PATH="${VENV_PATH:-.venv}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
USE_LOCAL_PROXY="${USE_LOCAL_PROXY:-0}"

if [[ "$VENV_PATH" != /* ]]; then
  VENV_PATH="$ROOT_DIR/$VENV_PATH"
fi

if [[ "$USE_LOCAL_PROXY" == "1" ]]; then
  export https_proxy="http://127.0.0.1:1088"
  export http_proxy="http://127.0.0.1:1088"
  export all_proxy="socks5://127.0.0.1:1088"
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[dev-web] npm not found. Please install Node.js."
  exit 1
fi

if [[ ! -d "$ROOT_DIR/frontend" ]]; then
  echo "[dev-web] frontend directory not found."
  exit 1
fi

if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "[dev-web] Installing frontend dependencies..."
  (
    cd "$ROOT_DIR/frontend"
    npm install
  )
fi

run_backend() {
  if [[ "$PY_ENV_MODE" == "conda" ]]; then
    if ! command -v conda >/dev/null 2>&1; then
      echo "[dev-web] conda not found. Set PY_ENV_MODE=venv or install conda."
      exit 1
    fi
    conda run -n "$CONDA_ENV" uvicorn app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT"
    return
  fi

  if [[ "$PY_ENV_MODE" == "venv" ]]; then
    if [[ ! -x "$VENV_PATH/bin/python" ]]; then
      echo "[dev-web] venv python not found: $VENV_PATH/bin/python"
      echo "[dev-web] Create it first (example): python -m venv .venv"
      exit 1
    fi
    "$VENV_PATH/bin/python" -m uvicorn app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT"
    return
  fi

  if [[ "$PY_ENV_MODE" == "auto" ]]; then
    if command -v conda >/dev/null 2>&1; then
      conda run -n "$CONDA_ENV" uvicorn app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT"
      return
    fi

    if [[ -x "$VENV_PATH/bin/python" ]]; then
      "$VENV_PATH/bin/python" -m uvicorn app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT"
      return
    fi

    echo "[dev-web] No Python runtime found."
    echo "[dev-web] Tried conda and venv path: $VENV_PATH"
    exit 1
  fi

  echo "[dev-web] Unsupported PY_ENV_MODE: $PY_ENV_MODE"
  echo "[dev-web] Allowed values: conda, venv, auto"
  exit 1
}

validate_backend_runtime() {
  if [[ "$PY_ENV_MODE" == "conda" ]]; then
    if ! command -v conda >/dev/null 2>&1; then
      echo "[dev-web] conda not found. Set PY_ENV_MODE=venv or install conda."
      exit 1
    fi
    return
  fi

  if [[ "$PY_ENV_MODE" == "venv" ]]; then
    if [[ ! -x "$VENV_PATH/bin/python" ]]; then
      echo "[dev-web] venv python not found: $VENV_PATH/bin/python"
      echo "[dev-web] Create it first (example): python -m venv .venv"
      exit 1
    fi
    return
  fi

  if [[ "$PY_ENV_MODE" == "auto" ]]; then
    if command -v conda >/dev/null 2>&1; then
      return
    fi

    if [[ -x "$VENV_PATH/bin/python" ]]; then
      return
    fi

    echo "[dev-web] No Python runtime found."
    echo "[dev-web] Tried conda and venv path: $VENV_PATH"
    exit 1
  fi

  echo "[dev-web] Unsupported PY_ENV_MODE: $PY_ENV_MODE"
  echo "[dev-web] Allowed values: conda, venv, auto"
  exit 1
}

validate_backend_runtime

echo "[dev-web] Starting backend on http://${BACKEND_HOST}:${BACKEND_PORT}"
(
  cd "$ROOT_DIR"
  run_backend
) &
BACKEND_PID=$!

echo "[dev-web] Starting frontend on http://${FRONTEND_HOST}:${FRONTEND_PORT}"
(
  cd "$ROOT_DIR/frontend"
  VITE_API_BASE_URL="http://${BACKEND_HOST}:${BACKEND_PORT}" npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

cleanup() {
  echo "[dev-web] Shutting down services..."
  kill "$BACKEND_PID" "$FRONTEND_PID" >/dev/null 2>&1 || true
  wait "$BACKEND_PID" "$FRONTEND_PID" >/dev/null 2>&1 || true
}

trap cleanup INT TERM EXIT

while true; do
  if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    echo "[dev-web] Backend exited."
    exit 1
  fi

  if ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    echo "[dev-web] Frontend exited."
    exit 1
  fi

  sleep 1
done
