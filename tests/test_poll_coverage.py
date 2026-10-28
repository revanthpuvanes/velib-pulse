from datetime import datetime, timedelta, timezone

from scripts.poll_coverage import (
    AUTOMATION_START,
    calculate_coverage,
)


def test_all_polls_present():
    polls = {
        AUTOMATION_START + timedelta(minutes=5 * i)
        for i in range(5)
    }

    now = datetime(
        2026, 10, 27, 21, 41, tzinfo=timezone.utc
    )

    result = calculate_coverage(polls, now)

    assert result["expected"] == 5
    assert result["recorded"] == 5
    assert len(result["missing"]) == 0
    assert result["coverage"] == 100.0


def test_missing_poll_detected():
    polls = {
        AUTOMATION_START,
        AUTOMATION_START + timedelta(minutes=5),
        AUTOMATION_START + timedelta(minutes=15),
        AUTOMATION_START + timedelta(minutes=20),
    }

    now = datetime(
        2026, 10, 27, 21, 41, tzinfo=timezone.utc
    )

    result = calculate_coverage(polls, now)

    assert result["expected"] == 5
    assert result["recorded"] == 4
    assert len(result["missing"]) == 1
    assert result["missing"][0] == (
        AUTOMATION_START + timedelta(minutes=10)
    )
    assert result["coverage"] == 80.0


def test_stopped_pipeline_detected():
    polls = {
        AUTOMATION_START,
        AUTOMATION_START + timedelta(minutes=5),
    }

    now = datetime(
        2026, 10, 27, 21, 41, tzinfo=timezone.utc
    )

    result = calculate_coverage(polls, now)

    assert result["expected"] == 5
    assert result["recorded"] == 2
    assert len(result["missing"]) == 3
    assert result["coverage"] == 40.0


def test_in_progress_poll_not_counted_as_missing():
    polls = {
        AUTOMATION_START,
        AUTOMATION_START + timedelta(minutes=5),
    }

    # 21:30 poll has started, but its 60-second grace
    # period has not elapsed.
    now = datetime(
        2026, 10, 27, 21, 30, 30, tzinfo=timezone.utc
    )

    result = calculate_coverage(polls, now)

    assert result["expected"] == 2
    assert result["recorded"] == 2
    assert len(result["missing"]) == 0
    assert result["coverage"] == 100.0
