# Backend người dùng — bochiso766.com

## Trạng thái 03/10/2026

Theo quản trị viên: domain Cloudflare đã mua, tunnel Healthy, một replica.
Repo đã có launcher riêng; chưa chạy server người dùng, chưa tạo route tunnel,
chưa sửa DNS/Netlify, chưa cấu hình OAuth thật hoặc bật khai thác/thu phí.

| Thành phần | Địa chỉ nội bộ | Công khai |
| --- | --- | --- |
| Quản trị đang chạy | 127.0.0.1:8767 | Không |
| Xem trước giao diện | 127.0.0.1:8768 | Không |
| Backend người dùng mới | 127.0.0.1:8769 | Chờ nghiệm thu |
| PostgreSQL | localhost:5432 | Không |

Không dùng `start_backend.ps1` để mở public. Dùng `tools/start_public_backend.py`:
chỉ bind loopback 8769; không migration, worker, đổi circuit hoặc scheduled task.
Chỉ đọc kết nối PostgreSQL từ `.env` và ba mục Google từ `.env.public`.
Không kế thừa cấu hình quản trị hoặc biến môi trường tiến trình.
Bắt buộc đăng nhập, chặn API quản trị/job/batch, khóa tỉnh theo tài khoản;
khai thác TTHC, giá credit và credit dùng thử đều tắt trong giai đoạn này.
Không đồng nghĩa kết nối SQL chỉ đọc: Google login phải ghi tài khoản/phiên.

## Bước quản trị phải làm trước khi chạy

1. Tạo project Google Cloud và Google Auth Platform. Tên ứng dụng: Bộ chỉ số 766.
   Cấu hình Branding, Audience và chỉ thông tin danh tính `openid email profile`.
   Nếu để Testing, thêm email người thử theo yêu cầu của Google Console.
2. Tạo OAuth client loại **Web application**; đăng ký chính xác:
   `https://api.bochiso766.com/api/v1/auth/google/callback`.
   Không dùng service account, không đăng ký callback về 8767/8768.
3. Tại repo, sao chép `.env.public.example` thành `.env.public`, điền client ID
   và secret tại máy. Không sửa `.env` bản quản trị; không gửi secret qua chat.
   File thật đã bị Git ignore. Không lưu thông tin Google vào frontend hoặc Netlify.
4. Cài thư viện auth trong môi trường Python đang dùng (bước này cần mạng):

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -e ".[auth]"
   .\.venv\Scripts\python.exe .\tools\start_public_backend.py --check
   ```

   Check chỉ kiểm tra cấu hình/thư viện, không gọi Google hoặc kết nối DB.
   Khi cấu hình thiếu, dừng mà không khởi chạy hoặc in secret.
5. Khi check PASS, chạy thử riêng trong terminal; Ctrl+C chỉ dừng bản 8769:

   ```powershell
   .\.venv\Scripts\python.exe .\tools\start_public_backend.py
   ```

   Từ máy cơ quan, kiểm tra access-policy, health/ready (kết nối DB), dashboard
   chưa đăng nhập phải 401; system-status và tạo job phải 403.
   Kiểm tra lại 8767/8768 không bị ảnh hưởng. Local HTTP không kiểm chứng cookie
   Secure/đăng nhập thật vì callback dùng HTTPS; không tắt Secure để thử localhost.

## Chốt trước khi thêm route HTTPS

- Backup dữ liệu và xác nhận schema tài khoản có sẵn; không migration tự động.
- Xác nhận 8769 đã chặn endpoint quản trị, dữ liệu snapshot/raw và TTHC chưa mở.
- Chuẩn bị rate limit auth và giới hạn request; không ghi query callback/code/state
  vào log của ứng dụng, tunnel hoặc proxy. Launcher đã tắt Uvicorn access log.
- Cấu hình test giới hạn người truy cập nếu cần; OAuth Testing không thay thế
  toàn bộ chính sách truy cập ứng dụng.
- Chỉ sau khi quản trị duyệt mới thêm route `api.bochiso766.com` tới
  `http://127.0.0.1:8769`. Tuyệt đối không proxy 8767/8768/5432.
- Nghiệm thu Google thật, phiên Secure/HttpOnly, hủy consent, logout, tài khoản
  chưa gán tỉnh, khóa tỉnh chéo và vô hiệu hóa tài khoản.
- Gán tỉnh bằng `tools/manage_user_accounts.py` tại máy cơ quan như GOOGLE_LOGIN.md.
- Chưa đăng ký task 8769: sẽ thêm sau khi chạy foreground và HTTPS được duyệt.

## Website Netlify và phiên đăng nhập

Giai đoạn đầu có thể nghiệm thu frontend được backend phục vụ tại cùng origin
`https://api.bochiso766.com/`, để tránh cookie khác site với `netlify.app`.
Launcher hiện không mở cross-origin CORS. Không đơn giản đổi URL frontend Netlify
rồi coi login đã hoạt động: cần thiết kế proxy cùng origin hoặc domain frontend
`bochiso766.com` và kiểm chứng cookie/CORS/CSRF. Đây là bước tiếp theo, chưa thay đổi
deployment Netlify đang có. Backend và frontend hiện vẫn phục vụ được cùng origin.

## Quay lại

Chưa thay file triển khai D:\QD766\app hoặc cấu hình .env hiện tại. Dừng terminal
8769 là đủ ở giai đoạn thử nội bộ. Nếu đã mở route về sau, gỡ route hoặc vô hiệu hóa
public instance; không dừng Cloudflared nếu nó còn phục vụ ứng dụng khác.
Không xóa database, phiên hoặc tài khoản để rollback mã launcher.

Nguồn: [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect),
[Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/).
