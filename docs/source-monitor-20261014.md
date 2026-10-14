# Giám sát thay đổi nguồn QĐ766 — 14/10/2026

## Phạm vi được duyệt

- Lượt cào 05:00 giữ nguyên 102 khối chi tiết, 3 gói tổng hợp, 3 luồng HTTP trong cùng job, lịch và quyền hiện có. Sau khi nhận gói tin, đối chiếu cơ cấu khai báo: mã/tên chỉ tiêu, điểm tối đa, ngưỡng/công thức/phiên bản nếu nguồn có trả về. Không gọi thêm nguồn để kiểm tra cơ cấu.
- Lượt riêng 06:00 hằng ngày, giờ Việt Nam: một gói tổng hợp điểm **34 tỉnh** cho mỗi kỳ tháng đã kết thúc và đã có dữ liệu hoàn chỉnh trong database. Không kiểm tra một tháng một lần. Không ghi mẫu vào bảng dữ liệu đang công bố.
- Dùng cơ cấu thay đổi để lập phạm vi tham khảo cần cào lại. Cào lại toàn bộ, lựa chọn ngày chuyển cơ cấu và loại lịch sử ngày cũ khỏi so sánh vẫn là thao tác cần duyệt riêng. Đánh dấu đã xử lý cảnh báo không thực hiện các thao tác này.

## Vận hành

`QD766 Source Monitor` là task độc lập 06:00, không sửa task cào 05:00 hay worker. Installer kiểm tra action/principal của task cào, backup XML, không âm thầm chuyển từ đăng nhập bằng mật khẩu sang chế độ chỉ chạy khi đăng nhập Windows. Nếu principal cần mật khẩu, cung cấp Credential tại máy, không đưa vào chat/log.

- Chưa tới 06:00: runner từ chối gửi yêu cầu.
- Checkpoint 05:00 phải COMPLETE, `completed = expected = 102`, đúng ngày báo cáo liền trước theo giờ Việt Nam.
- Nếu còn RUNNING, chờ mỗi 30 giây, tối đa tới 09:00. Nếu thiếu/FAILED/INCOMPLETE/HALTED/không đọc được hoặc quá thời hạn, lưu **Chưa kiểm tra** và cảnh báo, không coi là dữ liệu không đổi.
- Kiểm tra tuần tự, 1 luồng, giãn cách 1 giây; nhả shared lease sau mỗi tháng, nghỉ 2 giây để worker có thể tiếp tục. Không lấy lease đang còn hiệu lực của worker. Nếu bận lâu hơn 5 phút, lưu chưa kiểm tra. Không tạo paid request hay thu Credit.
- Không tự bỏ dừng an toàn. HTTP bị từ chối/429/SafetyStop khi đang giữ lease sẽ mở circuit theo cơ chế hiện hành và lưu cảnh báo; không retry vô hạn.
- PostgreSQL advisory lock ngăn chạy trùng CLI/task; task `IgnoreNew`. Hoàn tất một ngày thì chạy lại ngày đó không gọi nguồn nữa. Lượt chưa hoàn tất chỉ tiếp tục các kỳ còn thiếu.
- Mỗi lượt lấy mẫu giới hạn 20 phút/120 kỳ; vượt giới hạn được ghi chưa hoàn tất, không báo thành công. Hiện có 9 kỳ tháng, tương ứng **9 request nguồn/ngày**, không đi qua Netlify. Giới hạn 120 kỳ cần xem lại nếu lịch sử vượt 10 năm.

## Lưu trữ và giới hạn kết luận

Schema additive `20261014_0028`:

- `source_monitor_baselines`: dấu vết cơ cấu mới nhất theo tỉnh/loại kỳ/nhóm; lần đầu sử dụng raw capture cũ có SHA-256 hợp lệ nếu còn lưu. Không đủ bản cũ thì khởi tạo dấu vết, không bịa ra thay đổi.
- `source_monitor_samples`: bản nháp mới nhất của từng kỳ tháng, liên kết baseline công bố. Tách khỏi `national_summary_snapshots`, `snapshots`, `daily_observations`, không trở thành dữ liệu mới nhất của dashboard.
- `source_monitor_alerts`: cảnh báo chống trùng, phạm vi, old/new, trạng thái đọc/xử lý và người xử lý. Cùng sai lệch được xác nhận lại ở ngày Việt Nam khác thì đánh dấu đã thấy lại; điều này không chứng minh nguyên nhân là công thức mới. Cơ cấu chung xác nhận ở nhiều tỉnh được gom theo cùng dấu vết thay đổi.
- `source_monitor_runs`: tiến độ/kết quả từng ngày. File bằng chứng của mẫu có sai lệch lưu riêng `data/source-monitor/<ngày>/`, ngoài thư mục web. Raw capture 05:00 vẫn được giữ.

Số hồ sơ, tỷ lệ, điểm đạt, thứ tự dòng và tên đơn vị không phải cơ cấu. Thay đổi danh sách đơn vị không tự được xem là xoá chỉ tiêu. Giá trị 0 và null/thiếu không đồng nhất; 20 và 20.0 đồng nhất. Sai khác điểm nguồn được so sánh theo đúng độ chính xác trả về, không tự làm tròn để che sai lệch.

