# Thông báo dịch vụ cho người dùng · 15/10/2026

- Thay màn hình lỗi khởi động trang chính/quản trị bằng component chung:
  nền sáng tím–xanh, thẻ nội dung, logo có sẵn, SVG minh họa nội tuyến,
  hướng dẫn bằng tiếng Việt và nút Thử lại/Về trang chủ/Đăng nhập lại.
- Sáu mẫu: dịch vụ gián đoạn, thiết bị offline, phản hồi chậm, hết phiên,
  thiếu quyền và nội dung chưa sẵn sàng. Chỉ gọi là offline khi trình duyệt
  báo `navigator.onLine === false`; không quy kết mọi lỗi là mất Internet.
- Không hiển thị backend HTTPS/máy cơ quan, JSON parse, HTML gateway,
  Failed to fetch, SQL/stack trace. Lỗi 5xx/HTML không bị lộ nguyên văn.
- Giữ thông báo nghiệp vụ có thể hành động: Credit, hồ sơ/nhập liệu,
  link hết hạn. Không tự tuyên bố đã/không thu Credit khi chưa có xác nhận.
- Chuẩn hóa lỗi tải ở đăng ký, quản trị, lịch sử/tra cứu, theo dõi cơ quan,
  biến động ngày, Hỏi đáp/BXH, Thách đấu và phân tích. Không đổi timer,
  hàng chờ, timeout, idempotency, request payload, tính điểm hoặc ví.
- Nút Thử lại chỉ reload theo thao tác người dùng, một lần mỗi lần bấm;
  không replay POST, không tự khai thác lại hoặc gửi phân tích/đăng ký.
- Giữ guard publicReadOnly; production lỗi vẫn không dùng dữ liệu mẫu.
  Không thêm thư viện/font/ảnh từ bên ngoài, không thêm polling hay asset
  CSS cần whitelist. Module dùng styles/SVG cố định, như login-view hiện có.
- TypeScript compile và 18 bộ kiểm thử frontend PASS: các biến thể/lỗi
  mạng/HTTP/JSON, escape, thông báo nghiệp vụ, manual retry, cùng hồi quy
  đăng ký/Credit, collection, daily indicators, theo dõi, Trivia/Thách đấu.
- Điều chỉnh kiểm thử shared-registration cũ để phản ánh yêu cầu đã duyệt
  bỏ tạo link mời; vẫn kiểm tra chấp nhận link cũ và duyệt hồ sơ.
- `web/service-feedback-preview.html` là PoC thuần mô phỏng dùng cùng
  renderer, không gửi API hay ngắt mạng. Không nằm trong gói public.
  Preview chính 8840 cần người dùng restart để có route xem trang mẫu này.
- Thử máy chủ tĩnh 8841 trong phiên agent không truy cập được từ browser;
  đã dừng session thử đó. Không restart/push/deploy production.
- Sau khi người dùng restart preview 8840, kiểm tra trực tiếp đủ 6 mẫu;
  nút Thử lại chuyển sang disabled/Đang tải lại và hiện xác nhận mô phỏng,
  không gửi API. Mẫu hết phiên hiện Đăng nhập lại, không có nút Thử lại.
- Bố cục desktop và điện thoại 390×844 không tràn ngang; viewport đã reset.
  Không ghi nhận console error trong lượt kiểm tra. Đây là kiểm thử renderer
  dùng chung trong PoC, không phải mô phỏng sự cố thực trên production.
- Ảnh `outputs/service-feedback-desktop-20261015.jpg` và
  `outputs/service-feedback-mobile-20261015.jpg`. Tab xem trước được giữ lại.

## Bổ sung: phiên làm việc

- Rà soát xác nhận phiên ứng dụng có hạn cố định 8 giờ (`SESSION_SECONDS`),
  cookie và database cùng thời hạn, hoạt động không tự kéo dài phiên.
  Đăng xuất, đổi quyền/phạm vi hoặc vô hiệu hóa tài khoản có thể thu hồi
  phiên; đăng nhập lại ở tab khác cũng thay session/CSRF của trình duyệt.
- Chưa có thời điểm sự cố/log tương ứng nên không quy kết mọi lần người
  dùng bị yêu cầu đăng nhập lại đều do hết 8 giờ. Session nằm trong database,
  không phải bộ nhớ tiến trình; restart backend đơn thuần không xóa session.
- Thông báo 401: “Phiên làm việc đã kết thúc” / “Vui lòng đăng nhập lại
  để tiếp tục sử dụng hệ thống.” Không khẳng định nguyên nhân cụ thể.
- Với đúng lỗi CSRF 403 “Xác nhận phiên không hợp lệ.”, hướng dẫn tải lại
  trang để đồng bộ phiên, không gọi là hết hạn hoặc thiếu quyền.
- Sửa hai chỗ gán mọi HTTP lỗi thành hết phiên: bước kiểm tra trước gia hạn
  Credit và nút kiểm tra trạng thái đăng ký. HTTP 5xx được báo gián đoạn dịch
  vụ; thông báo nghiệp vụ/thiếu quyền vẫn giữ riêng. Lỗi 5xx khi tải form
  đăng ký không còn bị nuốt rồi đưa về màn hình đăng nhập.
- Không đổi thời hạn 8 giờ, cookie, CSRF, thu hồi phiên, Credit hoặc cơ chế
  đăng nhập. Không tự refresh token, retry hay phát lại thao tác ghi.
- Kiểm thử lifetime dùng đồng hồ/DB giả lập, không thay đổi dữ liệu thật;
  kiểm thử UI phân biệt 401, 403 CSRF, 403 nghiệp vụ và 5xx.
