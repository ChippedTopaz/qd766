# Chuẩn bị deploy các thay đổi đã duyệt — 13/10/2026

Trạng thái: người dùng đã duyệt triển khai; bản gộp sẵn sàng chốt commit, chưa push hoặc deploy frontend. Base release: `85ec5bb04dacc9e2fcb208b4e7592f56c83ae766`.

Ngày 13/10/2026 lúc 23:36 (+07:00): kiểm tra lại 31 file khớp checksum `approved-final`; SHA256 database backup khớp bản ghi bên dưới; index trống và diff-check PASS. Lệnh restart public backend bị từ chối quyền CIM/Task Scheduler trước khi thao tác task. Đã yêu cầu người dùng chạy script hiện có và gửi PUBLIC_BACKEND_READY/PUBLIC_RUNTIME_POLICY; chưa push frontend trước khi gate này hoàn tất. Không restart worker hoặc chỉnh database.

## Phạm vi bản gộp

1. Bấm điểm tổng/điểm nhóm ở So sánh theo thời gian và preview Báo cáo lãnh đạo để mở Tổng quan → Chi tiết điểm số đúng cơ quan, kỳ/ngày. Thiếu dữ liệu báo thiếu, không tự cào/đổi ngày/trừ Credit. Export chi tiết ngày cũ giữ đúng ngày đã mở.
2. Biến động theo ngày chỉ dành cho Tất cả TTHC: chọn hai ngày cùng kỳ/cơ quan/nhóm; số lượng đạt, tổng số, tỷ lệ, điểm và chênh lệch. Mặc định ngày dữ liệu mới nhất so ngày liền trước; không dùng ngày khác thay ngày thiếu.
3. Bố cục bảng trái/chart phải thay bảng so sánh trong tab ngày; bấm tên chỉ tiêu đổi chart. Biểu đồ hiện đủ các ngày trong khoảng, gồm hai đầu mốc, thanh 6 px, chung thang đo; 06–12/10 có 7 thanh. Ngày thiếu là `—`, không coi là 0 hoặc tính tăng trưởng vượt khoảng trống.
4. Bỏ bảng mở rộng trùng lặp và caption dưới tên chỉ tiêu. N/A là một dấu gạch; tỷ lệ/điểm không thay đổi ghi Không đổi. Số lượng và Không đổi xám đậm, tỷ lệ đạt/điểm tăng xanh đậm, giảm đỏ đậm; quá hạn giữ chiều tốt/xấu. Cơ sở điểm tính đối chiếu giữ ở tooltip, không thay điểm nguồn.
5. DVC trực tuyến cấp tỉnh có tab ngày; cơ quan chỉ có điểm nhóm mà thiếu chi tiết không hiện tab. Không lấy dữ liệu tỉnh giả làm dữ liệu cơ quan.
6. Sửa Window.fetch Illegal invocation. Hủy response đến muộn, giữ snapshot/URL lựa chọn chính khi thao tác chart.
7. Chốt hiệu năng riêng tính năng mới: GET theo lô, không polling/per-day requests; cache backend riêng tối đa 64 mục, TTL 60 giây, dọn hết hạn, single-flight. Cache dashboard/catalog cũ giữ mặc định không đổi. Frontend tối đa 36 ngữ cảnh và tái sử dụng HTML để không tính lại chart mỗi khi Trivia/presence gây render.

Không gộp 2-job/2-thread/watchdog; thống kê truy cập, đổi Netlify/API routing; các prototype, script sửa tài khoản/job/source và dữ liệu thử. Các phần đã nằm trong 85ec5bb không triển khai lại như tính năng mới.

Không đổi schema 0027, công thức đã lưu, quyền tài khoản, Credit/giá 5/giới hạn hàng chờ 3, worker/lịch 05:00, nguồn/circuit, đăng nhập/đăng ký/duyệt, Trivia, Theo dõi/Thách đấu, Giả lập hoặc nội dung báo cáo ngoài các điểm được phép bấm.

## Kết quả kiểm tra cuối

