SELECT
    stationcode,
    station_name,
    latitude,
    longitude
FROM {{ ref('mart_station_latest') }}
WHERE latitude IS NULL
   OR longitude IS NULL
   OR NOT (latitude BETWEEN -90 AND 90)
   OR NOT (longitude BETWEEN -180 AND 180)
