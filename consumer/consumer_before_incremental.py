import json
import os
from pathlib import Path

import duckdb
from confluent_kafka import Consumer, KafkaException, TopicPartition


TOPIC = "velib.station_status"
BOOTSTRAP_SERVERS = "localhost:19092"

DB_PATH = Path(os.environ.get("VELIB_DB_PATH", "storage/state/velib.duckdb"))
PARQUET_PATH = Path(
    os.environ.get(
        "VELIB_PARQUET_PATH",
        "storage/parquet/station_observations.parquet",
    )
)


def initialize_database(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS station_events (
            event_id VARCHAR PRIMARY KEY,
            poll_id VARCHAR NOT NULL,
            stationcode VARCHAR NOT NULL,
            collected_at TIMESTAMPTZ NOT NULL,
            bikes_available INTEGER NOT NULL,
            docks_available INTEGER NOT NULL,
            station_json VARCHAR NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS consumer_offsets (
            topic VARCHAR NOT NULL,
            partition_id INTEGER NOT NULL,
            next_offset BIGINT NOT NULL,
            PRIMARY KEY (topic, partition_id)
        )
    """)


def validate_event(message):
    if message.value() is None:
        raise ValueError("Kafka message has no value")

    event = json.loads(message.value())

    required = {
        "event_id",
        "poll_id",
        "stationcode",
        "collected_at",
        "station",
    }

    missing = required - event.keys()

    if missing:
        raise ValueError(f"Missing event fields: {missing}")

    station = event["station"]

    if not isinstance(station, dict):
        raise ValueError("Invalid station data")

    stationcode = str(event["stationcode"])
    poll_id = event["poll_id"]

    if not isinstance(poll_id, str) or not poll_id:
        raise ValueError("Invalid poll_id")

    if not stationcode or stationcode == "None":
        raise ValueError("Invalid stationcode")

    expected_id = f"{poll_id}:{stationcode}"

    if event["event_id"] != expected_id:
        raise ValueError("Event ID mismatch")

    if str(station.get("stationcode")) != stationcode:
        raise ValueError("Station code mismatch")

    for field in ("numbikesavailable", "numdocksavailable"):
        value = station.get(field)

        if type(value) is not int or value < 0:
            raise ValueError(f"Invalid {field}: {value}")

    return event


def process_message(connection, message):
    event = validate_event(message)

    partition_id = message.partition()
    next_offset = message.offset() + 1

    station = event["station"]

    connection.execute("BEGIN TRANSACTION")

    try:
        existing = connection.execute(
            "SELECT 1 FROM station_events WHERE event_id = ?",
            [event["event_id"]],
        ).fetchone()

        inserted = existing is None

        if inserted:
            connection.execute("""
                INSERT INTO station_events (
                    event_id,
                    poll_id,
                    stationcode,
                    collected_at,
                    bikes_available,
                    docks_available,
                    station_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                event["event_id"],
                event["poll_id"],
                str(event["stationcode"]),
                event["collected_at"],
                station["numbikesavailable"],
                station["numdocksavailable"],
                json.dumps(station, ensure_ascii=False),
            ])

        connection.execute("""
            INSERT INTO consumer_offsets (
                topic,
                partition_id,
                next_offset
            )
            VALUES (?, ?, ?)
            ON CONFLICT (topic, partition_id)
            DO UPDATE SET next_offset = excluded.next_offset
        """, [
            TOPIC,
            partition_id,
            next_offset,
        ])

        connection.execute("COMMIT")

        return inserted

    except Exception:
        connection.execute("ROLLBACK")
        raise


def get_starting_partitions(connection, consumer):
    metadata = consumer.list_topics(TOPIC, timeout=10)
    topic_metadata = metadata.topics[TOPIC]

    if topic_metadata.error is not None:
        raise RuntimeError(str(topic_metadata.error))

    partitions = []
    end_offsets = {}

    for partition_id in sorted(topic_metadata.partitions):
        partition = TopicPartition(TOPIC, partition_id)

        low, high = consumer.get_watermark_offsets(
            partition,
            timeout=10,
            cached=False,
        )

        saved = connection.execute("""
            SELECT next_offset
            FROM consumer_offsets
            WHERE topic = ? AND partition_id = ?
        """, [TOPIC, partition_id]).fetchone()

        start = saved[0] if saved else low

        if start < low:
            raise RuntimeError(
                f"Partition {partition_id}: saved offset {start} "
                f"is older than retained offset {low}. "
                "Recovery requires investigating missing data."
            )

        if start > high:
            raise RuntimeError(
                f"Partition {partition_id}: saved offset {start} "
                f"is ahead of broker offset {high}."
            )

        partition.offset = start
        partitions.append(partition)
        end_offsets[partition_id] = high

        print(
            f"Partition {partition_id}: "
            f"start={start}, end={high}"
        )

    return partitions, end_offsets


def export_parquet(connection):
    PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = PARQUET_PATH.with_suffix(".parquet.tmp")

    temporary_path.unlink(missing_ok=True)

    try:
        # Export the committed database state to a temporary file.
        connection.execute("""
            COPY (
                SELECT *
                FROM station_events
                ORDER BY poll_id, stationcode
            )
            TO ?
            (FORMAT PARQUET, COMPRESSION ZSTD)
        """, [str(temporary_path)])

        # Replace the previous export only after COPY succeeds.
        os.replace(temporary_path, PARQUET_PATH)

    finally:
        temporary_path.unlink(missing_ok=True)


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(DB_PATH))

    consumer = Consumer({
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": "velib-parquet-consumer",
        "enable.auto.commit": False,
        "enable.auto.offset.store": False,
        "auto.offset.reset": "earliest",
    })

    print("\n🚲 VÉLIB' KAFKA CONSUMER")
    print("=" * 45)

    processed = 0
    inserted = 0
    duplicates = 0

    try:
        initialize_database(connection)

        partitions, end_offsets = get_starting_partitions(
            connection,
            consumer,
        )

        consumer.assign(partitions)

        # Track the next offset required from each partition.
        positions = {
            partition.partition: partition.offset
            for partition in partitions
        }

        while any(
            positions[partition_id] < end
            for partition_id, end in end_offsets.items()
        ):
            message = consumer.poll(10.0)

            if message is None:
                raise TimeoutError(
                    "No Kafka message received within 10 seconds"
                )

            if message.error():
                raise KafkaException(message.error())

            partition_id = message.partition()
            offset = message.offset()

            # Ignore messages beyond the captured batch endpoint.
            if offset >= end_offsets[partition_id]:
                continue

            # Never process a message already committed in this run.
            if offset < positions[partition_id]:
                continue

            if offset != positions[partition_id]:
                raise RuntimeError(
                    f"Unexpected offset gap in partition {partition_id}: "
                    f"expected {positions[partition_id]}, got {offset}"
                )

            was_inserted = process_message(connection, message)

            positions[partition_id] = offset + 1
            processed += 1

            crash_after = int(os.environ.get("VELIB_CRASH_AFTER", "0"))

            if crash_after and processed >= crash_after:
                print(f"💥 Simulating crash after {processed} messages", flush=True)
                os._exit(42)

            if was_inserted:
                inserted += 1
            else:
                duplicates += 1

            if processed % 500 == 0:
                print(f"Processed {processed} Kafka messages...")

        print("\nExporting Parquet...")
        export_parquet(connection)

        total_rows = connection.execute(
            "SELECT COUNT(*) FROM station_events"
        ).fetchone()[0]

        print("\n📊 CONSUMER RESULTS")
        print("=" * 45)
        print("Kafka messages processed:", processed)
        print("New rows inserted:", inserted)
        print("Duplicate events skipped:", duplicates)
        print("Total unique database rows:", total_rows)
        print("Parquet file:", PARQUET_PATH)

        print("\n✅ CONSUMPTION COMPLETE")

    finally:
        consumer.close()
        connection.close()


if __name__ == "__main__":
    main()
