SELECT
    stationcode,
    hour_utc,
    COUNT(*) AS duplicate_count
FROM {{ ref('mart_hourly_availability') }}
GROUP BY
    stationcode,
    hour_utc
HAVING COUNT(*) > 1
