SELECT
    event_id,
    bikes_available,
    docks_available
FROM {{ ref('stg_station_observations') }}
WHERE
    bikes_available < 0
    OR docks_available < 0
