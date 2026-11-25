# CafeFlow Market BI — Nhóm 8

Học phần: Hệ thống Kinh doanh thông minh  
Giảng viên hướng dẫn: TS. Đỗ Oanh Cường  
Nhóm: `nhom08-65httt`

## 1. Trạng thái dự án

Dự án đang ở giai đoạn chuẩn bị triển khai. Kho nhóm hiện chứa đề cương, phân công và các tài liệu đặc tả ban đầu. Tài liệu này mô tả phạm vi, kiến trúc và cách tổ chức dự kiến; chưa xác nhận hệ thống web, API, collector, kho dữ liệu, dashboard, AI hoặc lịch n8n chạy hoàn chỉnh.

Hướng dẫn cài đặt và câu lệnh khởi chạy sẽ được bổ sung sau khi nhóm có mã nguồn và kiểm chứng môi trường. Không dùng các mục dự kiến bên dưới như minh chứng chức năng đã hoàn thành.

## 2. Giới thiệu

CafeFlow Market BI là hệ thống thu thập và phân tích thị trường cà phê đa nguồn, hỗ trợ người phụ trách thu mua của một cơ sở rang xay theo dõi giá, tỷ giá, tin ngành, lập kịch bản chi phí và xử lý cảnh báo.

Bối cảnh cơ sở rang xay được dùng để thiết kế bài tập; nhóm chưa xác nhận có dữ liệu giao dịch nội bộ hoặc đã khảo sát doanh nghiệp. Hệ thống hỗ trợ người dùng rà soát thông tin, không tự quyết định mua hay đặt lệnh giao dịch.

## 3. Luồng nghiệp vụ dự kiến

1. Thu thập giá, tỷ giá và tin ngành theo nguồn đã xác minh.
2. Lưu dữ liệu gốc, thời điểm hiệu lực, thời điểm thu thập và thông tin nguồn.
3. Chuẩn hóa, chống trùng, kiểm tra chất lượng và cách ly bản ghi nghi lỗi.
4. Nạp dữ liệu hợp lệ vào kho chung và cung cấp view phục vụ BI.
5. Theo dõi thị trường, kế hoạch thu mua và chất lượng dữ liệu trên dashboard.
6. Nhập khối lượng, ngân sách, chọn quan sát giá/tỷ giá để tính chi phí tham chiếu.
7. Tạo cảnh báo theo quy tắc; người dùng xác nhận, cập nhật trạng thái và ghi hành động.
8. AI hỗ trợ phân tích tin và diễn giải bản tin có dẫn nguồn; số liệu và điều kiện cảnh báo do mã xác định tính toán.

## 4. Phạm vi dự kiến

| Hạng mục | Nội dung |
| --- | --- |
| Thu thập và ETL | Collector Python cho nguồn PDF, HTML, XML và RSS/chuyên mục tin; raw, chuẩn hóa, chống trùng, kiểm tra lỗi và truy vết |
| Kho dữ liệu | PostgreSQL, fact/dimension và view KPI thống nhất |
| BI | Ba dashboard: thị trường, kế hoạch thu mua, chất lượng dữ liệu; tối thiểu 10 biểu đồ/bảng tổng cộng theo đề cương |
| Nghiệp vụ | Kế hoạch, kịch bản chi phí, cảnh báo, trạng thái và lịch sử xử lý |
| Giao diện | Trang tin, chi tiết tin, kế hoạch và xử lý cảnh báo bằng Django template |
| AI | Trích sự kiện/chủ đề và tạo bản tin có bằng chứng, có kiểm tra đầu ra |
| Môi trường | Django/Wagtail, Superset, n8n, PostgreSQL và Docker Compose |

Không thuộc MVP: POS, giỏ hàng, luật gợi ý combo, tự động đặt lệnh mua hoặc hệ thống ERP/CRM đầy đủ. Dự báo, chatbot và MCP chỉ là mở rộng có điều kiện; chưa ghi nhận đã triển khai.

## 5. Nguồn dữ liệu dự kiến và giới hạn

| Nguồn | Dữ liệu dự kiến | Điểm cần xác minh |
| --- | --- | --- |
| ICO | Báo cáo PDF giá chỉ báo cà phê | Quyền sử dụng, parser nhiều tháng; giá chỉ báo không phải giá kỳ hạn |
| Giacaphe | Bảng giá và giá kỳ hạn theo từng hợp đồng | Đơn vị, thời điểm, tính đầy đủ; ghi rõ nguồn công bố lại |
| Vietcombank | XML tỷ giá USD/VND | Tách loại mua/bán và thời điểm hiệu lực; lịch sử có thể chưa đủ |
| Nguồn tin ngành | Giacaphe, VietnamBiz và nguồn bổ sung phù hợp | Điều khoản, quyền lưu nội dung, độ liên quan, trùng tin và tần suất |

