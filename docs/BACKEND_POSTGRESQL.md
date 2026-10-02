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

Một bản chụp theo tỉnh, kỳ, phạm vi và TTHC. Từ phiên bản `snapshot:v2`,
`snapshot_key` gồm cả hash nội dung của các raw dataset. Vì vậy cùng
tỉnh/kỳ/phạm vi có thể có nhiều phiên bản bất biến khi dữ liệu nguồn thay đổi;
nhập lại đúng cùng nội dung vẫn trả về bản đã có. API dashboard và
`snapshots/latest` luôn chọn phiên bản hoàn chỉnh mới nhất.

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
GET /api/v1/province-batches
GET /api/v1/province-batches/{batchId}
GET /api/v1/province-batches/{batchId}/items
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

Đăng ký backend và worker chạy khi người dùng đăng nhập, cập nhật tổng hợp quốc
gia mỗi giờ, cùng backup lúc 01:30 mỗi ngày:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\register_windows_tasks.ps1
```

Bốn task chạy dưới tài khoản Windows hiện tại với quyền `Limited`; không lưu mật
khẩu PostgreSQL trong Task Scheduler. Worker ghi log trạng thái gọn vào
`D:\QD766\logs\worker.log`, backend ghi vào `D:\QD766\logs\backend.log`. Tác
vụ được thử khởi động lại tối đa ba lần nếu tiến trình thoát bất thường. Backup
chỉ chạy khi người dùng đang đăng nhập hoặc đăng nhập lại sau thời điểm đã định
(`StartWhenAvailable`).

## Triển khai ổn định trên máy cơ quan

Không đăng ký tác vụ Windows từ thư mục làm việc tạm của Codex. Dùng script sau
để sao chép ứng dụng sang `D:\QD766\app`, tạo môi trường Python riêng, chạy
migration và test, rồi tạo ngay một bản backup trên ổ F:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\deploy_local_server.ps1
```

Sau khi xác nhận deployment và backup thành công, đăng ký bốn tác vụ Windows:

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

## Cập nhật tại máy cơ quan ngày 01/10/2026

- circuit đã được kiểm tra và đang `closed`; worker đã hoàn tất các job theo
  hàng đợi tuần tự;
- PostgreSQL có 24 snapshot hoàn chỉnh: 23 snapshot Phú Thọ và một snapshot
  tổng hợp Tây Ninh năm 2026;
- bốn migration Alembic đã được áp dụng, gồm control và batch/checkpoint;
- ba fixture tháng bị thiếu byte đã được phục hồi từ raw response do worker
  thu lại ngày 28/09, đối chiếu manifest và SHA-256;
- frontend đã có bộ chọn tỉnh/thành phố và đã kiểm tra chuyển hai chiều giữa
  Phú Thọ và Tây Ninh;
- danh mục 34 `rootDepartmentId` cấp tỉnh được chụp bằng đúng một yêu cầu chỉ
  đọc tới `service-results`, lưu tại `data/config/provinces.json`; mỗi bản ghi
  giữ nguyên tên, mã đơn vị và đường dẫn nguồn để có thể kiểm tra lại;
- backend hiển thị đủ 34 tỉnh. Tỉnh đã có snapshot được mở ngay; tỉnh chưa có
  snapshot chỉ tạo một job tổng hợp chống trùng cho kỳ đang chọn. Worker tiếp
  tục lấy sáu nhóm tuần tự, chịu sự bảo vệ của circuit và không tự sinh batch
  hàng nghìn TTHC;
- Hà Nội năm 2026 là tỉnh thứ ba dùng để kiểm tra luồng thêm tỉnh mới.

Khi DVCQG thay đổi cơ cấu hoặc định danh đơn vị, chạy lại
`tools/bootstrap_catalog_api.py` sau khi kiểm tra kết nối. Script chỉ gửi một
yêu cầu, lưu bằng chứng tách biệt và từ chối kết quả nếu không đủ 34 tỉnh; không
được tự suy đoán hoặc sửa tay UUID.

### Batch tổng hợp liên tỉnh

Batch toàn quốc là thao tác quản trị, không có API công khai để tạo hoặc tiếp
tục. Công cụ đọc danh mục 34 `rootDepartmentId` đã xác minh, bỏ qua snapshot
đã có và chỉ xếp job cho tỉnh còn thiếu đầu tiên. Worker hoàn tất một tỉnh mới
tạo job kế tiếp; vì vậy hàng đợi không chứa đồng thời 34 job và upstream vẫn có
concurrency bằng 1.

```powershell
.venv\Scripts\python.exe tools\manage_province_batch.py create --period-type year --year 2026
.venv\Scripts\python.exe tools\manage_province_batch.py status
```

Khi batch dừng do safety stop, phải kiểm tra probe và đóng circuit theo runbook
trước. Sau đó tiếp tục đúng checkpoint bằng:

```powershell
.venv\Scripts\python.exe tools\manage_province_batch.py resume --batch-id <UUID> --confirm-reviewed
```

