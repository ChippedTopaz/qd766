# Phân tích ngược điểm số M0

## Nguyên tắc sử dụng

`score`/`totalScore` trong response DVCQG là giá trị chính thức mà hệ thống lưu
và hiển thị. Công thức trong tài liệu này chỉ phục vụ giải thích yếu tố nào làm
điểm tăng hoặc giảm, kiểm tra dữ liệu bất thường và chuẩn bị cho phần phân tích.
Không dùng kết quả tính lại để ghi đè điểm API.

Kết quả được kiểm chứng offline trên fixture Phú Thọ thu ngày 2026-09-26. Trạng
thái `verified-on-m0` chỉ có nghĩa là công thức tái tạo mọi quan sát M0 trong sai
số `0,015` điểm; không khẳng định đây là công thức pháp lý chính thức hoặc đã
đúng cho mọi tỉnh, mọi kỳ.

Báo cáo máy đọc và số lượng quan sát nằm tại
`docs/scoring-formula-analysis.m0.json`. Có thể tái tạo bằng:

```text
python tools/analyze_scoring_formulas.py --report docs/scoring-formula-analysis.m0.json
```

## Công thức đã tái tạo được

### Công khai, minh bạch

Với cả bốn metric:

```text
điểm = điểm tối đa × tỷ lệ / 100
```

Đã khớp 2.290 quan sát. Tổng điểm nhóm bằng tổng `score` của các metric.

### Tiến độ giải quyết

```text
tỷ lệ đúng hạn = totalOnTime / totalReceived
điểm = 20 × tỷ lệ đúng hạn
```

Đã khớp 984 parent/child. M0 chưa có mẫu `totalReceived = 0`, vì vậy chưa quy
định cách tự tính trường hợp mẫu số bằng 0; vẫn dùng điểm API.

### Mức độ hài lòng

`DOSSIER_RECEIVING_SATISFACTION` đạt tối đa 6 điểm từ ngưỡng hài lòng 90%:

```text
nếu denominator = 0: điểm = 0
ngược lại: điểm = min(6, 6 × numerator / denominator / 0,90)
```

Hai metric PAKN dùng:

```text
PETITION_PROCESSING_ON_TIME:
  nếu denominator = 0: điểm = 6
  ngược lại: điểm = 6 × numerator / denominator

PETITION_HANDLING_SATISFACTION:
  nếu denominator = 0: điểm = 6
  ngược lại: điểm = 6 × numerator / denominator
```

Quy tắc 6 điểm khi không có PAKN phù hợp mô tả trong cột “Công thức tính”. Mỗi
công thức đã khớp 492 quan sát. Hai metric phân loại PAKN có `maxScore = 0` và
`score = null`, chỉ dùng làm dữ liệu giải thích.

### Số hóa hồ sơ

Phần lớn metric dùng:

```text
điểm = min(điểm tối đa, điểm tối đa × tỷ lệ / 100)
```

Riêng `REUSED_DIGITIZED_DATA` đạt tối đa ở tỷ lệ 80%:

```text
điểm = min(2, 2 × tỷ lệ / 80)
```

Các metric có từ 492 đến 984 quan sát. `SYNCED_WITH_DVCQG_PERSONAL_STORAGE`
chỉ có tỷ lệ 0 trong M0 nên mới xác nhận được trường hợp 0 điểm; cần một fixture
có tỷ lệ dương để khóa hệ số. Các `score = null` được giữ nguyên và loại khỏi
phép khớp công thức.

### Thanh toán trực tuyến

Đặt:

```text
A = totalDossierOnlinePaymentSuccess / totalDossierFinancialObligation
B = totalDossierOnlineFormalityPaymentSuccess / totalFeeFormality
C = totalFeeDossierFormality / totalFeeFormality
```

Công thức tái tạo 984 parent/child là:

```text
điểm = 6 × A + min(2, 2,5 × B) + 2,5 × C
```

Khi mẫu số bằng 0, tỷ lệ tương ứng bằng 0 trong các quan sát M0. Sai số lớn
nhất là 0,0138 điểm do response chỉ công bố điểm đến hai chữ số thập phân.

## Công thức chưa xác định

Với Dịch vụ công trực tuyến, từng có giả thuyết về thành phần:

```text
4 × onlineDossierCount / onlineServiceTotal
```

Fixture tháng 8 đã kết thúc làm phần dư biến thiên vượt sai số cho phép, nên
giả thuyết này **không được coi là thành phần đã xác nhận**. Toàn bộ parameters
vẫn được lưu và hiển thị chi tiết, nhưng không dùng để tính lại điểm. Cần công
thức do người dùng cung cấp hoặc thêm bằng chứng độc lập trước khi triển khai.

## Kỳ báo cáo của Mức độ hài lòng

Người dùng vẫn chỉ chọn tháng, quý hoặc năm. Adapter tự chuyển lựa chọn thành
khoảng ngày bao trọn kỳ:

- tháng 8/2026: `2026-08-01` đến `2026-08-31`;
- quý 3/2026: `2026-07-01` đến `2026-09-30`;
- năm 2026: `2026-01-01` đến `2026-12-31`.

Sản phẩm không cung cấp lựa chọn ngày tự do cho nhóm này.
