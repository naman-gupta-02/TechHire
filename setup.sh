#!/usr/bin/env bash
set -e

# ── colours ───────────────────────────────────────────────────────────────────
GREEN="\033[0;32m"; YELLOW="\033[0;33m"; RED="\033[0;31m"; NC="\033[0m"
info()    { echo -e "${GREEN}[TechHire]${NC} $*"; }
warn()    { echo -e "${YELLOW}[TechHire]${NC} $*"; }
die()     { echo -e "${RED}[TechHire] ERROR:${NC} $*"; exit 1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ── prerequisites ─────────────────────────────────────────────────────────────
command -v python3 >/dev/null 2>&1 || die "python3 not found — install Python 3.11+"
command -v node    >/dev/null 2>&1 || die "node not found — install Node.js 18+"
command -v npm     >/dev/null 2>&1 || die "npm not found"
command -v docker  >/dev/null 2>&1 || die "docker not found — install Docker Desktop"

MODE="${1:-start}"   # setup | start | scrape | stop

# ── .env setup ────────────────────────────────────────────────────────────────
setup_env() {
    if [ ! -f "$ROOT/.env" ]; then
        warn ".env not found — creating from template"
        cat > "$ROOT/.env" <<'ENV'
DATABASE_URL=postgresql://techhire:localdev@localhost:5433/techhire_db
GROQ_API_KEY=your_groq_api_key_here
ENV
        warn "Edit .env and add your GROQ_API_KEY (free at console.groq.com), then re-run."
    else
        info ".env already exists — skipping"
    fi
}

# ── Python venv + deps ────────────────────────────────────────────────────────
setup_python() {
    if [ ! -d "$ROOT/.venv" ]; then
        info "Creating Python virtual environment..."
        python3 -m venv "$ROOT/.venv"
    fi
    info "Installing Python dependencies..."
    "$ROOT/.venv/bin/pip" install --quiet --upgrade pip
    "$ROOT/.venv/bin/pip" install --quiet -r "$ROOT/requirements.txt"
    info "Python deps installed"
}

# ── Node deps ─────────────────────────────────────────────────────────────────
setup_node() {
    info "Installing frontend dependencies..."
    npm --prefix "$ROOT/frontend" install --silent
    info "Node deps installed"
}

# ── Docker (Postgres) ─────────────────────────────────────────────────────────
start_db() {
    info "Starting Postgres (Docker)..."
    docker compose up -d ddb
    info "Waiting for Postgres to be ready..."
    for i in $(seq 1 20); do
        docker exec techhire_db pg_isready -U techhire -q 2>/dev/null && break
        sleep 2
    done
    docker exec techhire_db pg_isready -U techhire -q || die "Postgres did not start in time"
    info "Postgres is ready"
}

# ── DB tables ─────────────────────────────────────────────────────────────────
init_db() {
    info "Initialising database tables..."
    "$ROOT/.venv/bin/python3" -c "
from db.session import init_db
from db.models import JobListing
init_db()
import sqlalchemy
from db.session import engine
with engine.connect() as conn:
    conn.execute(sqlalchemy.text('ALTER TABLE job_listings ADD COLUMN IF NOT EXISTS ai_summary TEXT'))
    conn.execute(sqlalchemy.text('ALTER TABLE job_listings ADD COLUMN IF NOT EXISTS start_date_text VARCHAR(100)'))
    conn.commit()
print('Tables ready')
"
    info "Database ready"
}

# ── API server ────────────────────────────────────────────────────────────────
start_api() {
    info "Starting API server on http://localhost:8000 ..."
    "$ROOT/.venv/bin/uvicorn" api:app --reload --port 8000 &
    API_PID=$!
    echo $API_PID > "$ROOT/.api.pid"
    sleep 2
    curl -sf http://localhost:8000/health > /dev/null || die "API failed to start"
    info "API running (PID $API_PID)"
}

# ── Frontend dev server ───────────────────────────────────────────────────────
start_frontend() {
    info "Starting frontend on http://localhost:5173 ..."
    npm --prefix "$ROOT/frontend" run dev &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$ROOT/.frontend.pid"
    info "Frontend running (PID $FRONTEND_PID)"
}

# ── scraper ───────────────────────────────────────────────────────────────────
run_scraper() {
    info "Running scraper (this takes a few minutes)..."
    "$ROOT/.venv/bin/python3" -m scraper.runner
    info "Scrape complete"
}

stop_all() {
    info "Stopping servers..."
    [ -f "$ROOT/.api.pid"      ] && kill "$(cat "$ROOT/.api.pid")"      2>/dev/null; rm -f "$ROOT/.api.pid"
    [ -f "$ROOT/.frontend.pid" ] && kill "$(cat "$ROOT/.frontend.pid")" 2>/dev/null; rm -f "$ROOT/.frontend.pid"
    docker compose stop ddb 2>/dev/null || true
    info "All stopped"
}

# ── modes ─────────────────────────────────────────────────────────────────────
case "$MODE" in
    setup)
        info "=== First-time setup ==="
        setup_env
        setup_python
        setup_node
        start_db
        init_db
        info ""
        info "Setup complete! Next steps:"
        info "  1. Edit .env and set your GROQ_API_KEY"
        info "  2. Run:  bash setup.sh scrape   # fetch jobs (first time)"
        info "  3. Run:  bash setup.sh start    # start the app"
        ;;

    start)
        info "=== Starting TechHire ==="
        start_db
        start_api
        start_frontend
        info ""
        info "TechHire is running!"
        info "  Frontend → http://localhost:5173"
        info "  API      → http://localhost:8000"
        info ""
        info "Press Ctrl+C to stop"
        trap stop_all INT TERM
        wait
        ;;

    scrape)
        info "=== Running scraper ==="
        start_db
        run_scraper
        ;;

    stop)
        stop_all
        ;;

    *)
        echo "Usage: bash setup.sh [setup|start|scrape|stop]"
        echo ""
        echo "  setup   — first-time: install deps, create .env, init DB"
        echo "  start   — start API + frontend (DB must already be running)"
        echo "  scrape  — fetch jobs from all sources and save to DB"
        echo "  stop    — kill API, frontend, and DB"
        exit 1
        ;;
esac
