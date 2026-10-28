import json
from collections import Counter

from confluent_kafka import Consumer, KafkaException, TopicPartition


TOPIC = "velib.station_status"


def main():
    consumer = Consumer({
        "bootstrap.servers": "localhost:19092",
        "group.id": "velib-duplicate-audit",
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
    })

    try:
        metadata = consumer.list_topics(TOPIC, timeout=10)
        topic_metadata = metadata.topics[TOPIC]

        if topic_metadata.error is not None:
            raise RuntimeError(str(topic_metadata.error))

        partitions = [
            TopicPartition(TOPIC, partition_id)
            for partition_id in sorted(topic_metadata.partitions)
        ]

        # Capture a fixed endpoint for each partition.
        end_offsets = {}

        for partition in partitions:
            low, high = consumer.get_watermark_offsets(
                partition,
                timeout=10,
                cached=False,
            )

            end_offsets[partition.partition] = high
            partition.offset = low

        consumer.assign(partitions)

        counts = Counter()
        invalid_messages = 0
        read_counts = Counter()

        while True:
            finished = all(
                read_counts[p.partition] >= end_offsets[p.partition] - p.offset
                for p in partitions
            )

            if finished:
                break

            message = consumer.poll(5.0)

            if message is None:
                raise TimeoutError(
                    "Timed out before reaching captured partition endpoints"
                )

            if message.error():
                raise KafkaException(message.error())

            partition_id = message.partition()

            if message.offset() >= end_offsets[partition_id]:
                continue

            read_counts[partition_id] += 1

            try:
                event = json.loads(message.value())
                event_id = event["event_id"]

                if not isinstance(event_id, str) or not event_id:
                    raise ValueError("Invalid event_id")

                counts[event_id] += 1

            except (ValueError, TypeError, KeyError):
                invalid_messages += 1

        total_valid = sum(counts.values())
        unique = len(counts)
        duplicates = sum(count - 1 for count in counts.values())

        print("\n🚲 KAFKA DUPLICATE AUDIT")
        print("=" * 45)
        print("Total messages:", total_valid + invalid_messages)
        print("Valid messages:", total_valid)
        print("Unique event IDs:", unique)
        print("Duplicate messages:", duplicates)
        print("Invalid messages:", invalid_messages)
        print("Partitions checked:", len(partitions))

        print("\nTop repeated event IDs:")

        for event_id, count in counts.most_common(5):
            print(f"  {event_id}: {count} copies")

        print("\n✅ AUDIT COMPLETE")

    finally:
        consumer.close()


if __name__ == "__main__":
    main()
