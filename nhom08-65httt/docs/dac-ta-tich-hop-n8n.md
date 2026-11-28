# Đặc tả tích hợp n8n cho collector ICO (CF-003 — Mốc C)

Người phụ trách: Bùi Gia Hiếu  
Phạm vi theo đề cương: `R14` (Lịch n8n), `R15` (Môi trường Docker), `R16` (Tài liệu)  
Tình trạng hiện tại: Tài liệu thiết kế và hợp đồng tích hợp cho **Mốc C**. Mã nguồn `compose.yaml`, endpoint nội bộ và workflow n8n chưa được triển khai; mọi thành viên dùng tài liệu này làm căn cứ chung khi phối hợp trên nhánh `nhom08-65httt`.

---

## 1. Mục tiêu và nguyên tắc triển khai

- Bổ sung dịch vụ `n8n` vào Docker Compose để tự động hóa lịch thu thập giá chỉ báo ICO hằng ngày và tích lũy nhật ký chạy dài hạn (`R14`, `R15`).
- Tái sử dụng nguyên vẹn hàm `collect_ico(source_url, expected_month=None)` trong [collection.py](../src/backend/market/collection.py) và URL nguồn cố định trong [ico.py](../src/backend/market/ico.py); **không viết lại ETL trong n8n**.
- Mốc C chỉ điều phối collector **ICO**. Việc nối thêm collector Vietcombank (`collect_vcb`), Giacaphe, tin tức và bước kích hoạt cảnh báo (`collector → ETL → cảnh báo` của `R14`) sẽ mở rộng tiếp trên nền tảng này ở giai đoạn tích hợp.

---

## 2. Phạm vi tệp tác động và phối hợp trong nhóm

### 2.1. Danh sách tệp tạo mới và chỉnh sửa trong Mốc C

| Loại | Đường dẫn | Mục đích |
| --- | --- | --- |
| Tệp dùng chung (sửa) | `nhom08-65httt/src/compose.yaml` | Thêm dịch vụ `n8n`, volume `n8n-data` và truyền `N8N_INTERNAL_TOKEN` vào dịch vụ `web` |
| Tệp dùng chung (sửa) | `nhom08-65httt/src/.env.example` | Thêm `N8N_PORT=5678` và `N8N_INTERNAL_TOKEN=` (giá trị rỗng, không chứa khóa thật) |
| Tệp dùng chung (sửa) | `nhom08-65httt/src/backend/cafeflow/urls.py` | Đăng ký route `POST /api/v1/internal/collectors/ico/` |
| Tài liệu nhóm (sửa) | `nhom08-65httt/README.md` | Bổ sung hướng dẫn khởi động `n8n`, cấu hình credential và import workflow |
| Tệp mới (backend) | `nhom08-65httt/src/backend/market/internal_views.py` | View DRF nội bộ xác thực token và gọi `collect_ico` |
| Tệp mới (kiểm thử) | `nhom08-65httt/src/backend/market/tests/test_internal_ico.py` | Bộ test tự động kiểm tra xác thực, tham số, khóa chạy chồng và lỗi nguồn |
| Tệp mới (n8n) | `nhom08-65httt/src/n8n/workflows/ico-daily-collection.json` | Cấu hình workflow n8n đã xuất (không chứa token/credential thật) |

### 2.2. Phần giữ nguyên và điểm liên kết với các thành viên
- **Huy (nhóm trưởng):** giữ nguyên layout chung, trang Tổng quan (`/`) và hợp đồng các API công khai. Endpoint nội bộ dùng đường dẫn `/api/v1/internal/collectors/ico/` để thuận tiện nối tiếp bước kích hoạt cảnh báo sau khi thu thập xong.
- **Hiệp (collector/ETL):** giữ nguyên hoàn toàn `market/collection.py`, `market/ico.py`, `market/vcb.py`, `market/vcb_collection.py`, `market/models.py` và `market/views.py`. Giao diện gọi vẫn là `collect_ico(source_url, expected_month=None)` với khóa advisory lock `813001`.
- **Trang (BI/Superset):** giữ nguyên toàn bộ `src/database/*.sql`. Dữ liệu và nhật ký chạy do n8n kích hoạt hằng ngày sẽ ghi trực tiếp vào `raw_collection_run`, `raw_quality_issue`, `raw_document` và `dw_price_observation` để phục vụ [doi-chieu-kpi-ico.sql](../src/database/doi-chieu-kpi-ico.sql) và [kiem-tra-chat-luong-ico.sql](../src/database/kiem-tra-chat-luong-ico.sql) (Dashboard 3 — `CL01`, `CL02`, `CL03`).
- **Minh (giao diện/QA):** giữ nguyên toàn bộ template và quy ước giao diện; trạng thái chạy trong `raw_collection_run` là nguồn dữ liệu thật phục vụ theo dõi nguồn và kiểm thử tích hợp `R17`.

