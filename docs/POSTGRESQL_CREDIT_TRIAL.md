# Kiểm thử đồng thời PostgreSQL — chưa nghiệm thu

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

Kết nối PostgreSQL được nhưng tạo database bị chặn với SQLSTATE 42501.
Cần quản trị PostgreSQL tạo database thử riêng và giao quyền sở hữu cho tài khoản
ứng dụng hiện tại. Không cấp CREATEDB hoặc superuser cho tài khoản ứng dụng.
Chưa có kết quả kiểm thử đồng thời PostgreSQL; không được báo PASS.

## Sau khi tạo database

Trong PowerShell ở thư mục dự án:

```powershell
.\.venv\Scripts\python.exe .\tools\test_postgresql_credits.py --connection-file .env
```

Kết quả cần có `POSTGRESQL_CREDIT_TEST=PASS`. Không chạy migration hoặc cập nhật
Task Scheduler/production để thực hiện bộ kiểm thử này.
