# Biểu chi tiết nhóm chỉ tiêu

Nút Tải biểu Excel nằm cạnh tên nhóm trong tab Chi tiết điểm số.
Có hai lựa chọn: nhóm đang xem hoặc cả 6 nhóm, mỗi nhóm một sheet.

Endpoint GET `/api/v1/dashboard/group-export` chỉ đọc snapshot đã lưu.
Không tạo job, gọi DVCQG hoặc thay đổi Credit. Middleware xác thực tỉnh,
cơ quan, lời mời và quyền TTHC như dashboard selection. Payload xuất được
lọc lại thành danh sách cơ quan được phép; không sử dụng danh sách peer
còn giữ trên dashboard để tạo file của tài khoản cấp đơn vị.

Biểu giữ điểm nguồn, số 0 và ô thiếu riêng biệt. Chỉ tiêu thành phần gồm
số lượng đạt, tổng số, tỷ lệ, điểm ghi nhận, điểm tối đa. Tham số nghiệp vụ
có tên tiếng Việt nằm ở các cột riêng; không tự tạo công thức chấm điểm.
Không xuất scoreDelta, mã trường kỹ thuật, raw/extras hay sheet ẩn.
Chưa có chi tiết kỳ thì báo lý do, không tạo file rỗng hoặc lấy kỳ khác.
Nhóm còn thiếu vẫn có sheet và trạng thái thiếu, không mặc định bằng 0.

Phong cách xanh–tím, hàng xen kẽ nhạt. Metadata gọn 4 dòng không merge.
Chỉ merge nhãn tiêu đề hai tầng; không merge bất kỳ ô dữ liệu nào.
Freeze ba cột nhận diện và sáu dòng đầu, có bộ lọc, số và tỷ lệ dạng numeric.
Tên file giữ quy tắc tên đơn vị-ngày cập nhật-chitiet-ngày giờ xuất.xlsx.

Backup trước triển khai: `.tmp-release-preflight/group-export-20261005-065145`.
Chỉ cập nhật mã nguồn và assets thử nghiệm; chưa push/deploy hoặc restart public.
Nếu máy chạy 8771 chưa nạp route mới, chạy tại PowerShell của người vận hành:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\restart_local_google_trial.ps1
```

Script xác minh đúng launcher của listener 8771, giữ chế độ source-wallet,
không chạy lại các cờ seed/activation/mock-worker. Không sửa production DB,
không tác động 8767, 8769 hoặc worker. Giữ nguyên cả lựa chọn schema
expiry rehearsal agency/province nếu tiến trình hiện tại dùng chế độ này.
Chấp nhận đường dẫn launcher tuyệt đối hoặc tương đối đã biết, kết hợp xác minh
đúng Python của dự án, listener loopback và access-policy của bản Google local.
