# Nghiệm thu dashboard điểm tổng hợp — 02/10/2026

## Đã triển khai trong repository

- Dashboard đọc các kỳ tổng hợp toàn quốc đã lưu, kể cả khi tỉnh chưa có snapshot chi tiết của kỳ đó.
- Kỳ chỉ có tổng hợp hiển thị điểm nguồn của sáu nhóm và tổng điểm nguồn; không tạo dữ liệu thành phần hoặc điểm đơn vị trực thuộc.
- Thông báo rõ “Chỉ có điểm tổng hợp tỉnh”. Chọn đơn vị trực thuộc trong kỳ này hiển thị trạng thái thiếu dữ liệu, không thay bằng điểm tỉnh hoặc số 0.
- Xuất điểm tổng hợp vẫn được phép cho tỉnh; xuất số liệu thành phần bị khóa nếu chưa có chi tiết.
- Màn hình Theo thời gian dùng các kỳ thực đã lưu cùng loại; biến động chỉ tính với kỳ liền trước đúng loại. Thứ hạng chỉ hiện khi đã đọc được bảng so sánh tương ứng.
- Tra cứu là đọc dữ liệu đã lưu, không tạo yêu cầu lấy dữ liệu tổng hợp.

## Kết quả xác minh

- PASS: 85 kiểm thử Python.
- PASS: build TypeScript và sáu bộ kiểm thử frontend: analytics, leadership report, Excel, progress scoring, CSV, summary-only UI.
- PASS: `tools/verify_summary_dashboard.py` kiểm tra API với PostgreSQL thật trong giao dịch chỉ đọc: Phú Thọ có 15 kỳ (tháng 1–10, quý I–IV, năm 2026), mỗi kỳ sáu nhóm và bảng so sánh 34 tỉnh.
- Tháng 10 và quý IV chỉ có tổng hợp; các kỳ còn lại của Phú Thọ có snapshot chi tiết. Có snapshot không đồng nghĩa số liệu đã mới hoặc được nguồn chốt.
- PASS: kiểm thử renderer frontend trong môi trường DOM giả xác nhận thông báo thiếu chi tiết, bảng lịch sử, khóa xuất chi tiết và chỉ dùng GET. Đây không phải kiểm tra giao diện trực quan trong trình duyệt thật.
- Chưa nghiệm thu: phiên bản triển khai tại cổng 8767 và website Netlify sau cập nhật. Chưa kiểm tra mọi kỳ/đơn vị của cả 34 tỉnh bằng giao diện.

Không gọi DVCQG, không sửa dữ liệu PostgreSQL, circuit hoặc Scheduled Tasks trong lượt này. Chưa triển khai lên D:\QD766\app.

## Kiểm tra sau triển khai

1. Chạy `./update_qd766.ps1` theo quy trình hiện có, sau đó tải lại trang.
2. Chọn Phú Thọ, tháng 10/2026 hoặc quý IV/2026: xem điểm sáu nhóm, so sánh 34 tỉnh và thông báo chỉ có tổng hợp.
3. Chọn một sở hoặc xã trong kỳ này: phải báo chưa có điểm cơ quan, không hiển thị điểm tỉnh thay thế.
4. Mở Theo thời gian: xem các kỳ cùng loại và biến động so với kỳ liền trước; kỳ chưa có thứ hạng đã đọc hiển thị dấu trống.
5. Mở Xuất dữ liệu: xuất tổng hợp tỉnh được phép; xuất thành phần trong kỳ chỉ có tổng hợp bị khóa.

Backend dashboard vẫn cần ít nhất một snapshot chi tiết đã lưu để dựng danh mục đơn vị của tỉnh. Cả 34 tỉnh hiện đã có snapshot năm; chưa mở rộng luồng cho tỉnh hoàn toàn chưa có snapshot chi tiết nào.
