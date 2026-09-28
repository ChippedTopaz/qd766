# QĐ766 backend và PostgreSQL

## Mục tiêu của lát cắt đầu tiên

Backend phục vụ frontend từ dữ liệu snapshot đã xác minh. Frontend không gọi
trực tiếp DVCQG và request của người dùng không làm tăng concurrency upstream.
Collector/worker sẽ là tiến trình riêng ở bước sau.

Stack:

- FastAPI cho HTTP API;
- SQLAlchemy 2 cho model và transaction;
- Alembic cho migration;
- psycopg 3 cho PostgreSQL;
- PostgreSQL là database production; SQLite in-memory chỉ dùng trong unit test.

## Biên kiến trúc

```text
frontend
   |
   v
FastAPI read API
   |
   v
PostgreSQL snapshots  <--- transactional importer <--- verified normalized.json
   ^
   |
collection_jobs <--- future worker <--- DVCQG (sequential/rate-limited)
```

API đọc và collector không nằm cùng request lifecycle. Một snapshot chỉ được
nhập khi trạng thái `complete`, không có `missingGroups`, mọi dataset có cùng
`rootDepartmentId` và danh sách `loadedGroups` khớp dữ liệu thực tế. Khi một kỳ
chưa có snapshot, frontend chỉ tạo một job idempotent qua backend; request HTTP
không tự gọi DVCQG. Nếu circuit breaker đang mở, job được giữ ở trạng thái chờ
và giao diện không tự thăm dò liên tục.

## Mô hình dữ liệu

### `departments`

Danh mục đơn vị dùng UUID của DVCQG làm khóa chính. Tên, mã, cấp và metadata
được upsert khi nhập snapshot; điểm số không nằm ở bảng danh mục.

### `snapshots`

Một bản chụp theo tỉnh, kỳ, phạm vi và TTHC. `snapshot_key` là khóa idempotency
ổn định. Snapshot đã tồn tại chỉ được chấp nhận lại nếu toàn bộ raw SHA-256
giống nhau; cùng khóa nhưng hash khác bị từ chối.

### `formalities` và `formality_departments`

Danh mục TTHC và quan hệ áp dụng/công bố. Quan hệ này chỉ được nhập từ
`appliedDepartmentIds` và `publishingDepartmentIds` của `/reporting/formalities`;
không suy ra từ response đánh giá hay metadata `am-sieu-toc-data/details`.

### `datasets`

Một hàng cho mỗi nhóm chỉ số trong snapshot. Lưu loại schema, trạng thái công
thức, raw path/hash và detail như pagination, source, monthly chart.

### `entities`

Điểm tỉnh (`root`) và các cơ quan/xã (`child`). Điểm API được giữ nguyên;
parameters và source metadata lưu JSONB để không làm mất trường endpoint riêng.

### `metrics`

Metric có code của ba nhóm metric-schema. Các giá trị `null` vẫn là `NULL`,
không đổi thành 0.

### `collection_jobs`

Trạng thái bền vững cho worker sau này: `queued`, `running`, `succeeded`,
`failed`, `halted`; có priority, lần thử, lease và idempotency key. Bảng đã có
và lõi queue đã hỗ trợ enqueue chống trùng, claim bằng
`FOR UPDATE SKIP LOCKED`, retry có lịch, thu hồi lease hết hạn, hoàn tất và dừng
an toàn. API chỉ công khai thao tác đọc trạng thái; việc tạo job và worker xử lý
upstream không được mở qua HTTP.

Processor đã nối queue với collector và importer theo ba transaction tách biệt:
claim job, thu thập không giữ khóa database, rồi nhập snapshot/hoàn tất job.
Collector luôn tuần tự, mặc định nghỉ ít nhất 5 giây giữa request, tối đa một lần
retry ở transport, checkpoint raw sau từng nhóm và dừng job ngay khi gặp 403,
429, HTML, `Request Rejected`, `Access Denied` hoặc dữ liệu sai tỉnh. Worker nền
chạy qua `tools/run_collection_worker.py`; khi circuit mở, worker chỉ kiểm tra
trạng thái PostgreSQL và không claim job hay gọi DVCQG.

