# Quản lý Công thức tính

Trang Quản trị hệ thống → Công thức tính quản lý nội dung tra cứu, không sửa thuật toán tính điểm, số liệu thu thập, ví Credit, prompt AI hay phân quyền cơ quan.

## Nội dung

- 6 nhóm, 22 thẻ chỉ tiêu. Mục 5.1 hiển thị để tham khảo, không chấm điểm. Thanh toán trực tuyến gồm 3 chỉ tiêu, cơ cấu 2 + 2 + 6 được quản trị viên duyệt sau đối chiếu API và biểu đồ Cổng DVCQG ngày 08/10/2026.
- Tên chỉ tiêu/nhóm, điểm tối đa, ngưỡng, biểu thức toán học, công thức bổ sung, nghiệp vụ, nguồn, lưu ý. Không hiển thị khối nhóm/tài liệu/sổ tay.
- Để trống điểm tối đa để hiển thị Chưa xác định. Để trống ngưỡng nghĩa là không có ngưỡng: nếu biết điểm tối đa, hiển thị điểm = tỷ lệ (%) / 100 × điểm tối đa. Có ngưỡng: đạt ngưỡng được điểm tối đa, dưới ngưỡng tính tỷ lệ / ngưỡng × điểm tối đa. Đây là biểu thức tra cứu, không chạy lại phép tính hay ghi đè điểm nguồn.
- Giao diện máy tính luôn hiển thị hai cột: chọn nhóm/chỉ tiêu và chỉnh sửa bên trái, xem trước bên phải. Tên trường in đậm, giá trị nhập dùng chữ thường. Màn hình hẹp xếp hai phần thành một cột để tránh co nhỏ văn bản.
- Xem trước dùng cùng trình dựng thẻ công thức với trang người dùng; tất cả nội dung nhập được escape, không cho chạy HTML.
- Không có khối Giải thích thành phần riêng; tử số và mẫu số nằm trong biểu thức. Chú thích tiêu đề/phiên bản trước đây được đưa vào ô Nội dung nghiệp vụ để sửa chung, không mất văn bản và không tự thay đổi dữ liệu khi chỉ mở trang. Hai trường cũ chỉ được gộp vào nội dung lưu khi quản trị thực sự sửa ô nghiệp vụ.

## Lưu và khôi phục

Công thức phụ hiển thị ngay dưới công thức chính, có nhãn riêng và bố cục nhỏ gọn. Mỗi công thức phụ chọn Cộng, Trừ, Nhân hoặc Chia giữa hai thành phần, và có hệ số tiếp theo tùy chọn. Công thức cũ không có trường operator/multiplier vẫn dùng phép chia và × 100% như trước; công thức mới để trống hệ số mặc định. Các phép tính chỉ là nội dung trình bày, không thực thi mã hay thay đổi điểm đã thu thập.

Chọn nhóm và chỉ tiêu, sửa các trường cần thiết, nhập ghi chú, bấm Lưu thay đổi. Bản nháp được giữ khi chuyển giữa các chỉ tiêu trong tab. Mỗi lần lưu tạo một snapshot toàn bộ nội dung; chỉ trường người quản trị sửa thay đổi. Phiên bản cũ không bị ghi đè. Nếu một phiên khác lưu trước, yêu cầu lưu bị từ chối để tránh ghi đè.

Lịch sử phiên bản → đưa phiên bản vào bản nháp → kiểm tra → Lưu thay đổi để áp dụng. Tải lại bản đang áp dụng khi có bản nháp cần bấm xác nhận lần thứ hai.

Trang người dùng tải cấu hình khi mở Công thức tính, không thêm request chặn khởi động dashboard. Các request cùng lúc gộp một lượt; bản vừa tải được dùng trong 10 giây. Nội dung mới áp dụng ở lần mở tiếp theo sau thời gian này hoặc tải lại trang. Nếu tải lỗi, hiển thị cảnh báo đang dùng bản đã có.

## Cài đặt lần đầu

### Nội dung soạn trong bản thử nghiệm

Bản thử nghiệm loopback 8819 tự xuất cấu hình sau mỗi lần Lưu thành công vào `outputs/formula-preview-saved.json` và khôi phục nội dung này khi khởi động lại. Chỉ nội dung đã bấm Lưu được giữ, không phải bản nháp đang gõ. File này không được phục vụ qua HTTP hoặc đóng gói frontend. Khi triển khai, phải backup và đối chiếu snapshot, rồi nhập cấu hình qua endpoint quản trị có xác thực/CSRF và expectedVersion của bản chính; không ghi đè bảng hay thay seed. Việc deploy code tự nó không nhập snapshot. Bản chính tạo phiên bản mới và giữ phiên bản trước để khôi phục. Xác nhận lại nội dung với quản trị trước khi áp dụng.

Trước deploy phải backup PostgreSQL, nâng Alembic lên 20261008_0024, restart backend rồi deploy frontend cùng formula-admin.css và các module mới. Migration lưu nguyên trạng đầy đủ thành phiên bản 1; actor trống thể hiện bản gốc. Nếu chưa nâng schema, trang vẫn xem được nhưng không thể lưu. Không chạy migration production chỉ để xem thử giao diện.

Sau lần cài đặt đầu tiên, chỉnh nội dung trong quản trị không cần sửa code, restart hoặc deploy. Endpoint sửa chỉ cho admin, kiểm tra CSRF, lưu nhật ký; endpoint đọc không trả thông tin người sửa hoặc nhật ký quản trị.

formula_seed.json được xuất cơ học từ cấu hình mặc định, giữ nguyên văn bản tài liệu gốc và các mô tả đang hiển thị. Không chạy lại script export seed sau khi sửa nội dung qua quản trị: nội dung đã lưu nằm trong PostgreSQL, không trong file seed.
