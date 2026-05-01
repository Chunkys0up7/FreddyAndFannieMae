#!/usr/bin/env bash
# Stop all local services started by run-local.sh.
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d .pids ]; then
  echo "no .pids/ directory — nothing to stop"
  exit 0
fi

for pidfile in .pids/*.pid; do
  [ -f "$pidfile" ] || continue
  name="$(basename "$pidfile" .pid)"
  pid="$(cat "$pidfile")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "==> stopping $name (pid $pid)"
    kill "$pid" 2>/dev/null
    sleep 0.5
    kill -9 "$pid" 2>/dev/null || true
  else
    echo "==> $name not running"
  fi
  rm -f "$pidfile"
done

# Belt-and-braces: also kill any orphaned child processes by name.
pkill -9 -f "uvicorn agent.server:app" 2>/dev/null || true
pkill -9 -f "pipeline.api"             2>/dev/null || true
pkill -9 -f "chroma run"               2>/dev/null || true
pkill -9 -f "next dev"                 2>/dev/null || true

echo "all stopped"
