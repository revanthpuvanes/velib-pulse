SELECT
    event_id,
    mechanical_bikes,
    electric_bikes
FROM {{ ref('stg_station_observations') }}
WHERE
    mechanical_bikes < 0
    OR electric_bikes < 0
