# Điều hướng từ điểm so sánh sang chi tiết — 13/10/2026

Trạng thái: đã thực hiện và kiểm thử tự động; chưa commit/push/deploy hay restart backend production.

## Phạm vi đã thực hiện

- So sánh theo thời gian: điểm tổng, điểm kỳ trước và sáu điểm nhóm là nút mở chi tiết đúng kỳ của chính ô được bấm. Áp dụng bảng mặc định và so sánh tùy chỉnh ngày/tháng/quý/năm.
- Preview Báo cáo lãnh đạo: điểm nhóm/điểm tổng mở Tổng quan → Chi tiết điểm số đúng cơ quan và kỳ; đóng dialog báo cáo. Không thay nội dung/numerical logic của báo cáo Excel hoặc bản in.
- So sánh ngày sử dụng đúng liên kết DailyObservation → snapshot + national summary đã lưu. Không thay bằng ngày mới nhất nếu thiếu dữ liệu. Khi rời chế độ này, khôi phục snapshot mới nhất và bỏ `report_date` khỏi URL.
- Export chi tiết khi đang xem ngày cũ dùng cùng ngày dữ liệu và có ngày trong thông tin kỳ báo cáo.
- Chặn response đến muộn sau khi người dùng rời chi tiết ngày; không ghi đè dữ liệu mới nhất.

## Bảo mật và tác động

- Không mở rộng quyền. Tài khoản cơ quan chỉ mở chi tiết cơ quan đã gán; các điểm tổng quan của cơ quan khác vẫn hiển thị số thường, không có link mở dữ liệu chi tiết.
- Điều hướng tỉnh khác trong báo cáo toàn quốc chỉ dành cho admin/quyền toàn quốc, với tỉnh có dữ liệu và phạm vi tất cả TTHC. Middleware backend vẫn xác thực tỉnh và lọc chi tiết theo cơ quan sau cache.
- Thêm tham số đọc `report_date` cho selection/group-export, chỉ hợp lệ với phạm vi tất cả TTHC; kiểm tra ngày thuộc kỳ và ngày hợp lệ. Không cho phối hợp với snapshot TTHC.
- Benchmark ngày chỉ chứa điểm, không có metrics/parameters của tỉnh khác. Không chuyển token đăng nhập vào URL.
- Chỉ GET dữ liệu đã lưu; không tạo job, không đổi Credit, schema, công thức, worker, lịch cào, motion, sidebar hoặc Trivia.
- Dùng cache sẵn có và index `ix_daily_lookup`; không bổ sung polling hoặc truy vấn nguồn DVCQG. Các kỳ đã đủ chi tiết trong cache frontend không cần tải lại.

## Kiểm chứng

- TypeScript compile: PASS.
- 503 backend tests thuộc cấu hình release: PASS (51,3 giây). Không gồm bộ thử nghiệm 2-job/watchdog đang được gác lại.
- 93 frontend test files: PASS; thêm chạy riêng actual-app UI harness ở chế độ tài khoản cơ quan và admin/toàn quốc: PASS.
- Các trường hợp: tháng/quý/năm; ngày chính xác; điểm 0/thiếu; nhóm/period/unit; đóng preview; chuyển tỉnh; quyền cơ quan; 404 không fallback; response ngày đến muộn không ghi đè; URL khôi phục; GET-only.
- 100 lượt đọc ngày đã cache trên SQLite cô lập: p95 10,35 ms, tối đa 2 SQL/lượt, không lỗi. Không phải đánh giá tải production.
- Gói frontend mới: PASS allowlist, không fixture/secrets/source map.
- `git diff --check`: PASS. Không chỉnh sửa database production.

## Bản thử nghiệm và hạn chế xác minh

Theo computer-use skill đã thử kiểm tra trực quan, nhưng CUA không khởi tạo được (`failed to write kernel assets`, Windows error 3). Mở tab preview bằng app trả về queued. Server fixture chạy nhưng kết nối localhost từ công cụ bị timeout; vì vậy không tuyên bố đã xác minh trực quan hoặc OAuth thật.

Server preview của phiên được dừng trước bàn giao để không chiếm cổng. Tại thư mục qd766, người dùng có thể chạy:

```powershell
.\.venv\Scripts\python.exe -X utf8 .tmp-score-drilldown-preview.py
```

Sau đó mở `http://127.0.0.1:8836/?period=month-2026-10`.

Preview dùng frontend thực tế với phản hồi GET từ fixture riêng, có nhãn điểm mô phỏng và từ chối POST; không đọc/ghi database production. Dừng bằng Ctrl+C ở terminal preview.

Backup trước sửa: `.tmp-score-drilldown-backup-20261013-103809`. Gói kiểm tra: `outputs/score-drilldown-package-20261013-111422609/netlify-public`.

Khi được phép triển khai, dùng allowlist thay đổi của tính năng này, không `git add -A`: app/time-custom-comparison/score-drilldown source và dist, bento.css, routes.py, daily_selection.py, tests/doc tương ứng. Không gộp module/test/prototype 2-job/watchdog chưa được duyệt deploy.
