#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Start Retail Voice locally (macOS / Linux).
#
#   ./scripts/dev.sh            # install if needed, then run both servers
#   ./scripts/dev.sh --reseed   # rebuild the demo database first
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RESEED=false
for arg in "$@"; do
  case "$arg" in
    --reseed) RESEED=true ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

step() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }

# ------------------------------------------------------------------ backend --
if [ ! -d .venv ]; then
  step 'Creating the Python virtual environment'
  python3 -m venv .venv
fi

step 'Installing backend dependencies'
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet -r backend/requirements.txt

if [ "$RESEED" = true ]; then
  step 'Rebuilding the demo database'
  (cd backend && ../.venv/bin/python -m app.db.seed --reset)
fi

# ----------------------------------------------------------------- frontend --
if [ ! -d frontend/node_modules ]; then
  step 'Installing frontend dependencies'
  npm --prefix frontend install
fi

# ------------------------------------------------------------------- launch --
cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

step 'Starting the API on http://localhost:8000'
(cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000) &

sleep 2

step 'Starting the web app on http://localhost:5173'
npm --prefix frontend run dev &

cat <<'BANNER'

  Retail Voice is running.

    Web app    http://localhost:5173
    API docs   http://localhost:8000/docs

  Demo accounts (password shown):
    customer@retailvoice.ai    Demo@1234
    agent1@retailvoice.ai      Demo@1234
    admin@retailvoice.ai       Admin@123

  Ctrl-C stops both servers.

BANNER

wait