Lượt 06:00 chỉ lấy **điểm tỉnh/tổng và sáu điểm nhóm**. Nó không bảo đảm phát hiện thay đổi chỉ ở số lượng thành phần hoặc chỉ ở một xã nhưng điểm tỉnh giữ nguyên. Công thức thực thi không xuất hiện trong gói tin không thể được khẳng định đã đổi từ dấu vết schema; cảnh báo điểm chỉ là căn cứ yêu cầu kiểm tra tiếp.

## Giao diện và bảo mật

Quản trị hệ thống → **Cảnh báo nguồn dữ liệu**: badge chưa đọc, bộ lọc, 20 cảnh báo/trang, 7 ngày kiểm tra gần nhất, dialog old/new và phạm vi cần kiểm tra. Nếu hôm nay chưa ghi nhận lượt 6h, giao diện nói rõ chưa kiểm tra. Đọc lần đầu để lấy badge, sau đó tải khi mở menu/làm mới; không thêm polling cho người dùng.

API `/api/v1/admin/source-monitor` chỉ admin; review có CSRF, validation và AdminAudit. Không có API công bố bản nháp/cào lại/reset lịch sử. Nội dung nguồn, ghi chú và tên tỉnh được escape khi render.

## Kiểm thử và trạng thái

- 98 kiểm thử backend PASS: giám sát, API/role/CSRF, schema wallet, national summary, runner 102 khối/resume, lịch sử/so sánh ngày, admin hiện có. Nguồn HTTP trong kiểm thử đều là mock, không gửi lệnh cào thật.
- TypeScript compile PASS; 10 file kiểm thử frontend PASS, thêm hồ sơ tài khoản tỉnh của daily-indicator-ui PASS. Menu admin, tài khoản, Trivia, Công thức tính và biểu đồ đã duyệt được kiểm tra hồi quy.
- Kiểm tra production SELECT-only: 102 khối ngày 13/10, đủ 612 raw profile hợp lệ, không thiếu raw; 9 kỳ tháng. Không viết dữ liệu công bố/Credit trong probe, không gọi nguồn.
- Backup 76.300.309 byte: `.tmp-source-monitor-backup-20261014/qd766-20261014-160950.dump`; SHA-256 `6fd7ef32e0c60cb7deb3524e996cb23e2225d2d6fc91cc370d6759d2d0c18b6c`.
- Migration 0027 → 0028 đã áp dụng và xác minh trên PostgreSQL; fingerprint Công thức tính trước/sau không đổi, wallet schema PASS. Public configuration/schema check PASS.
- Ngày 14/10, chủ hệ thống đã restart backend và gửi `PUBLIC_BACKEND_READY=ok`, `PUBLIC_RUNTIME_POLICY=PASS`; nhật ký mới xác nhận startup hoàn tất 16:27:09, Credit maintenance sẵn sàng. Đã đăng ký `QD766 Source Monitor`: `SOURCE_MONITOR_SCHEDULE=06:00 VIETNAM`, lượt đầu **15/10/2026 06:00**, backup task `.tmp-source-monitor-task-backups/20261014-162715-269`. Chưa chạy cào ngay; chưa có kết quả lượt 6h đầu.
- `LastTaskResult=267011` = `0x41303` = `SCHED_S_TASK_HAS_NOT_RUN` (task mới chưa chạy), không phải một lượt cào thất bại. Task kế thừa principal `InteractiveToken` từ lượt 5h theo XML đã backup: Windows phải đang có phiên đăng nhập. Máy cần có mạng và không ngủ/tắt vào giờ chạy. Không tự đổi quyền/principal của task cũ.
- Sau kiểm tra, chủ hệ thống đã **duyệt deploy frontend ngày 14/10** cùng các nội dung trong release-20261014.md. Không đưa 2-job/watchdog vào lần cập nhật này. Kết quả xuất bản phải được kiểm tra riêng sau khi push; việc đăng ký lịch không chứng minh lượt cào 6h đầu đã chạy thành công.

## Lệnh kích hoạt đã thực hiện và bước còn lại

Trong thư mục qd766, người có quyền Windows chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\restart_public_backend.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\register_source_monitor_task.ps1 -Confirm
```

Hai lệnh trên đã được chủ hệ thống thực hiện thành công. Nếu đăng ký lại mà task 05:00 dùng Password, lệnh thứ hai cần thêm `-Credential (Get-Credential)`, đúng principal Windows đang chạy task cào. Installer không khởi chạy lượt đối chiếu ngay. Không restart worker. Sau lượt đầu cần xem kết quả `source_monitor_runs`/nhật ký; đăng ký thành công chưa đồng nghĩa đã kiểm chứng lượt lấy mẫu thật.

Chủ hệ thống đã duyệt deploy frontend. Công bố module admin và các điều chỉnh đã duyệt riêng theo danh sách file chọn rõ ràng. Không dùng `git add -A` vì workspace còn prototype/2-job/watchdog và dữ liệu riêng.

Rollback vận hành: tắt task monitor, giữ bảng/bằng chứng; không downgrade xoá lịch sử. Nếu lùi code phải giữ schema guard chấp nhận 0028 — code guard 0027 cũ sẽ từ chối khởi động trên database mới.
