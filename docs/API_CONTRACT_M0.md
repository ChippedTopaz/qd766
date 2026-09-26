# QĐ766 API contract M0

## Phạm vi đã khóa

Bộ fixture M0 được thu ngày 2026-09-26 từ trang công khai
`https://dichvucong.gov.vn/danh-gia-chat-luong-phuc-vu` cho UBND tỉnh Phú Thọ:

- `rootDepartmentId`: `019d2be3-6a88-732b-8b17-b68020c8553a`
- năm: 2026
- quý mẫu: quý 3
- tháng mẫu: tháng 9
- TTHC mẫu: `2.000815`
- `formalityId`: `019d2bfd-8e22-77ef-819f-e49460350904`

Mỗi raw response được lưu nguyên byte trong `tests/fixtures/`. Metadata request,
HTTP status, thời điểm thu thập, kích thước và SHA-256 nằm trong
`tests/fixtures/manifest.m0.json`.

## Endpoint và payload

Tất cả endpoint dùng `POST` và trả HTTP `201` với envelope
`{"code":"OK","data":...,"message":...}` trong lần thu thập này.

| Nhóm | Endpoint | Dạng response | Page size | TTHC |
| --- | --- | --- | ---: | --- |
| Công khai, minh bạch | `/api/v1/reporting/evaluation/transparency` | `overview`, `monthlyChart`, `evaluation`, `pagination`, `source` | 200 | `formalityId` |
| Mức độ hài lòng | `/api/v1/reporting/evaluation/handling-satisfaction` | `overview`, `evaluation`, `pagination`, `source` | 200 | Không hỗ trợ |
| Số hóa hồ sơ | `/api/v1/reporting/evaluation/dossier-digitized` | `overview`, `evaluation`, `pagination`, `source` | 200 | `formalityID` |
| Tiến độ giải quyết | `/api/v1/reporting/evaluation/dvc-progress-tree` | `parent`, `children`, `monthlyChart` | 100 | `formalityId` |
| Dịch vụ công trực tuyến | `/api/v1/reporting/evaluation/provide-online-tree` | `parent`, `children`, `monthlyChart` | 200 | `formalityId` |
| Thanh toán trực tuyến | `/api/v1/reporting/evaluation/formality-online-payment-tree` | `parent`, `children` | 100 | `formalityId` |

Năm nhóm trừ Mức độ hài lòng dùng:

```json
{"timeType":"year","year":2026,"rootDepartmentId":"019d2be3-6a88-732b-8b17-b68020c8553a","currentPage":1,"pageSize":200}
```

Kỳ quý thêm `"quarter":3`; kỳ tháng thêm `"month":9`. `pageSize` thay theo
bảng trên. Khi lọc TTHC, payload thêm đúng khóa phân biệt hoa/thường trong cột
TTHC. Không chuẩn hóa `formalityID` thành `formalityId` ở tầng adapter.

Mức độ hài lòng dùng khoảng ngày thay vì `timeType` ở tầng
transport:

```json
{"fromDate":"2026-07-01","toDate":"2026-09-30","rootDepartmentId":"019d2be3-6a88-732b-8b17-b68020c8553a","currentPage":1,"pageSize":200}
```

Ba fixture tương ứng dùng `2026-09-01..2026-09-30`,
`2026-07-01..2026-09-30` và `2026-01-01..2026-12-31`.

Mô hình sản phẩm vẫn chỉ có ba lựa chọn `month`, `quarter`, `year`.
Người dùng không nhập `fromDate`/`toDate`; adapter tự suy ra ngày đầu
và ngày cuối của kỳ. `src/qd766/periods.py` là phần triển khai tham
chiếu và đã được đối chiếu với toàn bộ 33 request trong manifest.

## Contract TTHC mẫu và phân trang

`POST /api/v1/reporting/formalities` với:

```json
{"q":"2.000815","currentPage":1,"pageSize":10}
```

