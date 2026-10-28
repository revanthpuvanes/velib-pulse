#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_ROOT"

# Support both local virtual environments and Docker.
if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
    DBT="$PROJECT_ROOT/.venv/bin/dbt"
else
    PYTHON="$(command -v python)"
    DBT="$(command -v dbt)"
fi

mkdir -p storage/state

exec 9>storage/state/analytics.lock

if ! flock -n 9; then
    echo "Analytics job already running. Skipping overlapping execution."
    exit 0
fi

echo "=============================================="
echo "VÉLIB' ANALYTICS + DASHBOARD REFRESH"
echo "Started: $(date -u --iso-8601=seconds)"
echo "=============================================="

echo ""
echo "[1/7] Running dbt models and tests..."

(
    cd analytics
    "$DBT" build --profiles-dir . --project-dir .
)

echo ""
echo "[2/7] Regenerating pipeline health..."
"$PYTHON" -m scripts.export_health_with_retry

echo ""
echo "[3/7] Exporting latest station availability..."
"$PYTHON" -m dashboard.export_stations

echo ""
echo "[4/7] Exporting hourly analytics..."
"$PYTHON" -m dashboard.export_hourly

echo ""
echo "[5/7] Exporting dashboard health..."
"$PYTHON" -m dashboard.export_health

echo ""
echo "[6/7] Exporting historical insights..."
"$PYTHON" -m dashboard.export_insights

echo ""
echo "[7/7] Publishing dashboard release..."
"$PYTHON" -m scripts.sync_dashboard_data

echo ""
echo "=============================================="
echo "DASHBOARD REFRESH COMPLETED"
echo "Finished: $(date -u --iso-8601=seconds)"
echo "=============================================="
