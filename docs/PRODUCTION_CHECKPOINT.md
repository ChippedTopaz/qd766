# Checkpoint chuẩn bị chạy thử production — 02/10/2026

## Cập nhật kiểm chứng ngày 03/10/2026

- Audit SELECT-only PostgreSQL: đợt năm 2026 `8b023c82-022e-45f0-94aa-323e10cc3334`
  đã succeeded, 34/34 tỉnh succeeded. Kho chi tiết năm có 34 tỉnh, mỗi tỉnh 6
  dataset. Không suy ra mọi cơ quan đều có đủ điểm từ số lượng dataset.
- Tổng hợp toàn quốc đủ 15 kỳ: tháng 1–10, quý 1–4, năm 2026; mỗi kỳ 34 tỉnh,
  6 nhóm và completeness complete. Kỳ hiện tại cập nhật gần nhất khoảng
  12:16 ngày 03/10/2026 giờ Việt Nam.
- Kiểm tra hợp đồng HTTP trên PostgreSQL đạt 15 kỳ Phú Thọ: mỗi kỳ 6 nhóm,
  34 tỉnh trong bảng so sánh; hiện tất cả 15 kỳ đều có bản chi tiết Phú Thọ.
- Các bảng account/login/paid request/ledger/notification đã có trong DB thật.
  Luồng thư viện cá nhân, xác nhận giá, entitlement và credit đã được nối API;
  99 kiểm thử backend đạt. Chưa nghiệm thu Google thật hoặc giao dịch đồng thời
  PostgreSQL. Các đoạn “chưa có entitlement API/chưa migration” dưới đây là
  checkpoint lịch sử, được thay thế bởi kết quả này.
- Cấu hình instance office hiện chưa bật public/login/paid, chưa có bộ cấu hình
  Google hay thư viện xác minh Google. Không tự public instance office.
- Công cụ `tools/audit_trial_readiness.py --year 2026` kiểm tra chỉ đọc, không
  hiển thị secret hoặc địa chỉ kết nối; không tạo job/tài khoản/giao dịch.

**Bước cần quản trị chốt:** HTTPS backend riêng cho người thử, OAuth client Google,
giá credit được duyệt. Sau đó mới cấu hình instance có hàng rào public, gán tỉnh,
cấp credit thử có sổ giao dịch và nghiệm thu bằng hai tài khoản thật.
Không bật thanh toán ở giai đoạn này.

## Đã chốt

- Mẫu báo cáo lãnh đạo xếp hạng cùng cấp được người dùng tạm chấp nhận.
- Nút xuất dữ liệu có nhãn **Xuất dữ liệu**.
- Dữ liệu tổng hợp tháng/quý/năm đủ sáu nhóm do lịch hệ thống lấy, không do người dùng yêu cầu.
- Khai thác theo TTHC chỉ mở sau xác thực, phân quyền và xác nhận giá credit.
- Chạy thử một tháng, quản trị viên cấp credit thủ công; chưa tích hợp thanh toán.

## Hàng rào dùng thử chỉ đọc

`QD766_PUBLIC_READ_ONLY=true` bật trên một instance phục vụ người dùng riêng.
Không bật trên server vận hành tại cơ quan nếu vẫn cần sử dụng màn hình vận hành/TTHC.
Biến mặc định `false`, không tự sửa `.env`, không thay đổi Task Scheduler hay circuit.

Chế độ này dùng danh sách cho phép, mặc định từ chối:

- Chỉ đọc dashboard phạm vi `all`, danh sách tỉnh, xếp hạng và tổng hợp toàn quốc đã lưu.
- Từ chối mọi thao tác ghi qua HTTP và mọi endpoint chưa được duyệt.
- Từ chối TTHC, danh mục khai thác, job/batch/control, snapshot/entity thô.
- Không phục vụ fixture JSON, source map hoặc tài liệu API ra ngoài.
- Giao diện ẩn TTHC, vận hành, gợi ý; không fallback sang fixture khi API lỗi.
- Worker/lịch tự động tiếp tục dùng database trực tiếp; hàng rào HTTP không tự mở circuit.

