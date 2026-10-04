# Google thật trên local, dữ liệu/credit mô phỏng

Không deploy Netlify. Không sửa `.env.public` hoặc callback production.
Server riêng: http://127.0.0.1:8771/; chỉ loopback, không dùng Tunnel.
Database `qd766_credit_test`, schema `credit_google_trial`, không đọc dữ liệu thật.
Danh mục và điểm được mô phỏng; giá 3 credit không phải giá thương mại.

## Google

Trong OAuth client hiện có, thêm Authorized redirect URI (không xóa các URI cũ):

```text
http://127.0.0.1:8771/api/v1/auth/google/callback
```

Không cần gửi client secret. Launcher đọc ID/secret đã lưu trong `.env.public`,
nhưng dùng callback local cố định riêng. Ngày 03/10/2026, chủ tài khoản đã xác nhận
đăng nhập Google thật và nhận lời mời thành công trên 8771; quyền admin local
đã được cấp. Chưa xác nhận toàn bộ luồng credit qua tài khoản Google thật.

## Khởi động và cấp quyền admin local

Frontend biên dịch riêng vào `.tmp-credit-trial/site/dist`; dùng cùng tài sản UI của
bản local, không ghi vào `web/dist`. Cần build bằng launcher thử 8770 khi mã thay đổi.
Sau khi tài sản đã được chuẩn bị, chạy trong thư mục dự án:

```powershell
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py
```

Trong PowerShell khác, tạo link mời local cho chủ tài khoản:

```powershell
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py --create-owner-invite
```

Mở link OWNER_INVITE bằng cùng trình duyệt, đăng nhập `vietnt89@gmail.com`.
Link một lần, hạn một ngày, chỉ đúng email được nhận; không chia sẻ link.
Sau khi Google xác minh và nhận lời mời thành công:

```powershell
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py --bootstrap-owner
```

Đăng xuất/đăng nhập lại rồi vào Quản trị dùng thử. Lệnh chỉ cấp admin trong schema
thử cho chủ tài khoản đã được Google xác minh và đã nhận lời mời, không tự cấp credit.
Tài khoản khác phải có link mời local; admin gán tỉnh/cơ quan và cấp credit local.

Nếu quay về `?login=invite-required`, mở lại link mời rồi đăng nhập đúng email
nhận lời mời. Cookie lời mời có hạn 10 phút; link mời chưa dùng có hạn một ngày.
Không chỉ mở trang chủ để đăng nhập lần đầu khi cookie lời mời đã hết hạn.

## Kiểm chứng tiếp theo qua Google thật

1. Admin tạo lời mời cho tài khoản Google thứ hai, gán tỉnh/cơ quan thử.
2. Admin cấp 30 credit thử và bật quyền khai thác riêng; có số dư không tự có quyền.
3. Người nhận đăng nhập qua link mời ở profile trình duyệt khác, kiểm tra đúng phạm vi.
4. Yêu cầu một TTHC mới: xác nhận giữ 3 credit, không tự cào khi chọn kỳ.
5. Chạy mock worker một lần theo hướng dẫn dưới; kiểm tra thu 3 credit, dữ liệu
   vào thư viện và có thông báo hoàn thành. Mở lại/F5 không thu thêm credit.
6. Tài khoản khác yêu cầu cùng dữ liệu: vẫn thu riêng 3 credit nhưng không tạo job mới.

Chỉ đánh dấu các mục đạt sau khi kiểm tra thực tế; không triển khai production.

## Hoàn thành yêu cầu bằng dữ liệu giả

Không có worker thật chạy nền. Sau khi người dùng tạo yêu cầu và giữ credit,
có thể xử lý một job bằng processor mô phỏng:

```powershell
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py --run-mock-worker-once
```

Để kiểm chứng hoàn credit khi job thất bại, tạo hai yêu cầu cùng dữ liệu mới rồi chạy:

```powershell
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py --run-mock-worker-once --mock-outcome failure
```

Chế độ này cố ý phát sinh lỗi mô phỏng và giới hạn một lần thử để job kết thúc
thất bại qua worker thật. Không sửa số dư trực tiếp, không mở circuit, không gọi
nguồn bên ngoài. Kiểm tra hai yêu cầu được hoàn, sổ giao dịch có `release` và
thông báo `data-failed`; chỉ chạy sau khi xác nhận đúng job thử đang chờ.

Lệnh dùng worker và quy tắc lưu/settle thật nhưng dữ liệu sáu nhóm là giả, không
gọi DVCQG. Đợi tối đa khoảng 60 giây cho cache local hết hạn rồi tải lại Dashboard.

Cookie localhost dùng chung giữa các cổng: chuyển vai ở bản 8770 có thể thay phiên
8771. Nên dùng trình duyệt/profile riêng cho Google local. Cookie production ở
bochiso766.com không bị ảnh hưởng.

## An toàn

## Quản trị phân mục và phạm vi toàn quốc

