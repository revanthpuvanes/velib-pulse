import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb


DATABASE = Path("storage/analytics/velib_analytics.duckdb")
OUTPUT = Path("storage/dashboard/hourly.json")


def export_hourly(database=DATABASE, output=OUTPUT):
    connection = duckdb.connect(str(database), read_only=True)

    try:
        rows = connection.execute("""
            SELECT
                hour_utc,
                COUNT(*) AS station_count,
                SUM(observation_count) AS observation_count,

                ROUND(
                    SUM(avg_bikes_available * observation_count)
                    / SUM(observation_count),
                    2
                ) AS avg_bikes_available,

                ROUND(
                    SUM(avg_docks_available * observation_count)
                    / SUM(observation_count),
                    2
                ) AS avg_docks_available,

                ROUND(
                    SUM(
                        pct_observations_without_bikes
                        * observation_count
                    ) / SUM(observation_count),
                    2
                ) AS pct_observations_without_bikes

            FROM main.mart_hourly_availability
            GROUP BY hour_utc
            ORDER BY hour_utc
        """).fetchall()

    finally:
        connection.close()

    if not rows:
        raise ValueError("Hourly mart is empty.")

    hours = []

    for (
        hour_utc,
        station_count,
        observation_count,
        avg_bikes,
        avg_docks,
        pct_without_bikes,
    ) in rows:

        if station_count <= 0 or observation_count <= 0:
            raise ValueError(f"Invalid observation counts: {hour_utc}")

        hours.append({
            "hour_utc": hour_utc.replace(
                tzinfo=timezone.utc
            ).isoformat(),
            "station_count": station_count,
            "observation_count": observation_count,
            "avg_bikes_available": avg_bikes,
            "avg_docks_available": avg_docks,
            "pct_observations_without_bikes": pct_without_bikes,
        })

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hour_count": len(hours),
        "hours": hours,
    }

    output.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=".hourly_",
            suffix=".tmp",
            delete=False,
        ) as temporary:

            temporary_path = Path(temporary.name)

            json.dump(
                payload,
                temporary,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )

            temporary.flush()
            os.fsync(temporary.fileno())

        os.replace(temporary_path, output)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    print("\n🚲 DASHBOARD HOURLY EXPORT")
    print("=" * 45)
    print(f"Hours exported: {len(hours)}")
    print(
        "Total observations represented:",
        sum(hour["observation_count"] for hour in hours),
    )
    print(f"Generated at: {payload['generated_at']}")
    print(f"Output: {output}")
    print(f"File size: {output.stat().st_size:,} bytes")


if __name__ == "__main__":
    export_hourly()
