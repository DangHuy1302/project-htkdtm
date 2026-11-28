-- CF-005: Truy vấn SQL chỉ đọc phục vụ đối chiếu chuỗi thời gian (TT03)
-- và chất lượng dữ liệu ICO (CL01, CL02, CL03) theo docs/dac-ta-dashboard.md.

-- =============================================================================
-- 1. Chuỗi thời gian giá ICO hợp lệ cho biểu đồ đường Robustas (TT03)
-- =============================================================================
SELECT o.effective_date,
       series.code AS series,
       series.name AS series_name,
       o.value,
       series.currency,
       series.unit,
       o.revision,
       o.id AS observation_id,
       r.id AS run_id
FROM dw_price_observation AS o
JOIN dw_price_series AS series ON series.id = o.series_id
JOIN market_source AS s ON s.id = series.source_id
JOIN raw_collection_run AS r ON r.id = o.run_id
WHERE s.code = 'ico'
  AND series.code = 'robustas'
  AND o.is_current = TRUE
  AND o.value > 0
ORDER BY o.effective_date ASC, o.id ASC;

-- =============================================================================
-- 2. Kiểm tra chống trùng bản hiện hành (phải trả về 0 dòng)
-- =============================================================================
SELECT series_id,
       effective_date,
       COUNT(*) AS current_row_count
FROM dw_price_observation
WHERE is_current = TRUE
GROUP BY series_id, effective_date
HAVING COUNT(*) > 1;

-- =============================================================================
-- 3. Tỷ lệ bản ghi hợp lệ theo từng lần chạy collector ICO (CL02)
-- Mẫu số = 0 trả NULL, không chia cho 0 hoặc mặc định 0%.
-- =============================================================================
SELECT r.id AS run_id,
       s.code AS source,
       r.status,
       r.http_status,
       r.started_at,
       r.collected_at,
       r.finished_at,
       r.rows_received,
       r.created_count,
       r.revised_count,
       r.unchanged_count,
       r.rejected_count,
       (r.rows_received - r.rejected_count) AS valid_rows,
       CASE
           WHEN r.rows_received IS NULL OR r.rows_received = 0 THEN NULL
           ELSE ROUND(((r.rows_received - r.rejected_count)::numeric / r.rows_received) * 100, 2)
       END AS valid_rate_pct
FROM raw_collection_run AS r
JOIN market_source AS s ON s.id = r.source_id
WHERE s.code = 'ico'
ORDER BY r.id DESC;

-- =============================================================================
-- 4. Chi tiết dòng bị cách ly / lỗi chất lượng của nguồn ICO (CL03)
-- =============================================================================
SELECT q.id AS issue_id,
       r.id AS run_id,
       r.collected_at,
       r.status AS run_status,
       q.reason,
       q.line
FROM raw_quality_issue AS q
JOIN raw_collection_run AS r ON r.id = q.run_id
JOIN market_source AS s ON s.id = r.source_id
WHERE s.code = 'ico'
ORDER BY q.id DESC
LIMIT 50;
