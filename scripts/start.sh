#!/usr/bin/env bash
# =============================================================================
# Tootak — single Linux/macOS entrypoint.
#
# Running this script once installs everything that is needed and starts the
# full service (transcription API + /live websocket + /realtime streaming),
# all served by the unified ASGI app `api.app.server:app`.
#
# Everything is configurable through arguments — run with --help for the list.
# =============================================================================
set -Eeuo pipefail

# ----------------------------- defaults --------------------------------------
HOST_NAME="${HOST_NAME:-0.0.0.0}"
PORT="${PORT:-${APP_PORT:-8030}}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LOCAL_MODEL_ID="${LOCAL_MODEL_ID:-}"
APP_MODULE="api.app.server:app"

NO_START=0
SKIP_PACKAGE_INSTALL=0
SKIP_FFMPEG_INSTALL=0
SKIP_TESTS=0
SKIP_SMOKE_TESTS=0
PRELOAD_MODEL=0
USE_RELOAD=1
NO_PAUSE="${TOOTAK_NO_PAUSE:-0}"
EXTRA_ENV=()
UVICORN_EXTRA=()

usage() {
  cat <<'EOF'
Tootak Linux/macOS launcher — installs all dependencies and starts every service.

Usage: ./scripts/start.sh [options] [-- <extra uvicorn args>]

Network:
  -h, --host <addr>        Bind address (default: 0.0.0.0 = reachable on LAN)
      --lan                Shortcut for --host 0.0.0.0
      --local              Shortcut for --host 127.0.0.1
  -p, --port <port>        Port (default: $APP_PORT or 8030)

Runtime:
      --python <bin>       Python interpreter to bootstrap the venv (default: python3)
      --local-model-id <id>  Set LOCAL_MODEL_ID (e.g. tiny|small|medium|large-v3)
      --preload-model      Download/warm the local faster-whisper model during setup
      --reload             Enable uvicorn auto-reload (default)
      --no-reload          Disable uvicorn auto-reload
  -e, --env KEY=VALUE      Export an extra environment variable (repeatable)

Setup control:
      --no-start           Run full setup + checks but do not start the server
      --skip-package-install
      --skip-ffmpeg-install
      --skip-tests
      --skip-smoke-tests
      --no-pause           Never wait for Enter on exit
  --help                   Show this help

Any arguments after `--` are passed straight to uvicorn.
Other settings (API keys, LIVE_*, DEEPGRAM_API_KEY, ...) live in .env — copy
.env.example and edit, or pass them with -e KEY=VALUE.
EOF
}

# ----------------------------- arg parsing -----------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--host) HOST_NAME="$2"; shift 2 ;;
    --lan) HOST_NAME="0.0.0.0"; shift ;;
    --local) HOST_NAME="127.0.0.1"; shift ;;
    -p|--port) PORT="$2"; shift 2 ;;
    --python) PYTHON_BIN="$2"; shift 2 ;;
    --local-model-id) LOCAL_MODEL_ID="$2"; shift 2 ;;
    --preload-model) PRELOAD_MODEL=1; shift ;;
    --reload) USE_RELOAD=1; shift ;;
    --no-reload) USE_RELOAD=0; shift ;;
    -e|--env) EXTRA_ENV+=("$2"); shift 2 ;;
    --no-start) NO_START=1; shift ;;
    --skip-package-install) SKIP_PACKAGE_INSTALL=1; shift ;;
    --skip-ffmpeg-install) SKIP_FFMPEG_INSTALL=1; shift ;;
    --skip-tests) SKIP_TESTS=1; shift ;;
    --skip-smoke-tests) SKIP_SMOKE_TESTS=1; shift ;;
    --no-pause) NO_PAUSE=1; shift ;;
    --help) usage; exit 0 ;;
    --) shift; UVICORN_EXTRA=("$@"); break ;;
    *) echo "Unknown argument: $1" >&2; echo "Run with --help for usage." >&2; exit 2 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

log(){  printf '\033[1;32m[tootak]\033[0m %s\n' "$*"; }
warn(){ printf '\033[1;33m[tootak]\033[0m %s\n' "$*"; }
fail(){ printf '\033[1;31m[tootak]\033[0m %s\n' "$*" >&2; exit 1; }

pause_before_exit(){
  local code="$1"; local reason="${2:-Script stopped}"
  if [[ "$NO_PAUSE" == "1" || ! -t 0 ]]; then return; fi
  if [[ "$code" != "0" ]]; then
    echo; echo "${reason}. Press Enter to close this window..."; read -r _ || true
  fi
}
on_error(){ local code="$?"; pause_before_exit "$code" "Script failed"; exit "$code"; }
trap on_error ERR

# ----------------------------- python ----------------------------------------
command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "Python not found: $PYTHON_BIN. Install Python 3.10+ first."
"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' \
  || fail "Python 3.10+ is required (found $("$PYTHON_BIN" --version 2>&1))."

# ----------------------------- ffmpeg ----------------------------------------
if [[ "$SKIP_FFMPEG_INSTALL" -eq 0 ]]; then
  if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
    warn "ffmpeg/ffprobe not found. Trying apt, dnf, yum, pacman, or brew."
    if command -v apt-get >/dev/null 2>&1; then sudo apt-get update && sudo apt-get install -y ffmpeg
    elif command -v dnf >/dev/null 2>&1; then sudo dnf install -y ffmpeg ffmpeg-free || sudo dnf install -y ffmpeg
    elif command -v yum >/dev/null 2>&1; then sudo yum install -y ffmpeg
    elif command -v pacman >/dev/null 2>&1; then sudo pacman -Sy --noconfirm ffmpeg
    elif command -v brew >/dev/null 2>&1; then brew install ffmpeg
    else fail "Could not auto-install ffmpeg. Install ffmpeg and ffprobe manually, then rerun (or use --skip-ffmpeg-install)."
    fi
  else
    log "ffmpeg/ffprobe already available."
  fi
