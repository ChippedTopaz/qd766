# Kiểm thử đồng thời PostgreSQL — đạt kiểm thử offline

Bộ kiểm thử offline: `tools/test_postgresql_credits.py`.
Chỉ kết nối loopback và database cố định `qd766_credit_test`; không gọi DVCQG.
File kết nối chỉ cung cấp host/port/user/password, không kế thừa tên database
production hay các tùy chọn kết nối khác.

Mỗi lần chạy tạo schema `credit_run_*` riêng, giữ lại để kiểm tra, không xóa dữ liệu
hay dùng database production làm phương án dự phòng. Các tài khoản/dữ liệu đều giả.

Các tình huống: sáu tài khoản gửi cùng lúc dùng chung job; nhiều xác nhận của một
tài khoản chỉ tính phí một lần; phát lại xác nhận cũ không thử lại job lỗi; xác nhận
mới sau hoàn credit tạo một job chung mới và giữ lịch sử hoàn cũ.

## Trạng thái hiện tại

Ban đầu tạo database bị chặn với SQLSTATE 42501. Quản trị đã tạo database riêng;
bộ kiểm thử chạy thành công ngày 03/10/2026, 21:36 giờ Việt Nam:

- Sáu tài khoản gửi đồng thời: một job chung, sáu giao dịch tính phí riêng.
- Nhiều xác nhận đồng thời của cùng tài khoản: chỉ mua dữ liệu một lần.
- Phát lại xác nhận cũ sau hoàn credit: không tự tạo lượt xử lý mới.
- Sáu xác nhận mới sau thất bại: một job kế tiếp chung, giữ sáu yêu cầu đã hoàn cũ.
- Kết quả cuối: `POSTGRESQL_CREDIT_TEST=PASS`.

Schema lưu lại: `credit_run_20261003_143633_984cd414` trong `qd766_credit_test`.
Không truy cập database production, không gọi DVCQG, không thay quyền tài khoản
ứng dụng, không restart server hoặc triển khai Netlify.
Kết quả này chỉ nghiệm thu các tình huống đồng thời của tầng giao dịch offline;
chưa nghiệm thu Google thật, worker gián đoạn hoặc tải thực tế production.

## Sau khi tạo database

Trong PowerShell ở thư mục dự án:

```powershell
.\.venv\Scripts\python.exe .\tools\test_postgresql_credits.py --connection-file .env
```

Kết quả cần có `POSTGRESQL_CREDIT_TEST=PASS`. Không chạy migration hoặc cập nhật
Task Scheduler/production để thực hiện bộ kiểm thử này.
