import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
import requests

from collector import collector


def test_poll_id_rounds_down_to_five_minutes():
    timestamp = datetime(
        2026, 10, 27, 19, 7, 42,
        tzinfo=timezone.utc,
    )

    assert collector.get_poll_id(timestamp) == (
        "2026-10-27T19:05:00Z"
    )


def test_poll_id_stable_within_same_slot():
    first = datetime(
        2026, 10, 27, 19, 5, 1,
        tzinfo=timezone.utc,
    )

    second = datetime(
        2026, 10, 27, 19, 9, 59,
        tzinfo=timezone.utc,
    )

    assert collector.get_poll_id(first) == collector.get_poll_id(second)


def test_poll_id_changes_at_next_slot():
    first = datetime(
        2026, 10, 27, 19, 9, 59,
        tzinfo=timezone.utc,
    )

    second = datetime(
        2026, 10, 27, 19, 10, 0,
        tzinfo=timezone.utc,
    )

    assert collector.get_poll_id(first) != collector.get_poll_id(second)


def test_naive_datetime_rejected():
    with pytest.raises(ValueError):
        collector.get_poll_id(datetime(2026, 10, 27, 19, 5))


def test_fetch_rejects_empty_dataset():
    response = Mock()
    response.json.return_value = []
    response.raise_for_status.return_value = None

    session = Mock()
    session.get.return_value = response

    with pytest.raises(ValueError):
        collector.fetch_stations(session)


def test_fetch_propagates_http_error():
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError(
        "503 Service Unavailable"
    )

    session = Mock()
    session.get.return_value = response

    with pytest.raises(requests.HTTPError):
        collector.fetch_stations(session)


def test_snapshot_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(collector, "OUTPUT_DIR", tmp_path)

    stations = [
        {
            "stationcode": "40001",
            "numbikesavailable": 10,
            "numdocksavailable": 15,
            "duedate": "2026-10-27T19:00:00+00:00",
        }
    ]

    checksum = collector.calculate_checksum(stations)
    poll_id = "2026-10-27T19:05:00Z"

    first_path, first_created = collector.save_snapshot(
        stations, checksum, poll_id
    )

    second_path, second_created = collector.save_snapshot(
        stations, checksum, poll_id
    )

    assert first_created is True
    assert second_created is False
    assert first_path == second_path

    files = list(tmp_path.glob("velib_poll_*.json"))
    assert len(files) == 1

    with first_path.open(encoding="utf-8") as file:
        saved = json.load(file)

    assert saved["poll_id"] == poll_id
    assert saved["station_count"] == 1


def test_retry_configuration():
    session = collector.create_session()

    try:
        adapter = session.get_adapter("https://")
        retry = adapter.max_retries

        assert retry.total == 3
        assert 429 in retry.status_forcelist
        assert 503 in retry.status_forcelist
        assert "GET" in retry.allowed_methods
    finally:
        session.close()
