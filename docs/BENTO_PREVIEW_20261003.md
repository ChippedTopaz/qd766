# Tổng quan Bento — bản chờ duyệt

## Sao lưu và phạm vi

- Bản chuẩn: `e4307bd`, tag `backup/pre-bento-20261002`.
- Nhánh thiết kế: `design/overview-bento-20261002`. Main và ứng dụng triển khai ở cổng 8767 chưa thay đổi.
- Chỉ đổi UI Tổng quan, icon/màu sidebar và style bộ lọc. Không đổi API, schema, công thức, xếp hạng, cấu trúc bảng chi tiết hoặc logic gợi ý.
- Hero giữ tổng điểm nguồn và điểm tối đa từ view hiện có; các nhóm giữ điểm tối đa 18/20/12/22/18/10 trong phạm vi tất cả TTHC.
- Xu hướng dùng tối đa 12 kỳ cùng loại đến kỳ đang chọn. Nhóm quy đổi phần trăm điểm tối đa để dùng chung trục 0–100, không phải tỷ lệ hồ sơ. Kỳ thiếu dữ liệu ngắt đường.
- Cơ cấu dùng tổng điểm sáu nhóm làm mẫu số; không ép tổng điểm nguồn bằng tổng các giá trị đã làm tròn. Thiếu nhóm không hiển thị cơ cấu.
- Thông tin cập nhật dùng disclosure mặc định thu gọn, vẫn giữ nhãn chất lượng/kỳ/tổng hợp. Không suy diễn TTHC gây mất điểm.

## Preview riêng, chỉ đọc

Chạy từ thư mục repo:

```powershell
.\.venv\Scripts\python.exe .\tools\preview_frontend.py
```

Mở http://127.0.0.1:8768/. Preview đọc API dashboard của backend hiện có ở 8767 và phục vụ frontend trong nhánh thiết kế. Không có dữ liệu mẫu thay thế nếu backend không sẵn sàng. Chỉ cho phép các GET dashboard/access-policy; POST bị từ chối. Trang Vận hành/TTHC không phải phạm vi nghiệm thu qua proxy này.

Đóng preview bằng Ctrl+C trong terminal chạy preview. Không dừng backend hoặc worker.

## Kiểm thử

- PASS: build TypeScript, 85 kiểm thử Python.
- PASS: analytics, leadership, Excel, progress, CSV, summary-only renderer, Bento và gói Netlify trong thư mục build tạm riêng.
- Trình duyệt dữ liệu thật: tìm/chọn Phú Thọ bằng TomSelect; chọn tháng 9/2026; hiển thị chuỗi tháng 1–9 và cơ cấu sáu nhóm; bấm Tiến độ giải quyết mở đúng bảng chi tiết hiện có; mở/thu gọn thông tin dữ liệu.
- Kiểm tra breakpoint nhỏ: sáu thẻ, bộ lọc không tràn ngang; bảng chi tiết cuộn trong khung của nó. Đã trả viewport về mặc định.
- Chưa được người dùng duyệt thẩm mỹ, chưa deploy hoặc push. Không chạy `update_qd766.ps1` từ nhánh thiết kế này: script hiện push main nhưng deploy checkout hiện tại.

## Khôi phục

Sau khi commit/sao lưu mọi chỉnh sửa trong nhánh thiết kế, dùng `git switch main` để trở về bản chuẩn và tải lại preview. Không dùng reset/clean. Backend/PostgreSQL vẫn giữ nguyên.

Chỉ sau khi người dùng duyệt: tích hợp nhánh thiết kế vào main, chạy kiểm thử lại rồi mới dùng quy trình cập nhật triển khai hiện có. Nếu cần bỏ thiết kế sau tích hợp, revert commit UI, không khôi phục database.
