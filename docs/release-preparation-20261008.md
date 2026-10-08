# Bản gộp chuẩn bị triển khai 08/10/2026

Trạng thái ban đầu: đã kiểm thử và backup trong lượt chuẩn bị. Sau khi chủ hệ thống đồng ý triển khai, migration và nội dung công thức đã được đưa vào PostgreSQL chính; backend đã restart, ready và runtime policy PASS. Frontend chờ phát hành qua Git/Netlify.

## Phạm vi được duyệt

1. Hỏi đáp: thu gọn/mở rộng, tự thu gọn ở sidebar chỉ có icon, thanh thu gọn dễ mở lại, icon căn giữa; tên HỎI ĐÁP. Bảng xếp hạng top 20 khi hết câu hỏi, tên hiển thị/tỉnh/chuỗi cao nhất/số câu trả lời đúng. Menu tài khoản đè lên hộp Hỏi đáp. Không sửa cách tính streak, điểm hay thời gian trả lời trong bản gộp này.
2. Tổng quan: bố cục tiêu đề, kỳ, thông tin dữ liệu và tab gọn hơn. So sánh thời gian chỉ hiện “Đây là dữ liệu tạm thời do chưa kết thúc kỳ báo cáo.” khi kỳ còn tạm thời.
3. Đổi Quản trị dùng thử thành Quản trị hệ thống. Thêm quản trị Công thức tính, editor và preview hai bên, highlight trường tương ứng, lưu phiên bản, API có kiểm tra admin/CSRF và chống ghi đè đồng thời.
4. Giữ nội dung công thức đã nhập. Các khu vực phụ đã yêu cầu bỏ không xuất hiện; không xóa dữ liệu gốc trong lịch sử. Công thức bổ sung nằm dưới công thức chính, hỗ trợ cộng/trừ/nhân/chia. Mục 5.1 về phân loại PAKN hiển thị để tham khảo, không chấm điểm.
5. Chi tiết Mức độ hài lòng: thứ tự theo yêu cầu. Chi tiết Số hóa hồ sơ: tên TTHC viết tắt, giải quyết viết đầy đủ, đổi thứ tự hai chỉ tiêu dữ liệu dân cư. Không sửa số liệu/công thức của các nhóm này.
6. DVC trực tuyến: rút gọn tên toàn trình, ẩn các dòng tham số nguồn; thông báo thiếu chi tiết cơ quan và nút Xem điểm tỉnh. Chỉ tham khảo chi tiết của tỉnh cho nhóm này; tổng điểm, mức tối đa, điểm chưa đạt của cơ quan không đổi.
7. Tiến độ: thứ tự đúng hạn/quá hạn/tổng tiếp nhận; ẩn thời gian giải quyết trung bình ở phạm vi Tất cả TTHC, giữ ở chi tiết TTHC.
8. Dialog tra cứu TTHC hiển thị tên cơ quan đang chọn thay vì luôn tên tỉnh. Không sửa yêu cầu thu thập hoặc chi phí.
9. Thanh toán: ba chỉ tiêu 2 + 2 + 6 điểm; hai tỷ lệ TTHC có ngưỡng 80%, tỷ lệ hồ sơ tuyến tính đến 100%. Tên tham số phản ánh đúng TTHC/hồ sơ. Điểm thành phần là đối chiếu, tổng điểm luôn lấy từ API. Thiếu dữ liệu/mẫu số 0 không tự tính thành 0 điểm.
10. Biểu Excel một nhóm/cả sáu nhóm và xuất chi tiết: dùng projection chung cho tên/thứ tự/thành phần; có điểm chưa đạt. DVC không xuất lại các tham số đã ẩn; khi Xem điểm tỉnh, biểu ghi rõ dữ liệu tham khảo tỉnh và vẫn giữ điểm nhóm của cơ quan. Giữ nguyên xuất tổng hợp và báo cáo lãnh đạo.

Commit a5d3a1b đã có từ đợt trước (so sánh cơ quan/time, ẩn Hỏi đáp mobile, lịch 05:00) không sửa lại lịch hoặc cào dữ liệu trong lượt này. Không đưa các tệp `.tmp-*`, dữ liệu cào thay thế, backups, cấu hình `.env*`, ảnh hoặc snapshot thử nghiệm lên frontend.

## Kiểm chứng

- 404 kiểm thử backend PASS: phân quyền cơ quan, projection, xác thực/CSRF, ví Credit, AI/queue, Trivia, cấu hình Công thức tính và các luồng khác.
- 62 tệp kiểm thử frontend PASS; kiểm thử gói Netlify riêng PASS: tổng 63 tệp. Các bài cần đường dẫn module được chạy với đường dẫn tương ứng; gói frontend kiểm tra ở thư mục mới, không dùng output cũ.
- TypeScript build/typecheck. Excel tạo trong bộ nhớ và đọc lại bằng thư viện Node/browser: kiểm tra số 0/ô thiếu, số nguyên, tỷ lệ, điểm, bộ lọc, freeze và tên/thứ tự. Không xác nhận mở thủ công bằng ứng dụng Excel desktop.
- Công thức thanh toán khớp ví dụ 7,20 và 7,29. Kiểm tra không ghi đè điểm nhóm, không mutate source entity.
- Cấu hình thử nghiệm giữ nguyên năm nhóm ngoài Thanh toán và các nội dung nghiệp vụ do quản trị nhập. Chuyển cấu hình thanh toán hai chỉ tiêu sang ba chỉ tiêu không ghi đè các đoạn văn đã nhập, không viết lại lịch sử cũ.
- Gói Netlify có module mới/CSS quản trị; không có fixture, secrets, source map, tài liệu hoặc backups.
- PUBLIC_CONFIG=PASS với real wallet/shared registration/Gemini; ANALYSIS_QUEUE=True. Đây là kiểm tra cấu hình/schema read-only, không phải thử đăng nhập Google hay chạy Gemini/thu thập thật.

