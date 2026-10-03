# Nghiệm thu luồng credit local — 03/10/2026

## Đã được người quản trị thử trực tiếp

- Cấp thêm 30 credit cho A.
- Hoàn credit khi lấy dữ liệu thất bại.
- Sau lỗi TEST.002, yêu cầu mới có thể thử lại (không gắn vào job lỗi cũ).
- A khai thác thành công; B yêu cầu sau đó được tính credit và xem ngay dữ liệu
  dùng chung, không cần lấy lại từ nguồn.

## Kiểm thử tự động

18 kịch bản trong `test_local_credit_trial.py`, gồm:

- A/B cùng chờ một job, mỗi người giữ và quyết toán credit riêng.
- Mở lại dữ liệu của mình không thu thêm; tài khoản khác chưa yêu cầu bị chặn.
- Thất bại, hủy, circuit chặn hoàn credit; circuit mở chặn yêu cầu mới.
- Thử lại job lỗi/hủy bằng xác nhận mới; giữ nguyên lịch sử hoàn cũ.
- Gửi lặp cùng mã xác nhận/cấp credit không ghi giao dịch hai lần.
- Không đủ credit cho cả yêu cầu nhiều thủ tục: không ghi một phần yêu cầu.
- Thu hồi quyền giữa báo giá và xác nhận chặn tạo yêu cầu.
- Thu hồi quyền tạo yêu cầu không xóa quyền đọc dữ liệu đã mua, không hủy yêu cầu
  đang chờ đã xác nhận. Khi yêu cầu đó thành công vẫn quyết toán bình thường.
- Tài khoản cơ quan chỉ đọc chi tiết cơ quan được gán. Điểm các đơn vị khác phục vụ
  so sánh; chỉ tiêu thành phần/điểm tổng tỉnh bị lược bỏ khỏi phản hồi.
- Bộ nhớ dữ liệu dùng chung không bị sửa bởi thao tác lọc cho tài khoản cơ quan.
- API admin, CSRF, giới hạn loopback và tách biệt môi trường thật.

## Giới hạn nghiệm thu

Đây là SQLite riêng với tài khoản/dữ liệu mô phỏng, giá thử 3 credit.
Chưa nghiệm thu tải đồng thời trên PostgreSQL, worker gọi DVCQG, kết nối Google
thật cho luồng credit, hoặc mức giá thương mại. Không coi kết quả này là nghiệm
thu thu phí production.

## Đợt tiếp theo, vẫn local

1. Duyệt thông báo và trải nghiệm khi thiếu credit, chờ lâu, thất bại, yêu cầu lại.
2. Chuẩn bị bản tích hợp với PostgreSQL thử nghiệm riêng; kiểm tra nhiều tài khoản
   xác nhận đồng thời, chống job/giao dịch trùng và khôi phục sau worker gián đoạn.
3. Chỉ thử lấy dữ liệu thật khi quản trị cho phép, giữ circuit và giới hạn nguồn.
4. Trước triển khai cần duyệt giá thử/đối tượng mở quyền, backup và migration 0011,
   kế hoạch rollback, chạy thử Google/worker thật. Chưa push/deploy lúc này.

Thanh toán SePay và thu phí chính thức vẫn để sau giai đoạn dùng thử.
