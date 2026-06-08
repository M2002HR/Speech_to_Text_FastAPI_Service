#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT_DIR/scripts/setup_and_start_linux.sh" --host 0.0.0.0 "$@"
