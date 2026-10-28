import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


files = sorted(Path("storage/raw").glob("velib_*.json"))

if len(files) < 2:
    raise SystemExit("Need at least two snapshots")

with files[-2].open(encoding="utf-8") as f:
    previous = json.load(f)

with files[-1].open(encoding="utf-8") as f:
    current = json.load(f)

previous_stations = {
    str(s["stationcode"]): s
    for s in previous["stations"]
}

current_stations = {
    str(s["stationcode"]): s
    for s in current["stations"]
}

collection_time = datetime.fromisoformat(current["collected_at"])

age_counts = Counter()
availability_changed = 0
timestamp_changed = 0
both_changed = 0
unchanged = 0
invalid_timestamps = 0

for station_id, station in current_stations.items():

    timestamp = station.get("duedate")

    try:
        updated_at = datetime.fromisoformat(timestamp)

        if updated_at.tzinfo is None:
            raise ValueError("Timezone missing")

        age_minutes = (
            collection_time - updated_at
        ).total_seconds() / 60

        if age_minutes > 1440:
            age_counts["Older than 24 hours"] += 1
        elif age_minutes > 60:
            age_counts["1-24 hours old"] += 1
        elif age_minutes >= 0:
            age_counts["Under 1 hour"] += 1
        else:
            age_counts["Future timestamp"] += 1

    except (ValueError, TypeError):
        invalid_timestamps += 1

    old = previous_stations.get(station_id)

    if old is None:
        continue

    availability_fields = (
        "numbikesavailable",
        "numdocksavailable",
        "mechanical",
        "ebike",
    )

    availability_diff = any(
        old.get(field) != station.get(field)
        for field in availability_fields
    )

    timestamp_diff = old.get("duedate") != station.get("duedate")

    if availability_diff:
        availability_changed += 1

    if timestamp_diff:
        timestamp_changed += 1

    if availability_diff and timestamp_diff:
        both_changed += 1

    if old == station:
        unchanged += 1


print("\n🚲 VÉLIB' DATA FRESHNESS ANALYSIS")
print("=" * 50)

print("\nCollection time:", collection_time.isoformat())
print("Total stations:", len(current_stations))

print("\nTIMESTAMP AGE DISTRIBUTION")

for category in (
    "Under 1 hour",
    "1-24 hours old",
    "Older than 24 hours",
    "Future timestamp",
):
    print(f"{category}: {age_counts[category]}")

print("Invalid timestamps:", invalid_timestamps)

print("\nCHANGES BETWEEN SNAPSHOTS")

print("Availability changed:", availability_changed)
print("Timestamp changed:", timestamp_changed)
print("Both changed:", both_changed)
print("Completely unchanged:", unchanged)
