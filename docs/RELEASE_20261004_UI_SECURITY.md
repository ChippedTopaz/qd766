# Đợt cập nhật giao diện và phòng vệ phiên — 04/10/2026

## Phạm vi

- Tổng quan có ba tab; chuyển nhóm bằng thẻ mũi tên lớn.
- Tăng điểm/tăng thứ hạng màu xanh, giảm màu đỏ, thiếu dữ liệu trung tính.
- Công thức chỉ hiển thị nhóm đang chọn; giữ nội dung nguồn.
- Tải Excel tại bảng so sánh/xếp hạng, giữ các cột và dòng đang hiển thị.
- Token CSRF sai/non-ASCII bị từ chối thay vì gây lỗi nội bộ.
- Không đổi schema, số dư Credit, worker hoặc công thức tính điểm.

## Kiểm chứng

223 kiểm thử backend đạt. Typecheck và các kiểm thử formula, comparison-export,
summary renderer, overview tabs, change-tone, Bento, Excel và leadership đạt.
Gói Netlify được kiểm tra không chứa fixtures, cấu hình bí mật hoặc source maps.

Backup phiên bản Git và gói Netlify trước cập nhật:
`.tmp-release-preflight/20261004-120815`.

## Kiểm kê dữ liệu chỉ đọc lúc khoảng 12:02 ngày 04/10/2026

15 kỳ tổng hợp toàn quốc hợp lệ 34 tỉnh × 6 nhóm:
tháng 1–10, quý I–IV và năm 2026. Kỳ hiện tại được cập nhật khoảng
11:16 ngày 04/10, chưa quá hạn 2 giờ tại thời điểm kiểm kê.

Chi tiết tháng 10, quý IV, năm 2026: 34 tỉnh, mỗi tỉnh đủ 6 nhóm;
không bản chi tiết kỳ hiện tại nào quá hạn 72 giờ.
Tháng 10 không phát hiện cơ quan đã có điểm nhưng thiếu nhóm.
Quý IV và năm còn ba cơ quan thiếu Công khai minh bạch, Số hóa hồ sơ,
Mức độ hài lòng:

- Sở Du lịch — Thành phố Huế.
- Trung tâm Phục vụ hành chính công tỉnh Quảng Ninhh (tên nguồn).
- Ban Quản lý — Đắk Lắk.

Đủ dữ liệu cấp tỉnh không đồng nghĩa mọi cơ quan đều đủ điểm thành phần.
Chi tiết tháng 1 và 9 mới có 2 tỉnh; tháng 2–8 và quý I–III mới có 1 tỉnh.
Tháng 9 và quý III mỗi kỳ có một bản chi tiết thu trước khi kỳ kết thúc.
Không xác nhận đây là số liệu chốt cuối kỳ.
Chi tiết DVCTT cơ quan trực thuộc chưa có từ nguồn là hạn chế đã được chấp nhận,
không tự suy diễn điểm thành phần hay công thức thanh toán chưa rõ.

## Lịch cào và triển khai

Cấu hình lịch: tổng hợp mỗi giờ; kiểm tra làm mới tỉnh hằng ngày 02:15,
so le tháng/quý/năm theo độ mới 72 giờ, có circuit protection.
Nhật ký tỉnh ngày 04/10 lúc 02:15 kết thúc exit 0, trạng thái fresh.
Nhật ký tổng hợp ngày 04/10 lúc 11:16 kết thúc exit 0.
Chạy dry-run lịch tỉnh trả fresh, không tạo job hoặc thay đổi circuit.

Windows từ chối đọc Task Scheduler trong phiên agent. Script restart public
backend dừng ngay ở kiểm tra task, chưa dừng bất kỳ dịch vụ nào.
Admin cần chạy `tools/restart_public_backend.ps1` tại máy để áp dụng sửa backend.
Không coi mã nguồn mới là đã hoạt động trước khi restart thành công.
