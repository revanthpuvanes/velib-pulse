#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$HOME/Data-Engineering-Projects/velib-live-pipeline"

cd "$PROJECT_ROOT"

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
    ../.venv/bin/dbt build --profiles-dir . --project-dir .
)

echo ""
echo "[2/7] Regenerating pipeline health..."

.venv/bin/python -m scripts.export_health_with_retry

echo ""
echo "[3/7] Exporting latest station availability..."

.venv/bin/python -m dashboard.export_stations

echo ""
echo "[4/7] Exporting hourly analytics..."

.venv/bin/python -m dashboard.export_hourly

echo ""
echo "[5/7] Exporting dashboard health..."

.venv/bin/python -m dashboard.export_health

echo ""
echo "[6/7] Exporting historical insights..."

.venv/bin/python -m dashboard.export_insights

echo ""
echo "[7/7] Publishing JSON to Next.js..."

.venv/bin/python -m scripts.sync_dashboard_data

echo ""
echo "=============================================="
echo "DASHBOARD REFRESH COMPLETED"
echo "Finished: $(date -u --iso-8601=seconds)"
echo "=============================================="
