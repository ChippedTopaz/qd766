# Làm mới tổng hợp và bổ sung lịch sử — 02/10/2026

## Nguyên nhân đã xác minh

Log D:\QD766\logs\national-summary.log có các lượt thành công 18:14, 19:14,
20:14, 21:14, 22:09 và 22:14 ngày 02/10. created=false và capturedAt không đổi
do store_national_summary trả ngay bản trùng content hash. Đây là lỗi ghi nhận
độ mới, không phải bằng chứng lịch ngừng chạy. Query Task Scheduler từ phiên
agent bị Access denied; chưa đọc được toàn bộ cấu hình task hiện tại.

Mã lịch trước đây chọn một kỳ mỗi giờ: năm mỗi 2 giờ, tháng/quý mỗi 4 giờ.
Do đó TTL 2 giờ cho tháng/quý cũng chưa tương thích lịch ngay cả khi sửa dedup.

## Sửa đã thực hiện

- Nội dung trùng vẫn ghi captured_at của lần lấy thành công mới (không lùi thời
  gian). Giữ phiên bản/hash/created_at; latest lookup nhận đúng nội dung nếu
  nguồn đổi rồi quay về phiên bản trước.
- Lịch mặc định kiểm tra tuần tự tháng, quý, năm trong một lượt; 3 API tổng hợp,
  không gọi API chi tiết 34 tỉnh. Khoảng nghỉ hiện có 5 giây; cần theo dõi nguồn.
- CLI backfill chỉ lấy tháng/quý đã đóng và chưa lưu; tối đa 12 kỳ/lượt, cách
  nhau ít nhất 30 giây. Checkpoint bằng DB commit mỗi kỳ; chạy lại bỏ qua kỳ đã có.
- Kiểm tra circuit/renew shared lease trước từng request. Không tự mở lại nguồn,
  không retry, dừng ngay khi có lỗi hoặc safety signal.

captured_at là lúc hệ thống lấy/kiểm chứng response, không phải ngày dữ liệu
thay đổi bên nguồn. Không giả lập timestamp cho lần refresh chưa thành công.

## Kế hoạch đã kiểm tra, chưa thu thập thành công trong phiên agent

Dry-run xác nhận thiếu 12 kỳ: tháng 1–9 và quý I–III năm 2026.
Thử --all-current dừng tại BrowserTransport startup: browser exited during
startup; chưa gửi POST API. Không tự lặp hay kết luận do WAF.
Đã có quyền network trong lượt; quyền này không giải quyết được việc process
trình duyệt không khởi động. Cần chạy từ PowerShell tương tác máy cơ quan.
Chưa sửa D:\QD766\app, chưa apply migration hoặc đổi task/circuit.

## Lệnh cho quản trị viên

Trong thư mục repository, chạy update_qd766.ps1 theo quy trình hiện có để push,
backup và triển khai sửa sang bản task dùng. Không dùng CloseReviewedCircuit.
Sau deploy, chạy:

```powershell
.\.venv\Scripts\python.exe .\tools\refresh_national_summaries.py --all-current
```

Chỉ khi state=succeeded (đủ 3 kỳ, mỗi kỳ 34 tỉnh và 6 nhóm) mới tiếp tục:

```powershell
.\.venv\Scripts\python.exe .\tools\refresh_national_summaries.py --backfill-missing-year 2026
```

Không chạy song song. Nếu busy thì dừng chờ lượt quản trị khác xong; circuit-open,
halted hoặc failed thì báo lại, không chạy vòng lặp/không tự đóng circuit.
Backfill 12 kỳ có 11 khoảng nghỉ 30s, tối thiểu 5,5 phút cộng thời gian request.
Có tiến độ period-saved từng kỳ; không đóng PowerShell giữa chừng.

Sau thành công, kiểm kê lại:

```powershell
.\.venv\Scripts\python.exe .\tools\audit_data_coverage.py
```

Bản kiểm kê DATA_COVERAGE_20261002.md là ảnh chụp trước backfill, không tự đổi.
