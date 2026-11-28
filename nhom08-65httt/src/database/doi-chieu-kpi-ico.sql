-- CF-005 (Mốc A): Truy vấn SQL chỉ đọc đối chiếu 3 KPI thị trường từ dữ liệu ICO hiện có.
-- Bảng thực tế theo nhom08-65httt/src/backend/market/models.py:
--   market_source, raw_collection_run, dw_price_series, dw_price_observation.
-- Quy ước: chỉ chọn bản giá hiện hành (o.is_current = TRUE), không trộn chuỗi hoặc đơn vị,
-- thiếu dữ liệu trả NULL (không mặc định thành 0).

-- =============================================================================
-- KPI 1: Giá ICO mới nhất hợp lệ của một chuỗi (mẫu: robustas; và bảng tất cả chuỗi ICO)
-- =============================================================================
SELECT s.code AS source,
       series.code AS series,
       series.name AS series_name,
       series.commodity,
       series.price_type,
       series.market,
       series.currency,
       series.unit,
       o.effective_date,
       o.value AS latest_value,
       o.revision,
       o.id AS observation_id,
       r.id AS run_id,
       r.source_url,
       r.collected_at
FROM dw_price_observation AS o
JOIN dw_price_series AS series ON series.id = o.series_id
JOIN market_source AS s ON s.id = series.source_id
JOIN raw_collection_run AS r ON r.id = o.run_id
WHERE s.code = 'ico'
  AND series.code = 'robustas'
  AND o.is_current = TRUE
  AND o.value > 0
ORDER BY o.effective_date DESC, o.id DESC
LIMIT 1;

-- Giá mới nhất hợp lệ cho từng chuỗi thuộc nguồn ICO (không cộng gộp giữa các chuỗi).
SELECT DISTINCT ON (series.id)
       s.code AS source,
       series.code AS series,
       series.name AS series_name,
       series.currency,
       series.unit,
       o.effective_date,
       o.value AS latest_value,
       o.revision,
       o.id AS observation_id,
       r.id AS run_id,
       r.collected_at
FROM dw_price_observation AS o
JOIN dw_price_series AS series ON series.id = o.series_id
JOIN market_source AS s ON s.id = series.source_id
JOIN raw_collection_run AS r ON r.id = o.run_id
WHERE s.code = 'ico'
  AND o.is_current = TRUE
  AND o.value > 0
ORDER BY series.id, o.effective_date DESC, o.id DESC;

-- =============================================================================
-- KPI 2: Hai quan sát hợp lệ liên tiếp và phần trăm biến động của chuỗi
-- Công thức: (giá mới - giá trước) / giá trước * 100
-- Nếu thiếu mốc trước hoặc giá trước <= 0 thì trả NULL, không mặc định 0.
-- =============================================================================
WITH ranked_obs AS (
    SELECT series.id AS series_id,
           s.code AS source,
           series.code AS series,
           series.name AS series_name,
           series.currency,
           series.unit,
           o.id AS observation_id,
           o.effective_date,
           o.value,
           o.revision,
           ROW_NUMBER() OVER (
               PARTITION BY series.id
               ORDER BY o.effective_date DESC, o.id DESC
           ) AS rn
    FROM dw_price_observation AS o
    JOIN dw_price_series AS series ON series.id = o.series_id
    JOIN market_source AS s ON s.id = series.source_id
    WHERE s.code = 'ico'
      AND o.is_current = TRUE
      AND o.value > 0
),
latest AS (
    SELECT * FROM ranked_obs WHERE rn = 1
),
previous AS (
    SELECT * FROM ranked_obs WHERE rn = 2
)
SELECT l.source,
       l.series,
       l.series_name,
       l.currency,
       l.unit,
       l.effective_date AS latest_date,
       l.value AS latest_value,
       p.effective_date AS previous_date,
       p.value AS previous_value,
       CASE
           WHEN p.value IS NULL OR p.value <= 0 THEN NULL
           ELSE ((l.value - p.value) / p.value) * 100
       END AS pct_change_raw,
       CASE
           WHEN p.value IS NULL OR p.value <= 0 THEN NULL
           ELSE ROUND(((l.value - p.value) / p.value) * 100, 4)
       END AS pct_change_4dp
FROM latest AS l
LEFT JOIN previous AS p ON p.series_id = l.series_id
ORDER BY l.series;

-- =============================================================================
-- KPI 3: Độ mới dữ liệu (tuổi dữ liệu theo độ phân giải ngày của ICO)
-- Tách biệt effective_date (ngày hiệu lực giá) với collected_at (thời điểm collector tải).
-- =============================================================================
WITH latest_price AS (
    SELECT series.id AS series_id,
           s.code AS source,
           series.code AS series,
           series.unit,
           MAX(o.effective_date) AS latest_effective_date
    FROM dw_price_observation AS o
    JOIN dw_price_series AS series ON series.id = o.series_id
    JOIN market_source AS s ON s.id = series.source_id
    WHERE s.code = 'ico'
      AND o.is_current = TRUE
      AND o.value > 0
    GROUP BY series.id, s.code, series.code, series.unit
),
latest_run AS (
    SELECT r.id AS latest_run_id,
           r.status AS latest_run_status,
           r.collected_at AS latest_collected_at
    FROM raw_collection_run AS r
    JOIN market_source AS s ON s.id = r.source_id
    WHERE s.code = 'ico'
    ORDER BY r.id DESC
    LIMIT 1
)
SELECT lp.source,
       lp.series,
       lp.unit,
       lp.latest_effective_date,
       (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS reference_date_vn,
       CASE
           WHEN lp.latest_effective_date IS NULL THEN NULL
           ELSE ((CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh')::date - lp.latest_effective_date)
       END AS data_age_days,
       lr.latest_run_id,
       lr.latest_run_status,
       lr.latest_collected_at
FROM latest_price AS lp
CROSS JOIN latest_run AS lr
ORDER BY lp.series;
