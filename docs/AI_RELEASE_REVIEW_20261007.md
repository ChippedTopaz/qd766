# Rà soát bản phân tích theo nhóm — 07/10/2026

## Kết luận

Mã nguồn đạt kiểm thử tự động và đóng gói, có thể chuẩn bị phát hành thử nghiệm có kiểm soát. **Chưa đủ điều kiện chỉ push frontend và coi như hoàn tất deploy**: database office đọc qua `.env` đang ở `20261007_0020`, chưa có bảng nhóm (0021) và công tắc (0022). Kiểm tra này chỉ đọc, không thay DB.

Trong phiên rà soát trước chưa chạy migration, restart, Gemini thật hoặc deploy. Xem cập nhật triển khai dưới đây; ghi nhận ban đầu không phải trạng thái sau triển khai.

## Triển khai sau khi người dùng đồng ý

- Backup mới: `F:\QD766\backups\qd766-20261007-132350.dump`, 34.135.886 bytes, SHA256 `E0DD99389B9B66A13B7A2E853F38A7E4F578D55FA2FB3A56525B37E280E29A69`.
- Script có guard đã nâng PostgreSQL office đúng 0020 → 0021 → 0022. Không thay ví, prompt, dữ liệu cào hoặc task.
- Cập nhật allowlist kiểm tra schema ví tới đúng 0021/0022 đã duyệt; vẫn từ chối phiên bản chưa duyệt và bảng thiếu. Kiểm thử giữ nguyên các kiểm tra bảng ví/nghiệp vụ cũ.
- `start_public_backend.py --real-wallet --shared-registration --gemini-analysis --check` PASS, queue True, requests paused False; không khởi động server.
- Fetch origin/main thành công: còn hai commit đã duyệt chưa push (7b2f223, 69459da) và các thay đổi mới. Không đưa helper/ảnh/preview không liên quan vào commit.
- Task Scheduler từ chối quyền trong phiên này; người vận hành đã chạy restart script và gửi READY/Runtime PASS. Endpoint availability mới trả 401 khi chưa đăng nhập, health ready OK: backend mới có route và giữ bảo vệ đăng nhập.
- Đã tắt công tắc mới (revision 1) bằng thao tác rollout đã duyệt, chỉ khi công tắc chưa từng được cấu hình; xác minh actor là admin active/admitted, dùng admission lock và ghi audit. Không thay prompt/ví. Có thể bật lại từ giao diện sau khi cập nhật prompt.

## Bằng chứng kiểm thử

- Backend: 329 test thành công. Bao gồm auth/CSRF, tắt trước giữ Credit, hàng chờ hoàn đúng một lần không gọi Gemini, lượt running hoàn tất, prompt độc lập công tắc, thiếu schema chặn an toàn; migration 0022 diễn tập SQLite.
- Frontend: 42 file test thành công (năm bài cần truyền đường dẫn module đã chạy đúng tham số). TypeScript compile thành công.
- Netlify: build/allowlist kiểm tra trong thư mục mới, không fixtures, secrets, source maps hoặc trang preview. Không ghi đè gói phát hành cũ.
- `git diff --check` không lỗi; warnings LF/CRLF không phải lỗi nội dung.
- Trình duyệt localhost: nút bật/tắt hoạt động trong mock; thông báo người dùng khi tắt đúng yêu cầu, không mở xác nhận trả Credit.
- Gemini thật, đăng nhập Google thật, cạnh tranh khóa PostgreSQL của công tắc mới và smoke test sau deploy chưa được xác minh trong phiên này. Kiểm thử mock không thay thế kiểm tra thật này.
- Đọc Task Scheduler qua `check_release_tasks.ps1` bị Access denied trong phiên này. Cần người vận hành chạy lại lệnh chỉ đọc để đối chiếu flags task trước khi restart; không suy đoán từ bản ghi cũ.

## Phạm vi cần đưa vào commit

- Công thức: tài liệu cấu trúc `formula-document.ts`, renderer `formula-reference.ts`, CSS và modules build tương ứng. Giữ tên/nghiệp vụ/lưu ý/nguồn theo tài liệu; điểm tối đa đã xác định không suy đoán lại.
- Phân tích: cấu hình riêng sáu nhóm và lịch sử snapshot; chọn nhóm 5 Credit/nhóm; bằng chứng tối đa ba kỳ trước và đồng cấp ±20% số hồ sơ; giao diện vấn đề/hành động chia theo nhóm, loại tiêu đề mẫu lặp.
- Công tắc: model, migration 0022, `analysis_feature.py`, API quản trị/availability, kiểm tra admission/worker, UI và startup schema guard.
- Các migration/tools/tests/docs mới liên quan phải được commit có chọn lọc cùng code. Không `git add .`: loại `.tmp-*`, ảnh QA, HTML xem trước/HTML xuất độc lập và các helper điều tra không liên quan khỏi commit phát hành. Trang preview được để local cho người dùng; không nằm trong gói Netlify.
- Không đổi lịch cào 04:00, dữ liệu/DB thật, phân quyền, sidebar, menu so sánh, quản lý tài khoản hoặc các nội dung ngoài phạm vi. Runtime flags hiện hành phải được giữ khi restart.

## Thứ tự phát hành

1. Sao lưu PostgreSQL mới bằng `tools/backup_postgresql.ps1`, kiểm tra dump và checksum. Backup ngày trước không thay thế backup ngay trước migration.
2. Từ schema 0020 hiện tại, chạy `tools/migrate_analysis_feature_control.py --confirm --backup "DUONG_DAN_DUMP_MOI"`: chỉ nâng 0021/0022, không dùng upgrade head. Script không restart hoặc thay prompt/ví. Nếu DB đã thay đổi, kiểm tra lại phiên bản trước khi chạy.
3. Kiểm tra cấu hình backend bằng chế độ `--check` với đúng flags task hiện hành; không tự bỏ cờ ví thật, shared registration, Gemini, queue hoặc pause. Schema công tắc thiếu phải báo BLOCKED trước khi restart.
4. Restart backend qua script hiện có. Tắt Phân tích điểm số trong quản trị; nhập/lưu prompt từng nhóm vào DB thật. Preview chỉ mock, không dùng để nhập prompt thật.
5. Commit/push chọn lọc, kiểm tra Netlify build thành công và phiên bản assets mới. Bản frontend mới yêu cầu backend mới; không đảo thứ tự.
6. Smoke test tài khoản admin và tài khoản cơ quan: tắt → thông báo đúng, không hold mới; bật → một lượt có xác nhận 5 Credit; đọc kết quả, billing, configVersion; người dùng thường không sửa cấu hình. Nếu chưa ổn, tắt lại bằng công tắc, không xóa ví/job hoặc downgrade bảng lịch sử.

Lượt running hoàn tất, lượt queued hoàn qua worker; khi worker dừng/runtime pause, không hứa hoàn ngay. Nút bật trong DB không tự bật Gemini runtime. Kiểm tra tắt không cần gọi provider; lượt thật có Credit chỉ chạy khi người dùng xác nhận.
