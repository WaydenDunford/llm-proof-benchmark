#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
shopt -s nullglob
for file in results/raw/*.json; do
  python -m src.cli evaluate "$file" "$@"
done
