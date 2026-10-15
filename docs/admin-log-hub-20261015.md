# Nhật ký hệ thống gọn — 15/10/2026 (chưa deploy)

## Phạm vi

- Một menu sidebar Nhật ký hệ thống, bốn tab: Tổng quan hôm nay, Lịch sử
  khai thác, Cảnh báo nguồn, Nhật ký quản trị.
- Hôm nay phân biệt ngày vận hành với ngày dữ liệu; tách lượt 05:00 và 06:00,
  102 khối và 3 gói toàn quốc. Không đọc được/chưa chạy không coi là thành công.
- Lịch sử ngày, lệnh hệ thống/người dùng, đợt cập nhật cũ, cảnh báo và thao tác
  quản trị phân trang 10 dòng. Chi tiết từng khối/nguyên văn TTHC/giá trị
  trước–sau mở trong dialog; giữ dữ liệu kiểm chứng cũ trong lịch sử.
- Bộ lọc chính dùng chiều rộng giới hạn, cao 36px; ngày và điều kiện phụ trong
  popover Bộ lọc đóng mặc định, có đếm điều kiện, Đặt lại, Escape/đóng bên ngoài.
- Tab dùng một thanh gạch nhấn, font và nút thống nhất trong phạm vi Nhật ký.
  Không ảnh hưởng stylesheet trang Tổng quan hay màn hình quản lý tài khoản.

## Sửa lỗi CSS

`/admin-logs.css` ban đầu bị middleware public-read-only trả 403 nên trình duyệt
chỉ dùng kiểu mặc định, khiến bộ lọc thành từng dòng dài. Đã thêm đúng đường dẫn
CSS này vào allowlist, không cho phép wildcard, file backup, preview hoặc .env.
Gói Netlify và kiểm thử allowlist bao gồm file CSS mới. Preview đang chạy phải
restart để middleware nhận thay đổi; sau đó tải lại trang để nhận JS/CSS mới.

## Đọc dữ liệu và hiệu năng

- API admin-only, đọc checkpoint bằng SQLite mode=ro, kiểm tra đường dẫn,
  giới hạn kích thước và cache theo mtime/size (256 bản tóm tắt).
- Lịch sử thông thường chỉ đọc 10 checkpoint/trang; lọc trạng thái sử dụng
  cache. Truy vấn lịch 06:00/cảnh báo theo lô, không truy vấn từng ngày.
- Chỉ Tổng quan hôm nay tự cập nhật 10 giây khi đang cào/đối chiếu và tab đang
  hiển thị. Lịch sử, cảnh báo, quản trị không có polling định kỳ.
- Nhật ký quản trị chỉ trả chi tiết allowlist, ẩn trường xác thực kể cả
  trong before/after. Không tìm kiếm raw JSON có thể chứa dữ liệu nhạy cảm.

## Không thay đổi

Không thay đổi schema, bộ cào, lịch 05:00/06:00, worker, queue, công thức,
phân quyền, Credit hoặc dữ liệu production. Bản sửa lựa chọn tài khoản cấp
Credit trước đó vẫn giữ nguyên trong working tree; không tự cấp Credit.

## Giới hạn dữ liệu cũ

Checkpoint cũ ghi trạng thái cuối theo ngày, không giữ đầy đủ từng lần chạy lại.
Giao diện không dựng thêm lịch sử lượt chạy hay thời điểm bắt đầu không có thật.
Trường Cập nhật lấy mtime checkpoint, không coi đó là ngày dữ liệu.

## Khi được duyệt triển khai

Cần restart backend để nhận các API chỉ đọc/allowlist CSS mới trước khi đưa
frontend mới lên. Không migrate database, không restart worker hoặc sửa lịch.
Preview `.tmp-admin-logs-preview.py` dùng SQLite mô phỏng riêng, chỉ bind
127.0.0.1:8840, chặn mọi POST và không thuộc gói public.

## Kiểm tra trực tiếp sau khi chủ máy restart preview

- CSS đã áp dụng; bộ lọc chính nằm cùng hàng tại viewport rộng 1239px.
  Chiều rộng trang 1239px, không tràn ngang; input/select cùng font 12px.
- Lọc ngày 14–15/10 cho 2 bản ghi, Đặt lại trở về 9 bản ghi mô phỏng.
- Dialog chi tiết: 105 khối, 10/trang; chuyển từ trang 1/11 sang 2/11 thành công.
- Nhật ký quản trị: lọc phân quyền cho 11 bản ghi, Đặt lại về 23 bản ghi,
  10 dòng/trang. Cảnh báo nguồn 23 bản ghi, 10/trang, 3 trang.
