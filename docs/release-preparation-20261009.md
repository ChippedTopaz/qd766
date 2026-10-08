# Phát hành bản gộp đã duyệt 09/10/2026

Base: 795e27e. Chưa xác nhận deploy cho đến khi backend restart và Netlify phát hành được kiểm chứng.

## Phạm vi

- Tổng quan ↔ Chi tiết: bảy khối điểm, motion 900ms, mặc định tổng hợp sáu nhóm, bàn phím và màn hình nhỏ.
- Đổi nhóm/Điểm tổng hợp: trượt ngang theo hướng chọn (520ms), mobile fade, giảm chuyển động, cleanup khi đổi nhanh/scroll/resize. Bản sao bảng cũ chỉ dùng trang trí, inert, không ID hay data-action; không request mới.
- Tiến độ: mô tả tỷ lệ quá hạn và công thức đối chiếu điểm gọn theo yêu cầu. Không sửa logic tính hoặc số liệu nguồn.
- Số hiệu công thức hiển thị 3.5a; ID lưu trữ vẫn 3.5, không thay dữ liệu đã nhập hoặc lịch sử.
- Bảng xếp hạng: số câu trả lời đúng COUNT(DISTINCT question_id), không đếm lại câu đúng ở vòng khác; chuỗi/kỷ lục không đổi.
- DVC trực tuyến: bỏ khối ghi chú được chỉ định, bảng chi tiết hiển thị đầy đủ không scrollbar nội bộ; các nhóm khác không thay đổi.
- Sidebar Tra cứu theo TTHC dưới So sánh theo cơ quan; Yêu cầu của tôi đổi thành Lịch sử tra cứu. Cấp thực hiện mặc định theo cơ quan được gán (xã/phường → xã; sở/ngành → tỉnh; tỉnh xem toàn tỉnh → tất cả), giữ lựa chọn thủ công.

## Kiểm tra và bảo toàn

- TypeScript PASS; 408 kiểm thử backend PASS; 67 tệp frontend PASS và kiểm thử gói Netlify riêng PASS (68 tệp).
- Gói mới ở outputs/release-preparation-20261009/validation/netlify-public; không fixture, secrets, source maps hay preview. Có dist/overview-motion.js.
- PUBLIC_CONFIG PASS: real wallet, shared registration, Gemini, analysis queue; không chạy phân tích/thu thập thật trong kiểm thử.
- Không migration hoặc ghi database. Không thay quyền, Credit, lịch thu thập, API phân tích, công thức lưu hay lịch sử.
- Không đưa .tmp-*, outputs, backups, snapshot cấu hình, tài liệu hay dữ liệu cào local vào commit/deploy.

## Backup

- PostgreSQL: outputs/release-preparation-20261009/database-backups/qd766-20261009-000809.dump.
- 44.865.106 bytes; SHA256 9E54C267A6D198D6BBA822580C87A8533BA858181DD156E429A561507CF50998.
- Source trước phát hành: previous-795e27e.zip; source đã duyệt: reviewed-source/ trong cùng thư mục outputs. Chỉ local.

## Còn lại

Windows từ chối Get-ScheduledTask trong phiên agent. Chủ hệ thống chạy tools/restart_public_backend.ps1 và gửi PUBLIC_BACKEND_READY / PUBLIC_RUNTIME_POLICY. Sau đó push commit và đối chiếu tài nguyên public với gói đã kiểm tra; không coi push thành deploy hoàn tất.
