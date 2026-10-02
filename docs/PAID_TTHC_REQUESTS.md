# Yêu cầu dữ liệu TTHC trả phí

## Ranh giới với dữ liệu tổng hợp

- Dữ liệu `all` theo tỉnh, tháng, quý và năm chỉ do lịch hệ thống cập nhật.
- Thao tác đổi tỉnh, cơ quan hoặc kỳ của người dùng không được tạo collection job.
- Chỉ yêu cầu `formality` của tài khoản trả phí mới đi qua quy trình credit.
- `PaidDataRequest` là đơn hàng/quyền truy cập của một tài khoản;
  `CollectionJob` chỉ là công việc kỹ thuật dùng chung.

## Quy tắc credit đã chốt

Khi người dùng xác nhận, credit được chuyển từ `credit_balance` sang
`credit_reserved`. Giao dịch chỉ được chốt khi snapshot hoàn chỉnh đã lưu thành
công:

- Dữ liệu chưa có: tạo hoặc tham gia job, giữ credit, chốt khi job thành công.
- Job giống hệt đang chờ/chạy: không tạo job mới; mỗi tài khoản vẫn giữ và trả
  đủ credit của yêu cầu riêng.
- Snapshot đã có: không tạo job; cấp quyền ngay và chốt credit ngay.
- Job thất bại, halted hoặc gặp safety stop: hoàn toàn bộ credit đã giữ.
- Một tài khoản đã mua đúng dataset thì xem lại không tạo giao dịch thứ hai.
- Mọi bước top-up, reserve, charge và release là bản ghi bất biến trong
  `credit_ledger_entries`.

## Trạng thái và thông báo

`PaidDataRequest` có bốn trạng thái:

- `reserved`: đã giữ credit, đang chuẩn bị xử lý;
- `waiting`: đang gắn với một collection job dùng chung;
- `ready`: snapshot hoàn chỉnh và credit đã chốt;
- `refunded`: không có kết quả hoàn chỉnh và credit đã hoàn.

Khi chuyển sang `ready` hoặc `refunded`, hệ thống tạo một
`UserNotification`. Một job có thể hoàn tất nhiều yêu cầu và phát thông báo
riêng cho từng tài khoản.

## Bảo mật trước khi mở giao diện

Mô hình dữ liệu và worker không tự nhận `accountId` do trình duyệt gửi lên.
Endpoint thương mại chỉ được mở sau khi có lớp xác thực server-side ánh xạ
phiên đăng nhập sang `UserAccount`. Trước khi người dùng xác nhận, API không
được tiết lộ snapshot đã có hay đang có người khác chờ cùng job.

Giá `credit_cost` phải do bảng giá phía server quyết định; không chấp nhận số
credit do trình duyệt gửi lên. Vì dự án chưa chốt nhà cung cấp đăng nhập và mức
giá, migration này chỉ đưa vào lõi tài khoản/ledger/worker, chưa công khai API
thương mại không có xác thực.

Luồng giao diện sau xác thực:

1. Chọn tỉnh, cơ quan, kỳ và đúng một TTHC; thay đổi bộ lọc không tạo job.
2. Hiển thị giá credit thống nhất, số dư khả dụng và nút **Lấy dữ liệu**.
3. Hộp xác nhận chỉ mô tả phạm vi và giá, không tiết lộ cache/queue.
4. Server giữ credit và trả trạng thái yêu cầu của chính tài khoản.
5. Badge thông báo dẫn thẳng tới kết quả khi `ready`; khi `refunded` phải nêu
   rõ toàn bộ credit đã được hoàn.