Bảng `collection_controls` giữ một lease toàn cục nên dù vô tình chạy nhiều
worker, chỉ một worker được phép gọi DVCQG tại một thời điểm. Safety stop sẽ mở
circuit breaker toàn cục; các job khác giữ nguyên trạng thái `queued` cho tới
khi quản trị viên chủ động đóng lại cầu dao sau khi kiểm tra nguyên nhân.

Probe kết nối chỉ thực hiện một GET trang chủ, không theo redirect, không POST
và không retry. Nếu DNS/HTTPS lỗi, nhận 403/429/5xx hoặc trang từ chối, tùy chọn
`--record-control` sẽ mở circuit breaker. Kết quả thành công không tự đóng cầu
dao:

```powershell
.venv\Scripts\python.exe tools\test_dvcqg_connectivity.py --record-control
.venv\Scripts\python.exe tools\manage_collection_control.py status
```

Chỉ sau khi người vận hành đã đọc kết quả probe và xác nhận có thể thử lại:

```powershell
.venv\Scripts\python.exe tools\manage_collection_control.py close --confirm-reviewed
```

## API đã có

```text
GET /api/v1/health/live
GET /api/v1/health/ready
GET /api/v1/system-status
GET /api/v1/collection-jobs
GET /api/v1/collection-jobs/{jobId}
GET /api/v1/collection-control
GET /api/v1/dashboard
GET /api/v1/dashboard/selection
POST /api/v1/dashboard/requests
GET /api/v1/snapshots
GET /api/v1/snapshots/latest
GET /api/v1/snapshots/{snapshotId}
GET /api/v1/snapshots/{snapshotId}/datasets
GET /api/v1/datasets/{datasetId}/entities
GET /api/v1/formalities
GET /api/v1/formalities/{formalityId}
```

Danh sách entity có phân trang `offset`/`limit`, tối đa 200 bản ghi. API cho
phép CORS `GET` và `POST` từ origin khai báo trong `QD766_CORS_ORIGINS`.

Dashboard dùng cache TTL 60 giây trong tiến trình backend. Các request cùng key
đến đồng thời dùng single-flight nên chỉ một request truy vấn và dựng payload;
những request còn lại nhận cùng kết quả. Header `X-QD766-Cache` cho biết
`miss`, `hit` hoặc `shared`. Endpoint `system-status` cung cấp trạng thái
PostgreSQL, circuit, số snapshot và thống kê cache mà không lộ credential.

FastAPI phục vụ luôn frontend trong thư mục `web` tại `/`. Endpoint
`/api/v1/dashboard/selection` nhận `period_type`, `year`, `period_value`,
`scope`, `formality_id` và chỉ trả một snapshot đầy đủ cho lựa chọn đó.
`POST /api/v1/dashboard/requests` nhận cùng lựa chọn ở dạng JSON camelCase,
trả ngay trạng thái `ready` nếu PostgreSQL đã có snapshot; nếu chưa có thì chỉ
xếp một job chống trùng và trả trạng thái circuit cho frontend.

Mục **Vận hành** trên frontend đọc `system-status` và `collection-jobs` để hiển
thị circuit, số snapshot và hàng đợi. Màn hình này không có thao tác mở circuit
hoặc kích hoạt worker; các bước đó vẫn phải làm theo runbook sau khi kiểm tra
kết nối nguồn.

## Cấu hình

Chỉ dùng biến môi trường; không commit credential:

```text
QD766_DATABASE_URL=postgresql+psycopg://<user>:<password>@127.0.0.1:5432/qd766
QD766_CORS_ORIGINS=https://<frontend-domain>
QD766_SQL_ECHO=false
```

`.env.example` chỉ là mẫu local. Không ghi URL kết nối thật vào log hoặc báo
cáo kiểm thử.

## Khởi tạo và chạy

Trong virtual environment:

