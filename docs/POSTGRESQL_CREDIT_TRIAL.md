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
Kết quả lần đầu này chỉ nghiệm thu các tình huống đồng thời của tầng giao dịch
offline; tại thời điểm đó chưa thử worker gián đoạn (bổ sung bên dưới).
Google thật và tải thực tế production vẫn chưa được nghiệm thu cho luồng credit.

## Kiểm thử worker gián đoạn — đạt mô phỏng offline

Ngày 03/10/2026, 21:42 giờ Việt Nam, chạy lại bộ PostgreSQL gồm bốn tình huống
đồng thời bên trên và ba tình huống bổ sung. Tất cả đạt.
Schema: `credit_run_20261003_144222_d25888ab`.

- Ngắt sau khi worker nhận job, trong bước lấy dữ liệu: job vẫn running, giữ credit;
  worker khác bị chặn trước khi hết lease. Sau khi mô phỏng hết lease, job được
  nhận lại, đủ sáu người được cấp dữ liệu và mỗi người chỉ quyết toán một lần.
- Ngắt sau khi flush snapshot, credit và thông báo nhưng trước commit: PostgreSQL
  rollback cả ba phần; sáu yêu cầu vẫn chờ và giữ credit. Lượt khôi phục chỉ tạo
  một snapshot và một thông báo thành công cho mỗi yêu cầu.
- Mất xác nhận sau commit: chạy worker lại không xử lý job thành công lần nữa,
  không thêm giao dịch trừ credit hoặc thông báo.

Dùng `run_one_job` thật với processor trả sáu nhóm dữ liệu mô phỏng. Gián đoạn
được chèn bằng BaseException để bỏ qua xử lý lỗi thông thường; lease được mô phỏng
hết hạn bằng timestamp trong schema thử. Không kill tiến trình thật, không khởi
động/dừng PostgreSQL hoặc worker production, không thay đồng hồ hệ thống.
Chưa nghiệm thu mất điện máy chủ, gián đoạn mạng thật hoặc tải production.

## Sau khi tạo database

Trong PowerShell ở thư mục dự án:

```powershell
.\.venv\Scripts\python.exe .\tools\test_postgresql_credits.py --connection-file .env
```

Kết quả cần có `POSTGRESQL_CREDIT_TEST=PASS`. Không chạy migration hoặc cập nhật
Task Scheduler/production để thực hiện bộ kiểm thử này.
