#!/usr/bin/env bash
# Lancement développeur uniquement — préférez ./install.sh pour une vraie app Ubuntu.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export NOOK_HOME="$SCRIPT_DIR"
if [[ -d ".venv" ]]; then source .venv/bin/activate; fi
exec python3 -m nook "$@"
