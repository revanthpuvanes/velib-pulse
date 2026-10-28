import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from collector.collector import calculate_checksum, validate_stations
from producer.producer import load_snapshot


OUTPUT_DIR = Path("storage/parquet/incremental")


def export_completed_poll(connection, snapshot_path, output_dir=OUTPUT_DIR):
    """
    Export one poll only after verifying that every expected
    station event exists in DuckDB.

    The original snapshot is the completeness manifest.
    """

    snapshot = load_snapshot(snapshot_path)

    poll_id = snapshot["poll_id"]
    stations = snapshot["stations"]
    expected_count = snapshot["station_count"]

    expected_ids = {
        f"{poll_id}:{station['stationcode']}"
        for station in stations
    }

    if len(expected_ids) != expected_count:
        raise ValueError("Duplicate stationcodes in snapshot")

    rows = connection.execute("""
        SELECT event_id
        FROM station_events
        WHERE poll_id = ?
    """, [poll_id]).fetchall()

    actual_ids = {row[0] for row in rows}

    missing = expected_ids - actual_ids
    unexpected = actual_ids - expected_ids

    if missing or unexpected:
        raise RuntimeError(
            f"Poll {poll_id} is incomplete or inconsistent: "
            f"missing={len(missing)}, "
            f"unexpected={len(unexpected)}"
        )

    if len(rows) != expected_count:
        raise RuntimeError(
            f"Poll row count mismatch: "
            f"expected={expected_count}, actual={len(rows)}"
        )

    timestamp = datetime.strptime(
        poll_id,
        "%Y-%m-%dT%H:%M:%SZ",
    ).replace(tzinfo=timezone.utc)

    date_partition = timestamp.strftime("%Y-%m-%d")
    filename = timestamp.strftime("poll_%Y%m%dT%H%M%SZ.parquet")

    destination = Path(output_dir) / f"poll_date={date_partition}"
    destination.mkdir(parents=True, exist_ok=True)

    final_path = destination / filename

    if final_path.exists():
        # Existing files must be checked rather than blindly trusted.
        existing_ids = {
            row[0]
            for row in connection.execute("""
                SELECT event_id
                FROM read_parquet(?)
            """, [str(final_path)]).fetchall()
        }

        if existing_ids != expected_ids:
            raise RuntimeError(
                f"Existing Parquet file is inconsistent: {final_path}"
            )

        existing_count = connection.execute("""
            SELECT COUNT(*)
            FROM read_parquet(?)
        """, [str(final_path)]).fetchone()[0]

        if existing_count != expected_count:
            raise RuntimeError(
                f"Existing Parquet row count mismatch: {final_path}"
            )

        print(f"⏭️ Already exported: {final_path}")
        return final_path, False

    temporary_path = destination / f"{filename}.tmp"

    temporary_path.unlink(missing_ok=True)

    try:
        connection.execute("""
            COPY (
                SELECT *
                FROM station_events
                WHERE poll_id = ?
                ORDER BY stationcode
            )
            TO ?
            (FORMAT PARQUET, COMPRESSION ZSTD)
        """, [poll_id, str(temporary_path)])

        # Validate the file before making it visible.
        exported_count = connection.execute("""
            SELECT COUNT(*)
            FROM read_parquet(?)
        """, [str(temporary_path)]).fetchone()[0]

        if exported_count != expected_count:
            raise RuntimeError(
                f"Parquet validation failed: "
                f"expected={expected_count}, actual={exported_count}"
            )

        os.replace(temporary_path, final_path)

    finally:
        temporary_path.unlink(missing_ok=True)

    print(f"✅ Exported {expected_count} rows: {final_path}")

    return final_path, True


def main():
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python -m consumer.incremental_export "
            "<snapshot1> [snapshot2 ...]"
        )
        raise SystemExit(2)

    connection = duckdb.connect(
        "storage/state/velib.duckdb",
        read_only=True,
    )

    try:
        for snapshot_path in sys.argv[1:]:
            export_completed_poll(connection, snapshot_path)

    finally:
        connection.close()


if __name__ == "__main__":
    main()


def reconcile_local_snapshots(
    connection,
    snapshot_dir=Path("storage/raw"),
    output_dir=OUTPUT_DIR,
):
    """
    Reconcile locally saved snapshots against committed DuckDB rows.

    Complete polls are exported or verified.
    Incomplete polls remain pending for a later retry.
    """
    snapshot_paths = sorted(
        Path(snapshot_dir).glob("velib_poll_*.json")
    )

    exported = 0
    already_exported = 0
    pending = 0

    for snapshot_path in snapshot_paths:
        try:
            _, created = export_completed_poll(
                connection,
                snapshot_path,
                output_dir=output_dir,
            )

        except RuntimeError as error:
            # Only incomplete polls should remain pending.
            # Other integrity errors must not be silently ignored.
            if "is incomplete or inconsistent:" not in str(error):
                raise

            print(f"⏳ Pending: {snapshot_path.name}")
            pending += 1
            continue

        if created:
            exported += 1
        else:
            already_exported += 1

    print("\n📊 INCREMENTAL EXPORT RECONCILIATION")
    print("=" * 45)
    print("Snapshots checked:", len(snapshot_paths))
    print("New Parquet files:", exported)
    print("Existing files verified:", already_exported)
    print("Incomplete polls pending:", pending)

    return {
        "snapshots_checked": len(snapshot_paths),
        "exported": exported,
        "already_exported": already_exported,
        "pending": pending,
    }