Admin local có sidebar Tài khoản, Credits, Mời dùng thử, Nhật ký quản trị.
Phạm vi mới `national` là quyền xem dữ liệu mọi tỉnh, không phải vai trò admin.
Không mở API vận hành hoặc dữ liệu tổng hợp thô; dữ liệu theo TTHC vẫn cần quyền
khai thác và entitlement trả credit. Tỉnh được gán là tỉnh mặc định khai thác TTHC,
không tự mở yêu cầu TTHC trên toàn quốc.

Schema `credit_google_trial` đã được nâng constraint qua cờ
`--upgrade-national-scope`; không thay đổi tài khoản hoặc phiên có sẵn.
Migration production `20261003_0012` chỉ được chuẩn bị, chưa áp dụng.
Trước deploy cần backup và nâng các migration chưa áp dụng theo quy trình.

HTTP chỉ được mở bởi cờ programmatic local_google_trial, với callback và tên
database cố định, hostname/client/origin loopback. Cờ này không được đọc từ môi
trường. Production vẫn yêu cầu HTTPS và không bật credit thử.
Không truy cập các API vận hành, thay Task Scheduler, bật payment hoặc đăng ký tunnel.

## Credit theo nguồn — thử nghiệm ngày 04/10/2026

- Chạy server 8771 bằng `--source-wallet`. Giá của yêu cầu mới là 5 Credit;
  các yêu cầu lịch sử giữ nguyên chi phí đã xác nhận trước đó.
- Đã bật riêng cho 3 tài khoản Google đang hoạt động. Mỗi tài khoản được cấp
  một lần 100 Credit subscription và 600 Credit mua riêng **mô phỏng**, không phải
  xác nhận thanh toán. Số dư cũ vẫn được lưu, hiển thị riêng, không được phân loại
  lại thành Credit mua riêng hoặc tự chi tiêu trong ví mới.
- Usage hiển thị hai nguồn, hạn dùng, lịch sử và xác nhận gia hạn 300/600 Credit.
  Nút gia hạn chỉ bật khi không còn chu kỳ hiện tại/tương lai và đủ nguồn mua riêng.
- Admin cấp thêm phải chọn nguồn. Credit subscription cấp thêm có hạn tới cuối
  chu kỳ đang hiệu lực; Credit mua riêng mô phỏng không hết hạn.
- API và worker dùng phân bổ ví mới cho yêu cầu mới của tài khoản đã bật; marker
  lưu trên yêu cầu giúp worker khởi động lại vẫn thu/hoàn đúng nguồn. Tài khoản
  chưa bật vẫn dùng luồng thử nghiệm cũ. Không chuyển khi còn yêu cầu cũ đang chờ
  hoặc số dư cũ đang giữ chưa được đối soát.

```powershell
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py --source-wallet
# Chạy worker mô phỏng trong cửa sổ khác khi đã xác nhận đúng job thử đang chờ:
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py --source-wallet --run-mock-worker-once
```

Cấp nguồn thử một lần (chỉ schema credit_google_trial; không chạy lại để đổi kỳ):

```powershell
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py --source-wallet --seed-source-wallets
```

Không chạy server bỏ cờ `--source-wallet` khi đang thử ví mới. Chưa có scheduler
production: local có lượt xử lý chu kỳ độc lập như hướng dẫn bên dưới, và cấp
chu kỳ đến hạn khi gửi báo giá. Không chạy seed để gia hạn hoặc reset tháng thử.
Chính sách cập nhật: đăng nhập lần đầu qua lời mời hợp lệ tự bắt đầu một tháng
miễn phí và cấp 100 Credit subscription một lần; không cần admin kích hoạt thêm.
Tra cứu là quyền mặc định cho tài khoản đã được mời, còn hoạt động và được gán
phạm vi; không có bước cấp quyền khai thác riêng. Vẫn kiểm tra Credit, subscription
và phạm vi khi xác nhận. Tài khoản test đã có kỳ giữ nguyên, không cấp lại.
Khi subscription hết hạn, người dùng vẫn xem lại thư viện đã khai thác, nhưng
không được tạo yêu cầu mới có phí trước khi gia hạn.

Backup giao diện đang phục vụ trước khi cập nhật được giữ tại
`.tmp-credit-trial/backups/before-source-wallet-20261004-011520/site`.
Không quay về luồng cũ khi còn yêu cầu ví mới đang giữ Credit: phải kết thúc/hoàn
đúng nguồn trước, rồi mới xem xét rollback. Migration 0013–0015 chưa áp dụng production.

## Lượt xử lý chu kỳ độc lập — 04/10/2026

Chạy trong cửa sổ PowerShell khác tại thư mục dự án, không cần dừng server:

```powershell
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py --source-wallet --run-subscription-maintenance-once
```

- Chỉ database `qd766_credit_test`, schema `credit_google_trial`, tài khoản đã
  opt-in. Không tự kích hoạt trial, không tạo gói thanh toán, không cấp lại ví cũ.
- Cấp Credit của chu kỳ đã được ghi nhận khi tháng đó bắt đầu; không cấp trước
  tháng tương lai hoặc bù Credit của tháng đã hết hạn. Chạy lại không cấp trùng.
- Ghi hết hạn phần subscription chưa sử dụng; giữ nguyên Credit mua riêng và
  phần đang giữ cho yêu cầu chưa kết thúc. Không mở khóa tài khoản bị khóa.
