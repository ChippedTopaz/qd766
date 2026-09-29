# Danh mục TTHC theo tỉnh từ Ấm Siêu Tốc

QD766 sao chép đúng logic của mục **Thống kê danh mục thủ tục hành chính**
trên Ấm Siêu Tốc. Nguồn là danh mục toàn quốc `data/index.json` và cấu hình
ngành dọc `niemyet/isVertical.json`. Nhánh `niemyet-data` phục vụ trang Niêm
yết và không phải nguồn để tính danh mục thống kê này.

Cả Ấm Siêu Tốc và QD766 dùng chung UUID, mã và tên TTHC do Cổng DVCQG công
bố. QD766 không cào hoặc sinh một danh mục thứ hai; nó chỉ đọc snapshot đã
được Ấm Siêu Tốc chuẩn hóa và áp dụng bộ lọc tỉnh/cấp thực hiện.

## Quy tắc lựa chọn

1. Chỉ xét TTHC có cấp thực hiện chứa cấp tỉnh và/hoặc cấp xã, phường.
2. Nếu tắt “Tính cả TTHC nội bộ”, loại các mục có loại TTHC chứa `nội bộ`.
3. Whitelist theo mã, lĩnh vực hoặc cơ quan công bố được áp dụng trước và
   thắng blacklist.
4. Nếu không thuộc whitelist, blacklist theo mã, lĩnh vực hoặc cơ quan công
   bố sẽ đánh dấu thủ tục ngành dọc.
5. Giữ thủ tục do tỉnh đang chọn công bố; loại thủ tục địa phương khác.
6. Với thủ tục do bộ/ngành công bố, chỉ giữ thủ tục không thuộc ngành dọc.
7. Một thủ tục có cả hai cấp được tính vào cả số cấp tỉnh và số cấp xã, nhưng
   chỉ tính một lần trong tổng số.

Đối chiếu dữ liệu ngày 28/09/2026 cho Phú Thọ khi bật TTHC nội bộ cho kết quả
đúng như giao diện Ấm Siêu Tốc: **2.227 tổng số, 1.914 cấp tỉnh, 439 cấp xã**.
Khi tắt TTHC nội bộ: **2.115 tổng số, 1.813 cấp tỉnh, 413 cấp xã**.

## API QD766

- `GET /api/v1/province-catalog`: danh sách 34 tỉnh/thành phố.
- `GET /api/v1/province-catalog/25`: toàn bộ danh mục tính cho Phú Thọ.
- `GET /api/v1/province-catalog/25?level=province`: chỉ cấp tỉnh.
- `GET /api/v1/province-catalog/25?level=ward`: chỉ cấp xã/phường.
- Thêm `include_internal=false` để loại TTHC nội bộ.
- `GET /api/v1/province-catalog/25/preview`: xem trước theo kỳ, cấp, lĩnh vực
  và từ khóa; trả số đã có trong PostgreSQL và số còn thiếu.

Kết quả trả cả `totalCount`, `provinceCount`, `wardCount`, thời điểm cập nhật
danh mục gốc và mã kiểm tra SHA-256 của bộ quy tắc.

## Cache và phạm vi

Ba tài liệu nguồn chỉ được tải lại khi cache hết hạn. Danh mục bật và tắt
TTHC nội bộ có cache riêng. Lớp này chỉ xác định danh sách TTHC; nó không tự
gửi yêu cầu DVCQG hay tạo hàng nghìn job.

## Luồng người dùng thống kê theo TTHC

Việc đổi kỳ hoặc chọn TTHC chỉ cập nhật bộ lọc và kiểm tra snapshot đã có;
không tự tạo job. Nếu chưa có dữ liệu, giao diện hiển thị trạng thái “Sẵn sàng
thống kê”. Chỉ khi người dùng bấm **Thống kê**, backend mới tạo một job chống
trùng trong hàng đợi. Giao diện theo dõi job ở nền và thông báo khi snapshot
hoàn chỉnh đã sẵn sàng; nếu người dùng đã cho phép thông báo trình duyệt, hệ
thống đồng thời gửi thông báo hệ thống.

Màn hình cho phép lọc theo cấp tỉnh/cấp xã, lĩnh vực, mã hoặc tên TTHC; phân
trang toàn bộ kết quả và hiển thị trước số TTHC đã có dữ liệu trong PostgreSQL
cùng số còn thiếu. Các thao tác lọc và phân trang chỉ đọc dữ liệu. Khi chọn
một TTHC và bấm **Thống kê**, backend đối chiếu UUID và mã với danh mục nguồn
trước khi ghi metadata vào bảng `formalities`; tên gửi từ trình duyệt không
được sử dụng làm nguồn tin cậy.

Chế độ **Toàn bộ kết quả sau lọc** tạo một bản ghi cha trong
`collection_batches` và checkpoint từng TTHC trong `collection_batch_items`.
Các snapshot đã có được đánh dấu `skipped`; các mục còn thiếu ở trạng thái
`pending`. Hệ thống chỉ tạo một `collection_job` cho mục đầu tiên. Sau khi mục
đó hoàn tất, worker mới tạo job cho mục kế tiếp. Vì vậy một batch 2.227 TTHC
không biến thành 2.227 request đồng thời. Khi gặp safety stop, item và batch
được đánh dấu `halted`; sau khi quản trị viên xử lý circuit, batch có thể tiếp
tục từ checkpoint trên màn hình Vận hành.

API batch:

- `POST /api/v1/formality-batches`: tạo hoặc lấy lại batch chống trùng.
- `GET /api/v1/formality-batches`: danh sách batch gần đây.
- `GET /api/v1/formality-batches/{id}`: tiến độ batch.
- `POST /api/v1/formality-batches/{id}/resume`: tiếp tục batch đã dừng.

Biến môi trường tùy chọn:

- `QD766_PROVINCE_CATALOG_INDEX_URL`
- `QD766_PROVINCE_CATALOG_VERSION_URL`
- `QD766_PROVINCE_CATALOG_RULES_URL`
- `QD766_PROVINCE_CATALOG_CACHE_TTL_SECONDS`
- `QD766_PROVINCE_CATALOG_TIMEOUT_SECONDS`
