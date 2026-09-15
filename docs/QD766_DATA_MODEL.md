# QĐ766 – Data Model & API Survey

## 1. Mục tiêu

Khảo sát API DVCQG để thiết kế crawler an toàn, có khả năng lưu RAW đầy đủ, tái dựng dữ liệu chuẩn hóa và phục vụ phân tích lịch sử.

Nguyên tắc: **RAW JSON là nguồn sự thật; không bỏ trường; không tự thay đổi giá trị `null`; không ghi đè snapshot tốt bằng dữ liệu chưa xác minh.**

## 2. Sáu nhóm chỉ tiêu

1. Công khai, minh bạch
2. Mức độ hài lòng
3. Số hoá hồ sơ
4. Tiến độ giải quyết
5. Dịch vụ công trực tuyến
6. Thanh toán trực tuyến

## 3. Chiều thời gian

DVCQG cho phép thống kê theo:

- `timeType = year` + `year`
- `timeType = quarter` + `year` + `quarter`
- `timeType = month` + `year` + `month`

Một request dữ liệu phải được định danh bởi tối thiểu:

```text
province/rootDepartmentId
criterion
 timeType + period
formalityId (nếu nhóm hỗ trợ drill-down)
```

Payload phải được lưu nguyên bản vì tên/đối số có thể khác theo endpoint; ví dụ có API dùng `formalityId`, có API dùng `formalityID`.

## 4. API đã xác định

### 4.1 Công khai, minh bạch

Tổng hợp và drill-down TTHC dùng cùng endpoint:

`POST https://dichvucong.gov.vn/api/v1/reporting/evaluation/transparency`

Mẫu tổng hợp năm:

```json
{
  "timeType": "year",
  "year": 2026,
  "rootDepartmentId": "...",
  "currentPage": 1,
  "pageSize": 200
}
```

Mẫu drill-down quý:

```json
{
  "timeType": "quarter",
  "year": 2026,
  "quarter": 3,
  "rootDepartmentId": "...",
  "formalityId": "...",
  "currentPage": 1,
  "pageSize": 200
}
```

Response chính: `data.overview`, `data.evaluation[]`, `data.monthlyChart` (có thể rỗng), cùng các `metrics[]`.

Metrics mẫu đã xác định: `PUBLISH_ON_TIME`, `PUBLIC_UPDATE_ON_TIME`, `PUBLIC_CONTENT_FULL`, `DOSSIER_SYNC`.

`DOSSIER_SYNC` có thể mang metadata chất lượng dữ liệu như `dataQualityStatus` và `dataQualityMessage`; phải lưu nguyên.

### 4.2 Mức độ hài lòng

Đã xác nhận cấu trúc response:

`data.overview.metrics[]` + `data.evaluation[].metrics[]`.

Nhóm này **không có drill-down theo TTHC**.

Endpoint cụ thể cần chốt lại trong manifest khi triển khai crawler (TBD).

Metrics mẫu đã quan sát: `PETITION_CLASSIFICATION_TTHC`, `DOSSIER_RECEIVING_SATISFACTION`, `PETITION_PROCESSING_ON_TIME`, `PETITION_HANDLING_SATISFACTION`, `PETITION_CLASSIFICATION_STAFF`.

### 4.3 Số hoá hồ sơ

`POST https://dichvucong.gov.vn/api/v1/reporting/evaluation/dossier-digitized`

Tổng hợp năm:

```json
{
  "timeType": "year",
  "year": 2026,
  "rootDepartmentId": "...",
  "currentPage": 1,
  "pageSize": 200
}
```

Drill-down quý:

```json
{
  "timeType": "quarter",
  "year": 2026,
  "quarter": 3,
  "rootDepartmentId": "...",
  "formalityID": "...",
  "currentPage": 1,
  "pageSize": 200
}
```

Đã kiểm chứng drill-down tháng với cùng endpoint, thêm `month` và `timeType=month`.

Response: `data.overview`, `data.evaluation[]`, mỗi đơn vị có `metrics[]`.

7 metrics đã xác định:

- `ORIGINAL_RESULT_AVAILABLE`
- `SO_HOA_GIAY_TO_GIAI_QUYET`
- `REUSED_DIGITIZED_DATA`
- `SYNCED_WITH_DVCQG_PERSONAL_STORAGE`
- `CITIZEN_DATA_CONNECTED_DOSSIER`
- `CITIZEN_DATA_CONNECTED_FORMALITY`
- `ELECTRONIC_CERTIFIED_COPY`

### 4.4 Tiến độ giải quyết

`POST https://dichvucong.gov.vn/api/v1/reporting/evaluation/dvc-progress-tree`

Drill-down quý mẫu:

```json
{
  "timeType": "quarter",
  "year": 2026,
  "quarter": 3,
  "rootDepartmentId": "...",
  "formalityId": "...",
  "currentPage": 1,
  "pageSize": 100
}
```

