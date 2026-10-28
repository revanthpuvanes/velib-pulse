#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_DIR"

# Support both local virtual environments and Docker.
if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
else
    PYTHON="$(command -v python)"
fi

mkdir -p storage/state storage/logs

exec 9>storage/state/pipeline.lock

if ! flock -n 9; then
    echo "SKIPPED: Another pipeline run is already active."
    exit 0
fi

echo "========================================"
echo "Pipeline started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "========================================"

"$PYTHON" -m scripts.run_pipeline

echo "========================================"
echo "Pipeline finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "========================================"
