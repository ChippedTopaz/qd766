# Phân tích thử nghiệm — prompt v2

## Vì sao kết quả cũ sơ sài

Prompt cũ yêu cầu viết lại hành động ngắn gọn. Gemini chỉ nhận findings và gợi ý chung theo nhóm, không nhận bảng số liệu thành phần đầy đủ. Do đó nhiều mục số hóa dùng chung lời khuyên, PAKN bị gợi ý theo hồ sơ TTHC thay vì phản ánh kiến nghị.

## Điều chỉnh

- Mỗi khuyến nghị yêu cầu khoảng ba đến bốn câu: ý nghĩa/điểm nghẽn → nội dung cần kiểm tra → hành động, phối hợp và theo dõi. Chưa đủ căn cứ phải nêu dữ liệu thiếu, không kết luận nguyên nhân.
- Bổ sung ngữ cảnh điểm sáu nhóm, chỉ tiêu thành phần, tham số tổng hợp dạng số và kỳ đã kết thúc hay chưa tại thời điểm chụp dữ liệu (múi giờ Việt Nam). Không gửi raw payload hoặc dữ liệu từng hồ sơ.
- Gợi ý riêng cho cấp kết quả điện tử, số hóa hồ sơ, tái sử dụng, kết nối chia sẻ, hồ sơ dùng dữ liệu dân cư và danh mục TTHC kết nối dân cư.
- Phân biệt PAKN đúng hạn với hài lòng PAKN; không nhầm với hồ sơ TTHC đúng hạn/quá hạn.
- Phân biệt hồ sơ đã/đang giải quyết, hồ sơ chưa có kết quả và chưa đến bước thanh toán. Khuyến nghị cấp nhóm định hướng ưu tiên; cấp thành phần chỉ rõ thao tác đối chiếu riêng để hạn chế lặp.
- Giữ schema cũ tương thích giao diện/kết quả lưu. Số liệu vẫn do hệ thống hiển thị, Gemini không thêm chữ số/công thức/URL/HTML hay bảo đảm tăng điểm. Giữ giới hạn mỗi khuyến nghị tối đa một nghìn ký tự; tăng trần output lên chín nghìn token cho các lượt có nhiều findings.
- Version mới `analysis-v2`. Không đổi giá hai mươi Credit, không thay hàng chờ/hoàn Credit, không chạy khi tải trang và không thay dữ liệu cào.

## Kiểm chứng và giới hạn

Kiểm thử dùng HTTP mock: nội dung prompt, ngữ cảnh gửi đi, parser, nghiệp vụ theo chỉ tiêu, bảo vệ phạm vi cơ quan và lọc tham số phi số. Chưa gọi Gemini thật để đánh giá chất lượng văn phong; độ sâu và mức lặp của đầu ra thật cần kiểm thử thủ công sau restart backend. Không cam kết prompt tự bảo đảm hoàn toàn tính đúng của nhận định AI.

Không cần migration/Netlify mới riêng cho thay đổi này; cần restart backend để nạp prompt mới. Kết quả đã lưu không tự thay đổi. Phân tích lại là một lượt trả Credit mới, vẫn cần người dùng xác nhận.
