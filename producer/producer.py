import json
import os
import sqlite3
import sys
from pathlib import Path

from confluent_kafka import Producer

from collector.collector import calculate_checksum, validate_stations


TOPIC = os.environ.get("VELIB_TOPIC", "velib.station_status")
BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
STATE_PATH = Path(os.environ.get("VELIB_PRODUCER_STATE", "storage/state/producer.sqlite"))


def initialize_state(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS published_events (
            event_id TEXT PRIMARY KEY,
            snapshot_checksum TEXT NOT NULL,
            published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.commit()


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

    if validate_stations(stations) != snapshot["station_count"]:
        raise ValueError("Station count mismatch")

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


def publish_snapshot(snapshot, connection):
    producer = Producer({
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "enable.idempotence": True,
        "acks": "all",
        "retries": 5,
        "message.timeout.ms": 30000,
    })

    published = 0
    skipped = 0
    failures = []

    def delivery_report(error, message):
        nonlocal published

        event_id = message.key().decode("utf-8")

        if error is not None:
            failures.append(str(error))
            return

        # The Kafka key is stationcode; recover the event ID from payload.
        event = json.loads(message.value())
        event_id = event["event_id"]

        connection.execute("""
            INSERT OR IGNORE INTO published_events (
                event_id,
                snapshot_checksum
            )
            VALUES (?, ?)
        """, [
            event_id,
            snapshot["checksum"],
        ])

        connection.commit()
        published += 1

        crash_after = int(os.environ.get("VELIB_PRODUCER_CRASH_AFTER", "0"))

        if crash_after and published >= crash_after:
            print(
                f"💥 Simulating producer crash after {published} acknowledgments",
                flush=True,
            )
            os._exit(42)

    for station in snapshot["stations"]:
        event = build_event(snapshot, station)
        event_id = event["event_id"]

        existing = connection.execute("""
            SELECT snapshot_checksum
            FROM published_events
            WHERE event_id = ?
        """, [event_id]).fetchone()

        if existing:
            if existing[0] != snapshot["checksum"]:
                raise ValueError(
                    f"Conflicting snapshot content for event {event_id}"
                )

            skipped += 1
            continue

        payload = json.dumps(
            event,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        while True:
            try:
                producer.produce(
                    TOPIC,
                    key=event["stationcode"].encode("utf-8"),
                    value=payload,
                    callback=delivery_report,
                )
                break

            except BufferError:
                producer.poll(1)

        # Wait for delivery callback and durable SQLite checkpoint
        # before publishing the next event.
        remaining = producer.flush(35)

        if remaining:
            raise RuntimeError(
                f"Kafka delivery unresolved for event {event_id}"
            )

        if failures:
            raise RuntimeError(
                f"Kafka delivery failed for event {event_id}: "
                f"{failures[-1]}"
            )

    remaining = producer.flush(35)

    print("\n📊 PRODUCER RESULTS")
    print("=" * 45)
    print("Events newly acknowledged:", published)
    print("Already published (skipped):", skipped)
    print("Delivery failures:", len(failures))
    print("Unresolved messages:", remaining)

    if failures:
        print("First error:", failures[0])

    if failures or remaining:
        raise RuntimeError("Some events were not successfully published")

    print("\n✅ PUBLISHING COMPLETE")


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m producer.producer <snapshot_path>")
        raise SystemExit(2)

    snapshot_path = Path(sys.argv[1])

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(STATE_PATH)

    try:
        initialize_state(connection)

        snapshot = load_snapshot(snapshot_path)

        print("\n🚲 VÉLIB' RELIABLE PRODUCER")
        print("=" * 45)
        print("Snapshot:", snapshot_path)
        print("Poll ID:", snapshot["poll_id"])

        publish_snapshot(snapshot, connection)

    except (OSError, ValueError, sqlite3.Error, RuntimeError) as error:
        print("❌ Publishing failed:", error)
        raise SystemExit(1) from error

    finally:
        connection.close()


if __name__ == "__main__":
    main()
