import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb

from scripts.poll_coverage import (
    AUTOMATION_START,
    calculate_coverage,
)


DB_PATH = Path("storage/state/velib.duckdb")
PARQUET_DIR = Path("storage/parquet/incremental")
OUTPUT_PATH = Path("storage/health/pipeline_health.json")

def parse_poll_id(value):
    return datetime.strptime(
        value, "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=timezone.utc)


def main():
    connection = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        rows = connection.execute("""
            SELECT
                poll_id,
                COUNT(*) AS observations,
                COUNT(DISTINCT stationcode) AS unique_stations
            FROM station_events
            WHERE poll_id >= ?
            GROUP BY poll_id
            ORDER BY poll_id
        """, [AUTOMATION_START.strftime("%Y-%m-%dT%H:%M:%SZ")]).fetchall()

        total_observations = connection.execute("""
            SELECT COUNT(*) FROM station_events
        """).fetchone()[0]

        unique_events = connection.execute("""
            SELECT COUNT(DISTINCT event_id)
            FROM station_events
        """).fetchone()[0]

        parquet_files = sorted(PARQUET_DIR.rglob("*.parquet"))

        parquet_observations = sum(
            connection.execute(
                "SELECT COUNT(*) FROM read_parquet(?)",
                [str(file)],
            ).fetchone()[0]
            for file in parquet_files
        )

        poll_times = {
            parse_poll_id(poll_id)
            for poll_id, _, _ in rows
        }

        latest_poll = max(poll_times) if poll_times else None

        now = datetime.now(timezone.utc)

        coverage_result = calculate_coverage(
            poll_times=poll_times,
            now=now,
            grace_seconds=60,
        )

        expected_count = coverage_result["expected"]
        recorded_expected_polls = coverage_result["recorded"]
        missing_times = coverage_result["missing"]
        coverage = coverage_result["coverage"]
        latest_expected_poll = coverage_result["latest_expected_poll"]

        latest_poll_age_seconds = (
            (now - latest_poll).total_seconds()
            if latest_poll else None
        )

        # Allow up to two polling intervals before declaring
        # the latest recorded data stale.
        freshness_threshold_seconds = 600

        is_fresh = (
            latest_poll_age_seconds is not None
            and 0 <= latest_poll_age_seconds <= freshness_threshold_seconds
        )

        report = {
            "generated_at": now.isoformat(),
            "freshness": {
                "latest_poll_age_seconds": (
                    round(latest_poll_age_seconds, 2)
                    if latest_poll_age_seconds is not None else None
                ),
                "threshold_seconds": freshness_threshold_seconds,
                "is_fresh": is_fresh,
            },
            "automation_start": AUTOMATION_START.isoformat(),
            "latest_poll": (
                latest_poll.isoformat()
                if latest_poll else None
            ),
            "automated_polling": {
                "expected_polls": expected_count,
                "recorded_polls": recorded_expected_polls,
                "missing_polls": len(missing_times),
                "completion_grace_seconds": 60,
                "latest_expected_poll": (
                    latest_expected_poll.isoformat()
                    if expected_count else None
                ),
                "coverage_percent": (
                    round(coverage, 2)
                    if coverage is not None else None
                ),
                "missing_poll_ids": [
                    timestamp.isoformat()
                    for timestamp in missing_times
                ],
            },
            "storage": {
                "duckdb_observations": total_observations,
                "unique_event_ids": unique_events,
                "duplicate_event_ids": (
                    total_observations - unique_events
                ),
                "parquet_files": len(parquet_files),
                "parquet_observations": parquet_observations,
                "row_counts_match": (
                    total_observations == parquet_observations
                ),
            },
        }

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=OUTPUT_PATH.parent,
                prefix=".pipeline_health_",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)

                json.dump(report, file, indent=2)

                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary_path, OUTPUT_PATH)

        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        print(json.dumps(report, indent=2))
        print(f"\n✅ Health report saved: {OUTPUT_PATH}")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
