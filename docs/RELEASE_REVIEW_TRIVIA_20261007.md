# Rà soát trước deploy — 07/10/2026

## Kết luận

Bản mã đạt các kiểm thử dưới đây, có thể chuyển sang quy trình deploy thử nghiệm
có kiểm soát. Chưa deploy, chưa nâng schema hoặc restart backend thật trong đợt
rà soát này. Database thật đang ở `20261007_0022`, chưa có bảng Trivia (0/3).

## Phạm vi thay đổi đang chờ

- So sánh điểm chỉ tiêu chi tiết cho tài khoản cơ quan: chỉ trả điểm so sánh cùng
  cấp, không mở quyền chọn cơ quan khác hay trả tham số nghiệp vụ của đơn vị khác.
- Hỏi–đáp nhanh: câu ngẫu nhiên không lặp trong lượt; chấm backend; hạn 60 giây;
  hiển thị kết quả rồi tự chuyển sau 15 giây; làm lại bộ câu hỏi.
- Ngân hàng quản trị: tạo/công khai/thu hồi; tìm kiếm, phân trang, thống kê và
  danh sách người đúng; import Excel thành bản nháp; xóa có xác nhận và tính lại
  điểm/chuỗi/kỷ lục, không nối lại chuỗi đã bị ngắt.
- Bố trí khung sidebar và ba bảng Trivia ở migration 0023.
- Không đổi Credit, prompt AI, lịch cào hoặc quyền gán tỉnh/cơ quan.

## Bằng chứng kiểm tra

- TypeScript biên dịch thành công; 48 bộ kiểm thử frontend PASS.
- `unittest discover`: 373 kiểm thử backend PASS (27,385 giây).
- Đóng gói trong thư mục kiểm tra mới: NETLIFY_PACKAGE_OK / NETLIFY_TEST_OK;
  không đưa fixture, file cấu hình bí mật, preview HTML hay source map vào gói.
- `git diff --check` đạt; Alembic có một head `20261007_0023`.
- Migration thử trên SQLite khớp models, không thay đổi tài khoản; script nâng
  thật yêu cầu backup mới có checksum, chỉ cho schema 0022/0023.
- Kiểm tra backend thật chỉ đọc PASS: đăng nhập, quyền admin, ví thật,
  shared registration, Gemini và analysis queue; không xác nhận OAuth/cào thật.
- Giao diện trên phiên SQLite độc lập 8813: gửi đúng +1; tự chuyển câu sau 15
  giây và giữ điểm 1; danh mục ngân hàng tải được; không có console error ở
  bước dashboard được kiểm tra. Phiên 8812 cũ đã hết hạn đăng nhập mô phỏng;
  không dùng lỗi phiên này để kết luận backend chính thức có lỗi.
- Kiểm thử bao gồm CSRF/phân quyền, không lộ đáp án trước chấm, chống gửi lại,
  hết hạn, tab ẩn, lỗi mạng, import độc hại và xóa/tính lại lịch sử.

## Điều kiện vận hành còn phải thực hiện

1. Backup PostgreSQL mới và kiểm tra checksum.
2. Chạy `tools/migrate_trivia.py --confirm --backup "BACKUP.dump"` theo hướng dẫn
   trong TRIVIA.md; xác nhận TRIVIA_SCHEMA_READY.
3. Kiểm tra cấu hình và restart backend bằng script đã duyệt, sau đó deploy
   frontend từ danh sách file thay đổi có chủ đích. Không đưa file .tmp, outputs
   hoặc HTML thử nghiệm vào commit phát hành.
4. Smoke test tài khoản admin/cơ quan trên thật, tạo câu nháp rồi công khai có
   chủ đích; không tự seed câu mẫu. Kiểm tra Credit/quyền/so sánh cũ vẫn giữ nguyên.

Chưa chạy stress test hoặc kiểm thử khóa đồng thời trên PostgreSQL thật; các
kiểm thử hành vi backend dùng SQLite. Không cam kết hiệu năng tải lớn chỉ từ
kết quả này. Khi deploy nên theo dõi độ trễ API và khóa DB, nhất là lúc xóa câu
có nhiều lịch sử (giao dịch xóa tạm khóa thao tác Trivia, không khóa dashboard).
