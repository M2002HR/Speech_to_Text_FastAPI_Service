#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

HOST_NAME="${HOST_NAME:-0.0.0.0}"
PORT="${PORT:-8030}"
NO_PAUSE="${TOOTAK_NO_PAUSE:-0}"

pause_before_exit(){
  local code="$1"
  local reason="${2:-Script stopped}"
  if [[ "$NO_PAUSE" == "1" || ! -t 0 ]]; then return; fi
  echo
  echo "${reason}. Press Enter to close this window..."
  read -r _ || true
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host|-h) HOST_NAME="$2"; shift 2 ;;
    --port|-p) PORT="$2"; shift 2 ;;
    --no-pause) NO_PAUSE=1; shift ;;
    *) echo "Unknown argument: $1" >&2; pause_before_exit 2 "Script failed"; exit 2 ;;
  esac
done

if [[ ! -x .venv/bin/python ]]; then
  echo "[start-linux] .venv not found. Run ./scripts/setup_and_start_linux.sh first." >&2
  pause_before_exit 1 "Script failed"
  exit 1
fi

source .venv/bin/activate
export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p runtime

echo "[start-linux] Local: http://127.0.0.1:${PORT}/live"
if [[ "$HOST_NAME" == "0.0.0.0" ]]; then
  LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  [[ -n "${LAN_IP:-}" ]] && echo "[start-linux] LAN: http://${LAN_IP}:${PORT}/live"
fi

python -m uvicorn api.app.main:app --host "$HOST_NAME" --port "$PORT" --reload
status=$?
if [[ "$status" == "0" ]]; then
  pause_before_exit "$status" "Server stopped"
else
  pause_before_exit "$status" "Server stopped or failed"
fi
exit "$status"
