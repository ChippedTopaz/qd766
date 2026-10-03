# Google thật trên local, dữ liệu/credit mô phỏng

Không deploy Netlify. Không sửa `.env.public` hoặc callback production.
Server riêng: http://127.0.0.1:8771/; chỉ loopback, không dùng Tunnel.
Database `qd766_credit_test`, schema `credit_google_trial`, không đọc dữ liệu thật.
Danh mục và điểm được mô phỏng; giá 3 credit không phải giá thương mại.

## Google

Trong OAuth client hiện có, thêm Authorized redirect URI (không xóa các URI cũ):

```text
http://127.0.0.1:8771/api/v1/auth/google/callback
```

Không cần gửi client secret. Launcher đọc ID/secret đã lưu trong `.env.public`,
nhưng dùng callback local cố định riêng. Chưa xác minh Google thật cho bản này.

## Khởi động và cấp quyền admin local

Frontend biên dịch riêng vào `.tmp-credit-trial/site/dist`; dùng cùng tài sản UI của
bản local, không ghi vào `web/dist`. Cần build bằng launcher thử 8770 khi mã thay đổi.
Sau khi tài sản đã được chuẩn bị, chạy trong thư mục dự án:

```powershell
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py
```

Trong PowerShell khác, tạo link mời local cho chủ tài khoản:

```powershell
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py --create-owner-invite
```

Mở link OWNER_INVITE bằng cùng trình duyệt, đăng nhập `vietnt89@gmail.com`.
Link một lần, hạn một ngày, chỉ đúng email được nhận; không chia sẻ link.
Sau khi Google xác minh và nhận lời mời thành công:

```powershell
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py --bootstrap-owner
```

Đăng xuất/đăng nhập lại rồi vào Quản trị dùng thử. Lệnh chỉ cấp admin trong schema
thử cho chủ tài khoản đã được Google xác minh và đã nhận lời mời, không tự cấp credit.
Tài khoản khác phải có link mời local; admin gán tỉnh/cơ quan và cấp credit local.

## Hoàn thành yêu cầu bằng dữ liệu giả

Không có worker thật chạy nền. Sau khi người dùng tạo yêu cầu và giữ credit,
có thể xử lý một job bằng processor mô phỏng:

```powershell
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py --run-mock-worker-once
```

Lệnh dùng worker và quy tắc lưu/settle thật nhưng dữ liệu sáu nhóm là giả, không
gọi DVCQG. Đợi tối đa khoảng 60 giây cho cache local hết hạn rồi tải lại Dashboard.

Cookie localhost dùng chung giữa các cổng: chuyển vai ở bản 8770 có thể thay phiên
8771. Nên dùng trình duyệt/profile riêng cho Google local. Cookie production ở
bochiso766.com không bị ảnh hưởng.

## An toàn

HTTP chỉ được mở bởi cờ programmatic local_google_trial, với callback và tên
database cố định, hostname/client/origin loopback. Cờ này không được đọc từ môi
trường. Production vẫn yêu cầu HTTPS và không bật credit thử.
Không truy cập các API vận hành, thay Task Scheduler, bật payment hoặc đăng ký tunnel.
