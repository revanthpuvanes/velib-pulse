SELECT
    stationcode,
    bikes_available,
    docks_available
FROM {{ ref('mart_station_latest') }}
WHERE
    bikes_available < 0
    OR docks_available < 0
