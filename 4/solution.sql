WITH
    hourly_views AS (
        SELECT
            phrase,
            toHour(dt) AS hour,
            min(views) AS min_views,
            max(views) AS max_views
        FROM phrases_views
        WHERE dt >= today()
          AND campaign_id = ?
        GROUP BY phrase, hour
    ),
    hourly_diffs AS (
        SELECT
            phrase,
            hour,
            max_views - lagInFrame(max_views, 1, min_views) OVER (PARTITION BY phrase ORDER BY hour) AS views_diff
        FROM hourly_views
    )

SELECT
    phrase,
    groupArray((hour, views_diff)) AS views_by_hour
FROM hourly_diffs
WHERE views_diff IS NOT NULL AND views_diff > 0
GROUP BY phrase;
