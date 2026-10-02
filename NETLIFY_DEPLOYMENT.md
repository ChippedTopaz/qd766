# Frontend production riêng trên Netlify

Site dự kiến: https://bochiso766.netlify.app/

## Kết nối repository

Trong Netlify, kết nối site này với repository `ChippedTopaz/qd766`, branch `main`.
Base directory để trống (gốc repo); build command `npm run build:netlify`;
publish directory `netlify-public`. Các giá trị đã được đặt trong `netlify.toml`.
Chỉ deploy sau khi các thay đổi này đã được đưa lên GitHub.
Không chỉnh cấu hình site `dieuphoi.netlify.app`.

Build không cần Python/PostgreSQL và không dựng fixtures. Chỉ công bố HTML,
CSS, JavaScript và thư viện giao diện; không công bố `web/data`, source maps,
`.env`, backend hoặc tài liệu nội bộ. Script yêu cầu output chưa tồn tại;
khi build lại local, dùng checkout/build directory mới.

## Chưa có backend public: chưa thể tra cứu

Frontend dùng các API cùng origin `/api/v1/...`. Chưa cấu hình proxy khi chưa
có địa chỉ HTTPS backend được kiểm chứng. Không dùng `127.0.0.1:8767` làm
đích proxy Netlify: đó không phải máy cơ quan từ môi trường Netlify.
Không bật fixture fallback cho bản public. Không thêm SPA wildcard rewrite
trả HTML cho đường dẫn API.

Backend public phải là instance tách khỏi instance quản trị nội bộ, dùng
`QD766_PUBLIC_READ_ONLY=true` và `QD766_REQUIRE_LOGIN=true`; cấu hình Google
đầy đủ theo `GOOGLE_LOGIN.md`. Không đưa mật khẩu PostgreSQL hay Google client
secret vào frontend/Netlify static assets. Không mở cổng PostgreSQL ra Internet.

Sau khi chốt đường dẫn HTTPS public, bổ sung proxy `/api/*` tới backend,
kiểm tra cookie và redirect đăng nhập thực tế. Đăng ký Google redirect URI:

`https://bochiso766.netlify.app/api/v1/auth/google/callback`

Proxy không được cache API/session; backend phải gửi `Cache-Control: no-store`
cho auth và nội dung tài khoản. Không ghi query OAuth callback vào access log.
Header trong `netlify.toml` chỉ dành cho static assets, không thay thế cấu hình
response của backend/proxy.

## Gate trước thử nghiệm người dùng

- HTTPS/proxy hoạt động, backend không lộ endpoint quản trị hoặc dữ liệu mẫu.
- Google login, logout, tài khoản chưa được gán tỉnh và tài khoản bị khóa được
  thử trên trình duyệt thật; không coi mock tests là kiểm chứng OAuth production.
- Người dùng chỉ xem dữ liệu thuộc tỉnh được cấp quyền; so sánh tỉnh khác chỉ
  dùng điểm tổng hợp được phép. Không cho người dùng tạo job all-TTHC.
- DVCQG vẫn chỉ được gọi bởi worker máy cơ quan và chịu circuit/rate controls.
- Khai thác theo TTHC/credit/thanh toán chưa mở cho production ở bước này.

Kiểm tra gói frontend: `npm run test:netlify` trên checkout sạch.

Tài liệu Netlify: https://docs.netlify.com/manage/routing/redirects/rewrites-proxies/
