# Bản thử credit riêng trên máy

Chỉ dùng dữ liệu và tài khoản **mô phỏng**. Không gọi Cổng DVCQG, không đọc cấu hình
production, không chạy worker thật, không sửa PostgreSQL hoặc Task Scheduler.
Giá 3 credit/TTHC chỉ phục vụ kiểm thử, chưa phải mức thu phí được duyệt.

## Mở bản thử

Trong PowerShell tại thư mục dự án:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\start_local_credit_trial.ps1
```

Giữ cửa sổ này mở, truy cập http://127.0.0.1:8770/local-trial.html.
Database và giao diện biên dịch nằm riêng trong `.tmp-credit-trial`.
Cổng 8767/8768/8769 không bị thay đổi. Dừng bằng Ctrl+C trong cửa sổ bản thử.

## Thử theo thứ tự

1. Chọn **Người thử A**, mở Dashboard, vào **Theo TTHC**, chọn TEST.001 năm 2026.
   Chỉ chọn bộ lọc không tạo job. Xem báo giá rồi xác nhận: giữ 3 credit.
2. Về bàn thử, chọn **Người thử B**, yêu cầu cùng thủ tục/kỳ: cũng giữ 3,
   dùng chung job, không tạo job mới.
3. Về bàn thử, chọn **Quản trị mô phỏng**, hoàn thành job.
   Mỗi người được quyết toán 3 credit, nhận thông báo và quyền xem dữ liệu riêng.
4. Chọn lại A, tải lại Dashboard, chọn thủ tục đã khai thác: không tính phí lại.
   Người khác chưa được cấp quyền xem phải tạo yêu cầu dù dữ liệu dùng chung đã có.
5. Thử thủ tục khác và mô phỏng thất bại, hủy hoặc circuit chặn: hoàn credit giữ.
6. Chọn người chưa có quyền: có số dư vẫn không được yêu cầu khai thác.
   Admin có thể bật quyền TTHC và cấp credit, xem sổ giao dịch trong trang quản trị.
7. Thử vai cấp xã: chỉ xem cơ quan được gán, không mở dữ liệu cơ quan khác.

Chuyển vai dùng cùng cookie trình duyệt: không thử hai vai đồng thời ở hai tab.
Tài khoản ban đầu có 30 credit; chạy lại giữ nguyên số dư/lịch sử của bản thử.

## Phạm vi đã chuẩn bị

- Quyền khai thác độc lập với số dư và vai quản trị.
- Giữ credit khi xác nhận; chỉ ghi nhận chi phí sau khi lưu dữ liệu thành công.
- Job dùng chung nhưng quyền xem và giao dịch thuộc từng tài khoản.
- Cấp credit có khóa chống thực hiện lặp và nhật ký quản trị.
- Thu hồi quyền tạo yêu cầu không xóa thư viện dữ liệu đã được cấp quyền xem.
- Migration `20261003_0011` mới được chuẩn bị, **chưa áp dụng production**.

Đây chưa phải nghiệm thu đăng nhập Google/worker thật/đồng thời PostgreSQL.
Không triển khai Netlify hoặc bật thu phí cho đến khi quản trị duyệt đợt cập nhật.
