#!/usr/bin/env bash
set -euo pipefail

exec python -m api.app.queue_worker
