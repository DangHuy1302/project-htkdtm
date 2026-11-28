# Đặc tả tích hợp n8n cho collector ICO (CF-003 — Mốc C)

Người phụ trách: Bùi Gia Hiếu  
Phạm vi liên quan: `R14` (Lịch n8n), `R15` (Môi trường Docker), `R16` (Tài liệu)  
Trạng thái: **Bản đề xuất thông số tích hợp để thống nhất với nhóm trưởng và các thành viên trước khi triển khai mã Mốc C.** Chưa sửa `compose.yaml`, chưa tạo endpoint nội bộ và chưa tạo workflow.

---

## 1. Mục tiêu và nguyên tắc

- Bổ sung dịch vụ `n8n` vào Docker Compose để tự động hóa lịch gọi collector ICO hằng ngày và tích lũy nhật ký chạy (`R14`, `R15`).
- Tái sử dụng nguyên vẹn hàm `collect_ico(source_url, expected_month=None)` trong [collection.py](../src/backend/market/collection.py) và bảng `raw_collection_run`; **không viết lại ETL trong n8n**.
- Chỉ điều phối collector **ICO** ở Mốc C; việc mở rộng sang tỷ giá Vietcombank (`collect_vcb`), Giacaphe, tin hoặc gọi quy tắc cảnh báo sẽ ghép tiếp sau khi chốt với Huy và Hiệp.

---

## 2. Phạm vi tệp dự kiến thay đổi (để cả nhóm theo dõi)

| Loại tệp | Đường dẫn dự kiến | Nội dung thay đổi |
| --- | --- | --- |
| Tệp dùng chung | `nhom08-65httt/src/compose.yaml` | Thêm dịch vụ `n8n`, volume `n8n-data` và biến `N8N_INTERNAL_TOKEN` cho `web` |
| Tệp dùng chung | `nhom08-65httt/src/.env.example` | Thêm `N8N_PORT=5678` và `N8N_INTERNAL_TOKEN=` (giá trị rỗng, không chứa khóa thật) |
| Tệp dùng chung | `nhom08-65httt/src/backend/cafeflow/urls.py` | Gắn route `POST /api/v1/internal/collectors/ico/` |
| Tệp mới (backend) | App backend phù hợp (hoặc module view nội bộ + test) | Endpoint nội bộ xác thực bằng token, gọi lại `collect_ico`, kiểm thử tự động |
| Tệp mới (n8n) | `nhom08-65httt/src/n8n/workflows/ico-daily-collection.json` | Bản xuất cấu hình workflow n8n (đã loại bỏ thông tin bí mật) |
| Tài liệu nhóm | `nhom08-65httt/README.md` | Bổ sung hướng dẫn khởi chạy `n8n`, tạo credential và import workflow |

**Cam kết giữ nguyên:** không sửa collector/parser của Hiệp (`market/collection.py`, `market/ico.py`, `market/vcb.py`, `market/vcb_collection.py`), không sửa giao diện/template của Huy và Minh, không sửa các tệp SQL đối chiếu của Trang (`src/database/*.sql`).

---

## 3. Cấu hình dịch vụ `n8n` trong Docker Compose (Commit C1)

| Tham số | Giá trị đề xuất | Ghi chú |
| --- | --- | --- |
| Tên service | `n8n` | Gọi tới Django qua mạng nội bộ `http://web:8000` |
| Image | `n8nio/n8n:1.106.3` (hoặc bản ổn định được chốt khi build) | Cố định tag, không dùng `latest` trôi nổi |
| Port host | `127.0.0.1:${N8N_PORT:-5678}:5678` | Chỉ bind `127.0.0.1` giống `web` (`8000`) |
| Volume dữ liệu | `n8n-data:/home/node/.n8n` | Giữ workflow, credential và execution log qua `stop`/`start` |
| Múi giờ | `TZ=Asia/Ho_Chi_Minh`, `GENERIC_TIMEZONE=Asia/Ho_Chi_Minh` | Đồng bộ với `TIME_ZONE` của Django |
| Lưu nhật ký chạy | `EXECUTIONS_DATA_SAVE_ON_ERROR=all`, `EXECUTIONS_DATA_SAVE_ON_SUCCESS=all`, `EXECUTIONS_DATA_PRUNE=true`, `EXECUTIONS_DATA_MAX_AGE=336` | Giữ log tối đa 14 ngày (336 giờ), đáp ứng yêu cầu tối thiểu 7 ngày của `R14` |
| Biến mới ở `.env.example` | `N8N_PORT=5678`, `N8N_INTERNAL_TOKEN=` | Thành viên tự sinh token ngẫu nhiên trong `.env` cục bộ |

---

## 4. Hợp đồng endpoint nội bộ gọi collector ICO (Commit C2)

### 4.1. Route và xác thực
- **Endpoint:** `POST /api/v1/internal/collectors/ico/`
- **Phương thức:** chỉ chấp nhận `POST` (`GET`/`PUT`/`DELETE` trả `405 Method Not Allowed`).
- **Xác thực machine-to-machine:**
  - Dùng header `X-Internal-Token: <token>` so sánh constant-time (`hmac.compare_digest`) với biến môi trường `N8N_INTERNAL_TOKEN`.
  - Không dùng session/CSRF trình duyệt và không mở `AllowAny`.
  - Nếu `N8N_INTERNAL_TOKEN` chưa cấu hình (rỗng) hoặc header thiếu/sai → từ chối ở backend (`401`/`403`, fail-closed).

