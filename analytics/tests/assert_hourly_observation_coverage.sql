WITH hourly_counts AS (

    SELECT
        hour_utc,
        MIN(observation_count) AS min_observations,
        MAX(observation_count) AS max_observations
    FROM {{ ref('mart_hourly_availability') }}
    GROUP BY hour_utc

)

SELECT *
FROM hourly_counts
WHERE min_observations <> max_observations