Hai endpoint `province-batches` chỉ đọc tiến độ. Việc tạo/resume không mở cho
frontend nhằm tránh người dùng phổ thông vô tình kích hoạt lượt thu thập toàn
quốc.

### Tổng hợp toàn quốc theo một request

Endpoint `service-results` trả điểm tổng hợp và sáu nhóm chỉ tiêu của toàn bộ
34 tỉnh/thành trong một response. QD766 lưu mỗi response thay đổi thành một
phiên bản bất biến trong `national_summary_snapshots`, chống trùng bằng
SHA-256.

Hợp đồng hoàn chỉnh áp dụng giống nhau cho tháng, quý và năm: mỗi một trong 34
tỉnh phải có đúng sáu mã nhóm `CKMB`, `TDGQ`, `CLGQ`, `MDSH`, `MDHL`, `TTTT`.
Snapshot được lưu với `completeness_state=complete`, `group_count=6` và danh
sách mã nhóm đã kiểm tra. Phản hồi thiếu hoặc thừa nhóm bị từ chối trước khi
ghi PostgreSQL, vì vậy không thể thay thế bản hoàn chỉnh gần nhất; task giờ kế
tiếp sẽ thử lại theo lịch.

```powershell
.\.venv\Scripts\python.exe .\tools\refresh_national_summaries.py
```

Không truyền tham số thì mỗi lần chạy công cụ chỉ gửi **một request**: ưu tiên
năm nếu chưa có dữ liệu, sau đó luân phiên năm, tháng và quý theo giờ. Cách này
giữ năm hiện tại cập nhật khoảng hai giờ/lần và tránh ba request sát nhau. Chỉ
dùng `--all-current` khi quản trị viên chủ động cần cập nhật tuần tự cả ba kỳ.
Công cụ dùng chung PostgreSQL collection lease với worker; nếu worker đang gọi
nguồn hoặc circuit đang mở thì không gửi request. HTTP 403, 429 và phản hồi
HTML/rejection tiếp tục mở circuit theo quy tắc an toàn.

Do lớp TLS của DVCQG có thể chủ động đóng kết nối từ client nền và từ chối
trình duyệt headless, công cụ mở một phiên Chrome hoặc Edge thông thường với hồ
sơ tạm, đặt cửa sổ ngoài vùng hiển thị, gọi API trong đúng origin
`dichvucong.gov.vn`, rồi đóng trình duyệt ngay sau request. Máy chủ Windows cần
có Chrome hoặc Edge; cơ chế này không dùng proxy, xoay IP, giả mạo dấu vân tay,
retry vượt giới hạn hay bỏ qua tín hiệu WAF.

Task `QD766 National Summary` chạy mỗi giờ. Dashboard cấp tỉnh ưu tiên tổng
điểm, điểm sáu nhóm và thứ hạng từ bản tổng hợp mới nhất; chi tiết sở, xã, chỉ
tiêu thành phần và TTHC vẫn dùng sáu adapter chuyên sâu. Dữ liệu kỳ đang mở quá
hai giờ được đánh dấu `stale` thay vì báo sai là mới.

API chỉ đọc:

- `GET /api/v1/national-summaries`
- `GET /api/v1/national-summaries/latest?period_type=year&year=2026`

Batch quản trị mặc định vẫn bỏ qua tỉnh đã có dữ liệu. Truyền `--refresh-key`
mới tạo một chu kỳ làm mới có chủ đích cho toàn bộ tỉnh; nếu raw không thay đổi
thì lớp lưu trữ vẫn chống trùng theo hash nội dung.

Task `QD766 Province Detail Refresh` chạy hằng ngày lúc 02:15. Nó không gọi
nguồn trực tiếp mà chỉ tạo tối đa một batch khi không có batch tỉnh đang chạy,
không có batch lỗi cần rà soát và circuit đang đóng. Ba kỳ hiện tại (năm,
tháng, quý) được luân phiên theo thời điểm hoàn tất cũ nhất, với ngưỡng mặc định
72 giờ. Worker tiếp tục xử lý từng tỉnh và sáu endpoint tuần tự; vì vậy không có
hai luồng chi tiết gọi DVCQG đồng thời. Điểm tổng hợp 34 tỉnh vẫn được task
National Summary cập nhật riêng mỗi giờ.

Dashboard tách riêng độ mới của hai lớp dữ liệu: `summaryStale` cho điểm/xếp
hạng toàn quốc (ngưỡng hai giờ) và `detailsStale` cho snapshot chi tiết sáu
nhóm (ngưỡng 72 giờ). Chỉ kỳ đang diễn ra mới hết hạn; tháng, quý hoặc năm đã
kết thúc được giữ nguyên. Màn hình **Vận hành** đọc API
`GET /api/v1/province-batches` để hiển thị kỳ, tiến độ, số tỉnh dùng lại và số
tỉnh phải thu thập mới; thao tác này không tạo job và không gọi DVCQG.