- Mỗi tài khoản là một transaction. Một tài khoản lỗi không chặn các tài khoản
  khác; kết quả trả `partial-failure` và exit code 1, có thể chạy lại an toàn.
- `grantedCycles=0`, `expiredCredit=0` là bình thường nếu chưa sang chu kỳ mới.
- Đây là lệnh một lượt để xử lý thủ công. Bản server local source-wallet hiện
  có lịch nền theo phần cập nhật bên dưới; không có Task Scheduler production.
  Không có worker cào dữ liệu hoặc kết nối DVCQG trong thao tác này.

Kiểm chứng: 179 tests backend đạt; PostgreSQL schema kiểm thử riêng kiểm chứng
6 lượt xử lý chạy đồng thời chỉ cấp Credit cho chu kỳ mới một lần.

## Nghiệm thu hết hạn → gia hạn trên giao diện

Bộ ca riêng dùng `credit_expiry_agency` hoặc `credit_expiry_province` trong DB
test. Chỉ sao chép định danh Google đã xác thực của owner từ bản local gốc;
không sao chép số dư, phiên hoặc thư viện. Trên ca này owner đóng vai người dùng,
không phải admin. Bản local gốc `credit_google_trial` và production không đổi.

Chuẩn bị một lần và khởi động ca cấp đơn vị (dừng đúng server 8771 cũ trước):

```powershell
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py --source-wallet --expiry-rehearsal agency --prepare-expiry-rehearsal
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py --source-wallet --expiry-rehearsal agency
```

F5 và đăng nhập lại bằng Google của owner. Không cần tạo lời mời mới.
Ca bắt đầu với subscription hết hạn, 0 Credit subscription, 600 Credit mua
riêng mô phỏng và `TEST.001` đã khai thác năm hiện tại. Không tạo số dư lại
khi chạy lại lệnh chuẩn bị hoặc khởi động lại server.

1. Mở Usage: thấy đã hết hạn; dữ liệu cũ vẫn khả dụng.
2. Chọn theo TTHC, xem lại `TEST.001`: dữ liệu có sẵn, không trừ thêm.
3. Yêu cầu `TEST.002` trước gia hạn: vẫn mở hộp Xác nhận lấy dữ liệu, hiển thị
   thủ tục/chi phí và thông báo subscription đã hết hạn; nút xác nhận bị khóa,
   có nút Gia hạn trong Usage. Không giữ Credit hoặc tạo job.
4. Usage → Gia hạn bằng Credit → Hủy: số dư giữ 600.
5. Xác nhận gia hạn 300 Credit: còn 300 mua riêng, 0 subscription; có tháng
   mới và một giao dịch quy đổi. F5 không thu lại, không cấp thêm Credit gói.
6. Yêu cầu `TEST.002`: giá 5 Credit, khả dụng 295, giữ 5. Chưa có worker tự chạy.

Ca tỉnh: thay `agency` bằng `province` trong cả hai lệnh, có schema riêng.
Đổi 600 Credit còn 0; muốn tạo yêu cầu mới cần Credit, không coi gia hạn là
được tặng thêm Credit. Không thay cấu hình Google callback hiện tại.

Quay lại bản Google local gốc: dừng đúng server ca đang chạy bằng Ctrl+C, rồi:

```powershell
.\.venv\Scripts\python.exe .\tools\start_local_google_trial.py --source-wallet
```

Đăng nhập lại để lấy phiên từ schema gốc. Không xóa/restore DB hoặc sửa số dư.
181 tests backend và test trình bày ví đạt. Chờ chủ dự án nghiệm thu UI bằng
Google thật; kiểm thử tự động không được coi là đã nghiệm thu thao tác thực tế.

## Tự xử lý chu kỳ khi server local chạy — 04/10/2026

- Server 8771 với `--source-wallet` chạy maintenance ngay khi khởi động và
  mỗi 60 giây sau lượt trước. Không cần người dùng mở trang hoặc gửi báo giá.
- Chỉ bật khi đồng thời có cờ Google local và source-wallet; không có biến
  môi trường tự bật trên production. Các lệnh `--check`/seed/chuẩn bị ca/worker
  một lượt không khởi động lifespan nên không tạo vòng lặp nền này.
- Chỉ xử lý các chu kỳ đã được phê duyệt và ví đã opt-in. Không tạo trial,
  không tự quy đổi, không cấp trước Credit của tháng tương lai; không cào DVCQG.
- Lỗi từng tài khoản rollback riêng, lần sau thử lại. Log chỉ ghi lỗi khi có
  thay đổi trạng thái và khi phục hồi, không in secret hoặc số dư từng người.
- Tắt server chờ lượt đang xử lý hoàn tất, không bỏ transaction đang chạy.
  Chạy chồng với lệnh maintenance thủ công vẫn chống cấp/hết hạn trùng.
- Đã chạy thật trên bản test: `LOCAL_CREDIT_CYCLES_READY accounts=4`.
  190 tests backend và kiểm tra PostgreSQL chạy đồng thời đạt. Chưa đăng ký
  lịch/đổi cấu hình/áp dụng schema production.
