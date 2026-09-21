#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.cli run-all "$@"
