#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d "venv" ]; then
  echo "No venv found. Run: scripts/install.sh"
  exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate
exec python glint.py start