```text
python -m pip install -e ".[dev]"
alembic upgrade head
python -m qd766.backend.main
```

Import một snapshot chuẩn hóa hoàn chỉnh:

```text
python tools/import_m1_snapshot.py path/to/normalized.json
python tools/import_formality_page.py path/to/formalities-page.json
```

## Backup trên máy cơ quan

Tạo bản dump nén và file SHA-256 trên ổ khác với data directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\backup_postgresql.ps1
```

Mặc định backup được ghi vào `F:\QD766\backups`. Script không tự xóa bản cũ;
chính sách retention chỉ được bật sau khi đã kiểm thử phục hồi.

Đăng ký backend và worker chạy khi người dùng đăng nhập, cùng backup lúc 01:30
mỗi ngày:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\register_windows_tasks.ps1
```

Ba task chạy dưới tài khoản Windows hiện tại với quyền `Limited`; không lưu mật
khẩu PostgreSQL trong Task Scheduler. Worker ghi log trạng thái gọn vào
`D:\QD766\logs\worker.log`. Backup chỉ chạy khi người dùng đang đăng nhập hoặc
đăng nhập lại sau thời điểm đã định (`StartWhenAvailable`).

## Triển khai ổn định trên máy cơ quan

Không đăng ký tác vụ Windows từ thư mục làm việc tạm của Codex. Dùng script sau
để sao chép ứng dụng sang `D:\QD766\app`, tạo môi trường Python riêng, chạy
migration và test, rồi tạo ngay một bản backup trên ổ F:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\deploy_local_server.ps1
```

Sau khi xác nhận deployment và backup thành công, đăng ký ba tác vụ Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\deploy_local_server.ps1 -RegisterTasks
```

Script không xóa file riêng đang có trong thư mục triển khai. File `.env` được
sao chép trực tiếp giữa hai vị trí local và vẫn bị Git bỏ qua.

Importer chạy trong một transaction. Lỗi ở bất kỳ dataset/entity/metric nào sẽ
rollback toàn bộ snapshot.

## Trạng thái tại máy cơ quan ngày 28/09/2026

Đã hoàn thành và xác minh:

- PostgreSQL 17 chạy local-only trên ổ G, database `qd766` và role ứng dụng;
- hai migration đã chạy, schema có tám bảng nghiệp vụ;
- đã nhập bốn snapshot hợp lệ, danh mục TTHC và quan hệ đơn vị;
- frontend ưu tiên API PostgreSQL và có snapshot tĩnh dự phòng;
- health/readiness/dashboard API và sáu backend test đều PASS;
- script backup đã tạo được dump hợp lệ và kiểm tra được bằng `pg_restore` trong
  thư mục thử nghiệm.

Chưa hoàn thành hoặc đang bị chặn:

- ba fixture tháng M0 bị hỏng byte/JSON nên chưa được nhập; kiểm tra cho thấy
  không thể phục hồi trung thực chỉ bằng chuyển mã;
- kết nối HTTPS tới DVCQG bị máy đích đóng cưỡng bức (`WinError 10054`); đã dừng
  theo nguyên tắc an toàn, không gửi POST hoặc thử vượt WAF; probe một GET ngày
  28/09/2026 xác nhận lỗi lặp lại và circuit breaker hiện đang `open`;
- queue, processor và worker nền đã có; worker được circuit bảo vệ và chỉ lấy
  job sau khi quản trị viên kiểm tra kết nối rồi chủ động đóng circuit;
- cache/single-flight đã có; benchmark rate/concurrency với DVCQG chưa thực
  hiện vì circuit đang mở;
- ứng dụng đã triển khai vào `D:\QD766\app`; backend, worker và backup được
  quản lý bằng Windows Task Scheduler;
- chưa kết nối frontend công khai tới backend máy cơ quan qua HTTPS.

Thứ tự tiếp theo: giữ circuit mở, chạy probe một GET duy nhất; chỉ khi người vận
hành xác nhận kết quả an toàn mới đóng circuit để worker xử lý lần lượt các job
đang chờ.