trả đúng một thủ tục. Item giữ nguyên các trường `id`, `code`, `name`, `state`,
`departmentId`, `publishingDepartmentIds` và `appliedDepartmentIds`. Fixture có
3.629 ID trong `appliedDepartmentIds`.

Ba fixture không có `q` khóa biên phân trang tại thời điểm thu thập:

- trang 1: 10 item;
- trang 2: 10 item;
- trang 575: 1 item;
- tổng: 5.741 item, `pageSize=10`, `totalPages=575`.

Crawler chỉ được đi trang kế tiếp khi `currentPage < totalPages`. M0 chỉ lưu ba
trang đại diện nói trên; không thu toàn bộ 575 trang.

## Schema nghiệp vụ

`transparency`, `handling-satisfaction` và `dossier-digitized` dùng `metrics[]`.
Mỗi metric giữ `code`, `name`, `numerator`, `denominator`, `ratio`, `score` và
`maxScore`, kể cả `null`. Không thay `null` bằng 0.

`dvc-progress-tree`, `provide-online-tree` và
`formality-online-payment-tree` dùng các parameter trực tiếp trên `parent` và
`children`; không có metric code riêng. Adapter phải giữ các parameter gốc để
công thức tính tỷ lệ/điểm được bổ sung sau.

Khi lọc một TTHC ở `dossier-digitized`, API không trả metric tổng hợp
`CITIZEN_DATA_CONNECTED_FORMALITY`. Đây là biến thể schema đã quan sát, không
phải lỗi fixture.

Phản hồi có thể chứa cờ chất lượng dữ liệu như
`TEMP_NATIONAL_REPORT_DENOMINATOR` và `NO_NATIONAL_REPORT_DATA`. Crawler phải
giữ nguyên các cờ và thông điệp đi kèm.

## Đối chiếu METRICS

`docs/metrics.m0.json` là bản trích read-only từ `METRICS!A1:I25` của file
`Công thức 766.xlsx`, kèm SHA-256 nguồn. Có 24 dòng chỉ tiêu và tổng các
`maxScore` đã khai báo bằng 100 cho cấp tỉnh.

Các STT 7, 8, 9, 10 và 18 chưa có `maxScore`; không suy diễn thành 0. Các STT
6, 8, 9, 16 và 17 không áp dụng cấp xã. Chính sách nghiệp vụ là cấp xã được
điểm tối đa cho tiêu chí không áp dụng, nhưng chỉ có thể triển khai khi điểm tối
đa của từng tiêu chí đã được cung cấp.

Cột “Công thức tính” là mô tả hiển thị. Điểm API trả về là
giá trị chính; không tính lại rồi ghi đè. Phân tích ngược từ cột này và
fixture được lưu trong `docs/SCORING_ANALYSIS_M0.md` và
`docs/scoring-formula-analysis.m0.json`. Tiến độ giải quyết đã khóa được
công thức trên M0; Dịch vụ công trực tuyến mới khóa được một thành
phần và chưa được phép triển khai thành công thức tổng quát.

## Kiểm tra và giới hạn

Chạy offline:

```text
python tests/validate_m0.py --report docs/m0-validation-report.json
```

PASS chỉ xác nhận raw bytes chưa đổi, đủ 37 fixture, endpoint/payload đã khóa,
schema và phạm vi tỉnh hợp lệ, phân trang danh mục nhất quán, metric trong
METRICS khớp response, và tổng điểm tỉnh đã khai báo bằng 100.

PASS của `validate_m0.py` không xác nhận công thức chấm điểm, mọi
tỉnh/mọi năm, trường hợp dữ liệu rỗng/lỗi, hay crawler production. PASS
của `analyze_scoring_formulas.py` chỉ xác nhận phép tính tái tạo được các
điểm M0 trong sai số đã công bố. API response không echo ID TTHC; bằng chứng
lọc TTHC gồm mã client đang triển khai, lựa chọn hiển thị trên giao diện, item
danh mục và sự khác biệt giữa fixture `all`/`formality`.
