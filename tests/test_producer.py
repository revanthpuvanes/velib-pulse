import sqlite3
from unittest.mock import Mock

import pytest

from producer import producer


class FakeProducer:
    """Simulate successful Kafka delivery without a real broker."""

    def __init__(self, config):
        self.config = config
        self.messages = []

    def produce(self, topic, key, value, callback):
        message = Mock()
        message.key.return_value = key
        message.value.return_value = value

        self.messages.append((topic, key, value))
        callback(None, message)

    def poll(self, timeout):
        return 0

    def flush(self, timeout):
        return 0


@pytest.fixture
def snapshot():
    stations = [
        {
            "stationcode": "40001",
            "numbikesavailable": 10,
            "numdocksavailable": 15,
            "duedate": "2026-10-27T20:10:00+00:00",
        },
        {
            "stationcode": "40002",
            "numbikesavailable": 5,
            "numdocksavailable": 20,
            "duedate": "2026-10-27T20:10:00+00:00",
        },
    ]

    return {
        "poll_id": "2026-10-27T20:10:00Z",
        "collected_at": "2026-10-27T20:11:00+00:00",
        "station_count": 2,
        "checksum": producer.calculate_checksum(stations),
        "stations": stations,
    }


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "producer.sqlite"
    connection = sqlite3.connect(path)

    producer.initialize_state(connection)

    yield connection

    connection.close()


def test_first_publish_records_checkpoints(
    snapshot, database, monkeypatch
):
    instances = []

    def create_fake(config):
        instance = FakeProducer(config)
        instances.append(instance)
        return instance

    monkeypatch.setattr(producer, "Producer", create_fake)

    producer.publish_snapshot(snapshot, database)

    count = database.execute(
        "SELECT COUNT(*) FROM published_events"
    ).fetchone()[0]

    assert count == 2
    assert len(instances[0].messages) == 2


def test_second_publish_skips_existing_events(
    snapshot, database, monkeypatch
):
    instances = []

    def create_fake(config):
        instance = FakeProducer(config)
        instances.append(instance)
        return instance

    monkeypatch.setattr(producer, "Producer", create_fake)

    producer.publish_snapshot(snapshot, database)
    producer.publish_snapshot(snapshot, database)

    assert len(instances[0].messages) == 2
    assert len(instances[1].messages) == 0

    count = database.execute(
        "SELECT COUNT(*) FROM published_events"
    ).fetchone()[0]

    assert count == 2


def test_conflicting_snapshot_is_rejected(
    snapshot, database, monkeypatch
):
    monkeypatch.setattr(producer, "Producer", FakeProducer)

    producer.publish_snapshot(snapshot, database)

    modified = {
        **snapshot,
        "stations": [
            {**snapshot["stations"][0], "numbikesavailable": 11},
            snapshot["stations"][1],
        ],
    }

    modified["checksum"] = producer.calculate_checksum(
        modified["stations"]
    )

    with pytest.raises(ValueError, match="Conflicting snapshot"):
        producer.publish_snapshot(modified, database)
