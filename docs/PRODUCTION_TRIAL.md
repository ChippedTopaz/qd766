# Đưa bản dùng thử lên tên miền chính

## Phạm vi và trạng thái

Người quản trị đã nghiệm thu Google thật, tài khoản thường được gán Phú Thọ,
dashboard/so sánh/tháng/quý/năm và đăng xuất tại api.bochiso766.com.
Repo chuẩn bị task riêng và proxy Netlify. Chưa đăng ký task, chuyển DNS,
đổi callback hoặc xác nhận tên miền chính đã hoạt động trong lượt chuẩn bị này.
Không bật paid requests, credit thử nghiệm hoặc thanh toán.

## 1. Chạy tự động — thực hiện trong PowerShell mới tại repo

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\register_public_backend_task.ps1
```

Script kiểm tra cấu hình trước, chỉ đăng ký `QD766 Public Backend`, không sửa năm
task quản trị/worker/backup hiện có, không tự dừng server hoặc khởi chạy bản trùng.
Nếu task đã tồn tại, dừng; dùng `-ReplaceExisting` chỉ sau khi xem cấu hình cũ.
Khi thay task, lưu XML cũ trong `.tmp-public-task-backups` trước.
Task chạy quyền người dùng, khởi động **khi người đó đăng nhập Windows**, không
chạy trước đăng nhập hoặc sau khi log off. Máy production phải giữ phiên Windows
đăng nhập; khóa màn hình được. Đây chưa phải dịch vụ Windows luôn chạy.
Không đổi máy sang tự động đăng nhập, không tắt chế độ bảo mật Windows.

Sau khi đăng ký, ở cửa sổ foreground 8769 nhấn Ctrl+C. Có gián đoạn ngắn, không
đóng cửa sổ 8767. Quay lại PowerShell quản trị task và chạy:

```powershell
Start-ScheduledTask -TaskName "QD766 Public Backend"
Start-Sleep -Seconds 3
Invoke-RestMethod http://127.0.0.1:8769/api/v1/health/ready
Get-ScheduledTask -TaskName "QD766 Public Backend" | Select-Object TaskName,State
```

Kết quả kỳ vọng health `ok`, task `Running`. Log `.tmp-public-logs/public-backend.log`
được lưu riêng; xoay log >10 MB lúc khởi chạy tiếp theo, không xóa log cũ.
Tự thử lại tối đa ba lần khi thoát lỗi; không hứa giám sát 24/7 hoặc tự sửa mất mạng.
Task đang chạy có LastTaskResult 267009 có thể chỉ là “currently running”, không
chỉ dựa vào LastTaskResult để kết luận failure.

Restart: `Stop-ScheduledTask` rồi `Start-ScheduledTask` tên task mới. Không kill
mọi python.exe hoặc dừng các task backend/worker cũ. Nếu task lỗi, đọc log cuối;
không gửi nội dung `.env.public` hoặc callback chứa code/state.

## 2. Netlify và Cloudflare DNS

1. Push commit đã nghiệm thu lên GitHub main để Netlify build cấu hình proxy:
   `/api/*` → `https://api.bochiso766.com/api/:splat`. Chỉ backend bảo vệ 8769.
2. Trong đúng site `bochiso766.netlify.app`, thêm custom domain `bochiso766.com`.
   Giữ site Ấm Siêu Tốc độc lập. Không chuyển nameserver khỏi Cloudflare Registrar.
3. Dùng chính xác DNS record Netlify hiển thị cho apex; thiết lập record tương ứng
   trong Cloudflare, ban đầu DNS only để kiểm chứng TLS Netlify. Không sửa record
   `api` của tunnel, không đoán địa chỉ IP Netlify, không proxy apex vào 8769.
4. Chờ Netlify cấp HTTPS rồi chọn primary domain `bochiso766.com`.
   Kiểm tra `https://bochiso766.com/api/v1/health/live` và access-policy.

Custom headers Netlify không áp dụng vào response proxied theo tài liệu:
backend đã trả Cache-Control no-store cho dữ liệu phiên đăng nhập. Cần kiểm tra
thật rằng Set-Cookie/Location không bị đổi sai và nội dung phiên không bị cache.
Proxy có timeout 26 giây; dashboard không được cào đồng bộ trong request.

## 3. Chuyển callback Google — chỉ khi Netlify HTTPS/proxy đã hoạt động

1. Thêm (chưa xóa callback api cũ) vào OAuth Web client:
   `https://bochiso766.com/api/v1/auth/google/callback`.
2. Sao lưu `.env.public` **tại máy**, không commit/upload. Thay đúng dòng
   `QD766_GOOGLE_REDIRECT_URI` thành callback mới; client ID/secret giữ nguyên.
3. Chạy `start_public_backend.py --check`, rồi restart task mới.
4. Đăng nhập bắt đầu từ **bochiso766.com**, không bắt đầu từ api hoặc netlify.app.
   Cookie flow/phiên host-only, Secure/HttpOnly: domain mới phải đăng nhập lại.
   CORS vẫn đóng; frontend gọi API cùng origin qua proxy, không mở wildcard CORS.

Nếu lỗi: khôi phục dòng callback api cũ, restart task rồi dùng địa chỉ api đã
nghiệm thu. Netlify cho rollback deployment trước nếu cần. Không xóa account/DB.

## 4. Nghiệm thu trước mời người dùng

- HTTPS, đăng nhập/hủy consent/đăng xuất/đăng nhập lại.
- Tài khoản chưa gán tỉnh hiện chờ duyệt; tài khoản bị disable không đọc được.
- Tài khoản Phú Thọ không lấy được snapshot chi tiết tỉnh khác; bảng so sánh chỉ
  trả điểm cấp tỉnh. Không mở raw snapshots/TTHC/system-status/collection jobs.
- Kiểm tra hai tài khoản riêng không thấy phiên, tên hoặc thư viện của nhau;
  đăng xuất rồi F5 không đọc được dashboard bằng phiên cũ.
- Month/quarter/year, phân biệt thời điểm điểm tổng hợp/chi tiết, Excel đúng dữ liệu.
- Test restart task và sau đăng nhập Windows; health/readiness thật, backup gần đây
  và diễn tập restore riêng trước mở rộng. Chưa coi tồn tại file backup là restore PASS.
- Kiểm tra rate limit/auth traffic, giám sát outage, điều khoản và chính sách riêng tư
  trước mở rộng; các phần này chưa được xác minh chỉ bằng kiểm thử mã.
- Không quảng cáo là production HA: máy cơ quan hoặc Internet mất là API ngừng.

Nguồn: [Netlify rewrites/proxies](https://docs.netlify.com/manage/routing/redirects/rewrites-proxies/).
