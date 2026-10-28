{{ config(severity='warn') }}

SELECT
    event_id,
    bikes_available,
    mechanical_bikes,
    electric_bikes
FROM {{ ref('stg_station_observations') }}
WHERE
    mechanical_bikes IS NOT NULL
    AND electric_bikes IS NOT NULL
    AND bikes_available <> mechanical_bikes + electric_bikes
