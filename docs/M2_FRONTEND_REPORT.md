# Báo cáo triển khai frontend M2

## 1. Kiến trúc và mô hình dữ liệu

Frontend được xây lại thành một ứng dụng TypeScript không phụ thuộc framework,
gồm thanh ngữ cảnh toàn cục và sáu không gian nghiệp vụ: Tổng quan, So sánh
theo thời gian, So sánh trong tỉnh, Phân tích TTHC, Gợi ý cải thiện và Chất
lượng dữ liệu. `web/src/types.ts` định nghĩa hợp đồng ViewModel; `analytics.ts`
đảm nhiệm xếp hạng chuẩn 1224, median, P75, percentile, nhóm ngang hàng theo
quy mô và luật gợi ý; `app.ts` chỉ dựng màn hình từ các ViewModel đó.

Tại màn hình Tổng quan, sáu nhóm chỉ tiêu có thể chọn trực tiếp. Mỗi lựa chọn mở
bảng chỉ tiêu hoặc số liệu nghiệp vụ thành phần, điểm chưa đạt, trung vị nhóm
cùng cấp và các đơn vị liền kề trong xếp hạng.

Pipeline `tools/build_web_data.py` đọc sáu snapshot M0, giữ chi tiết metrics và
parameters cho toàn bộ xã/phường, thêm metadata capture và danh mục METRICS.
Danh sách lựa chọn gồm kết quả chung tỉnh, 15 Sở/ban/ngành và 148 xã/phường.
Tập so sánh cấp xã có 148 xã/phường chung trong sáu nhóm. Điểm nguồn luôn là chuẩn;
`null` không được đổi thành 0. Phạm vi TTHC chỉ có năm nhóm; Mức độ hài lòng được
biểu diễn bằng trạng thái nguồn không hỗ trợ.

## 2. Dữ liệu thật và phần chưa có dữ liệu

| Module | Trạng thái | Cách hiển thị |
|---|---|---|
| Điểm 6 nhóm, tổng điểm, thứ hạng, median, P75, percentile | Dữ liệu thật | Tính từ fixture của 148 xã/phường |
| Tháng 8/2026, Quý III/2026, Năm 2026 | Dữ liệu thật | Hiển thị độc lập theo đúng loại kỳ |
| TTHC `2.000815` ở 5 nhóm | Dữ liệu thật | Giữ nguyên metrics/parameters từ API |
| Hài lòng theo TTHC | Nguồn không hỗ trợ | Card giải thích, không thay bằng 0 |
| Delta kỳ trước, chuỗi 6/12/24 kỳ, streak, volatility | Thiếu lịch sử đồng nhất | Empty state “Chưa đủ dữ liệu lịch sử” |
| Công thức chi tiết DVC trực tuyến | Đã khớp 6 fixture M0 trong sai số 0,015 | Điểm API vẫn là giá trị chính thức; công thức chỉ dùng để giải thích |
| Tiêu chí không áp dụng cấp xã | Danh mục có dữ liệu, mapping response chưa đủ | Chưa gắn nhãn vào điểm cụ thể để tránh kết luận sai |
| Impact–Effort | Có bố cục; effort chưa có dữ liệu | Gắn nhãn giả định cần phê duyệt |
| CSV export | Đã triển khai | Bảng điểm 6 nhóm và số liệu thành phần của cơ quan đang chọn; kèm kỳ, độ mới và thời điểm cập nhật; mở bằng Excel |
| Excel XLSX export | Chưa triển khai | Dùng CSV để đối chiếu trước |
| Báo cáo lãnh đạo một trang | Hoạt động | Modal A4, có In/PDF |

Không có dữ liệu mô phỏng trộn vào dữ liệu thật.

## 3. Kiểm tra giao diện và kỹ thuật

- Kiểm tra desktop cho tổng quan: KPI, sáu nhóm, bullet bar, xếp hạng đồng hạng,
  cảnh báo và ưu tiên đều hiển thị đúng từ fixture.
- Kiểm tra responsive ở 390 × 844: bộ lọc xếp lại thành hai hàng, nội dung thành
  một cột và điều hướng chuyển xuống đáy màn hình.
- Đã kiểm tra trực tiếp việc tải `snapshots.json`; trình duyệt không phát sinh
  lỗi hoặc cảnh báo console.
- `npm run build` tái tạo dữ liệu và TypeScript strict compilation.
- `python -m unittest discover -s tests -p "test_*.py"` kiểm tra contract và
  pipeline fixture.
- Màn hình Chất lượng dữ liệu có bộ chuyển trực tiếp để nghiệm thu skeleton,
  empty, malformed/error và insufficient-history.

## 4. Quyết định và giả định cần xác nhận

1. Mặc định hiển thị kết quả chung tỉnh Phú Thọ. Khi có đăng nhập, có thể thay
   bằng cơ quan, đơn vị gắn với tài khoản cán bộ.
2. Xếp hạng chỉ gồm các cơ quan, đơn vị cùng cấp có điểm hợp lệ và dùng standard
   competition ranking (`1224`). Các đơn vị bằng điểm hiển thị số lượng đồng hạng.
3. Percentile đang suy ra từ thứ hạng trong tập hợp hợp lệ; cần chốt cách diễn
   đạt nếu nghiệp vụ muốn percentile theo phân phối có xử lý đồng hạng khác.
4. Cần cung cấp thêm ít nhất hai kỳ cùng loại để mở delta, xu hướng, contribution,
   streak, stagnation và volatility. Tháng, quý và năm hiện có không được coi là
   ba điểm của cùng một chuỗi.
5. Cần khóa mapping từ dòng METRICS sang field response trước khi UI gắn nhãn
   “Điểm tối đa mặc định — không áp dụng cấp xã” cho từng tiêu chí cụ thể.
6. Công thức và trọng số chi tiết của DVC trực tuyến vẫn để mở. Mọi what-if và
   target planner liên quan được khóa cho tới khi có công thức được phê duyệt.
7. Dữ liệu lịch sử chỉ được thu thập từ ngày 01/01/2026. Không nhập, thu thập
   hoặc hiển thị dữ liệu năm 2025 trở về trước. Chuỗi tháng bắt đầu từ tháng
   1/2026 và chuỗi quý bắt đầu từ quý I/2026.
