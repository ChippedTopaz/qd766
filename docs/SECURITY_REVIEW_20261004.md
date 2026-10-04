# Rà soát an toàn và kiểm thử trước phát hành — 04/10/2026

## Phạm vi và môi trường

Rà soát mã backend API, xác thực/phân quyền, Credit, truy vấn động và giao diện
Tổng quan ba tab. Payload giả chỉ chạy qua TestClient trên SQLite trong bộ nhớ.
Kiểm thử cạnh tranh dùng database `qd766_credit_test`, schema riêng
`credit_run_20261004_042338_a3c8f1f3` (giữ lại để kiểm tra), không gọi DVCQG.
Không chạy payload tấn công trên production, không sửa dữ liệu production,
không restart public/worker, không push hoặc deploy Netlify trong đợt này.

## SQL injection

Không phát hiện đường khai thác SQL injection trong các truy vấn đã rà soát.
Các giá trị ID, mã TTHC, tài khoản, kỳ và điều kiện truy vấn dùng SQLAlchemy
expressions với tham số bind. UUID, loại kỳ và giới hạn phân trang có validation.
Các lệnh text trong backend là chuỗi cố định; sắp xếp API dùng cột ORM cố định,
không nhận tên cột/lệnh ORDER BY trực tiếp từ người dùng.

Các công cụ vận hành ngoài API có SQL động: audit dùng danh sách bảng cố định;
fingerprint lấy tên bảng từ inspector và quote identifier; schema mô phỏng
được sinh từ UUID/timestamp hoặc lựa chọn cố định. Không dùng input HTTP làm
tên schema/bảng. Không mở các công cụ này thành API.

Thêm test_security_boundaries.py: payload OR/UNION/DROP được lưu như dữ liệu
giả rồi tìm chính xác bằng mã; kết quả chỉ trả bản ghi phù hợp, payload nằm
trong parameters không nằm trong câu SQL, bảng và số bản ghi giữ nguyên.
AST guard chặn raw SQL không phải constant tại text/exec_driver_sql/literal_column,
và ghép chuỗi trực tiếp ở execute. Guard này không phải công cụ phân tích taint
đầy đủ; không thay cho rà soát luồng dữ liệu khi thêm API/truy vấn mới.

## Phân quyền và phòng vệ

Test sửa root tỉnh, tham số root lặp với thứ tự khác nhau, sửa cơ quan,
truy cập admin/operator bằng user, cookie giả, tài khoản khóa và quote giả:
không mở rộng quyền, không tạo job trái phép. Các test hiện hữu tiếp tục kiểm
tra entitlement của từng tài khoản và dữ liệu agency sau shared cache.

Sửa lỗi phòng vệ ở xác nhận phiên: compare_digest trên chuỗi non-ASCII có
thể gây TypeError. csrf_matches dùng bytes UTF-8, từ chối giá trị rỗng/lỗi
encoding; áp dụng thống nhất cho admin, tra cứu và đăng xuất. Token sai nhận
403 thay vì lỗi nội bộ. Không nới CSRF hoặc thay đổi cách tạo token.
Sửa hiện nằm trong mã nguồn, chưa restart dịch vụ đang chạy để áp dụng.

## Credit và giao diện

Toàn bộ 223 bài kiểm tra backend đạt sau sửa; gồm 9 bài trong nhóm bảo mật mới.

PostgreSQL concurrency checks đạt: shared job trả tiền riêng, xác nhận lặp
thu một lần, tối đa hai yêu cầu chờ, không chi vượt số dư, hoàn/retry đúng,
crash trước commit rollback, phục hồi lease, quy đổi/gia hạn/cấp tháng đồng
thời không trùng, không sửa số dư legacy. Không có thu thập thật trong test.

Frontend typecheck, overview tabs, change-tone, renderer summary-only, Bento,
Excel export và leadership workbook/browser roundtrip đạt. Kiểm thử renderer
xác nhận thẻ nhóm mở tab chi tiết, chuyển nhóm, tách insights khỏi overview,
giữ bảng theo thời gian và xuất chi tiết khi đủ dữ liệu. CSS mobile đã được
rà soát; chưa xác nhận bằng kiểm tra trực quan trên thiết bị điện thoại thật.

Đây là rà soát có phạm vi, không phải chứng nhận hệ thống an toàn tuyệt đối.
Còn cần duyệt giao diện điện thoại và smoke test luồng tra cứu thật sau đợt
deploy tiếp theo, cùng giám sát lỗi/quyền/Credit trong thời gian dùng thử.