- TypeScript PASS; 95 frontend test files PASS; thêm actual-app profile tỉnh cho biểu đồ ngày, agency và national cho drilldown PASS.
- 521 backend tests release PASS trong 47,235 giây, gồm cache capacity/expiry/concurrency và tách cache riêng. Các test 2-job/watchdog đang gác lại được loại khỏi suite release.
- Quyền: anonymous 401; agency chỉ chi tiết đơn vị đã gán; không truy cập tỉnh/đơn vị khác bằng đổi tham số, kể cả cache primed; scope/formality_id/POST bị chặn. Tỉnh/admin giữ phạm vi hiện có. Không raw payload/đường dẫn snapshot/chi tiết peer trong endpoint mới.
- Ngày/kỳ, số 0, dữ liệu thiếu, năm nhuận 366 ngày, duplicate observation lấy phiên mới nhất, async race/khôi phục snapshot, export/preview/motion/đăng ký/admin/Credit/Trivia/worker recovery hiện có đều nằm trong kiểm thử hồi quy.
- PostgreSQL production chạy transaction READ ONLY, statement timeout 15 giây: kiểm tra mẫu 06–12/10 đủ 7 ngày ở 6 nhóm, cấp tỉnh DVC trực tuyến cũng đủ 7 ngày; liên kết ngày → snapshot đúng. Không tạo job hoặc ghi Credit.
- Mẫu production: nhóm 7 ngày khoảng 3,9–20 KB JSON, 13 SQL (không N+1); sau warm-up thực thi helper khoảng 15,6–23,0 ms. Lượt đầu transparency 194,7 ms. Không phải load test hoặc dự báo công suất production.
- SQLite cache 100 reads: p95 6,36 ms, 4 SQL gồm auth; cold 47,65 ms/13 SQL. Range 7 ngày 15 SQL/5.647 byte, không writes.
- JS dựng HTML (không đo DOM/layout): 7/31/366 ngày p95 2,25/4,81/34,98 ms. HTML được memoize giữa các render không đổi dữ liệu/chỉ tiêu. Module mới gzip khoảng 6,7 KB; không thêm thư viện/CDN hoặc background polling.
- Cấu hình/schema launcher `--check`: PUBLIC_CONFIG PASS, real wallet/shared registration/Gemini/analysis queue giữ bật, requests_paused false. Current running public backend read-only probe: health ready ok, publicReadOnly/loginRequired/inviteRequired/paidRequestsEnabled/sharedRegistrationEnabled/geminiAnalysisEnabled true, collectionRequestsPaused false. Đây không phải xác minh Google OAuth thật hoặc nguồn DVCQG.
- Fresh package cuối `.tmp-release-prep-daily-20261013-231754003/final-package-check/netlify-public`: allowlist PASS, không fixtures/secrets/maps. `git diff --check` PASS; index không staged changes.

## Backup / dữ liệu giữ nguyên

Thư mục backup riêng: `.tmp-release-prep-daily-20261013-231754003`.

- Git bundle đầy đủ refs/history: verify PASS; patch local và bản sao 27 file trước chốt cache; `final-candidate` chứa bản cuối theo allowlist, được so checksum từng file.
- PostgreSQL `database/qd766-20261013-231830.dump`: 71.467.775 byte, SHA256 `C4147E01BEFBE9FB3C7CC7CB7ACD588022E632461F40B442EFCF45F063E32456`. pg_restore --list PASS (320 dòng); chưa diễn tập full restore.
- Formula fingerprint trước/sau transaction chỉ đọc giữ nguyên: head 1 row `5c7a98ef8809b60929e7a93e6338fe533cc7c5dd5c77c8dd057a0dad08197046`, revisions 3 rows `af609201cbb09ed5bb33c8170248542fa8e89f384a4dec80794fca93471a0319`. Fingerprint dùng serialization của probe hiện tại, không suy diễn so checksum bằng thuật toán khác trong các receipt trước.
- Dirty status của worker.py, collection.css, types.ts không có canonical diff; không stage hoặc sửa các file này. Không đưa local .env/backup/outputs/prototype lên Git hoặc package public.

## Allowlist commit sau khi được phép deploy

```text
src/qd766/backend/access_policy.py
src/qd766/backend/app.py
src/qd766/backend/cache.py
src/qd766/backend/daily_routes.py
src/qd766/backend/routes.py
src/qd766/backend/daily_indicators.py
src/qd766/backend/daily_selection.py
web/src/app.ts
web/src/time-custom-comparison.ts
web/src/score-drilldown.ts
web/src/daily-indicator-comparison.ts
web/bento.css
web/dist/app.js
web/dist/app.js.map
web/dist/time-custom-comparison.js
web/dist/time-custom-comparison.js.map
web/dist/score-drilldown.js
web/dist/score-drilldown.js.map
web/dist/daily-indicator-comparison.js
web/dist/daily-indicator-comparison.js.map
tests/test_cache.py
tests/test_daily_selection.py
tests/test_daily_indicators.py
web/tests/score-drilldown.test.mjs
web/tests/score-drilldown-ui.test.mjs
web/tests/daily-indicator-comparison.test.mjs
web/tests/daily-indicator-ui.test.mjs
web/tests/online-province-reference.test.mjs
docs/score-drilldown-20261013.md
docs/daily-indicator-comparison-20261013.md
docs/release-preparation-daily-20261013.md
```

Không `git add -A`.

## Deployment gates / rollback

Khi người dùng cho phép deploy: xác nhận backup vẫn phù hợp, chỉ restart **public backend** bằng script hiện có; kiểm tra PUBLIC_BACKEND_READY và PUBLIC_RUNTIME_POLICY, login guards/endpoint mới. Không cần migrate hoặc restart worker. Sau đó commit/push allowlist, kiểm tra Netlify và public assets/login/các tab. Không push frontend trước backend mới sẵn sàng.

Rollback bằng bản code/frontend tương thích trước release và restart backend có kiểm soát; không reset worktree hoặc restore toàn database đang có hoạt động người dùng. Giữ các dữ liệu phát sinh sau backup; schema không đổi.

Giới hạn: chưa có lần kiểm tra trực quan đa thiết bị bằng CUA do lỗi khởi tạo ở phiên trước; các preview được người dùng xem/duyệt và kiểm thử actual-app bằng harness, không gọi đó là browser screenshot QA. Không thử Google thật, không cào nguồn hoặc tải thử đồng thời production.
