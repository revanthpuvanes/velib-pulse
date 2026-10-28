{{ config(materialized='table') }}
-- Hourly sampled availability for the last seven days, bounded for dashboard export.
SELECT stationcode, station_name, hour_utc, observation_count,
       avg_bikes_available, avg_docks_available,
       pct_observations_without_bikes
FROM {{ ref('mart_hourly_availability') }}
WHERE hour_utc >= (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') - INTERVAL '7 days'