---

## 3. Cấu hình dịch vụ `n8n` trong Docker Compose (Commit C1)

| Thành phần | Giá trị áp dụng | Mục đích |
| --- | --- | --- |
| Service | `n8n` | Chạy cùng mạng Docker Compose với `web` (`http://web:8000`) và `db` |
| Image | `n8nio/n8n:1.106.3` | Cố định phiên bản image để môi trường giữa các thành viên đồng nhất |
| Port | `127.0.0.1:${N8N_PORT:-5678}:5678` | Chỉ mở trên `127.0.0.1`, tương đồng với cổng `8000` của `web` |
| `depends_on` | `web` (`service_started`) | Đảm bảo container `web` được khởi tạo cùng `n8n` |
| Volume | `n8n-data:/home/node/.n8n` | Giữ workflow, credential và lịch sử execution khi `docker compose stop` / `start` |
| Múi giờ | `TZ=Asia/Ho_Chi_Minh`, `GENERIC_TIMEZONE=Asia/Ho_Chi_Minh` | Đồng bộ với `TIME_ZONE = "Asia/Ho_Chi_Minh"` trong `settings.py` |
| Lưu trữ log | `EXECUTIONS_DATA_SAVE_ON_ERROR=all`, `EXECUTIONS_DATA_SAVE_ON_SUCCESS=all`, `EXECUTIONS_DATA_PRUNE=true`, `EXECUTIONS_DATA_MAX_AGE=336` | Lưu toàn bộ lịch sử chạy thành công và lỗi tối đa 14 ngày (336 giờ), đáp ứng mốc tối thiểu 7 ngày của `R14` |
| Biến môi trường mới | `N8N_PORT=5678`, `N8N_INTERNAL_TOKEN=` | Khai báo mẫu rỗng trong `.env.example`; mỗi máy tự sinh chuỗi ngẫu nhiên trong `.env` |

---

## 4. Hợp đồng endpoint nội bộ gọi collector ICO (Commit C2)

### 4.1. Định danh và xác thực
- **URL:** `POST /api/v1/internal/collectors/ico/` (named URL: `internal-collect-ico`).
- **Phương thức:** chỉ cho phép `POST` (`GET`, `PUT`, `PATCH`, `DELETE` trả `405 Method Not Allowed`).
- **Xác thực:**
  - Dùng header `X-Internal-Token: <token>`.
  - Backend đọc `os.environ.get("N8N_INTERNAL_TOKEN", "")` và kiểm tra bằng `hmac.compare_digest`.
  - Không dùng `AllowAny` và không dùng session/CSRF trình duyệt (tránh lộ endpoint nội bộ qua cookie trình duyệt).
  - Nếu `N8N_INTERNAL_TOKEN` chưa được cấu hình (rỗng) → trả `503 Service Unavailable` (fail-closed).
  - Nếu thiếu header `X-Internal-Token` hoặc sai token → trả `403 Forbidden`.

### 4.2. Tham số đầu vào và khóa URL nguồn
- **Yêu cầu mặc định:** body rỗng hoặc `{}` → gọi `collect_ico(ico.CURRENT_URL, None)`.
- **Yêu cầu chạy tháng lưu trữ (tùy chọn cho kiểm thử/chạy bù):** `{"month": "YYYY-MM"}` → kiểm tra đúng định dạng `^[0-9]{4}-[0-9]{2}$` và tháng/năm hợp lệ để dựng URL theo `ico.ARCHIVE_URL`.
- **Khóa nguồn chống SSRF:** không nhận trường `url` hoặc bất kỳ trường ngoài danh sách cho phép (`month`); mọi payload sai kiểu, sai định dạng `month` hoặc chứa trường lạ đều trả `400 Bad Request`.

### 4.3. Bảng mã trạng thái HTTP và định dạng JSON

Phản hồi lỗi thống nhất theo quy ước trong [ke-hoach-trien-khai.md](ke-hoach-trien-khai.md) (`code`, `detail`, kèm `fields` khi lỗi đầu vào `400`):

| HTTP | `code` | Khi nào xảy ra | Hành vi của n8n |
| --- | --- | --- | --- |
| `200` | — | Collector ICO chạy xong và lưu `CollectionRun` thành công | Kết thúc thành công, ghi log Execution |
| `400` | `invalid_payload` | `month` sai định dạng hoặc body chứa trường không hợp lệ | Dừng, không retry |
| `403` | `forbidden` | Thiếu header `X-Internal-Token` hoặc token không khớp | Dừng, không retry |
| `409` | `collection_locked` | Đang có phiên khác giữ khóa PostgreSQL `pg_try_advisory_lock(813001)` | Kết thúc báo trùng phiên, **không retry** |
| `502` | `collection_failed` | Lỗi kết nối/HTTP từ nguồn ICO hoặc lỗi parse PDF (đã ghi `CollectionRun.status = failed`) | Retry giới hạn theo cấu hình node |
| `503` | `internal_token_not_configured` | Biến môi trường `N8N_INTERNAL_TOKEN` chưa được thiết lập trên `web` | Dừng, không retry |

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