Response: `data.parent` + `data.children[]`.

Trường chính: `totalReceived`, `totalOnTime`, `totalOverdue`, `totalCompleted` (tùy parent/child), `avgProcessingDays`, `ratio`, `score`, `maxScore`, `scoreDelta`.

### 4.5 Dịch vụ công trực tuyến

`POST https://dichvucong.gov.vn/api/v1/reporting/evaluation/provide-online-tree`

Drill-down TTHC đã xác định. Mẫu dùng `pageSize=200`.

Response: `data.parent` + `data.children[]`.

Trường chính của `parent`: `authorityCount`, `partialCount`, `fullCount`, `onlineDossierCount`, `onlineServiceTotal`, `channelOnlineSum`, `channelDirectSum`, `channelPostalSum`, `channelTotalSum`, `onlineOnTimeSum`, `onlineOverdueSum`, điểm tổng.

### 4.6 Thanh toán trực tuyến

`POST https://dichvucong.gov.vn/api/v1/reporting/evaluation/formality-online-payment-tree`

Không có `formalityId`: tổng hợp tỉnh/cơ quan/xã.

Có `formalityId`: thống kê của riêng TTHC đó.

Mẫu drill-down dùng `pageSize=100`.

Response: `data.parent` + `data.children[]`.

Trường chính: `totalDossierOnlinePaymentSuccess`, `totalDossierFinancialObligation`, `totalDossierOnlineFormalityPaymentSuccess`, `totalFeeDossierFormalityDistinct`, `totalFeeDossierFormality`, `totalFeeFormality`, `ratio`, `totalScore`, `totalMaxScore`; child có cùng nhóm trường và `scoreDelta`.

## 5. Danh mục TTHC

`POST https://dichvucong.gov.vn/api/v1/reporting/formalities`

Ví dụ:

```json
{
  "q": "chứng thực bản sao",
  "currentPage": 1,
  "pageSize": 10
}
```

Item có thể chứa:

- `id`
- `code`
- `name`
- `state`
- `departmentId`
- `publishingDepartmentIds`
- `appliedDepartmentIds`

Danh mục quan trọng vì `formalityId` nối TTHC với các API drill-down.

## 6. Pagination

Hiện tại đã kiểm tra trên giao diện: các API dữ liệu QĐ766 đang được sử dụng theo kiểu **một response chứa toàn bộ dữ liệu hiển thị**, không cần crawler lặp page 1→N trong các mẫu đã kiểm tra.

Tuy vậy, `currentPage`/`pageSize` vẫn xuất hiện trong payload và phải được lưu nguyên request. Crawler không tự tạo vòng lặp trang nếu response không chứng minh có trang tiếp theo.

## 7. Cấu trúc dữ liệu nghiệp vụ

Có hai dạng response chính:

### Dạng A – overview/evaluation/metrics

```text
data
├── overview
│   └── metrics[]
├── evaluation[]
│   └── metrics[]
└── monthlyChart (nếu có)
```

### Dạng B – parent/children

```text
data
├── parent
└── children[]
```

Không ép hai dạng này thành cùng một RAW schema. Chúng chỉ được chuẩn hóa ở lớp analytics/index.

## 8. TTHC drill-down

Đối với nhóm có drill-down:

```text
criterion
  + time period
  + rootDepartmentId
  + formalityId
      ↓
  parent + children / overview + evaluation
```

`appliedDepartmentIds` của API `formalities` là thông tin phạm vi áp dụng của TTHC và phải lưu riêng. Không dùng `children[]` để thay thế `appliedDepartmentIds`.

## 9. Data integrity

Bắt buộc bảo toàn:

- `null` khác `0`.
- giá trị API trả về không tự tính đè lên giá trị gốc.
- mọi trường lạ mới xuất hiện phải được giữ trong RAW.
- metadata chất lượng dữ liệu phải giữ nguyên.
- một snapshot chỉ được đánh dấu `complete` khi tất cả dataset bắt buộc của tổ hợp kỳ/tỉnh đã thành công và hợp lệ.
- nếu schema/API thay đổi bất thường: lưu RAW, đánh dấu schema mismatch và **không ghi đè normalized snapshot cuối cùng đã xác minh**.

## 10. Ghi chú triển khai crawler

Crawler production nên chạy trên máy/môi trường có kết nối DVCQG ổn định, không phụ thuộc GitHub-hosted runner.

Nguyên tắc an toàn:

- tuần tự, không song song hàng loạt;
- delay + jitter;
- retry giới hạn;
- dừng khi 403/429 hoặc response bất thường lặp lại;
- không proxy/IP rotation/WAF bypass;
- checkpoint sau từng dataset;
- lưu RAW ngay sau khi xác minh response;
- chỉ push GitHub sau khi snapshot được đánh dấu hoàn chỉnh.
