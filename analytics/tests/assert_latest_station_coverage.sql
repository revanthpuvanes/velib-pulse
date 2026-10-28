WITH staging_stations AS (

    SELECT DISTINCT stationcode
    FROM {{ ref('stg_station_observations') }}

),

mart_stations AS (

    SELECT stationcode
    FROM {{ ref('mart_station_latest') }}

)

SELECT stationcode
FROM staging_stations

EXCEPT

SELECT stationcode
FROM mart_stations
