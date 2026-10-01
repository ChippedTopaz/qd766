# Live smoke QĐ766 — tháng 8/2026

Ngày kiểm tra: 27/09/2026. Đơn vị: UBND tỉnh Phú Thọ,
`rootDepartmentId=019d2be3-6a88-732b-8b17-b68020c8553a`.

## Kết quả

Live collection hoàn chỉnh cho kỳ tháng gần nhất đã kết thúc:

| Phạm vi | Request | HTTP | Raw bytes | Điểm API cộng từ các nhóm |
| --- | ---: | --- | ---: | ---: |
| Toàn bộ TTHC | 6/6 | 201 | 824.612 | 59,91/100 |
| TTHC `2.000815` | 5/5 | 201 | 585.475 | 50,94/80 quan sát được |

Mức 80 của phạm vi TTHC là tổng `maxScore` của năm endpoint có hỗ trợ lọc
TTHC; đây không phải tuyên bố về thang điểm TTHC chính thức. Mức độ hài lòng
không hỗ trợ drill-down TTHC.

Mười một raw response được giữ nguyên byte và thay thế các fixture `month-*`
trước đây lấy từ tháng 9 chưa kết thúc. SHA-256, kích thước, payload, HTTP status
và thời điểm thu nằm trong `tests/fixtures/manifest.m0.json`.

## Contract live đã xác nhận

- Cả sáu endpoint vẫn trả HTTP 201 với envelope `code=OK` và đúng
  `rootDepartmentId` Phú Thọ.
- Năm endpoint thông thường dùng `timeType=month`, `year=2026`, `month=8`.
- `handling-satisfaction` dùng `fromDate=2026-08-01` và
  `toDate=2026-08-31`; người dùng vẫn chỉ chọn kỳ tháng.
- Bốn endpoint drill-down dùng `formalityId`.
- `dossier-digitized` tiếp tục dùng đúng khóa phân biệt hoa/thường
  `formalityID`.
- Raw response của mỗi nhóm qua kiểm tra envelope, schema, root và child
  identity trước khi ghi file.

## Quy tắc kỳ báo cáo

Collector chặn tháng chưa kết thúc trước khi gọi mạng. Quý hiện tại và năm
hiện tại được chấp nhận; quý hoặc năm tương lai bị chặn. Tại ngày 27/09/2026,
tháng 8/2026 và quý 3/2026 hợp lệ, còn tháng 9 và quý 4/2026 chưa hợp lệ.

## Xác minh

- 21/21 unit test: PASS.
- M0 fixture/contract validator: PASS trên 37 fixture.
- M1 normalization/completeness validator: PASS trên fixture đã khóa.
- Scoring analysis: **PASS** trên fixture M0. Dịch vụ công trực tuyến dùng
  profile `qd766-online-v1`, khớp 6/6 response parent trong sai số 0,015 điểm;
  điểm API vẫn là giá trị chính thức.

Các PASS chỉ áp dụng cho fixture Phú Thọ và pipeline hiện có. Chưa kiểm chứng
các tỉnh khác, dữ liệu rỗng/lỗi, hoặc thay đổi công thức từ hệ thống nguồn.
