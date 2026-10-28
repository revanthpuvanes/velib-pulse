{{ config(materialized='table') }}
-- Percentage of recorded samples with zero bikes; not a continuous-time estimate.
SELECT stationcode, MAX(station_name) AS station_name,
       COUNT(*) AS observation_count,
       COUNT(*) FILTER (WHERE bikes_available = 0) AS empty_observations,
       ROUND(100.0 * COUNT(*) FILTER (WHERE bikes_available = 0) / NULLIF(COUNT(*),0),2) AS empty_pct,
       MIN(collected_at) AS first_observed_at,
       MAX(collected_at) AS last_observed_at
FROM {{ ref('stg_station_observations') }}
WHERE collected_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
GROUP BY stationcode
