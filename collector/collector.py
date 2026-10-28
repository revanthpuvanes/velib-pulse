import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


API_URL = (
    "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
    "velib-disponibilite-en-temps-reel/exports/json"
)

OUTPUT_DIR = Path("storage/raw")
POLL_INTERVAL_SECONDS = 300

REQUIRED_FIELDS = {
    "stationcode",
    "numbikesavailable",
    "numdocksavailable",
    "duedate",
}


def create_session():
    """Create an HTTP session with retries and backoff."""

    retry_strategy = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)

    session = requests.Session()
    session.mount("https://", adapter)

    return session


def get_poll_id(now=None):
    """Return the UTC five-minute slot identifier."""

    if now is None:
        now = datetime.now(timezone.utc)

    if now.tzinfo is None:
        raise ValueError("Poll time must be timezone-aware")

    now = now.astimezone(timezone.utc)

    seconds = int(now.timestamp())
    slot_start = seconds - (seconds % POLL_INTERVAL_SECONDS)

    return datetime.fromtimestamp(
        slot_start, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_stations(session):
    """Fetch stations, retrying transient JSON decoding failures."""
    import time

    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        response = session.get(API_URL, timeout=(5, 30))
        response.raise_for_status()

        try:
            stations = response.json()
        except ValueError as error:
            content_type = response.headers.get(
                "Content-Type", "unknown"
            )

            print(
                f"Invalid API JSON "
                f"(attempt {attempt}/{max_attempts}, "
                f"HTTP {response.status_code}, "
                f"content_type={content_type}, "
                f"bytes={len(response.content)})",
                flush=True,
            )

            if attempt == max_attempts:
                raise ValueError(
                    "API returned invalid JSON after "
                    f"{max_attempts} attempts"
                ) from error

            time.sleep(attempt)
            continue

        if not isinstance(stations, list) or not stations:
            raise ValueError("Expected a non-empty station list")

        return stations

    raise RuntimeError("Unreachable: API retry loop exhausted")


def validate_stations(stations):
    """Validate station identifiers and availability fields."""

    station_ids = set()

    for station in stations:
        if not isinstance(station, dict):
            raise ValueError("Invalid station record")

        missing = REQUIRED_FIELDS - station.keys()

        if missing:
            raise ValueError(f"Missing fields: {missing}")

        station_id = str(station["stationcode"])

        if not station_id or station_id == "None":
            raise ValueError("Invalid station ID")

        if station_id in station_ids:
            raise ValueError(f"Duplicate station ID: {station_id}")

        station_ids.add(station_id)

        for field in ("numbikesavailable", "numdocksavailable"):
            value = station[field]

            if type(value) is not int or value < 0:
                raise ValueError(
                    f"Invalid {field} for station {station_id}: {value}"
                )

    return len(station_ids)


def calculate_checksum(stations):
    """Calculate a deterministic dataset checksum."""

    ordered = sorted(
        stations,
        key=lambda station: str(station["stationcode"]),
    )

    serialized = json.dumps(
        ordered,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def save_snapshot(stations, checksum, poll_id):
    """Atomically save one snapshot per scheduled poll."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    safe_poll_id = poll_id.replace(":", "").replace("-", "")

    output_path = OUTPUT_DIR / f"velib_poll_{safe_poll_id}.json"

    # Never overwrite a successfully committed poll.
    if output_path.exists():
        return output_path, False

    collected_at = datetime.now(timezone.utc)

    snapshot = {
        "poll_id": poll_id,
        "collected_at": collected_at.isoformat(),
        "source": "paris_open_data",
        "station_count": len(stations),
        "checksum": checksum,
        "stations": stations,
    }

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=OUTPUT_DIR,
            prefix=".velib_",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)

            json.dump(
                snapshot,
                file,
                ensure_ascii=False,
            )

            file.flush()
            os.fsync(file.fileno())

        # Create the destination without overwriting an existing snapshot.
        os.link(temporary_path, output_path)

        return output_path, True

    except FileExistsError:
        return output_path, False

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main():
    print("\n🚲 VÉLIB' RELIABLE COLLECTOR")
    print("=" * 45)

    poll_id = os.environ.get("VELIB_POLL_ID") or get_poll_id()

    print("Poll ID:", poll_id)

    session = create_session()

    try:
        stations = fetch_stations(session)

        count = validate_stations(stations)
        checksum = calculate_checksum(stations)

        output_path, created = save_snapshot(
            stations,
            checksum,
            poll_id,
        )

        print("Stations received:", count)
        print("Checksum:", checksum)

        if created:
            print("✅ New snapshot committed:", output_path)
        else:
            print("♻️ Poll already exists. Skipping duplicate.")
            print("Existing snapshot:", output_path)

        print("\n✅ COLLECTION COMPLETE")

    except (requests.RequestException, ValueError, OSError) as error:
        print("❌ Collection failed:", error)
        raise SystemExit(1) from error

    finally:
        session.close()


if __name__ == "__main__":
    main()