### 4.2. Tham số đầu vào và khóa nguồn
- **Body mặc định** (rỗng hoặc `{}`): chạy `collect_ico(ico.CURRENT_URL, None)`.
- **Body tùy chọn khi chạy bù lịch sử:** `{"month": "YYYY-MM"}` (kiểm tra khớp `^[0-9]{4}-[0-9]{2}$` và ngày hợp lệ để dựng URL từ `ico.ARCHIVE_URL`).
- **Chặn SSRF:** không nhận bất kỳ trường `url` hoặc nguồn tùy ý nào từ request; nếu gửi trường không hợp lệ hoặc `month` sai định dạng → trả `400 Bad Request`.

### 4.3. Phản hồi và mã trạng thái HTTP

| Tình huống | HTTP | Hành vi backend | Ghi chú cho n8n |
| --- | --- | --- | --- |
| Thu thập thành công | `200` | Trả thông tin `CollectionRun` vừa chạy | Ghi Execution `Success` |
| Thiếu/sai `month` hoặc body sai | `400` | Từ chối trước khi gọi collector | Không retry |
| Thiếu/sai `X-Internal-Token` hoặc thiếu biến môi trường | `401` / `403` | Chặn truy cập nội bộ | Không retry |
| Đang có phiên ICO khác giữ khóa `pg_try_advisory_lock(813001)` | `409` | Bắt `RuntimeError` chống chạy chồng | **Không retry**, ghi nhận lý do trùng phiên |
| Lỗi kết nối/HTTP từ ICO hoặc lỗi parser PDF | `502` | `collect_ico` đã ghi `CollectionRun` với `status=failed` và `error` | Có thể retry giới hạn |

**Mẫu JSON thành công (`200 OK`):**

```json
{
  "run_id": 12,
  "source": "ico",
  "status": "succeeded",
  "http_status": 200,
  "raw_document_id": 5,
  "rows_received": 19,
  "created_count": 1,
  "revised_count": 0,
  "unchanged_count": 18,
  "rejected_count": 0,
  "started_at": "2026-11-29T08:30:00+07:00",
  "finished_at": "2026-11-29T08:30:03+07:00"
}
```

**Mẫu JSON lỗi (`400` / `401` / `403` / `409` / `502`):**

```json
{
  "code": "collection_locked",
  "detail": "An ICO collection is already running"
}
```

---

## 5. Cấu hình workflow n8n, lịch chạy và nhật ký (Commit C3)

- **Lịch chạy hằng ngày:** `Schedule Trigger` chạy mỗi ngày vào **08:30 (`Asia/Ho_Chi_Minh`)**, kèm **Manual Trigger** để chạy thủ công khi kiểm thử/demo. *(Có thể chỉnh giờ nếu Hiệp hoặc Huy cập nhật khung giờ công bố chính thức của ICO.)*
- **Credential:** cấu hình một credential dạng *Header Auth* trong giao diện n8n cho header `X-Internal-Token`. Tệp xuất `ico-daily-collection.json` không được chứa giá trị token thật.
- **Timeout & Retry trên node HTTP Request:**
  - `Timeout`: `60000` ms (bao phủ `timeout=(5, 15)` và `Retry(total=2)` bên trong `download_pdf`).
  - `Retry`: tối đa `2` lần, giãn cách `5000` ms, chỉ áp dụng cho lỗi mạng hoặc `5xx` tạm thời (`502`, `503`, `504`); **không retry** các mã `400`, `401`, `403`, `409`.
- **Đối chiếu log hai lớp:**
  1. Nhật ký điều phối trên n8n (*Executions*) trong volume `n8n-data`.
  2. Nhật ký nghiệp vụ trong PostgreSQL (`raw_collection_run`, `raw_quality_issue`, `raw_document`) qua truy vấn `src/database/kiem-tra-ico.sql`.

---

## 6. Lộ trình chia 3 commit và kiểm thử độc lập

1. **Commit C1 — Cấu hình n8n:** `feat(nhom08-65httt): them dich vu n8n vao docker compose`
   - Kiểm thử: `docker compose config --quiet`, `docker compose up -d n8n`, mở `http://127.0.0.1:5678`, kiểm tra `stop`/`start` giữ volume `n8n-data`.
2. **Commit C2 — Endpoint nội bộ:** `feat(nhom08-65httt): them endpoint noi bo chay collector ICO`
   - Kiểm thử: test tự động cho `401`/`403`, `400`, `405`, `200`, `409` (khóa chồng), `502`; kiểm thử gọi `http://web:8000/api/v1/internal/collectors/ico/` từ mạng Compose.
3. **Commit C3 — Workflow & tài liệu:** `feat(nhom08-65httt): them workflow n8n thu thap ICO hang ngay`
   - Kiểm thử: chạy thủ công workflow, chạy thử theo lịch (tạm đặt giờ gần để nghiệm thu rồi trả về `08:30`), thử khóa chồng `pg_advisory_lock(813001)` nhận `409`, kiểm tra `stop`/`start` giữ nguyên workflow và execution log.

---

**Điểm cần nhóm trưởng (Bùi Đăng Huy) và Hiệp phản hồi nếu muốn điều chỉnh trước khi code C1:**
- Có cần đổi đường dẫn `/api/v1/internal/collectors/ico/`, tên header `X-Internal-Token`, hoặc giờ chạy `08:30` không?
- Nếu đồng ý với bảng thông số trên, mình sẽ bắt đầu triển khai tuần tự từ Commit C1.
