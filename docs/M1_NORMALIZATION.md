# QĐ766 M1 – Chuẩn hóa và snapshot

## Mục tiêu

M1 chuyển raw response của sáu nhóm chỉ tiêu thành mô hình thống nhất
phục vụ thống kê. Raw JSON vẫn là nguồn truy vết và không bị thay đổi.

Quy tắc cốt lõi:

- `apiScore`/`apiMaxScore` lấy nguyên từ `score`/`totalScore` và
  `maxScore`/`totalMaxScore` của DVCQG;
- không tính lại hay ghi đè điểm API;
- metric có `null` vẫn giữ `null`;
- nhóm không có metric code giữ toàn bộ parameter để hiển thị;
- công thức chưa xác định có `formulaApplied = false`;
- mỗi dataset có đường dẫn và SHA-256 của raw response.

## Mô hình chuẩn hóa

Mỗi dataset có:

```text
group
schemaKind                 metrics | parameters
formulaStatus
scorePolicy                api-authoritative
period                     month | quarter | year
scope                      all | formality
formalityId
root                       điểm tỉnh và dữ liệu chi tiết
children[]                 cơ quan/xã
details                    pagination, source, monthlyChart...
raw.path + raw.sha256
```

Mỗi `root`/`child` có thông tin đơn vị, `apiScore`, `apiMaxScore`,
`apiRatio`, `metrics[]`, `parameters` và metadata gốc. `scoreSource` luôn là
`dvcqg-api` trong M1.

Ba nhóm dạng metric:

- `transparency`;
- `handling-satisfaction`;
- `dossier-digitized`.

Ba nhóm dạng parameter:

- `dvc-progress-tree`;
- `provide-online-tree`;
- `formality-online-payment-tree`.

M1 không cần biết công thức của parameter để thống kê. Giao diện có thể
hiển thị nguyên tên trường và giá trị trong `parameters`; khi có công thức
chính thức sẽ bổ sung lớp giải thích riêng.

## Tính hoàn chỉnh của snapshot

Snapshot `all` chỉ `complete` khi có đủ sáu nhóm. Snapshot `formality`
chỉ yêu cầu năm nhóm; Mức độ hài lòng được ghi rõ là
`unsupported`, không bị ghi nhận nhầm thành request lỗi hoặc thiếu dữ liệu.

Khi thiếu một nhóm bắt buộc:

- snapshot có trạng thái `incomplete`;
- `missingGroups` liệt kê nhóm thiếu;
- không xuất tổng điểm hoặc tổng điểm tối đa một phần.

`provinceAggregatedScore` là tổng các `root.apiScore` của nhóm đã
thu thập. Đây là phép cộng các điểm nhóm do API trả về, không phải
một trường tổng do endpoint riêng trả về.

Ba snapshot `all` M0 đều có `provinceAggregatedMaximum = 100`. Snapshot
TTHC mẫu có tổng điểm tối đa quan sát được là 80 do không có nhóm
Hài lòng và API Số hóa không trả metric tổng hợp
`CITIZEN_DATA_CONNECTED_FORMALITY` khi lọc một TTHC. Không diễn giải 80
thành thang điểm chính thức của TTHC.

## Chính sách cấp xã

Yêu cầu nghiệp vụ là tiêu chí không áp dụng cấp xã được tính điểm tối
đa. M1 ghi chính sách này nhưng chưa tự điều chỉnh điểm vì METRICS còn
thiếu `maxScore` của STT 7, 8, 9, 10 và 18. Cho đến khi bảng điểm tối
đa hoàn chỉnh, hệ thống hiển thị điểm API và không âm thầm cộng bù.

## Chạy offline

Tạo snapshot đầy đủ:

```text
python tools/build_m1_snapshot.py --period year --year 2026 --scope all --output snapshot.json
```

Với tháng hoặc quý, thêm `--value`:

```text
python tools/build_m1_snapshot.py --period quarter --year 2026 --value 3 --scope formality
```

Kiểm tra cả sáu tổ hợp fixture:

```text
python tools/validate_m1.py --report docs/m1-validation-report.json
python -m unittest discover -s tests -p "test_*.py" -v
```

PASS M1 chỉ xác nhận chuẩn hóa offline, tính hoàn chỉnh và phép cộng
điểm API trên fixture M0. PASS không xác nhận crawler production, công thức
parameter chưa cung cấp hoặc dữ liệu của tỉnh khác.

## Thu thập snapshot mới

`tools/collect_m1.py` mặc định chỉ in kế hoạch request và không gọi
DVCQG:

```text
python tools/collect_m1.py --period month --year 2026 --value 9 --root-department-id <id>
```

Chỉ khi có `--execute` và `--output`, công cụ mới gửi request. Collector:

- chạy tuần tự, không song song;
- có delay và jitter giữa request;
- checkpoint raw bytes và manifest sau từng nhóm;
- retry giới hạn với lỗi thông thường;
- dừng ngay khi HTTP 403 hoặc 429;
- xác minh envelope, schema, `rootDepartmentId` và danh tính child trước
  khi ghi raw;
- không ghi đè snapshot có manifest `complete`;
- có thể tiếp tục snapshot dở dang nếu hash các checkpoint cũ còn nguyên.

Sau khi thu đủ nhóm, công cụ tạo `normalized.json` từ chính raw response
đã checkpoint. M1 chưa tự chạy lịch và chưa được coi là crawler
production cho đến khi có một live smoke test được xác minh.
