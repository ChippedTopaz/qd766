# Audit phân tích và so sánh — 02/10/2026

## Phạm vi

Theo yêu cầu người dùng, tạm dừng kết nối backend ra Internet. Audit mã nguồn,
kiểm thử với fixture/synthetic data và đọc API dashboard localhost đã lưu.
Không gọi DVCQG, không sửa PostgreSQL, .env, circuit, Task Scheduler hoặc bản
triển khai D:\QD766\app. Không thay đổi thiết kế giao diện tổng thể.

## Lỗi được xác minh trong mã và đã sửa

- Kỳ trước chọn kỳ gần nhất có snapshot, có thể bỏ qua tháng/quý thiếu. Nay chỉ
  so sánh kỳ liền trước đúng loại, bao gồm giao năm. Không có snapshot thì để trống.
- Dashboard cộng các điểm nhóm dù nguồn có tổng điểm tỉnh riêng. Nay ưu tiên
  provinceAggregatedScore cho tỉnh/all khi đủ sáu nhóm; Excel dùng cùng view.
- Hàm tổng cộng trên các dataset hiện diện có thể cho tổng giả khi thiếu nhóm.
  Nay kiểm tra đủ sáu nhóm; giữ null khác 0, không xếp hạng tổng thiếu nhóm.
- Nhãn 6/6 cố định được thay bằng số nhóm thực có điểm của cơ quan đang chọn.
- Thời điểm điểm sở/xã trong metadata/file xuất có thể bị gán ngày tổng hợp
  quốc gia. Nay lấy thời điểm chi tiết, cả filename và workbook/context.
- Hiển thị thông báo khi tổng hợp quốc gia và chi tiết dùng hai thời điểm.

Giữ nguyên: DVCTT đơn vị con chưa có tham số thì không dựng chi tiết; Thanh toán
chưa xác minh công thức thì chỉ hiển thị tham số nguồn, không suy diễn điểm.

## Kết quả

- PASS: 79 unittest Python (có cảnh báo deprecation thư viện TestClient).
- PASS: build TypeScript; analytics-integrity, leadership-report, excel-export,
  progress-scoring, csv-export. Excel được kiểm tra roundtrip bằng cả thư viện
  Node và bundle dùng trên browser, không phải kiểm tra hình thức bằng Excel UI.
- PASS: git diff --check.
- PASS read-only API: Cà Mau year-2026/all, 6 datasets, tổng công bố 63,06 và
  tổng sáu nhóm 63,06. Nguồn điểm root là dvcqg-national-summary; danh sách cấp
  gồm PROVINCE_TOTAL, PROVINCE, COMMUNE.
- Xác minh timestamp API: điểm 02/10/2026 10:13:24 +07:00; chi tiết
  01/10/2026 19:08:35 +07:00. Chưa coi chúng là một ảnh chụp đồng thời.

## Chưa xác minh / giới hạn

Chưa đối chiếu trực tiếp số liệu mới trên DVCQG cho toàn bộ 34 tỉnh; chưa nghiệm
thu trình duyệt thật sau deploy; chưa mở file xuất bằng Excel để đánh giá hình
thức. Không coi fixture là dữ liệu thực tế. Không kết luận toàn hệ thống
production PASS, OAuth và thử tải vẫn chưa nghiệm thu.

Bước tiếp theo: cập nhật bản local theo quy trình backup/deploy hiện có, kiểm tra
bằng giao diện cùng kỳ/cùng cấp; sau đó mở rộng đối chiếu dữ liệu đã lưu giữa
tỉnh/sở/xã. Internet/tunnel, thanh toán và redesign giao diện tiếp tục tạm hoãn.
