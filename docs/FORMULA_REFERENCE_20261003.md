# Đối chiếu công thức ngày 03/10/2026

## Nguồn và giới hạn

Tài liệu do người dùng cung cấp: **Mô tả công thức tính chỉ số 766.docx**.
SHA256: `41A27E55E251C616408D310EE7467CC831D373ED95B108FD65D5832A337087AF`.
Đọc toàn bộ nội dung OOXML của bảng: 20 mục nghiệp vụ, 5 nhóm; mục 4.5 có hai tỷ lệ khác nhau nên sổ tay có 21 công thức. Không có ảnh hoặc phương trình OMML. Thanh toán 3.5–3.6 được đặt ở menu nhóm Thanh toán để khớp sáu nhóm của ứng dụng; giữ số mục nguồn, không đổi phân loại nguồn một cách ngầm định.

Không xác minh độc lập tính ban hành, ngày hiệu lực hay tính pháp lý của tài liệu. Đây là căn cứ mô tả nghiệp vụ người dùng cung cấp, không phải bằng chứng rằng quy định vừa thay đổi. Bộ dựng trang Word không có LibreOffice đi kèm nên không xác minh phân trang/ảnh render của bản gốc; không sửa hoặc tái xuất DOCX. Nội dung nguồn hoàn toàn là văn bản trong bảng, đã đọc đủ các ô.

## Khác biệt so với cách hiển thị cũ

| Nội dung | Trước đối chiếu | Theo tài liệu và xử lý lần này |
| --- | --- | --- |
| DVCTT 3.3 | channelOnlineSum / channelTotalSum, đủ điểm từ 50%; không có hệ số đồng bộ | Nhân thêm hệ số đồng bộ; hồ sơ trực tuyến phải đáp ứng điều kiện kết quả điện tử khi TTHC yêu cầu. Không tự ánh xạ trường chưa được xác nhận. |
| Điểm DVCTT | Suy luận 2–4–6; mục dịch vụ phát sinh dùng ngưỡng 100% | Tài liệu không phân bổ điểm tối đa riêng, không nêu ngưỡng 100% tại 3.2. Ngừng trả kết quả đối chiếu và gợi ý mất điểm từ cấu hình cũ; giữ điểm API, hiển thị tham số gốc. |
| DVCTT toàn trình | Thiếu định nghĩa mẫu số đủ điều kiện | Sổ tay 3.1 phân biệt mẫu số của toàn trình với một phần/tổng DVCTT. |
| Tiến độ 2.1 | Đúng hạn/tiếp nhận × điểm tối đa | Tỷ lệ tính cả đã và đang xử lý trong hạn; thêm quy tắc kết thúc, bổ sung, thiếu ngày hẹn. Phép nhân điểm hiện tại được ghi rõ chỉ là đối chiếu cũ, tài liệu chưa xác nhận quy đổi. |
| Quá hạn suy ra | Phần chênh tổng và đúng hạn mang nhãn quá hạn | Khi không có số quá hạn riêng, frontend gọi là phần ngoài nhóm đúng hạn, không khẳng định mọi hồ sơ đều quá hạn. |
| Thời gian 2.2 | Chỉ hiển thị avgProcessingDays | Bổ sung phạm vi TTHC cụ thể và các đơn vị giờ/ngày/ngày làm việc/tháng. Giữ trường API ngày, phân biệt với toàn bộ chỉ tiêu 2.2. |
| Số hóa 4.1 | Thiếu giải thích tập hồ sơ đủ điều kiện | Nêu mẫu số chỉ gồm TTHC yêu cầu văn bản/giấy tờ, không mặc định toàn bộ hồ sơ. |
| Số hóa 4.2, 4.3 | Thiếu diễn giải ngưỡng | Bổ sung ngưỡng 80%, điều kiện tệp kết quả/tái sử dụng. |
| Hài lòng 5.4 | Thiếu công thức và ngưỡng | Bổ sung 100% trừ tỷ lệ quá hạn và tỷ lệ hồ sơ có PAKN/dislike; ngưỡng 90%. |
| Đồng bộ 1.4 | Thiếu cách chọn mẫu số/fallback | Lấy mẫu số lớn hơn BCQG và DVCQG; fallback năm trước chia 12/4 cho tháng/quý. |
| Các mục còn thiếu | Chưa có trang tra cứu riêng | Bổ sung công khai 1.1–1.4, tiến độ 2.1–2.2, DVCTT 3.1–3.3, thanh toán 3.5–3.6, số hóa 4.1–4.5, hài lòng 5.1–5.4. |

