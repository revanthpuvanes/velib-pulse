import json
import os
import tempfile
from pathlib import Path


SOURCE = Path("storage/health/pipeline_health.json")
OUTPUT = Path("storage/dashboard/health.json")


def export_health(source=SOURCE, output=OUTPUT):
    if not source.exists():
        raise FileNotFoundError(
            f"Health report not found: {source}"
        )

    data = json.loads(source.read_text(encoding="utf-8"))

    required_fields = {
        "generated_at",
        "freshness",
        "automated_polling",
        "storage",
    }

    missing = required_fields - data.keys()

    if missing:
        raise ValueError(
            f"Missing health fields: {sorted(missing)}"
        )

    polling = data["automated_polling"]
    storage = data["storage"]

    if (
        polling["expected_polls"]
        != polling["recorded_polls"] + polling["missing_polls"]
    ):
        raise ValueError("Inconsistent polling counts.")

    if storage["unique_event_ids"] > storage["duckdb_observations"]:
        raise ValueError("Invalid unique event count.")

    output.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=".health_",
            suffix=".tmp",
            delete=False,
        ) as temporary:

            temporary_path = Path(temporary.name)

            json.dump(
                data,
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

    print("\n🚲 DASHBOARD HEALTH EXPORT")
    print("=" * 45)
    print(f"Poll coverage: {polling['coverage_percent']}%")
    print(f"Missing polls: {polling['missing_polls']}")
    print(f"Fresh: {data['freshness']['is_fresh']}")
    print(f"Generated at: {data['generated_at']}")
    print(f"Output: {output}")
    print(f"File size: {output.stat().st_size:,} bytes")


if __name__ == "__main__":
    export_health()
