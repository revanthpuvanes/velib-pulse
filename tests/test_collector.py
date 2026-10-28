import copy

import pytest

from collector.collector import (
    validate_stations,
    calculate_checksum,
)


@pytest.fixture
def sample_stations():
    return [
        {
            "stationcode": "40001",
            "name": "Hôpital Mondor",
            "numbikesavailable": 10,
            "numdocksavailable": 15,
            "duedate": "2026-10-27T18:00:00+00:00",
        },
        {
            "stationcode": "40002",
            "name": "Test Station",
            "numbikesavailable": 5,
            "numdocksavailable": 20,
            "duedate": "2026-10-27T18:00:00+00:00",
        },
    ]


def test_valid_stations(sample_stations):
    assert validate_stations(sample_stations) == 2


def test_missing_required_field(sample_stations):
    stations = copy.deepcopy(sample_stations)

    del stations[0]["stationcode"]

    with pytest.raises(ValueError):
        validate_stations(stations)


def test_duplicate_station_id(sample_stations):
    stations = copy.deepcopy(sample_stations)

    stations[1]["stationcode"] = "40001"

    with pytest.raises(ValueError):
        validate_stations(stations)


def test_negative_bike_count(sample_stations):
    stations = copy.deepcopy(sample_stations)

    stations[0]["numbikesavailable"] = -5

    with pytest.raises(ValueError):
        validate_stations(stations)


def test_checksum_independent_of_order(sample_stations):
    checksum_original = calculate_checksum(sample_stations)

    checksum_reversed = calculate_checksum(
        list(reversed(sample_stations))
    )

    assert checksum_original == checksum_reversed


def test_checksum_changes_when_availability_changes(sample_stations):
    stations = copy.deepcopy(sample_stations)

    original_checksum = calculate_checksum(stations)

    stations[0]["numbikesavailable"] = 12

    new_checksum = calculate_checksum(stations)

    assert original_checksum != new_checksum
