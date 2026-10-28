import tempfile
from pathlib import Path

import duckdb

from consumer.incremental_export import reconcile_local_snapshots


SOURCE_DB = Path("storage/state/velib.duckdb")
SNAPSHOT_DIR = Path("storage/raw")


def main():
    with tempfile.TemporaryDirectory(prefix="velib-recovery-") as directory:
        test_dir = Path(directory)
        test_db = test_dir / "recovery.duckdb"
        parquet_dir = test_dir / "parquet"

        # Copy committed database state into an isolated test database.
        source = duckdb.connect(str(SOURCE_DB), read_only=True)

        try:
            export_path = test_dir / "database_export"
            source.execute(
                f"EXPORT DATABASE '{export_path.as_posix()}' (FORMAT PARQUET)"
            )
        finally:
            source.close()

        connection = duckdb.connect(str(test_db))

        try:
            connection.execute(
                f"IMPORT DATABASE '{export_path.as_posix()}'"
            )

            original_rows = connection.execute("""
                SELECT COUNT(*) FROM station_events
            """).fetchone()[0]

            print("\n🚲 PARQUET EXPORT RECOVERY TEST")
            print("=" * 50)
            print("Committed DuckDB rows:", original_rows)
            print("Parquet files before recovery:", len(
                list(parquet_dir.rglob("*.parquet"))
            ))

            assert original_rows == 3038
            assert not list(parquet_dir.rglob("*.parquet"))

            print("\n🔄 Simulating consumer restart...")
            result = reconcile_local_snapshots(
                connection,
                snapshot_dir=SNAPSHOT_DIR,
                output_dir=parquet_dir,
            )

            files = sorted(parquet_dir.rglob("*.parquet"))

            parquet_rows = sum(
                connection.execute("""
                    SELECT COUNT(*)
                    FROM read_parquet(?)
                """, [str(file)]).fetchone()[0]
                for file in files
            )

            print("\n📊 RECOVERY RESULTS")
            print("=" * 50)
            print("New Parquet files:", result["exported"])
            print("Recovered Parquet rows:", parquet_rows)
            print("Original DuckDB rows:", original_rows)

            assert result["exported"] == 2
            assert result["pending"] == 0
            assert parquet_rows == original_rows

            print("\n✅ PARQUET EXPORT RECOVERY VERIFIED")

        finally:
            connection.close()


if __name__ == "__main__":
    main()
