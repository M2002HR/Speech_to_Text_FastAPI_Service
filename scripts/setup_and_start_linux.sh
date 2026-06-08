#!/usr/bin/env bash
set -Eeuo pipefail

HOST_NAME="${HOST_NAME:-127.0.0.1}"
PORT="${PORT:-8030}"
NO_START=0
SKIP_PACKAGE_INSTALL=0
SKIP_TESTS=0
SKIP_SMOKE_TESTS=0
PYTHON_BIN="${PYTHON_BIN:-python3}"
LOCAL_MODEL_ID="${LOCAL_MODEL_ID:-tiny}"
NO_PAUSE="${TOOTAK_NO_PAUSE:-0}"

pause_before_exit(){
  local code="$1"
  local reason="${2:-Script stopped}"
  if [[ "$NO_PAUSE" == "1" || ! -t 0 ]]; then return; fi
  if [[ "$code" != "0" ]]; then
    echo
    echo "${reason}. Press Enter to close this window..."
    read -r _ || true
  fi
}

on_error(){
  local code="$?"
  pause_before_exit "$code" "Script failed"
  exit "$code"
}
trap on_error ERR

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host|-h) HOST_NAME="$2"; shift 2 ;;
    --port|-p) PORT="$2"; shift 2 ;;
    --python) PYTHON_BIN="$2"; shift 2 ;;
    --local-model-id) LOCAL_MODEL_ID="$2"; shift 2 ;;
    --no-start) NO_START=1; shift ;;
    --skip-package-install) SKIP_PACKAGE_INSTALL=1; shift ;;
    --skip-tests) SKIP_TESTS=1; shift ;;
    --skip-smoke-tests) SKIP_SMOKE_TESTS=1; shift ;;
    --no-pause) NO_PAUSE=1; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

log(){ printf '\033[1;32m[setup-linux]\033[0m %s\n' "$*"; }
warn(){ printf '\033[1;33m[setup-linux]\033[0m %s\n' "$*"; }
fail(){ printf '\033[1;31m[setup-linux]\033[0m %s\n' "$*" >&2; exit 1; }

command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "Python not found: $PYTHON_BIN. Install Python 3.10+ first."
"$PYTHON_BIN" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
[[ $? -eq 0 ]] || fail "Python 3.10+ is required."

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  warn "ffmpeg/ffprobe not found. Trying to install with apt, dnf, yum, pacman, or brew."
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y ffmpeg
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y ffmpeg ffmpeg-free || sudo dnf install -y ffmpeg
  elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y ffmpeg
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm ffmpeg
  elif command -v brew >/dev/null 2>&1; then
    brew install ffmpeg
  else
    fail "Could not auto-install ffmpeg. Install ffmpeg and ffprobe manually, then rerun."
  fi
fi

[[ -x .venv/bin/python ]] || { log "Creating virtual environment"; "$PYTHON_BIN" -m venv .venv; }
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
if [[ "$SKIP_PACKAGE_INSTALL" -eq 0 ]]; then
  log "Installing Python requirements"
  pip install -r requirements.txt
else
  warn "Skipping package install"
fi

[[ -f .env ]] || { log "Creating .env from .env.example"; cp .env.example .env; }
[[ -f config/config.yml ]] || { log "Creating config/config.yml from example"; mkdir -p config; cp config/config.example.yml config/config.yml; }

mkdir -p runtime/models runtime/uploads runtime/outputs runtime/cache runtime/checkpoints

export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export LOCAL_MODEL_ID="$LOCAL_MODEL_ID"

if [[ "$SKIP_TESTS" -eq 0 ]]; then
  log "Running tests"
  pytest -q
else
  warn "Skipping tests"
fi

if [[ "$SKIP_SMOKE_TESTS" -eq 0 ]]; then
  log "Running smoke test on temporary server"
  TMP_PORT=$((PORT + 17))
  python -m uvicorn api.app.main:app --host 127.0.0.1 --port "$TMP_PORT" > runtime/linux-smoke.log 2>&1 &
  SERVER_PID=$!
  cleanup(){ kill "$SERVER_PID" >/dev/null 2>&1 || true; }
  trap cleanup EXIT
  ok=0
  for _ in {1..45}; do
    if curl -fsS "http://127.0.0.1:${TMP_PORT}/health" >/dev/null 2>&1; then ok=1; break; fi
    sleep 1
  done
  [[ "$ok" -eq 1 ]] || { tail -80 runtime/linux-smoke.log >&2 || true; fail "Smoke server did not become healthy"; }
  curl -fsS "http://127.0.0.1:${TMP_PORT}/providers" >/dev/null
  curl -fsS "http://127.0.0.1:${TMP_PORT}/live" >/dev/null
  cleanup
  trap - EXIT
  trap on_error ERR
else
  warn "Skipping smoke tests"
fi

if [[ "$NO_START" -eq 1 ]]; then
  log "Setup complete. Not starting because --no-start was passed."
  exit 0
fi

log "Starting Tootak on ${HOST_NAME}:${PORT}"
if [[ "$HOST_NAME" == "0.0.0.0" ]]; then
  LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  [[ -n "${LAN_IP:-}" ]] && log "LAN URL: http://${LAN_IP}:${PORT}/live"
fi
log "Local URL: http://127.0.0.1:${PORT}/live"
python -m uvicorn api.app.main:app --host "$HOST_NAME" --port "$PORT" --reload
status=$?
if [[ "$status" != "0" ]]; then pause_before_exit "$status" "Server stopped or failed"; fi
exit "$status"
