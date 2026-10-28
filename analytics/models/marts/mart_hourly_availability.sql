{{ config(materialized='table') }}

WITH hourly_observations AS (

    SELECT
        stationcode,
        station_name,

        DATE_TRUNC(
            'hour',
            collected_at AT TIME ZONE 'UTC'
        ) AS hour_utc,

        bikes_available,
        docks_available,
        mechanical_bikes,
        electric_bikes

    FROM {{ ref('stg_station_observations') }}

)

SELECT
    stationcode,
    MAX(station_name) AS station_name,
    hour_utc,

    COUNT(*) AS observation_count,

    ROUND(
        AVG(bikes_available),
        2
    ) AS avg_bikes_available,

    ROUND(
        AVG(docks_available),
        2
    ) AS avg_docks_available,

    ROUND(
        AVG(mechanical_bikes),
        2
    ) AS avg_mechanical_bikes,

    ROUND(
        AVG(electric_bikes),
        2
    ) AS avg_electric_bikes,

    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE bikes_available = 0
        ) / COUNT(*),
        2
    ) AS pct_observations_without_bikes,

    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE docks_available = 0
        ) / COUNT(*),
        2
    ) AS pct_observations_without_docks

FROM hourly_observations

GROUP BY
    stationcode,
    hour_utc
