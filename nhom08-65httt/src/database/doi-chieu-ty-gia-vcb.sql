-- CF-005: Truy vấn SQL chỉ đọc đối chiếu tỷ giá Vietcombank (FX) phục vụ Dashboard 2 & quy đổi tham chiếu.
-- Bảng thực tế theo nhom08-65httt/src/backend/market/models.py:
--   market_source, raw_collection_run, dw_fx_observation.
-- Quy ước: tách riêng 3 loại tỷ giá (cash_buy, transfer_buy, sell), chỉ chọn bản hiện hành (is_current = TRUE),
-- thiếu dữ liệu trả NULL (không mặc định thành 0).

-- =============================================================================
-- 1. Tỷ giá USD mới nhất hợp lệ theo từng loại (cash_buy, transfer_buy, sell)
-- =============================================================================
SELECT DISTINCT ON (fx.rate_type)
       s.code AS source,
       fx.currency_code,
       fx.currency_name,
       fx.rate_type,
       fx.value AS latest_rate_vnd,
       fx.effective_at,
       fx.revision,
       fx.id AS observation_id,
       r.id AS run_id,
       r.collected_at
FROM dw_fx_observation AS fx
JOIN market_source AS s ON s.id = fx.source_id
JOIN raw_collection_run AS r ON r.id = fx.run_id
WHERE s.code = 'vietcombank'
  AND fx.currency_code = 'USD'
  AND fx.is_current = TRUE
  AND fx.value > 0
ORDER BY fx.rate_type, fx.effective_at DESC, fx.id DESC;

-- =============================================================================
-- 2. Biến động tỷ giá USD giữa 2 mốc effective_at hợp lệ liên tiếp theo từng rate_type
-- Nếu thiếu mốc trước hoặc giá trị trước <= 0 thì trả NULL.
-- =============================================================================
WITH ranked_fx AS (
    SELECT s.code AS source,
           fx.currency_code,
           fx.rate_type,
           fx.id AS observation_id,
           fx.effective_at,
           fx.value,
           ROW_NUMBER() OVER (
               PARTITION BY fx.currency_code, fx.rate_type
               ORDER BY fx.effective_at DESC, fx.id DESC
           ) AS rn
    FROM dw_fx_observation AS fx
    JOIN market_source AS s ON s.id = fx.source_id
    WHERE s.code = 'vietcombank'
      AND fx.currency_code = 'USD'
      AND fx.is_current = TRUE
      AND fx.value > 0
),
latest AS (
    SELECT * FROM ranked_fx WHERE rn = 1
),
previous AS (
    SELECT * FROM ranked_fx WHERE rn = 2
)
SELECT l.source,
       l.currency_code,
       l.rate_type,
       l.effective_at AS latest_effective_at,
       l.value AS latest_rate_vnd,
       p.effective_at AS previous_effective_at,
       p.value AS previous_rate_vnd,
       CASE
           WHEN p.value IS NULL OR p.value <= 0 THEN NULL
           ELSE ((l.value - p.value) / p.value) * 100
       END AS pct_change_raw,
       CASE
           WHEN p.value IS NULL OR p.value <= 0 THEN NULL
           ELSE ROUND(((l.value - p.value) / p.value) * 100, 4)
       END AS pct_change_4dp
FROM latest AS l
LEFT JOIN previous AS p
       ON p.currency_code = l.currency_code
      AND p.rate_type = l.rate_type
ORDER BY l.rate_type;

-- =============================================================================
-- 3. Độ mới dữ liệu tỷ giá (giờ) theo effective_at, tách với collected_at
-- =============================================================================
WITH latest_fx_time AS (
    SELECT fx.currency_code,
           fx.rate_type,
           MAX(fx.effective_at) AS latest_effective_at
    FROM dw_fx_observation AS fx
    JOIN market_source AS s ON s.id = fx.source_id
    WHERE s.code = 'vietcombank'
      AND fx.currency_code = 'USD'
      AND fx.is_current = TRUE
      AND fx.value > 0
    GROUP BY fx.currency_code, fx.rate_type
),
latest_run AS (
    SELECT r.id AS latest_run_id,
           r.status AS latest_run_status,
           r.collected_at AS latest_collected_at
    FROM raw_collection_run AS r
    JOIN market_source AS s ON s.id = r.source_id
    WHERE s.code = 'vietcombank'
    ORDER BY r.id DESC
    LIMIT 1
)
SELECT lf.currency_code,
       lf.rate_type,
       lf.latest_effective_at,
       CURRENT_TIMESTAMP AS reference_time_utc,
       ROUND(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - lf.latest_effective_at)) / 3600.0, 2) AS data_age_hours,
       lr.latest_run_id,
       lr.latest_run_status,
       lr.latest_collected_at
FROM latest_fx_time AS lf
CROSS JOIN latest_run AS lr
ORDER BY lf.rate_type;
