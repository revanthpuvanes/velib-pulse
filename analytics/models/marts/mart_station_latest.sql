{{ config(materialized='table') }}

WITH ranked AS (

    SELECT
        stationcode,
        station_name,
        collected_at,
        poll_id,
        station_capacity,
    latitude,
    longitude,
        bikes_available,
        docks_available,
        mechanical_bikes,
        electric_bikes,
        is_renting,
        is_returning,

        ROW_NUMBER() OVER (
            PARTITION BY stationcode
            ORDER BY collected_at DESC, poll_id DESC, event_id DESC
        ) AS row_num

    FROM {{ ref('stg_station_observations') }}

)

SELECT
    stationcode,
    station_name,
    collected_at AS last_observed_at,
    poll_id AS last_poll_id,
    station_capacity,
    latitude,
    longitude,
    bikes_available,
    docks_available,
    mechanical_bikes,
    electric_bikes,
    is_renting,
    is_returning

FROM ranked

WHERE row_num = 1
