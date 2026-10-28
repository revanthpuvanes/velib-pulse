import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb


DATABASE = Path("storage/analytics/velib_analytics.duckdb")
OUTPUT = Path("storage/dashboard/stations.json")


def export_stations(database=DATABASE, output=OUTPUT):
    connection = duckdb.connect(str(database), read_only=True)

    try:
        rows = connection.execute("""
            SELECT
                stationcode,
                station_name,
                latitude,
                longitude,
                station_capacity,
                bikes_available,
                docks_available,
                mechanical_bikes,
                electric_bikes,
                is_renting,
                is_returning,
                last_observed_at
            FROM main.mart_station_latest
            ORDER BY stationcode
        """).fetchall()

    finally:
        connection.close()

    if not rows:
        raise ValueError("Station mart is empty.")

    stations = []
    seen_codes = set()

    for row in rows:
        (
            code,
            name,
            latitude,
            longitude,
            capacity,
            bikes,
            docks,
            mechanical,
            electric,
            is_renting,
            is_returning,
            observed_at,
        ) = row

        if not code or code in seen_codes:
            raise ValueError(f"Missing or duplicate station code: {code}")

        seen_codes.add(code)

        if (
            latitude is None
            or longitude is None
            or not (-90 <= latitude <= 90)
            or not (-180 <= longitude <= 180)
        ):
            raise ValueError(f"Invalid coordinates for station {code}")

        stations.append({
            "stationcode": code,
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "capacity": capacity,
            "bikes_available": bikes,
            "docks_available": docks,
            "mechanical_bikes": mechanical,
            "electric_bikes": electric,
            "is_renting": is_renting,
            "is_returning": is_returning,
            "last_observed_at": observed_at.isoformat(),
        })

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "station_count": len(stations),
        "stations": stations,
    }

    output.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=".stations_",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)

            json.dump(
                payload,
                temporary,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )

            temporary.flush()
            os.fsync(temporary.fileno())

        os.replace(temporary_path, output)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    print("🚲 DASHBOARD STATION EXPORT")
    print("=" * 45)
    print(f"Stations exported: {len(stations)}")
    print(f"Generated at: {payload['generated_at']}")
    print(f"Output: {output}")
    print(f"File size: {output.stat().st_size:,} bytes")


if __name__ == "__main__":
    export_stations()
