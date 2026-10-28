import json
import sys
from pathlib import Path

from confluent_kafka import Producer


TOPIC = "velib.station_status"
BOOTSTRAP_SERVERS = "localhost:19092"


def load_snapshot(path):
    with Path(path).open(encoding="utf-8") as file:
        snapshot = json.load(file)

    required = {
        "poll_id",
        "collected_at",
        "station_count",
        "checksum",
        "stations",
    }

    missing = required - snapshot.keys()

    if missing:
        raise ValueError(f"Snapshot missing fields: {missing}")

    stations = snapshot["stations"]

    if not isinstance(stations, list):
        raise ValueError("Invalid stations list")

    if len(stations) != snapshot["station_count"]:
        raise ValueError("Station count mismatch")

    from collector.collector import (
        calculate_checksum,
        validate_stations,
    )

    validate_stations(stations)

    if calculate_checksum(stations) != snapshot["checksum"]:
        raise ValueError("Snapshot checksum mismatch")

    return snapshot


def build_event(snapshot, station):
    stationcode = str(station["stationcode"])

    return {
        "event_id": f"{snapshot['poll_id']}:{stationcode}",
        "poll_id": snapshot["poll_id"],
        "collected_at": snapshot["collected_at"],
        "stationcode": stationcode,
        "station": station,
    }


def publish_snapshot(snapshot):
    producer = Producer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "enable.idempotence": True,
            "acks": "all",
            "retries": 5,
            "message.timeout.ms": 30000,
        }
    )

    acknowledged = 0
    failures = []

    def delivery_report(error, message):
        nonlocal acknowledged

        if error is not None:
            failures.append(str(error))
        else:
            acknowledged += 1

    stations = snapshot["stations"]

    for station in stations:
        event = build_event(snapshot, station)

        payload = json.dumps(
            event,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        while True:
            try:
                producer.produce(
                    topic=TOPIC,
                    key=event["stationcode"].encode("utf-8"),
                    value=payload,
                    callback=delivery_report,
                )
                break

            except BufferError:
                producer.poll(1)

        producer.poll(0)

    remaining = producer.flush(35)

    print(f"Stations in snapshot: {len(stations)}")
    print(f"Broker acknowledgments: {acknowledged}")
    print(f"Delivery failures: {len(failures)}")
    print(f"Unresolved messages: {remaining}")

    if failures:
        print("First delivery error:", failures[0])

    if failures or remaining or acknowledged != len(stations):
        raise RuntimeError("Not all events were acknowledged")

    print("✅ Snapshot successfully published to Redpanda")


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m producer.producer <snapshot_path>")
        raise SystemExit(2)

    snapshot_path = Path(sys.argv[1])

    try:
        snapshot = load_snapshot(snapshot_path)

        print("\n🚲 VÉLIB' KAFKA PRODUCER")
        print("=" * 45)
        print("Snapshot:", snapshot_path)
        print("Poll ID:", snapshot["poll_id"])

        publish_snapshot(snapshot)

    except (OSError, ValueError, RuntimeError) as error:
        print("❌ Publishing failed:", error)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
