SELECT
    phrase,
    groupArray((hour, views_diff)) AS views_by_hour
FROM (
    -- Основной запрос, считающий разницу просмотров
    SELECT
        pv.phrase,
        toHour(pv.dt) AS hour,
        max(pv.views) AS max_views,
        max_views - lagInFrame(max_views, 1, COALESCE(prev_max_views, 0))
            OVER (PARTITION BY pv.phrase ORDER BY toHour(pv.dt)) AS views_diff
    FROM phrases_views AS pv
    -- Оптимизированный подзапрос для поиска числа просмотров до today()
    LEFT JOIN (
        SELECT
            phrase,
            max(views) AS prev_max_views
        FROM phrases_views
        WHERE campaign_id = ?
          AND dt < today()  -- Берем максимум просмотров только до сегодняшнего дня
        GROUP BY phrase
    ) AS pv_prev USING (phrase)
    WHERE pv.dt >= today()
      AND pv.campaign_id = ?
    GROUP BY pv.phrase, hour, prev_max_views
) AS hourly_diffs
WHERE views_diff IS NOT NULL AND views_diff > 0
GROUP BY phrase;
