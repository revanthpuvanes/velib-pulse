{{ config(materialized='view') }}

WITH source AS (

    SELECT *
    FROM read_parquet(
        '../storage/parquet/incremental/poll_date=*/*.parquet',
        hive_partitioning = true,
        union_by_name = true
    )

),

cleaned AS (

    SELECT
        CAST(event_id AS VARCHAR) AS event_id,
        CAST(poll_id AS VARCHAR) AS poll_id,
        CAST(stationcode AS VARCHAR) AS stationcode,

        CAST(collected_at AS TIMESTAMPTZ) AS collected_at,

        CAST(bikes_available AS INTEGER) AS bikes_available,
        CAST(docks_available AS INTEGER) AS docks_available,

        CAST(
            json_extract_string(station_json, '$.name')
            AS VARCHAR
        ) AS station_name,

        TRY_CAST(
            json_extract_string(station_json, '$.capacity')
            AS INTEGER
        ) AS station_capacity,

        TRY_CAST(
            json_extract_string(station_json, '$.coordonnees_geo.lat')
            AS DOUBLE
        ) AS latitude,

        TRY_CAST(
            json_extract_string(station_json, '$.coordonnees_geo.lon')
            AS DOUBLE
        ) AS longitude,

        TRY_CAST(
            json_extract_string(station_json, '$.mechanical')
            AS INTEGER
        ) AS mechanical_bikes,

        TRY_CAST(
            json_extract_string(station_json, '$.ebike')
            AS INTEGER
        ) AS electric_bikes,

        TRY_CAST(
            json_extract_string(station_json, '$.is_renting')
            AS BOOLEAN
        ) AS is_renting,

        TRY_CAST(
            json_extract_string(station_json, '$.is_returning')
            AS BOOLEAN
        ) AS is_returning

    FROM source

)

SELECT *
FROM cleaned
