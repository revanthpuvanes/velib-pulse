from unittest.mock import Mock, patch

import pytest

from collector.collector import fetch_stations


def make_response(payload=None, invalid_json=False):
    response = Mock()
    response.status_code = 200
    response.headers = {"Content-Type": "application/json"}
    response.content = b"invalid-json" if invalid_json else b"[]"
    response.raise_for_status.return_value = None

    if invalid_json:
        response.json.side_effect = ValueError("Invalid JSON")
    else:
        response.json.return_value = payload

    return response


def test_invalid_json_then_success():
    session = Mock()

    session.get.side_effect = [
        make_response(invalid_json=True),
        make_response(payload=[{"stationcode": "123"}]),
    ]

    with patch("time.sleep") as sleep:
        result = fetch_stations(session)

    assert result == [{"stationcode": "123"}]
    assert session.get.call_count == 2
    sleep.assert_called_once_with(1)


def test_invalid_json_exhausts_retries():
    session = Mock()

    session.get.side_effect = [
        make_response(invalid_json=True)
        for _ in range(3)
    ]

    with patch("time.sleep"):
        with pytest.raises(
            ValueError,
            match="API returned invalid JSON after 3 attempts",
        ):
            fetch_stations(session)

    assert session.get.call_count == 3


def test_valid_json_does_not_retry():
    session = Mock()
    session.get.return_value = make_response(
        payload=[{"stationcode": "123"}]
    )

    result = fetch_stations(session)

    assert len(result) == 1
    assert session.get.call_count == 1
