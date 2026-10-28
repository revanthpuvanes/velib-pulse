import json
from collections import Counter

from confluent_kafka import Consumer, TopicPartition


TOPIC = "velib.producer_recovery_test"


def main():
    consumer = Consumer({
        "bootstrap.servers": "localhost:19092",
        "group.id": "velib-producer-recovery-audit",
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
    })

    try:
        metadata = consumer.list_topics(TOPIC, timeout=10)
        partitions = sorted(metadata.topics[TOPIC].partitions)

        assignments = []
        expected_messages = 0

        for partition in partitions:
            tp = TopicPartition(TOPIC, partition)
            low, high = consumer.get_watermark_offsets(
                tp,
                timeout=10,
                cached=False,
            )

            assignments.append(
                TopicPartition(TOPIC, partition, low)
            )

            expected_messages += high - low

        consumer.assign(assignments)

        counts = Counter()
        processed = 0

        while processed < expected_messages:
            message = consumer.poll(5)

            if message is None:
                raise TimeoutError(
                    "Timed out before reading all Kafka messages"
                )

            if message.error():
                raise RuntimeError(message.error())

            event = json.loads(message.value())
            counts[event["event_id"]] += 1
            processed += 1

        duplicates = sum(
            count - 1
            for count in counts.values()
        )

        print("\n🚲 PRODUCER RECOVERY KAFKA AUDIT")
        print("=" * 45)
        print("Kafka messages:", processed)
        print("Unique event IDs:", len(counts))
        print("Duplicate messages:", duplicates)
        print("Expected unique station events:", 1519)

        assert len(counts) == 1519
        assert processed == len(counts) + duplicates

        print("\n✅ All expected event IDs represented")

    finally:
        consumer.close()


if __name__ == "__main__":
    main()
