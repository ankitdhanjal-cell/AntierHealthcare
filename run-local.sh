#!/usr/bin/env bash
# Runs everything locally, no Docker: Postgres (bundled), Redis, API, Celery worker, web.
# Requires: python3, node 20+, redis-server.  Usage: ./run-local.sh   (stop with ./stop-local.sh)
set -e
cd "$(dirname "$0")"
./stop-local.sh >/dev/null 2>&1 || true; sleep 1
DATA=$HOME/.ahs-local; mkdir -p "$DATA/logs"

cd backend
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt pgserver
export DATABASE_URL=$(.venv/bin/python local_db.py)
export REDIS_URL=redis://localhost:6389/0
export PUBLIC_WEB_URL=http://localhost:3010
set -a; [ -f ../.env ] && . ../.env; set +a   # picks up OPENAI_API_KEY / SMTP_*
redis-cli -p 6389 ping >/dev/null 2>&1 || redis-server --port 6389 --daemonize yes --dir "$DATA" >/dev/null
.venv/bin/python -m app.seed --if-empty
nohup .venv/bin/uvicorn app.main:app --port 8010 > "$DATA/logs/api.log" 2>&1 &
echo $! > "$DATA/api.pid"
nohup .venv/bin/celery -A app.celery_app worker --beat --loglevel=info > "$DATA/logs/worker.log" 2>&1 &
echo $! > "$DATA/worker.pid"

cd ../web
[ -d node_modules ] || npm install --no-audit --no-fund
[ -d .next ] || npm run build
echo "Open http://localhost:3010   (logs: $DATA/logs)"
API_INTERNAL_URL=http://localhost:8010 npx next start -p 3010
