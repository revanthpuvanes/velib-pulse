from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb


DB_PATH = Path("storage/state/velib.duckdb")
PARQUET_DIR = Path("storage/parquet/incremental")


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)

    connection = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        polls = connection.execute("""
            SELECT
                poll_id,
                COUNT(*) AS observations,
                COUNT(DISTINCT stationcode) AS unique_stations
            FROM station_events
            GROUP BY poll_id
            ORDER BY poll_id
        """).fetchall()

        total_observations = connection.execute("""
            SELECT COUNT(*)
            FROM station_events
        """).fetchone()[0]

        unique_events = connection.execute("""
            SELECT COUNT(DISTINCT event_id)
            FROM station_events
        """).fetchone()[0]

        parquet_files = sorted(
            PARQUET_DIR.rglob("*.parquet")
        )

        parquet_observations = 0

        for file in parquet_files:
            count = connection.execute("""
                SELECT COUNT(*)
                FROM read_parquet(?)
            """, [str(file)]).fetchone()[0]

            parquet_observations += count

        print("\n🚲 VÉLIB' PIPELINE HEALTH REPORT")
        print("=" * 55)

        print("Total observations:", total_observations)
        print("Unique event IDs:", unique_events)
        print(
            "Duplicate event IDs:",
            total_observations - unique_events,
        )
        print("Completed poll IDs recorded:", len(polls))
        print("Incremental Parquet files:", len(parquet_files))
        print("Parquet observations:", parquet_observations)

        if not polls:
            print("\nNo polling history available.")
            return

        poll_times = [
            datetime.strptime(
                poll_id,
                "%Y-%m-%dT%H:%M:%SZ",
            ).replace(tzinfo=timezone.utc)
            for poll_id, _, _ in polls
        ]

        first_poll = poll_times[0]
        latest_poll = poll_times[-1]

        expected_times = []

        current = first_poll

        while current <= latest_poll:
            expected_times.append(current)
            current += timedelta(minutes=5)

        actual_times = set(poll_times)

        missing = [
            timestamp
            for timestamp in expected_times
            if timestamp not in actual_times
        ]

        expected_count = len(expected_times)

        coverage = (
            len(polls) / expected_count * 100
            if expected_count
            else 0
        )

        print("\n📊 POLLING COVERAGE")
        print("=" * 55)
        print("First poll:", first_poll.isoformat())
        print("Latest poll:", latest_poll.isoformat())
        print("Expected five-minute polls:", expected_count)
        print("Recorded polls:", len(polls))
        print("Missing polls:", len(missing))
        print("Poll coverage:", f"{coverage:.2f}%")

        print("\n📊 STORAGE CONSISTENCY")
        print("=" * 55)

        if parquet_observations == total_observations:
            print("✅ DuckDB and Parquet row counts match")
        else:
            print("❌ DuckDB and Parquet row counts differ")

        if total_observations == unique_events:
            print("✅ No duplicate event IDs in DuckDB")
        else:
            print("❌ Duplicate event IDs detected")

        if missing:
            print("\n⚠️ FIRST 10 MISSING POLLS")
            print("=" * 55)

            for timestamp in missing[:10]:
                print(timestamp.isoformat())

        print("\n📊 LATEST FIVE POLLS")
        print("=" * 55)

        for poll_id, observations, unique_stations in polls[-5:]:
            print(
                f"{poll_id}: "
                f"{observations} observations, "
                f"{unique_stations} unique stations"
            )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