Khảo sát tải mẫu trong đề cương không đồng nghĩa collector đã vận hành ổn định. Nguồn, quyền và khả năng truy cập phải được xác minh khi triển khai. Nếu nguồn lỗi, chỉ dùng dữ liệu gần nhất với nhãn thời điểm rõ ràng, không giả dữ liệu mới.

## 6. Công nghệ dự kiến

| Thành phần | Công nghệ | Vai trò |
| --- | --- | --- |
| Backend và quản trị | Python, Django, Wagtail | API, nghiệp vụ, tài khoản/quyền và quản trị |
| Giao diện ứng dụng | Django template, HTML/CSS/JavaScript khi cần | Trang tin, kế hoạch và xử lý cảnh báo |
| Dữ liệu | PostgreSQL, SQL | Raw, kho dữ liệu, bảng nghiệp vụ và view BI |
| Dashboard | Apache Superset | Phân tích, bộ lọc và trực quan hóa |
| Điều phối | n8n | Gọi collector, ETL và tác vụ theo lịch |
| AI | LLM qua API, nhà cung cấp/model chờ chốt | Trích sự kiện và bản tin có căn cứ |
| Đóng gói | Docker Compose | Môi trường các dịch vụ |
| Cộng tác | Git/GitHub | Phiên bản, phân công và kiểm tra thay đổi |

## 7. Tổ chức thư mục

Các đường dẫn dưới đây đều tính từ thư mục nhóm `nhom08-65httt/`.

| Đường dẫn | Mục đích |
| --- | --- |
| `danhsachnhom.md` | Thông tin thành viên, nhiệm vụ và đóng góp |
| `README.md` | Giới thiệu và trạng thái dự án của nhóm; bổ sung hướng dẫn chạy khi đã kiểm chứng |
| `docs/` | Đề cương, đặc tả, tài liệu kiểm thử và báo cáo |
| `src/backend/` | Mã nguồn backend và tác vụ Python khi triển khai |
| `src/frontend/` | Tài nguyên/giao diện khi nhóm chốt vị trí triển khai |
| `src/database/` | SQL, mô hình dữ liệu và tài nguyên CSDL khi triển khai |

Thư mục có `.gitkeep` chỉ là chỗ giữ cấu trúc, không chứng minh đã có mã nguồn. Vị trí Django template thực tế sẽ chốt khi khởi tạo ứng dụng để tránh lưu trùng với frontend.

## 8. Tài liệu liên quan

- [Danh sách và phân công nhóm](danhsachnhom.md)
- [Đề cương CafeFlow Market BI](docs/De_cuong_CafeFlow_Market_BI_Nhom8.docx)
- [Đặc tả dashboard dự kiến](docs/dac-ta-dashboard.md)
- [Đặc tả giao diện tin và cảnh báo dự kiến](docs/dac-ta-tin-va-canh-bao.md)

Hai tài liệu đặc tả có thể được bổ sung bằng các commit riêng; liên kết chỉ mở được sau khi tệp tương ứng được đưa lên nhánh nhóm.

## 9. Quy tắc làm việc

- Làm việc trên nhánh `nhom08-65httt` và chỉ thêm/sửa tệp bên trong thư mục `nhom08-65httt/`.
- Giữ nguyên `README.md`, `.gitignore` và `_template_nhom/` ở gốc kho theo hướng dẫn học phần.
- Pull bản mới trước khi sửa; chỉ stage đúng tệp phụ trách và kiểm tra trước khi commit.
- Mỗi thành viên tự kiểm tra nội dung và commit bằng danh tính của mình. Không dùng số commit thay cho đánh giá chất lượng công việc.
- Không đưa `.env`, mật khẩu, API key, thư viện cài sẵn hoặc tệp nén lớn vào kho.
- Khi bàn giao, ghi rõ phần đã làm, chưa làm, phụ thuộc và đường dẫn minh chứng.

## 10. Công việc tiếp theo

1. Xác minh nguồn/quyền, loại giá, trường dữ liệu và khả năng parser.
2. Chốt mô hình dữ liệu, KPI, hợp đồng API và trạng thái cảnh báo.
3. Khởi tạo môi trường và triển khai một luồng nhỏ có thể chạy kiểm tra.
4. Bàn giao view/dữ liệu mẫu cho Trang, API/tài khoản mẫu cho Minh.
5. Cập nhật hướng dẫn chạy, kết quả kiểm thử và tiến độ theo minh chứng thực tế.