## Backup

- PostgreSQL: `outputs/release-preparation-20261008/database-backups/qd766-20261008-215813.dump`, 44.820.990 bytes.
- SHA256: `734E35AF4EEAB3F801C0E3FA653FC0B4455835E9DFF0A613F0BAB41D49EB2A04`.
- pg_restore --list đọc được archive (281 mục). Chưa thử phục hồi database.
- Backup source/assets/tests/migration và snapshot: `outputs/release-preparation-20261008/application-20261008-220009/`.
- Gói validation cập nhật: `outputs/release-preparation-20261008/validation-20261008-220402/`.
- Snapshot công thức trong gói validation: SHA256 `100B729FFFCAC7065B7F1431961259089BF11DF15326A045109CB0F8328621A7`.
- Những file này chỉ nằm local; không đóng gói hoặc commit backups/snapshot chứa nội dung thử nghiệm.

## Bước còn lại trước phát hành

1. Xác nhận nội dung đã bấm Lưu ở preview là bản muốn nhập; lưu lại snapshot mới nếu chỉnh thêm. Không lấy dữ liệu nháp chưa lưu. Backup lại ngay trước khi ghi production nếu database đã thay đổi kể từ bản backup này.
2. Database chính đang ở `20261007_0023`, chưa có bảng công thức. Nâng migration `20261008_0024` sau backup; migration chỉ thêm bảng công thức, không xóa/sửa bảng dữ liệu hoặc Credit.
3. Nhập snapshot đã lưu qua API quản trị có xác thực/CSRF; hoặc công cụ import triển khai được chủ hệ thống cho phép rõ ràng, kiểm chứng backup/checksum, chỉ chấp nhận production còn bản gốc và một quản trị hoạt động duy nhất. Tạo revision mới có audit, không sửa bản gốc; đối chiếu toàn bộ nội dung sau nhập. Không tạo phiên đăng nhập giả hay mở endpoint bỏ xác thực.
4. Restart backend và xác nhận PUBLIC_BACKEND_READY/PUBLIC_RUNTIME_POLICY. Không thay Task Scheduler hoặc runtime flags.
5. Chuẩn bị commit theo allowlist source/assets/tests/migration/docs được duyệt, không git add toàn bộ worktree. Push/deploy frontend sau backend sẵn sàng.
6. Kiểm tra site chính: admin/cấp tỉnh/cơ quan, chi tiết và so sánh, xuất Excel, Hỏi đáp/sidebar/mobile, Công thức tính và quyền lưu. Nếu lỗi, dừng phát hành và khôi phục artifact/phiên bản cấu hình phù hợp; không tự rollback bằng xóa bảng hoặc ghi đè ví.

## Bảo mật và giới hạn

Không mở rộng quyền đọc cơ quan, Credit, quyền quản trị, thu thập hoặc điều khiển worker. Dữ liệu chi tiết tỉnh dùng allowlist số hữu hạn chỉ cho DVC trực tuyến; không sao chép metric/params nhóm khác. Workbook dùng dữ liệu đã được backend phân quyền, không lấy thêm dữ liệu khi bấm xuất. Tên/nội dung là plain text; file XLSX không tạo công thức từ tên người dùng/đơn vị, CSV có chống formula injection. Leaderboard trả tên hiển thị và tỉnh, không trả email/ID tài khoản. API công thức công khai chỉ đọc nội dung, không lộ lịch sử/người sửa.

Các kiểm thử tự động không chứng minh không còn mọi lỗi. Đăng nhập Google thật, thao tác trình duyệt production và Excel desktop vẫn cần smoke test sau phát hành. Không tối ưu PageSpeed, sửa SSL/Sophos, đổi prompt AI, sửa DVCTT hoặc thay thuật toán chấm điểm tổng ngoài yêu cầu.

## Thực hiện sau khi chủ hệ thống đồng ý nhập dữ liệu và deploy

- Backup mới trước migration: `outputs/release-preparation-20261008/database-backups/qd766-20261008-221135.dump`, 44.820.990 bytes; SHA256 `AC9B387C20D1D58DEB88E9535F398256EBEC2FBDFBC75234E7C49FFFB2D5E85F`. pg_restore --list PASS, không thực hiện restore.
- Xuất lại snapshot đã lưu từ preview 8820: checksum không đổi `100B729FFFCAC7065B7F1431961259089BF11DF15326A045109CB0F8328621A7`.
- Công cụ `tools/migrate_formula_configuration.py` đã nâng PostgreSQL lên 0024, nhập snapshot thành revision 2 và audit gắn với quản trị hoạt động duy nhất. So sánh cấu trúc/nội dung đọc lại với snapshot PASS; revision 1 giữ nguyên.
- Kiểm tra runtime cập nhật allowlist 0024 và yêu cầu đủ bảng công thức, Trivia, AI, ví của các migration trước. PUBLIC_CONFIG=PASS, queue bật, paid requests không pause. Không thay runtime flags.
- Restart qua Task Scheduler bị Access denied; chưa restart, chưa push/deploy frontend. Cần chủ hệ thống chạy restart và gửi READY/RUNTIME_POLICY trước khi phát hành.
- Chủ hệ thống đã chạy restart và gửi PUBLIC_BACKEND_READY=ok, PUBLIC_RUNTIME_POLICY=PASS. GET loopback health/ready xác nhận status=ok. Bộ backend chạy lại 406 tests PASS; typecheck, kiểm thử nội dung công thức, parity Excel và gói Netlify PASS trước commit.