- Không có console error trong lượt kiểm tra. Chỉ thao tác lọc/xem/chuyển trang,
  không gửi thao tác cấp Credit, review cảnh báo hay chỉnh dữ liệu.
- 36 kiểm thử backend, 7 bộ kiểm thử frontend và kiểm tra gói public PASS.
  Ảnh xác nhận: `outputs/admin-log-refined-20261015.jpg` (không deploy ảnh).

## Diễn giải cảnh báo nguồn

- Danh sách cảnh báo bổ sung tên nhóm và tóm tắt chỉ tiêu/tham số liên quan.
- Dialog tách cột Nhóm chỉ tiêu, Chỉ tiêu/tham số thay đổi, Đang lưu, Nguồn mới;
  giữ mã nguồn trong phần mở thêm để đối chiếu kỹ thuật.
- Tên chỉ tiêu lấy từ profile nguồn trước/sau, kể cả chỉ tiêu thêm/bớt/đổi tên.
  Metadata tên được giữ theo thời điểm phát hiện; không thay bằng tên hôm nay
  khi mở cảnh báo lịch sử. Giá trị cũ/mới và fingerprint không đổi.
- Cảnh báo cũ được diễn giải trên GET từ bằng chứng/profile lưu sẵn (truy vấn
  theo lô và giới hạn), không cập nhật bản ghi hay gọi thêm Cổng DVCQG.
- Cảnh báo mẫu kỳ đã kết thúc gọi đúng là điểm nhóm/tổng điểm tỉnh, không gán
  thành điểm chỉ tiêu con. Trường mới chưa rõ tên ghi rõ chưa có diễn giải,
  không tự đoán. Không sửa cấu hình công thức quản trị đã lưu.
- 41 kiểm thử backend liên quan và 2 bộ frontend PASS sau bổ sung.
- Preview có ví dụ Mức độ hài lòng → Tỷ lệ hài lòng trong tiếp nhận, giải quyết
  TTHC → Điểm tối đa 6 → 8; tất cả là dữ liệu mô phỏng, không phải cảnh báo thật.

## Gộp thông báo theo đợt (15/10)

- Một thẻ thông báo cho một đợt logic: `daily:<ngày dữ liệu>` (cào 05:00),
  `monitor:<ngày kiểm tra>` (đối chiếu 06:00). Retry/resume thuộc cùng đợt;
  không dùng PID làm mã đợt, không gộp hai tác vụ chỉ vì cùng ngày.
- Dedupe cơ cấu trong một đợt vẫn gộp thay đổi giống nhau ở nhiều tỉnh;
  ghi số tỉnh/phạm vi trong chi tiết. Đợt sau có bản ghi riêng, không làm
  mất bằng chứng hoặc ghi đè trạng thái xử lý của đợt trước.
- Từng bản ghi cảnh báo vẫn là nội dung con riêng, giữ bằng chứng cũ/mới,
  xác nhận, ghi chú và quyền xử lý. Danh sách đợt và nội dung đều 10/trang.
- Bộ lọc chọn các đợt có nội dung phù hợp; chi tiết vẫn chứa toàn bộ nội dung
  đợt đó. Tổng số là số nội dung/thay đổi thực tế, không nhân theo occurrences.
- Đánh dấu cả đợt đã đọc bằng một POST có kiểm tra admin/CSRF và ghi audit;
  không có nút xử lý toàn bộ. Cần ghi nội dung xử lý riêng từng cảnh báo.
- Cảnh báo lịch sử thiếu mã đợt giữ riêng, ghi rõ chưa lưu mã đợt; không đoán
  theo thời gian updatedAt vì bản ghi cũ có thể gộp nhiều ngày.
- Không nâng schema, không đổi lịch cào, tốc độ, Credit hay công thức đã lưu.
  API gộp dùng GROUP BY/COUNT tại DB, chỉ tải 10 nội dung mỗi trang, không
  tải hết bằng chứng vào trình duyệt; không polling nền và không gọi nguồn.
- 45 kiểm thử backend + 2 bộ frontend PASS. Preview 23 nội dung mô phỏng
  gộp thành 3 đợt, không sửa dữ liệu production. Cần restart preview để xem.