else
  warn "Skipping ffmpeg install (--skip-ffmpeg-install)."
fi

# ----------------------------- venv + deps -----------------------------------
[[ -x .venv/bin/python ]] || { log "Creating virtual environment (.venv)"; "$PYTHON_BIN" -m venv .venv; }
# shellcheck disable=SC1091
source .venv/bin/activate

if [[ "$SKIP_PACKAGE_INSTALL" -eq 0 ]]; then
  log "Upgrading pip and installing requirements"
  python -m pip install --upgrade pip
  pip install -r requirements.txt
else
  warn "Skipping package install (--skip-package-install)."
fi

# ----------------------------- config + dirs ---------------------------------
[[ -f .env ]] || { log "Creating .env from .env.example"; cp .env.example .env; }
[[ -f config/config.yml ]] || { log "Creating config/config.yml from example"; mkdir -p config; cp config/config.example.yml config/config.yml; }
mkdir -p runtime/models runtime/uploads runtime/outputs runtime/cache runtime/checkpoints runtime/logs runtime/smoke

# ----------------------------- environment -----------------------------------
export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export APP_HOST="$HOST_NAME"
export APP_PORT="$PORT"
[[ -n "$LOCAL_MODEL_ID" ]] && export LOCAL_MODEL_ID="$LOCAL_MODEL_ID"
for kv in "${EXTRA_ENV[@]:-}"; do
  [[ -z "$kv" ]] && continue
  [[ "$kv" == *=* ]] || fail "Bad -e value (expected KEY=VALUE): $kv"
  export "${kv?}"
  log "env: ${kv%%=*} set"
done

# ----------------------------- optional model preload ------------------------
if [[ "$PRELOAD_MODEL" -eq 1 ]]; then
  log "Preloading local faster-whisper model (this can take a while on first run)"
  python - <<'PY'
import os
from api.app.config import get_settings
from faster_whisper import WhisperModel
s = get_settings()
model_id = os.getenv("LOCAL_MODEL_ID") or s.local.model_id
print(f"[tootak] preparing model: {model_id}")
WhisperModel(model_id, device="cpu", compute_type="int8", download_root=s.storage.model_dir)
print("[tootak] local model ready")
PY
fi

# ----------------------------- tests -----------------------------------------
if [[ "$SKIP_TESTS" -eq 0 ]]; then
  log "Running test suite"
  pytest -q
else
  warn "Skipping tests (--skip-tests)."
fi

# ----------------------------- smoke test ------------------------------------
if [[ "$SKIP_SMOKE_TESTS" -eq 0 ]]; then
  log "Running smoke test against a temporary server"
  TMP_PORT=$((PORT + 17))
  python -m uvicorn "$APP_MODULE" --host 127.0.0.1 --port "$TMP_PORT" > runtime/logs/smoke.log 2>&1 &
  SERVER_PID=$!
  cleanup(){ kill "$SERVER_PID" >/dev/null 2>&1 || true; }
  trap cleanup EXIT
  ok=0
  for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${TMP_PORT}/health" >/dev/null 2>&1; then ok=1; break; fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then break; fi
    sleep 1
  done
  [[ "$ok" -eq 1 ]] || { tail -80 runtime/logs/smoke.log >&2 || true; fail "Smoke server did not become healthy"; }
  for ep in /providers /realtime /live; do
    curl -fsS "http://127.0.0.1:${TMP_PORT}${ep}" >/dev/null || { tail -80 runtime/logs/smoke.log >&2 || true; fail "Smoke check failed for ${ep}"; }
  done
  log "Smoke test passed (/health /providers /realtime /live)."
  cleanup
  trap - EXIT
  trap on_error ERR
else
  warn "Skipping smoke tests (--skip-smoke-tests)."
fi

# ----------------------------- start -----------------------------------------
if [[ "$NO_START" -eq 1 ]]; then
  log "Setup complete. Not starting because --no-start was passed."
  exit 0
fi

log "Starting Tootak on ${HOST_NAME}:${PORT} (module: ${APP_MODULE})"
if [[ "$HOST_NAME" == "0.0.0.0" ]]; then
  LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  [[ -n "${LAN_IP:-}" ]] && log "LAN:   http://${LAN_IP}:${PORT}/"
fi
log "Local: http://127.0.0.1:${PORT}/      (panel)"
log "       http://127.0.0.1:${PORT}/lab   (lab)"
log "       http://127.0.0.1:${PORT}/live  (live)"
log "       http://127.0.0.1:${PORT}/realtime (realtime)"
log "Press Ctrl+C to stop."

RUN_ARGS=(-m uvicorn "$APP_MODULE" --host "$HOST_NAME" --port "$PORT")
[[ "$USE_RELOAD" -eq 1 ]] && RUN_ARGS+=(--reload)
[[ "${#UVICORN_EXTRA[@]}" -gt 0 ]] && RUN_ARGS+=("${UVICORN_EXTRA[@]}")
set +e
python "${RUN_ARGS[@]}"
status=$?
set -e
[[ "$status" != "0" ]] && pause_before_exit "$status" "Server stopped or failed"
exit "$status"
