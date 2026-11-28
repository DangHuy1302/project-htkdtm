# Hướng dẫn chạy đối chiếu SQL và chuẩn bị Superset (CF-005)

Tài liệu này hướng dẫn cách chạy các truy vấn đối chiếu KPI và chất lượng dữ liệu trên PostgreSQL thật, đồng thời chuẩn bị các bước cấu hình cho Mốc B (Apache Superset).

## 1. Điều kiện trước khi chạy

1. Khởi động dịch vụ và nạp dữ liệu thật theo [README.md](../README.md):
   ```powershell
   Set-Location .\nhom08-65httt\src
   docker compose up -d --build
   docker compose exec web python manage.py collect_ico
   docker compose exec web python manage.py collect_vcb
   ```
2. Đảm bảo đang đứng ở thư mục `nhom08-65httt\src`.

## 2. Chạy các tệp SQL đối chiếu KPI và chất lượng

Chạy từng tệp SQL chỉ đọc qua container `db`:

```powershell
# Đối chiếu 3 KPI thị trường ICO (KPI-01, KPI-02, KPI-03)
Get-Content -LiteralPath .\database\doi-chieu-kpi-ico.sql |
    docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

# Đối chiếu chuỗi thời gian Robustas (TT03) và chất lượng dữ liệu ICO (CL02, CL03)
Get-Content -LiteralPath .\database\kiem-tra-chat-luong-ico.sql |
    docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

# Đối chiếu tỷ giá USD Vietcombank (FX)
Get-Content -LiteralPath .\database\doi-chieu-ty-gia-vcb.sql |
    docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

## 3. Kiểm tra kết quả cần đạt

- **KPI-01 (`doi-chieu-kpi-ico.sql`):** trả đúng 1 dòng mới nhất cho `robustas` (`is_current = TRUE`, `unit = 'US cents/lb'`).
- **KPI-02 (`doi-chieu-kpi-ico.sql`):** khớp công thức `(latest_value - previous_value) / previous_value * 100`; nếu chỉ có 1 mốc quan sát thì `pct_change_raw` và `pct_change_4dp` phải là `NULL`.
- **KPI-03 (`doi-chieu-kpi-ico.sql`):** hiển thị rõ `latest_effective_date` tách biệt với `latest_collected_at`.
- **Chống trùng (`kiem-tra-chat-luong-ico.sql`):** truy vấn kiểm tra trùng `is_current = TRUE` phải trả về `0` dòng.

## 4. Chuẩn bị cho Mốc B (Superset)

Sau khi Hiếu và Hiệp bàn giao môi trường Superset và tài khoản PostgreSQL chỉ đọc:

1. Kết nối PostgreSQL với quyền chỉ đọc vào database `cafeflow`.
2. Tạo dataset giá ICO từ view/truy vấn đã thống nhất (lọc `is_current = TRUE`).
3. Dựng biểu đồ đường theo ngày (`effective_date`) cho chuỗi `robustas`, hiển thị đơn vị `US cents/lb`, nguồn `ico` và bộ lọc ngày/chuỗi.
4. Đối chiếu ít nhất một điểm giá trên biểu đồ Superset với kết quả của `doi-chieu-kpi-ico.sql` và lưu ảnh minh chứng.
5. Xuất cấu hình dataset/biểu đồ (không chứa mật khẩu hoặc chuỗi kết nối bí mật) để commit vào repository.
