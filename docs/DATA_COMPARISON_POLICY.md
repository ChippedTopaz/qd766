# Nguyên tắc dữ liệu, so sánh và báo cáo QĐ766

Chốt với chủ dự án ngày 05/10/2026. Đây là nguyên tắc nghiệp vụ áp dụng cho các bước phát triển tiếp theo; ghi nhận chính sách không có nghĩa mọi ràng buộc giao diện đã được triển khai.

### Làm rõ phạm vi giao diện (chốt tiếp ngày 05/10/2026)

Giữ nguyên cách so sánh theo kỳ trên hai menu So sánh theo thời gian / So sánh theo cơ quan. Không thêm chế độ ngày hoặc tự áp ràng buộc chỉ chọn kỳ đóng vào hai menu này. Quan sát ngày chỉ nằm trong ô so sánh của thẻ Tổng điểm ở tab Tổng quan khi chọn kỳ năm (phạm vi tất cả TTHC có lịch sử ngày). Ô chọn ngày chỉ thay đổi phần biến động tham khảo và điểm ngày chọn; không thay đồng hồ/điểm hiện tại hay dữ liệu dùng để xuất báo cáo. Tháng/quý tiếp tục so với kỳ trước. Lịch sử thiếu không tự tính bù. Các nguyên tắc báo cáo chính thức bên dưới không phải chỉ thị thay đổi logic hai menu đã duyệt.

## 1. Hai mục đích sử dụng độc lập

- Quan sát ngày: ảnh chụp điểm của tháng/quý/năm tại thời điểm lấy dữ liệu, phục vụ theo dõi biến động tham khảo hôm nay so với hôm qua. Không phải điểm riêng của một ngày hoặc kết quả chính thức của kỳ. Không cộng các ảnh chụp ngày để tính điểm kỳ.
- So sánh, thống kê và báo cáo chính thức: dùng dữ liệu kỳ tháng, quý, năm đã kết thúc, lấy theo công thức nguồn phù hợp. Kỳ kết thúc là điều kiện cần, không đủ: phải kiểm tra độ đầy đủ, phạm vi và tính tương thích công thức.
- Kỳ đang diễn ra vẫn có thể xem trên tổng quan/theo dõi vận hành, nhưng phải thể hiện tạm thời/tham khảo, không đưa vào kết luận chính thức. Nếu cho xuất dữ liệu kỳ mở, tệp phải ghi rõ tính tạm thời và không gọi là báo cáo chính thức.

## 2. Quy ước quan sát ngày

- Cào 02:00 ngày 06/10 mang ngày tham chiếu 05/10; lưu riêng thời gian lấy thật. Không khẳng định nguồn đã chốt dữ liệu cuối ngày 05/10.
- So sánh hai ngày liên tiếp trong cùng kỳ, phạm vi, cơ quan và cơ sở tính. Không có ngày trước thì không tính biến động; thứ hạng chỉ so sánh khi cùng tập cơ quan hợp lệ.
- Điểm tăng / thứ hạng cải thiện: xanh lá. Điểm giảm / thứ hạng giảm: đỏ. Không đổi: trung tính. Hạng có số nhỏ hơn là cải thiện.
- Không suy diễn biến động thành thành tích hoặc lỗi xử lý hồ sơ khi chưa có bằng chứng: nguồn có thể bổ sung dữ liệu hoặc điều chỉnh cách tính.

## 3. Khi Cổng DVCQG thay đổi công thức

- Lưu nguyên lịch sử đã quan sát và thời điểm lấy; không ghi đè hay gán lại ngày cũ bằng dữ liệu cào mới.
- Ngừng kết luận tăng/giảm qua ranh giới đổi công thức hoặc khi chưa xác minh được khả năng so sánh. Ghi rõ: dữ liệu không cùng cơ sở tính. Không tự khẳng định đã phát hiện công thức mới chỉ vì điểm thay đổi.
- Cào lại các kỳ chịu ảnh hưởng: tháng/quý/năm, tổng hợp tỉnh và chi tiết sáu nhóm/cơ quan tương ứng. Kiểm chứng với nguồn rồi chọn phiên bản kỳ mới làm dữ liệu phục vụ báo cáo; lưu bản cũ để truy vết.
- Nếu nguồn không cung cấp lịch sử ngày theo công thức mới, không thể tái dựng chuỗi ngày cũ cùng cơ sở tính. Chỉ cập nhật được dữ liệu kỳ mà nguồn hiện cung cấp; không giả lập hay tính ngược điểm từng ngày.
- Có thể bắt đầu chuỗi quan sát ngày mới sau thay đổi; chỉ so sánh các quan sát mới đã được xác nhận cùng cơ sở tính. Không nối xuyên ranh giới với chuỗi cũ.
- Quản lý phiên bản/cơ sở công thức, đánh dấu ranh giới thay đổi và chặn so sánh không tương thích là yêu cầu triển khai tiếp theo, chưa được xem là đã có chỉ từ tài liệu này.

## 4. Thu thập và dữ liệu phục vụ báo cáo

- Lịch 02:00 tiếp tục phục vụ theo dõi kỳ đang mở, đồng thời thu bản cuối kỳ sau khi kỳ kết thúc. Kỳ đã kết thúc không cào hàng ngày; vẫn phải cào lại có kiểm soát khi nguồn sửa dữ liệu/công thức.
- Không dùng số lượng bản tổng hợp tỉnh làm bằng chứng đầy đủ chi tiết cơ quan. Kiểm tra đủ tỉnh, sáu nhóm, cơ quan nguồn trả về và kỳ; giá trị thiếu khác số 0.
- Không trộn điểm tổng hợp mới với chi tiết cũ thành một bộ dữ liệu đã xác nhận đồng nhất. Hiển thị riêng thời điểm cập nhật và giới hạn sử dụng nếu chưa đối soát.
- So sánh kỳ phải cùng loại (tháng với tháng, quý với quý, năm với năm), cùng phạm vi và cùng cơ sở tính. Thiếu dữ liệu thì trình bày thiếu, không tự điền.

## 5. Trạng thái xác nhận vận hành

Chủ dự án đã gửi kết quả đăng ký lịch 02:00 thành công và khởi động lại backend với PUBLIC_BACKEND_READY=ok, PUBLIC_RUNTIME_POLICY=PASS, REAL_WALLET=True, REQUESTS_PAUSED=False. Đây chưa phải bằng chứng lượt cào tự động đầu tiên đã hoàn tất. Chính sách này không thay đổi quyền, Credit, lịch cào hoặc tự deploy Netlify.
