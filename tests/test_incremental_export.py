import json
from pathlib import Path

import duckdb
import pytest

from consumer.incremental_export import export_completed_poll
from producer.producer import load_snapshot


SNAPSHOT_PATH = Path(
    "storage/raw/velib_poll_20261027T201000Z.json"
)


def test_incomplete_poll_is_rejected(tmp_path):
    snapshot = load_snapshot(SNAPSHOT_PATH)

    db_path = tmp_path / "incomplete.duckdb"
    output_dir = tmp_path / "parquet"

    connection = duckdb.connect(str(db_path))

    try:
        connection.execute("""
            CREATE TABLE station_events (
                event_id VARCHAR PRIMARY KEY,
                poll_id VARCHAR NOT NULL,
                stationcode VARCHAR NOT NULL,
                collected_at TIMESTAMPTZ NOT NULL,
                bikes_available INTEGER NOT NULL,
                docks_available INTEGER NOT NULL,
                station_json VARCHAR NOT NULL
            )
        """)

        # Insert only 100 observations from the 1519-station poll.
        for station in snapshot["stations"][:100]:
            stationcode = str(station["stationcode"])

            connection.execute("""
                INSERT INTO station_events
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                f"{snapshot['poll_id']}:{stationcode}",
                snapshot["poll_id"],
                stationcode,
                snapshot["collected_at"],
                station["numbikesavailable"],
                station["numdocksavailable"],
                json.dumps(station),
            ])

        with pytest.raises(
            RuntimeError,
            match="incomplete or inconsistent",
        ):
            export_completed_poll(
                connection,
                SNAPSHOT_PATH,
                output_dir=output_dir,
            )

        assert not list(output_dir.rglob("*.parquet"))

    finally:
        connection.close()


def test_missing_poll_is_rejected(tmp_path):
    snapshot = load_snapshot(SNAPSHOT_PATH)

    connection = duckdb.connect(
        str(tmp_path / "empty.duckdb")
    )

    try:
        connection.execute("""
            CREATE TABLE station_events (
                event_id VARCHAR PRIMARY KEY,
                poll_id VARCHAR NOT NULL,
                stationcode VARCHAR NOT NULL,
                collected_at TIMESTAMPTZ NOT NULL,
                bikes_available INTEGER NOT NULL,
                docks_available INTEGER NOT NULL,
                station_json VARCHAR NOT NULL
            )
        """)

        with pytest.raises(
            RuntimeError,
            match="incomplete or inconsistent",
        ):
            export_completed_poll(
                connection,
                SNAPSHOT_PATH,
                output_dir=tmp_path / "parquet",
            )

    finally:
        connection.close()