**Mẫu JSON lỗi (`400`, `403`, `409`, `502`, `503`):**

```json
{
  "code": "collection_locked",
  "detail": "An ICO collection is already running."
}
```

```json
{
  "code": "invalid_payload",
  "detail": "Invalid request payload.",
  "fields": {
    "month": ["month must be a valid YYYY-MM."]
  }
}
```

---

## 5. Cấu hình workflow n8n, lịch chạy và nhật ký (Commit C3)

- **Tên workflow:** `CafeFlow - ICO Daily Collection` (xuất lưu tại `nhom08-65httt/src/n8n/workflows/ico-daily-collection.json`).
- **Trigger:**
  - `Schedule Trigger`: chạy hằng ngày lúc **08:30** (`Asia/Ho_Chi_Minh`).
  - `Manual Trigger`: giữ song song để chạy thủ công khi kiểm thử hoặc demo.
- **Xác thực trong n8n:** tạo Credential kiểu **Header Auth** trên giao diện n8n (tên `CafeFlow Internal Token`, Header Name `X-Internal-Token`, Value lấy từ `N8N_INTERNAL_TOKEN` trong `.env` cục bộ). Tệp JSON xuất vào Git không chứa giá trị secret.
- **Node `HTTP Request` gọi backend:**
  - Method: `POST`
  - URL: `http://web:8000/api/v1/internal/collectors/ico/`
  - Timeout: `60000` ms (bao phủ `timeout=(5, 15)` và `Retry(total=2)` của `download_pdf` bên trong Django).
  - Retry khi lỗi: tối đa `2` lần, giãn cách `5000` ms cho lỗi kết nối hoặc HTTP `502`/`503`/`504`; **không retry** khi nhận `400`, `403`, `409`, `503`.
- **Kiểm tra trạng thái & ghi log hai lớp:**
  - Trên n8n: node kiểm tra phản hồi xác nhận HTTP `200` và `status == "succeeded"` để lịch sử *Executions* phân tách rõ ca thành công và ca lỗi.
  - Trên PostgreSQL: đối chiếu qua `raw_collection_run`, `raw_quality_issue`, `raw_document` bằng [kiem-tra-ico.sql](../src/database/kiem-tra-ico.sql).

---

## 6. Thứ tự 3 commit và tiêu chí kiểm thử độc lập

1. **Commit C1 — `feat(nhom08-65httt): them dich vu n8n vao docker compose`**
   - Kiểm thử: `docker compose config --quiet`, `docker compose up -d n8n`, mở `http://127.0.0.1:5678`, kiểm tra `docker compose stop` / `start` giữ nguyên volume `n8n-data`.
2. **Commit C2 — `feat(nhom08-65httt): them endpoint noi bo chay collector ICO`**
   - Kiểm thử: `python manage.py test market.tests.test_internal_ico` (đủ các ca `200`, `400`, `403`, `405`, `409`, `502`, `503`) và gọi kiểm tra trực tiếp `http://web:8000/api/v1/internal/collectors/ico/` từ mạng Compose.
3. **Commit C3 — `feat(nhom08-65httt): them workflow n8n thu thap ICO hang ngay`**
   - Kiểm thử: chạy thủ công workflow (`Manual Trigger`), chạy thử theo lịch (`Schedule Trigger` kiểm chứng tự kích hoạt rồi đưa về `08:30`), kiểm tra chống chạy chồng bằng `SELECT pg_advisory_lock(813001)` nhận `409`, kiểm tra `stop` / `start` giữ nguyên workflow và Execution log.

---

## 7. Checklist hoàn thành Mốc C

- [ ] `n8n` khởi động được cùng `db` và `web` qua Docker Compose, `.env.example` không chứa khóa thật.
- [ ] Endpoint `POST /api/v1/internal/collectors/ico/` chặn truy cập thiếu/sai token (`403`/`503`), chặn URL tự do (`400`) và trả `409` khi trùng khóa `813001`.
- [ ] Bộ test tự động endpoint nội bộ và `manage.py check` đạt toàn bộ.
- [ ] Workflow n8n chạy thành công cả thủ công và theo lịch hằng ngày `08:30`, lưu log lỗi/thành công và giữ dữ liệu qua `stop`/`start`.
- [ ] Đã xuất tệp `ico-daily-collection.json` sạch secret và cập nhật hướng dẫn sử dụng vào `nhom08-65httt/README.md`.