Ngưỡng được ghi rõ chỉ tại: 3.1 = 80%, 3.3 = 50%, 3.5 = 80%, 4.2 = 80%, 4.3 = 80%, 5.4 = 90%.
Điểm tối đa nhóm 18/20/12/22/18/10 và tổng 100 giữ theo hệ thống hiện tại; tài liệu này không cung cấp bảng phân bổ điểm. Không gán điểm tối đa riêng, không tự coi DVCTT chủ động là 0 điểm chỉ vì tài liệu không nêu.

## Những điểm cần xác nhận thêm

- 1.2: ngày quyết định trước ngày cuối kỳ cộng 10/5 ngày làm việc; cách xác định tập cần công khai và khử trùng giữa các tập.
- 1.3: nghiệp vụ nói không theo thời gian nhưng lưu ý chung nói theo kỳ.
- 3.2: đoạn cũ ẩn theo TTHC, Update lại mô tả theo TTHC; ngưỡng, phân bổ điểm và định nghĩa trường API.
- 3.3: channelOnlineSum đã lọc kết quả điện tử chưa, hệ số đồng bộ có được gộp vào tỷ lệ API chưa.
- 3.5: có dòng bỏ thống kê rồi bổ sung công thức; chưa rõ phạm vi bị bỏ.
- 3.6: công thức dùng mẫu số hồ sơ, đoạn tình huống dùng số TTHC; không tự giải quyết mâu thuẫn bằng việc chọn một trường API.
- 5.2: dòng công thức lỗi văn bản; diễn giải tử số từ phần quy tắc phải được xác nhận.
- 5.3: tham chiếu 5c không khớp số mục và điều kiện phản ánh lặp lại có ghi chú chưa triển khai.
- Bảng điểm tối đa của từng thành phần cho đủ 100 điểm; không có trong tài liệu này.

## Triển khai

- Sidebar “Công thức tính”; tra cứu độc lập với bộ lọc tỉnh/kỳ, không enqueue/fetch khi mở menu.
- Sáu mục lục liên kết, công thức dạng phân số, ngưỡng, điều kiện và cảnh báo điểm chưa rõ. Hiển thị responsive, bàn phím dùng được các liên kết.
- Tại bảng chi tiết có mục mở sổ tay; không đổi cấu trúc bảng, dữ liệu nguồn, snapshot, DB, lịch chạy hoặc circuit.
- `online-scoring.ts` ngừng công thức suy luận; không tạo gợi ý “mất điểm lớn nhất” từ phân bổ chưa được xác nhận.
- Nhánh xem thử `design/overview-bento-20261002`; mốc trước sửa `backup/pre-official-formulas-20261003` tại `fb788ae`.
- Chỉ phục vụ xem thử cổng 8768. Không deploy D:\QD766\app, không push main/Netlify, không chạy update_qd766.ps1 từ nhánh này.

## Kiểm chứng

- Build TypeScript PASS.
- 85 kiểm thử Python PASS.
- 8 bộ kiểm thử frontend PASS, gồm formula-reference và kiểm tra mở menu qua renderer thật không tạo network request.
- Kiểm tra giao diện desktop PASS: 6 nhóm, 21 thẻ; mục lục nhảy đúng nhóm, không có cảnh báo dữ liệu kỳ/tỉnh trên trang tra cứu độc lập.
- Kiểm tra mobile PASS tại bề rộng thực tế 375px: không tràn ngang (scrollWidth = clientWidth = 375); phân số xuống dòng, nội dung đọc được. Trả viewport về mặc định sau kiểm tra.
- Đóng gói Netlify PASS trong thư mục kiểm thử tạm riêng: đủ tài nguyên, không kèm fixture, secret hay source map. Tổng 9 bộ frontend/đóng gói PASS.
