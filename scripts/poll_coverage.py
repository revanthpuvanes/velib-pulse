from datetime import datetime, timedelta, timezone


AUTOMATION_START = datetime(
    2026, 10, 27, 21, 20, tzinfo=timezone.utc
)


def calculate_coverage(
    poll_times,
    now,
    grace_seconds=60,
    automation_start=AUTOMATION_START,
):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    if automation_start.tzinfo is None or automation_start.utcoffset() is None:
        raise ValueError("automation_start must be timezone-aware")

    if grace_seconds < 0:
        raise ValueError("grace_seconds cannot be negative")

    now = now.astimezone(timezone.utc)
    automation_start = automation_start.astimezone(timezone.utc)

    poll_times = {
        timestamp.astimezone(timezone.utc)
        for timestamp in poll_times
    }

    eligible_time = now - timedelta(seconds=grace_seconds)

    latest_expected_poll = eligible_time.replace(
        minute=(eligible_time.minute // 5) * 5,
        second=0,
        microsecond=0,
    )

    expected_times = []

    current = automation_start

    while current <= latest_expected_poll:
        expected_times.append(current)
        current += timedelta(minutes=5)

    expected_set = set(expected_times)

    recorded_expected = len(expected_set & poll_times)

    missing = sorted(expected_set - poll_times)

    coverage = (
        recorded_expected / len(expected_times) * 100
        if expected_times
        else None
    )

    return {
        "expected": len(expected_times),
        "recorded": recorded_expected,
        "missing": missing,
        "coverage": coverage,
        "latest_expected_poll": (
            latest_expected_poll if expected_times else None
        ),
    }
