# Checkpoint chuẩn bị chạy thử production — 02/10/2026

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
