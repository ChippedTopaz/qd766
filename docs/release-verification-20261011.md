# Rà soát bản chưa deploy — 11/10/2026

## Kết quả

- TypeScript: PASS; diff whitespace: PASS.
- Backend sau bổ sung phân trang: 482 tests PASS (43,4 giây).
- Frontend sau bổ sung phân trang: 82 file kiểm thử PASS. Kiểm thử gói Netlify PASS ở lượt trước phân trang; cần đóng gói lại trước deploy.
- Preview Thách đấu: kiểm tra send/accept với SQLite riêng PASS.
- Migration 0026 và 0027: chạy trong SQLite thử nghiệm PASS; xuất DDL PostgreSQL PASS. Chưa chạy migration trên PostgreSQL production.
- Không deploy, restart dịch vụ production, thay đổi Credit, công thức đã lưu hoặc dữ liệu thật trong lần rà soát này.

## Sửa điểm chưa đạt: lưu Theo dõi

Bản cũ dùng localStorage theo khóa tài khoản/tỉnh, vẫn phụ thuộc máy. Đã chuyển sang bảng agency_watch_preferences với khóa chính (account_id, root_department_id), tối đa 5 UUID cơ quan. Backend lấy account_id từ session, không nhận chủ sở hữu từ client.

Kiểm thử hai phiên đăng nhập khác nhau của cùng tài khoản đọc đúng cùng danh sách; tài khoản khác không đọc được danh sách đó. Chặn chưa đăng nhập/chưa duyệt, sai tỉnh, sai CSRF, hơn 5 cơ quan, trùng cơ quan, chọn cơ quan mình, gửi thêm accountId. Lưu/đọc không động đến ví hoặc điểm số.

Frontend chỉ GET khi vào tab lần đầu trong phiên trang; POST khi bấm Lưu. Lọc, tìm kiếm và sắp xếp không phát sinh ghi database. Sau khi đổi danh sách trên thiết bị khác, tải lại trang để đọc danh sách mới. Bản xem thử không đăng nhập chỉ giữ draft trong bộ nhớ của phiên, không giả vờ đã lưu database.

## Tải và hiệu năng

Số đo local, không phải cam kết dung lượng production:

| Kiểm tra | Dữ liệu | p95 | SQL tối đa |
|---|---|---:|---:|
| Đọc Theo dõi | 100 request tuần tự | 4,00 ms | 4 |
| Theo dõi đồng thời | 8 phiên, 160 request; không lỗi hoặc lẫn tài khoản | 24,68 ms | — |
| Notification Thách đấu | 1.000 kèo mô phỏng; trả tối đa 20 | 7,24 ms | 7 |
| BXH Thách đấu | 1.000 kèo; 10 dòng/trang, top 20 giữ nguyên | 8,97 ms | 8 |
| Lịch sử kèo | 10 dòng/trang | 7,17 ms | 7 |
| Kèo đã kết thúc, trang 50 | 500 kèo kết thúc; 10 dòng/trang | 7,47 ms | 7 |
| Danh mục đối thủ | 7 cơ quan có tài khoản | 4,94 ms | 5 |

Đã bỏ truy vấn theo từng dòng cho các danh sách Thách đấu, lọc/đếm notification trong SQL, tổng hợp BXH trong SQL và bổ sung index recipient/state/year cùng root/state/created_at. API phân trang lịch sử, đang diễn ra và đã kết thúc: 10 dòng/trang, mới nhất trước (created_at rồi id), tổng số và số trang tính tại backend. Payload local khoảng 4,4–4,8 KB/trang thay vì khoảng 92 KB cho 200 dòng. Hai tab lưu số trang độc lập trong dialog; chặn phản hồi cũ ghi đè tab mới. Top 20 người chơi và notification giữ nguyên. Kiểm thử đủ các trang, không trùng dòng, trạng thái, quyền theo tài khoản/tỉnh, trang cuối, trang sai, trang rỗng và không đổi Credit.

Notification kiểm tra mỗi 30 giây ở tab đang hiển thị; tab ẩn không fetch. 100 tab hiển thị tạo khoảng 3,3 request/giây riêng notification; 1.000 tab khoảng 33,3 request/giây. Đây là mô hình tần suất, không phải kết quả thử tải 1.000 người.

Giả lập tính trên máy người dùng, chỉ GET Công thức tính khi mở (cache ngắn), không POST, không tạo job, không trừ Credit. Theo dõi lọc/sort tối đa 6 hàng (cơ quan mình + 5 cơ quan). So sánh tùy chỉnh chỉ đọc các kỳ cần dùng; không khai thác tự động.

JS: app.js gzip tăng từ 38.675 lên 44.617 byte so với HEAD. Bốn module mới agency-watch/challenges/score-simulator/time-custom-comparison tổng khoảng 11 KB gzip. Tổng phần tăng này khoảng 16,5 KiB gzip; không thêm thư viện nặng. Đây là dung lượng nén đo local, không phải đo LCP/TTFB/INP trong trình duyệt production.

Gói Netlify được xây dựng trong thư mục thử nghiệm riêng: kiểm tra allowlist PASS; không chứa fixtures, secrets, source maps hoặc file preview. Không ghi đè thư mục netlify-public hiện có.

## Điều kiện trước deploy

1. Backup database production và xác nhận schema hiện tại.
2. Nâng 0026 + 0027 trên PostgreSQL, kiểm tra bảng/index/quyền truy cập; restart backend và worker trước frontend.
3. Rà lại diff được duyệt, không đưa bản chọn ngày TTHC đã gác, preview và dữ liệu mô phỏng vào release.
4. Sau cập nhật, smoke-test thật: cùng tài khoản trên hai trình duyệt, tài khoản khác, gửi/chấp nhận kèo, notification, Theo dõi, Giả lập, tra cứu TTHC/Excel.
5. Quan sát latency, CPU/RAM, kết nối PostgreSQL và lỗi API ở tải thật. Chưa đo tải production hoặc Core Web Vitals mới trong lần này; chưa thử các ghi đồng thời trên PostgreSQL thực.

Lưu ý kiểm thử đồng thời dùng SQLite file với connection pool riêng; fixture in-memory một connection chỉ phù hợp kiểm thử tuần tự. Các warning thư viện TestClient/ResourceWarning và lỗi Gemini timeout/503 xuất hiện trong các ca mô phỏng của bộ test; kết quả cuối cùng vẫn PASS.
