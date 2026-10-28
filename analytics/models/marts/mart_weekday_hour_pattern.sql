{{ config(materialized='table') }}
-- Paris-local day/hour, including daylight-saving behavior from timezone conversion.
WITH samples AS (
 SELECT stationcode, bikes_available,
        collected_at AT TIME ZONE 'Europe/Paris' AS paris_time
 FROM {{ ref('stg_station_observations') }}
 WHERE collected_at >= CURRENT_TIMESTAMP - INTERVAL '28 days'
)
SELECT CAST(EXTRACT(isodow FROM paris_time) AS INTEGER) AS weekday_iso,
       CAST(EXTRACT(hour FROM paris_time) AS INTEGER) AS hour_local,
       COUNT(*) AS observation_count,
       COUNT(DISTINCT stationcode) AS station_count,
       ROUND(AVG(bikes_available),2) AS avg_bikes_available,
       ROUND(100.0 * COUNT(*) FILTER (WHERE bikes_available=0)/NULLIF(COUNT(*),0),2) AS empty_pct
FROM samples
GROUP BY 1,2
