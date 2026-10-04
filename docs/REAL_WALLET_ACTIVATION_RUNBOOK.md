# Bật ví thật có kiểm soát — đã chuẩn bị, chưa bật production

## Chuyển đổi được duyệt và đã bắt đầu — 04/10/2026

Chủ dự án đã duyệt phát hành và chấp nhận xử lý các tài khoản cũ của mình.
Metadata người vận hành cung cấp: public chạy launcher từ checkout; worker
chạy `D:\QD766\app\tools\start_worker.ps1`. Không có thay đổi Task từ phiên agent.
Backup mới `F:\QD766\backups\qd766-20261004-100854.dump` đã xác minh SHA256
`86422E1EE26B4BBD1A486B78ED1937CFAC528DF0C76CFD7A337A8F99710CF46C`.
`migrate_real_wallet.py --confirm` đã chạy trên qd766/public thành công,
nâng 0010 lên 0015, kiểm tra schema đạt; chưa cấp Credit/backfill.
Launcher `--real-wallet --pause-paid-requests --check` đạt sau migration.
Các mục trạng thái cũ bên dưới là lịch sử trước chuyển đổi, không phải trạng thái hiện tại.

Scripts đăng ký Task nhận `-RealWallet -PausePaidRequests`; không cho đổi
Task real-wallet về legacy. Restart kiểm tra đúng chế độ của Task trước khi dừng.
Tiếp theo người vận hành đăng ký lại và restart public với hai cờ này,
giữ yêu cầu mới bị khóa trong khi cập nhật worker D:\QD766\app và backfill.
Chưa bỏ pause, chưa phát hành frontend/Netlify, chưa đổi circuit hoặc DNS.

Người vận hành đã đăng ký lại Task public có `--real-wallet --pause-paid-requests`
và restart thành công: ready=ok, Task Running (kết quả được gửi trong chat).
Rà soát trực tiếp production có 2 tài khoản đủ điều kiện. Đã commit backfill
với operation `7a239f69-21bc-4350-8429-cc318d8c028b`:
`37ead06d-16bb-49aa-9e4c-dd06ca6eb618` và
`b9a7caed-1a5b-4de1-9033-47f52fe302ed`, mỗi tài khoản một tháng lịch và
100 subscription Credit tại thời điểm áp dụng. Đọc lại sau commit:
mỗi tài khoản available=100, reserved=0; admin excluded, không đổi role/scope.
`activate_approved_trials.py` mặc định review-only; confirm yêu cầu UUID cụ thể,
operation, backup/hash và owner hợp lệ. Không tự động áp dụng toàn bộ danh sách.

Chuẩn bị `update_wallet_worker.ps1` cho người vận hành: kiểm tra Task public
paused, cấu hình database trùng nhau, schema/dependencies; backup code worker
và XML Task vào `.tmp-worker-release` trước khi dừng. Chỉ cập nhật `src/qd766`
và `tools/run_collection_worker.py` ở `D:\QD766\app`, kiểm hash từng file Python,
kiểm import rồi mới khởi động worker. Không sao chép `.env`, frontend, database
hay đổi Task worker. Lỗi sau khi dừng thì giữ worker dừng/public paused để xử lý.
Parser PowerShell đạt; script CHƯA được chạy tại môi trường triển khai.
UPDATE: Người vận hành đã chạy script thành công, backup code worker ở
`.tmp-worker-release\20261004-101905-335`, imports/hash PASS, Task Running.
Log worker ghi idle sau restart; kiểm tra trực tiếp access-policy ở 8769:
loginRequired/inviteRequired/paidRequestsEnabled/defaultCollectionAccess=true,
collectionRequestsPaused=true, localSimulation=false. Chưa có kiểm chứng
thu thập/settle yêu cầu thật sau update; chuẩn bị bước gỡ pause có kiểm tra policy.
`restart_public_backend.ps1` hiện kiểm tra cả policy đang phục vụ sau ready,
không chỉ HTTP health. Công cụ alignment đổi tên trường default wallet để tránh
nhầm với trạng thái runtime; chỉ là đối chiếu cấu hình.

Người vận hành đã gỡ pause bằng đăng ký lại `-RealWallet` (không PausePaidRequests)
và restart. Kết quả: PUBLIC_BACKEND_READY=ok,
PUBLIC_RUNTIME_POLICY=PASS REAL_WALLET=True REQUESTS_PAUSED=False, Task Running.
Đã rebuild gói Netlify và kiểm asset allowlist, account menu, wallet UI,
personal Credit, admin subscription, collection copy: PASS. Backup gói trước build
ở `.tmp-release-preflight\20261004-102424-496`. Chuẩn bị push một bản phát hành gộp;
chưa khẳng định Netlify đã publish hoặc yêu cầu DVCQG thật đã hoàn tất.
Task Running sau update chỉ chứng minh tiến trình sống, không chứng minh đã
thu thập/settle thành công một yêu cầu thật. Chưa gỡ pause hoặc push Netlify.

## Trạng thái 04/10/2026

- Launcher mặc định giữ nguyên chế độ cũ: paid requests/ví thật tắt.
  Không đọc cờ bật ví từ `.env` hoặc `.env.public`.
- Có opt-in CLI `--real-wallet`. Chỉ sau khi được duyệt, nâng schema,
  kiểm tra backup/worker và xử lý tài khoản cũ mới dùng để chạy thực.
