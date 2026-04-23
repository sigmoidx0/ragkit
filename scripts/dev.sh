#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cleanup() {
  echo ""
  echo "Stopping..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup INT TERM

echo "[backend] starting..."
cd "$ROOT/server"
bash run.sh &
BACKEND_PID=$!

echo "[frontend] starting..."
cd "$ROOT/admin"
npm run dev &
FRONTEND_PID=$!

echo "[dev] backend PID=$BACKEND_PID, frontend PID=$FRONTEND_PID"
echo "[dev] press Ctrl+C to stop"
wait
