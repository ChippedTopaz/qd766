# Nghiệm thu luồng dùng thử — 04/10/2026

## Phạm vi và bằng chứng

Kiểm thử tự động qua API thật của ứng dụng, Google identity được mock, danh mục
và dữ liệu được mô phỏng. Không đăng nhập Google thay người dùng, không gọi
DVCQG, không thay schema đang phục vụ 8771 hoặc production.

Ca xuyên suốt chạy trên SQLite riêng và PostgreSQL `qd766_credit_test`, schema
`journey_20261004_020146_52a01516` được giữ để kiểm tra. Không phải kiểm chứng
worker production truy cập nguồn thật hoặc nghiệm thu UI trên thiết bị thật.

| Tình huống | Kết quả |
| --- | --- |
| Admin tạo lời mời và người dùng đổi lời mời qua callback | Tự có một tháng thử + 100 Credit; không cần quyền tra cứu riêng |
| Hai tài khoản gửi cùng thủ tục, cùng kỳ | Một job; mỗi tài khoản giữ 5 Credit riêng |
| Mock worker hoàn tất | Cả hai còn 95 Credit; Credit đang giữ trở về 0 |
| Xem lại và xác nhận lại dữ liệu của mình | Credit sử dụng bằng 0; số dư không đổi |
| Tài khoản thứ ba chưa có quyền sở hữu dữ liệu đó | Thư viện chưa hiển thị; xác nhận 5 Credit, dữ liệu có ngay, còn 95 |
| Xem chi tiết dữ liệu đã khai thác | Có đủ 6 nhóm chỉ tiêu mô phỏng |
| Tài khoản cấp cơ quan | Chỉ chọn cơ quan được gán; không mở API admin |
| Gửi yêu cầu thứ ba khi còn hai yêu cầu chờ | Bị chặn; không giữ thêm Credit |
| Job thất bại | Hoàn Credit; giải phóng chỗ để gửi yêu cầu mới |
| Đăng nhập lại | Giữ thư viện/số dư; không cấp lại tháng thử hoặc 100 Credit |
| Admin khóa tài khoản | Phiên cũ mất quyền ngay; worker vẫn hoàn đúng Credit cho yêu cầu thất bại còn chờ |

## Tổng kết

- 191 tests backend đạt, bao gồm ca xuyên suốt mới.
- Ca xuyên suốt trên PostgreSQL đạt.
- Kiểm tra kiểu frontend và test câu chữ tra cứu/ví hai nguồn đạt.
- Chỉ bổ sung kiểm thử và tài liệu trong bước này; không khởi động lại server,
  reset tài khoản, sửa số dư thực tế hoặc deploy.
- UI Google thật và tương tác người dùng không được suy ra từ test callback mock.
  Các xác nhận trước của chủ dự án giữ nguyên; phần chưa xác nhận cần thử thực tế.

## Trước khi chuẩn bị phát hành

1. Tách cờ chính sách ví dùng thử ra khỏi cờ Google local bằng cơ chế production
   được phê duyệt. Hiện `source_wallet_trial` cố ý chỉ cho local, không được bật
   trực tiếp trên public backend hoặc mang trình mô phỏng vào production.
2. Rà soát migration và số dư cũ/đang giữ; không tự phân loại số dư admin đã cấp
   thành Credit mua riêng. Cần backup và kế hoạch đối soát trước khi nâng DB thật.
3. Chuẩn bị lịch xử lý chu kỳ production, trạng thái vận hành và đường rollback;
   local lifespan không thay thế việc triển khai lịch production.
4. Kiểm chứng public boundary, worker thật/circuit và cấp Credit thử trên dữ liệu
   thật sau khi chủ dự án cho phép. Thanh toán vẫn tắt.
5. Gộp frontend vào một đợt deploy sau phê duyệt để tránh deploy Netlify nhiều lần.

Chưa tuyên bố sẵn sàng thu phí hay đã hoàn tất kiểm toán bảo mật production.
