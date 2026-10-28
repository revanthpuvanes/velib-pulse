SELECT
    stationcode,
    hour_utc,
    observation_count,
    avg_bikes_available,
    avg_docks_available,
    pct_observations_without_bikes,
    pct_observations_without_docks
FROM {{ ref('mart_hourly_availability') }}
WHERE
    observation_count <= 0
    OR avg_bikes_available < 0
    OR avg_docks_available < 0
    OR pct_observations_without_bikes IS NULL
    OR pct_observations_without_docks IS NULL
    OR pct_observations_without_bikes NOT BETWEEN 0 AND 100
    OR pct_observations_without_docks NOT BETWEEN 0 AND 100
