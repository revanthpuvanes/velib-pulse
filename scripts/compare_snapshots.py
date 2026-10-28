import json
import sys
from datetime import datetime, timezone
from pathlib import Path


RAW_DIR = Path("storage/raw")


def load_snapshot(path):
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def main():
    files = sorted(RAW_DIR.glob("velib_*.json"))

    if len(files) < 2:
        print("Need at least two snapshots.")
        sys.exit(1)

    previous = load_snapshot(files[-2])
    current = load_snapshot(files[-1])

    previous_stations = {
        str(s["stationcode"]): s
        for s in previous["stations"]
    }

    current_stations = {
        str(s["stationcode"]): s
        for s in current["stations"]
    }

    common_ids = previous_stations.keys() & current_stations.keys()

    changed = sum(
        previous_stations[sid] != current_stations[sid]
        for sid in common_ids
    )

    previous_time = datetime.fromisoformat(previous["collected_at"])
    current_time = datetime.fromisoformat(current["collected_at"])

    timestamps = [
        datetime.fromisoformat(s["duedate"])
        for s in current["stations"]
        if s.get("duedate")
    ]

    print("\n🚲 VÉLIB' SNAPSHOT COMPARISON")
    print("=" * 45)

    print("Previous collection:", previous_time.isoformat())
    print("Current collection:", current_time.isoformat())

    print(
        "Time between collections:",
        round((current_time - previous_time).total_seconds(), 2),
        "seconds"
    )

    print("\nPrevious stations:", len(previous_stations))
    print("Current stations:", len(current_stations))

    print("Changed stations:", changed)
    print("New stations:", len(current_stations.keys() - previous_stations.keys()))
    print("Removed stations:", len(previous_stations.keys() - current_stations.keys()))

    print("\nSame checksum:", previous["checksum"] == current["checksum"])

    if timestamps:
        now = datetime.now(timezone.utc)

        newest = max(timestamps)
        oldest = min(timestamps)

        print("\nNewest station update:", newest.isoformat())
        print("Oldest station update:", oldest.isoformat())

        print(
            "Newest station age:",
            round((now - newest).total_seconds() / 60, 2),
            "minutes"
        )

        print(
            "Oldest station age:",
            round((now - oldest).total_seconds() / 60, 2),
            "minutes"
        )


if __name__ == "__main__":
    main()
