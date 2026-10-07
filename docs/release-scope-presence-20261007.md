# Bản gộp ngày 07/10/2026

So với commit chính thức `0a54bd2`, chỉ bổ sung các thay đổi đã yêu cầu:

- Admin và tài khoản có quyền toàn quốc tra cứu TTHC theo tỉnh đang chọn. Tỉnh được gán là mặc định, không phải giới hạn đối với hai loại quyền này. Báo giá, xác nhận, thư viện và lịch sử yêu cầu ràng buộc đúng tỉnh; vẫn kiểm tra quyền sở hữu dữ liệu trả phí. Quyền cấp tỉnh/cơ quan không được vượt tỉnh được gán.
- Tài khoản cấp cơ quan chỉ chọn được cơ quan đã gán. Không bổ sung cơ quan đối chiếu vào bộ lọc khi tải chi tiết hoặc đổi kỳ. Kiểm tra đường dẫn khôi phục, thao tác bộ lọc và liên kết cơ quan. Điểm cơ quan khác vẫn là dữ liệu đối chiếu; chỉ tiêu chi tiết và tham số vẫn được backend lọc.
- Nhãn số người online trên frontend chính và quản trị. Đếm tài khoản có hoạt động trong 3 phút, cập nhật mỗi phút, không công khai danh tính và không tải lại trang. Bộ đếm trong bộ nhớ của một tiến trình backend; khởi động lại sẽ đặt lại bộ đếm. Muốn chạy nhiều tiến trình cần kho đếm dùng chung.
- Lịch cào: bổ sung retry hữu hạn cho lỗi kết nối tạm thời, tận dụng bản tải thành công; không retry mù lỗi dữ liệu hoặc vượt cơ chế SafetyStop. Giữ dấu thời gian lấy dữ liệu gốc và ghi nhận danh mục cơ quan bị nguồn thiếu giữa các nhóm. Nhãn quản trị hiển thị 04:00, không tự thay lịch Windows.

Không thay schema, công thức, prompt AI, lịch Windows, chính sách Credit hoặc quyền tài khoản. Việc khôi phục 6 khối dữ liệu ngày 06/10 và duyệt một tài khoản đã thực hiện riêng, không được chạy lại khi deploy.

## Kiểm tra

- TypeScript biên dịch thành công.
- Backend: 341 kiểm thử đạt.
- Frontend: 44 file kiểm thử đạt, gồm hồi quy giới hạn cơ quan sau đổi kỳ/đường dẫn/thao tác giả lập.
- Đóng gói Netlify và kiểm tra allowlist đạt; không có dữ liệu mẫu, secrets, source maps hoặc trang xem trước trong gói public.
- Cấu hình backend và kết nối/schema ví Credit đạt kiểm tra chỉ đọc. Không thay thế kiểm thử Google thật hoặc gọi Cổng DVCQG thật.

## Thứ tự triển khai

1. Khởi động lại backend bằng `tools/restart_public_backend.ps1`, giữ các cờ đã đăng ký. Xác nhận `PUBLIC_BACKEND_READY=ok` và `PUBLIC_RUNTIME_POLICY=PASS`.
2. Push commit gộp lên `main`, chờ Netlify build/publish thành công.
3. Tải lại trình duyệt. Kiểm tra admin tra TTHC tại tỉnh khác; cơ quan chỉ có đơn vị được gán trước/sau đổi kỳ; nhãn online cập nhật.

Chỉ stage file mã nguồn, bản JavaScript biên dịch, kiểm thử và tài liệu thuộc phạm vi này. Không stage `.tmp-*`, file HTML xem trước hoặc cấu hình môi trường.
