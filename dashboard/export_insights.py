"""Export bounded, observed historical mobility analytics for the frontend."""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import duckdb

DATABASE = Path('storage/analytics/velib_analytics.duckdb')
OUTPUT = Path('storage/dashboard/insights.json')

def export_insights(database=DATABASE, output=OUTPUT):
    con = duckdb.connect(str(database), read_only=True)
    try:
        history_rows = con.execute("""
            SELECT stationcode, hour_utc, observation_count,
                   avg_bikes_available, avg_docks_available,
                   pct_observations_without_bikes
            FROM main.mart_station_history
            ORDER BY stationcode, hour_utc
        """).fetchall()
        empty_rows = con.execute("""
            SELECT stationcode, station_name, observation_count,
                   empty_observations, empty_pct,
                   first_observed_at, last_observed_at
            FROM main.mart_station_empty_frequency
            ORDER BY empty_pct DESC, observation_count DESC
        """).fetchall()
        pattern_rows = con.execute("""
            SELECT weekday_iso, hour_local, observation_count, station_count,
                   avg_bikes_available, empty_pct
            FROM main.mart_weekday_hour_pattern
            ORDER BY weekday_iso, hour_local
        """).fetchall()
    finally:
        con.close()
    if not history_rows or not empty_rows or not pattern_rows:
        raise ValueError('At least one insights mart is empty')
    history = {}
    for code, hour, n, bikes, docks, empty_pct in history_rows:
        history.setdefault(code, []).append([
            hour.replace(tzinfo=timezone.utc).isoformat(), n, bikes, docks, empty_pct
        ])
    empty = [
        {'stationcode':code, 'station_name':name, 'observation_count':n,
         'empty_observations':zero, 'empty_pct':pct,
         'first_observed_at':first.isoformat(), 'last_observed_at':last.isoformat()}
        for code,name,n,zero,pct,first,last in empty_rows
    ]
    patterns = [
        {'weekday_iso':day, 'hour_local':hour, 'observation_count':n,
         'station_count':stations, 'avg_bikes_available':bikes, 'empty_pct':pct}
        for day,hour,n,stations,bikes,pct in pattern_rows
    ]
    payload = {
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'history_window_days':7, 'empty_window_days':7, 'pattern_window_days':28,
        'history_by_station':history, 'empty_frequency':empty,
        'weekday_hour_pattern':patterns,
    }
    output.parent.mkdir(parents=True,exist_ok=True)
    temp_path=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=output.parent,
                                         prefix='.insights_',suffix='.tmp',delete=False) as temp:
            temp_path=Path(temp.name)
            json.dump(payload,temp,separators=(',',':'),allow_nan=False)
            temp.flush(); os.fsync(temp.fileno())
        os.replace(temp_path,output)
    finally:
        if temp_path is not None: temp_path.unlink(missing_ok=True)
    print(f'Insights: {len(history)} stations, {len(history_rows)} hourly points, '
          f'{len(empty)} empty-frequency rows, {len(patterns)} weekday/hour cells')
    print(f'Output: {output} ({output.stat().st_size:,} bytes)')

if __name__ == '__main__':
    export_insights()
