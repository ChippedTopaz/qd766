# Sửa lựa chọn tài khoản cấp Credit — 14/10/2026

## Nguyên nhân

Danh sách cấp Credit trước đây dùng `GET admin/accounts` (mảng tối đa 500
tài khoản mới nhất). Tài khoản cũ ngoài danh sách bị báo nhầm là chưa hoạt động
hoặc chưa duyệt khi mở nút Thêm Credit từ Quản lý tài khoản.

## Bản sửa

- Danh sách cấp Credit dùng phân trang có sẵn, 10 tài khoản/trang; tìm họ tên,
  email trên toàn database, chỉ liệt kê tài khoản hoạt động và đã duyệt.
- Thêm bộ lọc `accountId` UUID vào API danh sách quản trị để nút Thêm Credit
  tải chính xác tài khoản được chọn, bất kể vị trí trong danh sách.
- Phân biệt không tìm thấy tài khoản với tài khoản thực sự bị khóa/chưa duyệt.
- Chặn cấp Credit trong khi tìm kiếm/tải danh sách, bỏ phản hồi cũ, không giữ
  tài khoản khác khi mở tài khoản đích thất bại. Sau cấp giữ đúng tài khoản đích.
- Giữ nguồn Credit, kiểm tra quyền quản trị, CSRF, idempotency và logic ví cũ.
  Không sửa schema, ví, số dư, subscription hoặc dữ liệu production.

## Kiểm thử

- TypeScript compile.
- Frontend: shortcut, chống gửi hai lần, phân trang với 510 tài khoản,
  tìm email ngoài giới hạn cũ, trạng thái thật, phản hồi chậm, không phát sinh cấp
  Credit khi mở/tìm kiếm, tương thích Quản lý tài khoản.
- Backend: `test_admin_accounts_pagination` và `test_trial_admin` (24 tests),
  bao gồm kiểm tra tài khoản cũ, khóa/chưa duyệt, UUID, quyền quản trị,
  giới hạn số truy vấn và không ghi database khi đọc.

## Triển khai

Bản sửa chưa được deploy. Khi được duyệt deploy, restart backend trước khi
đưa frontend mới lên (frontend cần bộ lọc `accountId`). Không cần migrate
database hoặc restart worker. Không tự cấp Credit để kiểm tra production.