- Startup/check với opt-in đọc schema trước khi phục vụ, không tự migration.
  Database cấu hình hiện ở 0010; thử `--real-wallet --check` bị chặn đúng
  kỳ vọng, không khởi chạy server hoặc đổi dữ liệu. Check chế độ mặc định đạt.
- Chưa đổi Scheduled Tasks, cấu hình riêng tư, server đang chạy hoặc Netlify.

## Tạm dừng yêu cầu mới, không tắt ví đang sử dụng

Sau khi đã có giao dịch ví mới, không chuyển về core legacy như rollback.
Giữ `--real-wallet` và dùng `--pause-paid-requests` khi cần tạm ngừng khai thác.
Quote mới và xác nhận quote đã ký trước khi pause đều bị chặn, không tạo
job/hold/trừ Credit. Xem lại quyền đã mua, settlement/refund của worker,
Usage và vòng cấp/hết hạn vẫn hoạt động. Pause không hủy job hoặc hoàn
Credit hàng loạt; không thay circuit. Không đồng nghĩa tạm dừng gia hạn.
Gỡ pause bằng cách bỏ riêng cờ pause khi khởi động lại có kiểm soát.
Frontend nhận collectionRequestsPaused; chưa thêm giao diện quản trị
bật/tắt runtime hoặc sửa Scheduled Task qua Internet.

Chỉ kiểm tra, không khởi chạy (dành cho sau khi schema được nâng):

```powershell
.\.venv\Scripts\python.exe .\tools\start_public_backend.py --real-wallet --pause-paid-requests --check
```

Không bật trước phê duyệt migration/backfill. `--check` không đăng nhập
Google thật hoặc chứng minh worker truy cập DVCQG. Hai cờ local và real
wallet không được trộn; payment chưa có và vẫn không được bật.

## Tài khoản cũ

Nguồn rà soát là bản phục hồi backup 04/10/2026 09:21:35, không phải cam
kết trạng thái production hiện tại. Kết quả xem trước: 2 tài khoản đủ điều
kiện, 1 admin bị loại. Không đưa email/token lời mời vào log/công cụ.
Danh sách cụ thể xem qua tools/review_trial_backfill.py và đối chiếu admin UI.

Eligibility phải kiểm tra lại trong transaction lúc áp dụng:

- Active, admitted, Google identity, có phạm vi tỉnh/cơ quan hợp lệ.
- Lời mời đã sử dụng, chưa bị thu hồi và khớp phạm vi hiện tại. Hết hạn
  gửi lời mời sau khi đã được sử dụng không tự loại một lời mời hợp lệ cũ.
- Không có bất cứ chu kỳ subscription nào trước đó; không có lịch sử
  lots/events cần đối soát; không có số dư legacy hoặc khoản đang giữ/job chờ.
- Tổng delta sổ legacy phải khớp số dư. Không biến Credit cũ thành purchased.
- Admin không được tự đưa vào đợt cấp; tài khoản khóa không bị tự mở khóa.

Core `trial_backfill.apply_selected` chỉ áp dụng các UUID được chủ dự án
duyệt, dùng actor chính xác vietnt89@gmail.com (admin, active, Google,
admitted) và operation UUID. Khóa actor/từng tài khoản/lời mời, re-review
trước khi cấp; audit riêng ghi danh sách duyệt. Cấp 1 tháng lịch +100
subscription tại thời điểm áp dụng, không truy hồi ngày đăng nhập cũ.
Không đổi vai trò/phạm vi/số dư legacy. Replay cùng operation/danh sách
không cấp thêm; đổi danh sách cùng operation bị từ chối. Caller phải bao
toàn bộ batch trong transaction; một tài khoản không đủ điều kiện → rollback.

Chưa cung cấp CLI commit vào production hoặc tự chạy backfill khi startup.
Review chỉ đọc, rehearsal luôn rollback, chỉ chấp nhận database restore:

```powershell
.\.venv\Scripts\python.exe .\tools\review_trial_backfill.py --database qd766_restore_20261004_092135 --connection-file .env
.\.venv\Scripts\python.exe .\tools\rehearse_trial_backfill.py --database qd766_restore_20261004_092135 --connection-file .env
```

Đã chạy rehearsal thật trên bản phục hồi: 2 tài khoản ×100, replay cấp 0;
fingerprint mọi bảng public sau rollback khớp trạng thái trước. Không có
tài khoản được kích hoạt thật hoặc Credit mới tồn tại sau rehearsal.
214 tests backend đạt: pause, quote cũ, default opt-out, eligibility,
identity owner, replay và batch rollback. Production chưa deploy.

## Điều kiện còn lại trước phát hành

Xác minh cấu hình của public/worker đang chạy (chưa đọc được metadata Task
trong phiên hiện tại); backup mới tại cửa sổ chuyển đổi; migration đã duyệt;
review danh sách/tình trạng hiện tại và duyệt cấp tháng thử; cơ chế cập nhật
Task/launcher dùng opt-in có backup và restart an toàn; đối soát sau chuyển.
Gom frontend và backend vào một đợt phát hành sau khi chủ dự án duyệt.
Không tự deploy Netlify, không bỏ qua các điều kiện trên vì test đã đạt.
