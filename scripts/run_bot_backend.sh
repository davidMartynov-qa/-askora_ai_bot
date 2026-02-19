#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f ".venv/bin/python" ]; then
  echo ".venv is missing. Run scripts/bootstrap_vps_backend.sh first."
  exit 1
fi

exec .venv/bin/python bot.py
