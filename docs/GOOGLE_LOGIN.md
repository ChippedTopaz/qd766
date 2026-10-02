# Đăng nhập Google — triển khai chờ cấu hình thật

## Phạm vi đã làm

Google xác minh danh tính; QĐ766 quản lý tài khoản theo `google:<sub>`, không dùng
email làm khóa và không tự nối tài khoản trùng email. Chỉ xin `openid email profile`,
không xin quyền Gmail, Drive, lịch hoặc dữ liệu của người dùng trên Google.

Luồng authorization-code phía server dùng state một lần gắn cookie, nonce và PKCE
S256. ID token được thư viện `google-auth` xác minh chữ ký, audience, issuer và hạn;
server kiểm tra thêm nonce và email đã xác minh. Không lưu access/refresh/ID token.
Cookie phiên HttpOnly, SameSite=Lax, Secure với HTTPS; chỉ hash của token phiên
được lưu trong PostgreSQL. Phiên có hạn tuyệt đối tám giờ, đăng xuất xóa phiên và
cần CSRF token. Vô hiệu hóa tài khoản có tác dụng ngay trên mọi request.

Tài khoản mới luôn `free`, active, 0 credit, chưa gán tỉnh. Không cấp admin từ email,
client payload, query string hoặc lần đăng nhập đầu tiên. Đăng nhập lại giữ nguyên
plan và credit. Không có API tự gán tỉnh hay nâng quyền.

Khi `QD766_REQUIRE_LOGIN=true`: API dashboard lấy đúng tỉnh quản trị đã gán;
chặn yêu cầu chi tiết tỉnh khác, job/batch và TTHC. Danh sách chọn tỉnh chỉ trả tỉnh
của tài khoản. Bảng so sánh tỉnh vẫn dùng điểm tổng hợp cấp tỉnh, không trả snapshot
chi tiết tỉnh khác. API tổng hợp thô toàn quốc bị chặn trong chế độ này.

Chưa gán chi tiết Sở/xã cho tài khoản: phiên bản này chỉ khóa phạm vi tỉnh. Phân quyền
TTHC trả phí, UI cấp credit, thông báo và thanh toán sẽ triển khai sau.

## Cấu hình cần người quản trị thực hiện

1. Chốt domain HTTPS của instance dùng thử. Giữ server office/operator riêng.
2. Trong Google Cloud Console, cấu hình Google Auth Platform/consent và tạo OAuth
   client loại **Web application**. Khi đang Testing, thêm email người thử vào test users.
3. Đăng ký chính xác redirect URI:
   `https://<domain>/api/v1/auth/google/callback`.
4. Cài thư viện bổ sung trong môi trường của instance:

   ```powershell
   .venv\Scripts\python.exe -m pip install -e ".[auth]"
   ```

5. Lưu vào `.env` riêng của instance, không gửi Client Secret qua chat/Git:

   ```text
   QD766_GOOGLE_CLIENT_ID=<client-id>
   QD766_GOOGLE_CLIENT_SECRET=<client-secret>
   QD766_GOOGLE_REDIRECT_URI=https://<domain>/api/v1/auth/google/callback
   QD766_PUBLIC_READ_ONLY=true
   QD766_REQUIRE_LOGIN=true
   ```

6. Backup PostgreSQL rồi chạy migration `alembic upgrade head` bằng quy trình deploy
   đã có. Migration 0009 bổ sung email/tỉnh và hai bảng login, không sửa credit.
7. Restart instance, đăng nhập thật và nghiệm thu HTTPS/cookie, hủy consent,
   đăng xuất, gán tỉnh và chặn truy cập chéo. Không coi test giả lập là PASS Google thật.

HTTP localhost chỉ được chấp nhận cho instance office (`public_read_only=false`),
không dùng làm cấu hình production. Khi chạy thử localhost có thể dùng URI
`http://127.0.0.1:8767/api/v1/auth/google/callback` nếu Google client chấp nhận URI
đó. Không bật `REQUIRE_LOGIN` trước khi HTTPS, thư viện và client được kiểm chứng.

## Gán tỉnh hoặc vô hiệu hóa tài khoản tại máy cơ quan

Người dùng đăng nhập một lần để tài khoản xuất hiện. Công cụ sau chỉ dùng nội bộ,
không công khai lên trình duyệt:

```powershell
.venv\Scripts\python.exe tools\manage_user_accounts.py list
.venv\Scripts\python.exe tools\manage_user_accounts.py assign-province --account-id <UUID> --province-code <ma-tinh>
.venv\Scripts\python.exe tools\manage_user_accounts.py disable --account-id <UUID>
```

Mã tỉnh lấy từ danh mục 34 tỉnh đã xác minh. Gán tỉnh/disable thu hồi phiên cũ;
người dùng đăng nhập lại. Công cụ không nâng plan hoặc thay credit.

## Chưa đủ điều kiện mở production

- Chưa có domain/HTTPS và OAuth client thật.
- Lượt cài thư viện từ `files.pythonhosted.org` tại máy cơ quan bị reset kết nối;
  gói auth được để riêng để không chặn deploy office mặc định.
- Luồng và phân quyền đã kiểm thử với Google giả lập; chưa kiểm tra đăng nhập thật,
  xác minh chữ ký trên Google và migration trên PostgreSQL đang chạy.
- Reverse proxy cần rate-limit đường dẫn auth, HTTPS, giới hạn request và không
  ghi query callback (chứa code/state) vào access log. Script office đã tắt access log
  Uvicorn; vẫn cần kiểm tra cấu hình proxy trước khi public.
- Không expose instance office `PUBLIC_READ_ONLY=false` ra Internet. Chế độ public
  chỉ đọc là ranh giới tạm; chưa mở tính năng trả phí khi chưa có entitlement API.

Tài liệu nguồn: [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect),
[google-auth ID token verification](https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.id_token.html).
