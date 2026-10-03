# Dùng thử theo lời mời

## Trạng thái

Mã nguồn đã triển khai và kiểm thử cục bộ; **chưa nâng cấp database thật, chưa
cấp quyền quản trị thật và chưa khởi động lại production**. Không chạy restart
trước khi hoàn thành migration và bootstrap bên dưới. Không dùng `update_qd766.ps1`
thay thế quy trình này: lệnh đó còn đẩy GitHub và thay bản office.

## Quy tắc

- Public 8769 bắt buộc lời mời; người chưa được mời không có tài khoản mới hoặc
  phiên truy cập dữ liệu. Tài khoản cũ chưa được mời cũng cần nhận lời mời.
- `vietnt89@gmail.com`: cấp vai admin đúng tài khoản Google đã có bằng công cụ
  local, không tự nâng quyền theo email trong luồng đăng nhập. Không đổi plan,
  credit hoặc tạo Google identity khác.
- Admin tạo link một lần, hạn 1–30 ngày, thu hồi trước khi dùng. Có thể gắn email
  (khuyến nghị). Không gắn email thì bất cứ người có link nào cũng có thể nhận.
- Token ngẫu nhiên 256 bit; DB chỉ lưu hash. Link dùng fragment `/#invite=...`
  để token không xuất hiện trong URL gửi HTTP; frontend xóa fragment ngay, gửi
  token bằng POST. OAuth challenge gắn invitation; kiểm tra lại và nhận lời mời
  một lần trong cùng transaction tạo tài khoản/phiên.
- Quyền `province`: xem tỉnh và các cơ quan trực thuộc. Quyền `agency`: xem chi
  tiết đúng cơ quan được gán; cơ quan khác chỉ có điểm để so sánh, không có
  metrics/parameters. API lọc trên bản sao để không làm hỏng cache chung.
- Gán cơ quan phải kiểm chứng thành viên từ snapshot tỉnh đã lưu. Không tin
  tên tỉnh/cơ quan do trình duyệt cung cấp. Đổi quyền/khóa thu hồi phiên cũ.
- Giao diện `/admin.html`: tạo/thu hồi lời mời, tìm tài khoản, đổi quyền/khóa,
  nhật ký. Mọi thao tác ghi bắt buộc session admin và CSRF. Không tự cấp quyền
  admin khác; không thay credit, circuit hay tạo job. Thu phí vẫn tắt.
- Danh sách hiện giới hạn 500 tài khoản, 200 lời mời, 100 log mới nhất phù hợp
  dùng thử nhỏ; phân trang và nhật ký chi tiết UI sẽ mở rộng khi cần.

## Đưa lên bản đang chạy (PowerShell tại thư mục repo)

1. Sao lưu PostgreSQL bằng lệnh riêng; lưu đường dẫn `FILE=` được in ra:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\backup_postgresql.ps1
```

2. Thay đường dẫn ví dụ bằng chính file vừa sao lưu. Công cụ kiểm tra hash trước
   khi chạy migration cộng thêm bảng/cột, không cào hay thay dữ liệu điểm:

```powershell
.\.venv\Scripts\python.exe .\tools\migrate_trial_access.py --backup "F:\QD766\backups\qd766-YYYYMMDD-HHMMSS.dump"
```

3. Cấp admin cho duy nhất Google account có email chính xác của anh; thu hồi
   phiên của admin để đăng nhập lại nhận quyền:

```powershell
.\.venv\Scripts\python.exe .\tools\bootstrap_trial_admin.py --confirm
```

4. Biên dịch frontend (không sửa dữ liệu), rồi khởi động lại public instance:

```powershell
.\node_modules\.bin\tsc.cmd
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\restart_public_backend.ps1
```

5. Push code đã commit lên GitHub để Netlify deploy giao diện admin mới. Đăng
   nhập lại bằng tài khoản admin trên bochiso766.com, mở **Quản trị dùng thử**.
   Không gửi lời mời thật trước khi deploy hoàn tất.

## Nghiệm thu thật

- Admin đăng nhập, mở quản trị, chọn tỉnh/quyền/cơ quan, gắn email và tạo link.
- Tài khoản Google mới không có link bị chặn. Có link đúng email đăng nhập
  được, về trang chủ đúng quyền, credit 0; dùng lại link bị chặn.
- Link sai email/hết hạn/thu hồi không vào được; sai email không tiêu hủy link.
- Tài khoản agency không thấy chọn cơ quan khác; sửa query tỉnh khác bị 403.
- Thay quyền và khóa tài khoản thu hồi phiên; đăng nhập lại sau khóa bị chặn.
- Admin và người thử vẫn không gọi được circuit/collection endpoints; không
  có thu phí, không phát sinh job do chọn kỳ.
- Đồng thời PostgreSQL và UI qua Google thật **chưa nghiệm thu** ở bản này.

## Quay lại

Mốc mã nguồn trước thay đổi: `d38ed13`. Migration chỉ cộng thêm cấu trúc, nên
code cũ có thể chạy lại với DB mới (đăng nhập sẽ quay về cơ chế duyệt cũ).
Không downgrade hoặc restore dump sau khi đã có người nhận lời mời mới mà
chưa đánh giá mất dữ liệu. Khi cần rollback, dùng checkout riêng ở mốc cũ,
đổi task sang checkout đó và rollback Netlify deploy; giữ nguyên dump/hash.