Đây là lớp bảo vệ **trước xác thực**, không phải production hoàn chỉnh. Chưa bật,
chưa triển khai instance mới, chưa mở port, chưa sửa firewall/tunnel/DNS.
Không public server mặc định `false`; không coi CORS là xác thực.

## Thứ tự tiếp theo

Đã được người dùng duyệt đăng nhập Google. Lõi và giao diện đăng nhập đã triển khai;
xem [GOOGLE_LOGIN.md](GOOGLE_LOGIN.md) để cấu hình, gán tỉnh và nghiệm thu.
Chưa bật đăng nhập, chưa có OAuth client/domain, chưa áp dụng migration trên DB thật.

1. Chốt nhà cung cấp đăng nhập và domain/HTTPS. Khuyến nghị đăng nhập Google;
   tài khoản, tỉnh/cơ quan, vai trò và credit vẫn do QD766 quản lý phía server.
   Người dùng đã duyệt Google; cần cấu hình OAuth/domain trước khi kích hoạt.
2. Server ánh xạ phiên đăng nhập sang tài khoản; phân quyền theo tỉnh/cơ quan.
   Tài khoản thử nghiệm mặc định thường, không tự cấp admin hay quyền khai thác TTHC.
3. Kết nối luồng TTHC vào account/ledger đã có; cấp credit thủ công có sổ giao dịch.
   Xác nhận giá, chống lặp giao dịch, thông báo thành công hoặc hoàn credit.
4. Nghiệm thu production: HTTPS, hạn chế endpoint, không lộ secret, backup/restore,
   kiểm thử phân quyền chéo tài khoản, chất lượng dữ liệu và tải an toàn.
5. Sau một tháng chạy thử mới tích hợp thanh toán; SePay hiện chỉ là dự kiến.

Không triển khai công thức thanh toán chưa rõ hoặc dựng chi tiết DVCTT của đơn vị
con khi nguồn chỉ trả điểm. Mọi mở rộng dữ liệu lịch sử phải qua lịch quản trị an toàn.
# Chuẩn bị backend người dùng riêng — 03/10/2026

Launcher `tools/start_public_backend.py` bind loopback 8769; đọc riêng `.env.public`,
bắt buộc Google login/public boundary và giữ paid/trial credits tắt. Chỉ dùng chung
kết nối PostgreSQL từ `.env`; không kế thừa quyền quản trị hoặc SQL echo.
104 kiểm thử backend PASS, gồm 5 kiểm thử launcher/config/boundary mới.
Check khởi chạy hiện BLOCKED vì chưa có cấu hình Google riêng; chưa chạy 8769,
chưa triển khai D:\QD766\app, thêm task, sửa DNS, route tunnel hoặc Netlify.
Google login thật, cookie HTTPS và kết nối DB của instance này chưa được nghiệm thu.
Hướng dẫn: `docs/PUBLIC_BACKEND_ROLLOUT.md`. Không mở cổng 8767/8768 ra Internet.
# Chuẩn bị production trial — 03/10/2026

Quản trị đã xác nhận Google thật, gán Phú Thọ, xem kỳ/so sánh và đăng xuất tại
api.bochiso766.com. Chuẩn bị task QD766 Public Backend riêng (at logon, hidden,
log riêng, restart on failure, không tự start/stop), proxy API Netlify cùng origin
và cho phép callback chính bochiso766.com ngoài callback api đã nghiệm thu.
107 kiểm thử Python PASS; PowerShell syntax PASS; build và test Netlify PASS.
Chưa đăng ký task mới, thay config secret/callback, DNS, Netlify deployment hoặc
nghiệm thu cookie/session qua Netlify. Không bật credit/paid/payment.
Thực hiện từng bước theo docs/PRODUCTION_TRIAL.md, giữ callback api để rollback.
