# Gói cập nhật dùng thử — chuẩn bị, chưa deploy

## Đã duyệt phát hành — 04/10/2026, chưa thực thi production

Chủ dự án đã chốt phát hành và xử lý các tài khoản cũ do mình sở hữu.
Không coi phê duyệt này là đã deploy thành công hoặc miễn các bước backup/
kiểm tra tác vụ. Phiên làm việc không có quyền ghi D:\QD766\app,
F:\QD766\backups; đọc Scheduled Tasks bị HRESULT 0x80041003.
Network được cấp nhưng không push Git/Netlify trước backend.

- Build Netlify mới thành công; kiểm tra package không chứa fixture, secret,
  source map đạt; UI tài khoản/Usage/subscription/tra cứu đạt 5 nhóm test Node.
- Asset cũ và package cũ đã sao lưu vào
  `.tmp-release-preflight/20261004-095924` trước build; không xóa package cũ.
- Cấu hình D:\QD766\app\.env và .env.public dự án trỏ cùng DB theo preflight;
  vẫn chưa chứng minh các tiến trình đang chạy nạp đúng hai cấu hình này.
- Đối soát nguồn 09:59 Việt Nam: 3 tài khoản, Credit/reserved/pending đều 0,
  revision vẫn0010; chưa nâng schema, cấp trial hoặc bật runtime thật.
- Cần chủ dự án chạy check_release_tasks.ps1 và backup_postgresql.ps1 từ
  PowerShell quản trị, gửi đường dẫn tác vụ/backup để chuyển backend trước.
- Chưa commit/push hoặc kích hoạt deploy Netlify. Chưa cập nhật Windows tasks.

Chính sách thương mại và Credit cập nhật 04/10/2026 được lưu tại
[COMMERCIAL_POLICY_DECISIONS.md](COMMERCIAL_POLICY_DECISIONS.md).
Mức 5 Credit và quy đổi 300/600 đã được chốt; không dùng mức thử 3 Credit
làm bảng giá. Tài liệu quyết định không đồng nghĩa code đã triển khai.

## Nội dung

- Quản trị có sidebar riêng: tài khoản, credits, lời mời, nhật ký.
- Form tạo link mời luôn trở lại mục Mời dùng thử sau khi chỉnh quyền.
- Quyền xem toàn quốc độc lập vai trò admin. TTHC vẫn cần quyền khai thác và credit.
- Menu tài khoản có thông tin tài khoản, Usage, đăng xuất; desktop cuối sidebar,
  mobile đầu trang, tự đổi vị trí khi thay kích thước.
- Usage đọc sổ giao dịch của chính tài khoản, có phân trang và xác nhận đổi Credit
  mua riêng để gia hạn trên local. Credit theo hai nguồn chưa bật production.
- Yêu cầu thất bại hiển thị Thất bại / 0 credit; thành công hiển thị chi phí âm.
- Local có thao tác xử lý chu kỳ Credit độc lập, không cần yêu cầu khai thác;
  cấp/hết hạn chống lặp và rollback riêng từng tài khoản. Server Google local
  source-wallet tự chạy ngay khi khởi động và mỗi 60 giây. Chưa có lịch production.

## Đã kiểm chứng và giới hạn

Người dùng đã xác nhận trên 8771: Google thật, dùng lại thư viện không thu thêm,
tài khoản khác trả phí cho dữ liệu có sẵn, hai tài khoản chung job thành công,
hai tài khoản chung job thất bại và hoàn credit.
Data/credit trên 8771 là mô phỏng trong qd766_credit_test/credit_google_trial,
không chứng minh worker production truy cập DVCQG thành công.

Phân quyền backend được kiểm chứng tự động bằng phiên/tài khoản giả trong database
riêng; xem LOCAL_ACCESS_VERIFICATION.md. Không tuyên bố đã kiểm toán bảo mật đầy đủ.
Giao diện admin/mobile mới còn cần người dùng xem thực tế.

## Điều kiện trước khi deploy (chưa thực hiện)

Phương án chuyển đổi và kết quả đối soát chỉ đọc được lưu tại
[CREDIT_PRODUCTION_TRANSITION.md](CREDIT_PRODUCTION_TRANSITION.md).
Cách opt-in ví thật, pause yêu cầu mới và backfill tài khoản cũ được chuẩn bị
tại [REAL_WALLET_ACTIVATION_RUNBOOK.md](REAL_WALLET_ACTIVATION_RUNBOOK.md).
214 tests đạt; rehearsal 2 tài khoản trên bản phục hồi đã rollback toàn bộ.
Launcher mặc định vẫn tắt ví; opt-in kiểm tra schema 0010 bị chặn, không chạy.
Đã phục hồi backup mới trên database riêng, nâng 0010–0015 và bảo toàn
22 bảng cũ. Core ví + API/worker mock payload + actual lifespan/tick 60s
đạt trên PostgreSQL riêng; schema public của bản phục hồi giữ nguyên.
Chưa xác minh Google/DVCQG thật hay launcher ví thật production.
Database cấu hình `.env` có 3 tài khoản, số dư/đang giữ/yêu cầu chờ bằng 0,
migration 0010; chưa xác minh đồng nhất với tiến trình public/worker đang chạy.
Không tự chuyển số dư legacy thành Credit mua riêng hoặc backfill tháng thử.

Lưu ý: nguồn ví/chính sách mới hiện được chặn trong local source-wallet.
Trước production cần chế độ ví thực được phê duyệt, không bật cờ mô phỏng hoặc
tái sử dụng cờ Google local trên public backend. Xem LOCAL_TRIAL_JOURNEY_ACCEPTANCE.md.

1. Người dùng duyệt giao diện mới. Local theo nguồn dùng 5 Credit cho yêu cầu mới;
   dữ liệu lịch sử mức 3 không bị sửa. Không tự bật thu phí production.
2. Ghi nhận commit và bản Netlify/backend đang chạy, sao lưu cấu hình riêng tư
   ngoài Git; không đưa secret hoặc cookie vào gói.
3. Sao lưu PostgreSQL mới, kiểm tra SHA256 và khả năng phục hồi; ghi migration hiện tại.
4. Xác minh migrations 0011–0015 còn thiếu (quyền khai thác, national, ví theo
   nguồn, chu kỳ và opt-in).
   Chỉ nâng production sau phê duyệt và backup; không dùng schema test.
5. Rà soát public backend: login/invite-only/admin boundary bật, không có cờ
   mô phỏng. Credit thử và paid requests chỉ bật theo phê duyệt; payment vẫn tắt.
6. Xác minh worker thật cùng DB với public backend, có circuit, timeout/lease,
   settle/refund, không mở thêm API quản trị vận hành ra Internet.
   Chuẩn bị và kiểm chứng lịch xử lý chu kỳ Credit riêng trước khi bật nguồn ví:
   service local đã có, chưa có launcher hoặc Task Scheduler production. Cần
   theo dõi lượt chạy thất bại để không bỏ lỡ cấp Credit trong tháng còn hiệu lực.
7. Deploy backend trước, kiểm tra health và quyền; deploy frontend một đợt sau.
8. Thử với tài khoản dùng thử được cấp credit: dữ liệu thật, trả phí riêng cho
   cache dùng chung, không thu lại dữ liệu đã mua, thông báo và Excel.

## Rollback

- Giao diện: quay về deploy Netlify trước; giữ sổ giao dịch và DB hiện tại.
- Backend lỗi: tắt nhận yêu cầu khai thác mới, giữ ledger; kiểm tra các yêu cầu
  đang xử lý trước khi quay về mã cũ. Không xóa job hoặc sửa số dư trực tiếp.
- Không hạ 0012 khi còn account/invite national; migration chủ động từ chối.
- Khôi phục toàn DB chỉ theo kế hoạch có đối soát: backup cũ có thể làm mất
  giao dịch phát sinh sau backup. Không dùng restore như rollback mặc định.
- Worker/circuit/Task Scheduler production không đổi trong lượt chuẩn bị này.

Chưa push, chưa deploy, chưa áp dụng migration hoặc thay cấu hình production.

## Đối soát và trở lại Google local — 04/10/2026

- Sau các thao tác thử: schema ca đơn vị có một chu kỳ quy đổi và 300 Credit
  mua riêng; schema ca tỉnh có một chu kỳ quy đổi và 0 Credit mua riêng. Cả hai
  đều không có Credit đang giữ, không được cấp thêm Credit subscription.
- Chủ dự án xác nhận thông báo thiếu Credit. Nút tra cứu vẫn bấm được để hiển thị
  thông báo; không gửi yêu cầu khi số dư đang hiển thị không đủ. Backend trả
  cùng thông báo nếu số dư giảm do tab khác sau khi mở hộp, rollback đầy đủ.
- Đổi tên luồng thành Tra cứu dữ liệu/Credit sử dụng. Subscription hết hạn
  vẫn mở hộp xác nhận, khóa gửi và có đường sang Usage để gia hạn.
- 183 tests backend, kiểm tra kiểu frontend và PostgreSQL đồng thời đều đạt.
  Các ca UI chưa có xác nhận riêng từng thao tác Hủy/F5 không tự đánh dấu đạt.
- Đã đưa 8771 về schema Google local gốc, không seed lại hoặc reset tài khoản.
  Hai schema nghiệm thu được giữ để kiểm tra lại; không ảnh hưởng production.
- Tiếp theo: nghiệm thu admin kích hoạt tài khoản mới (trial bắt đầu từ thao tác
  kích hoạt), phân quyền/nguồn Credit và khóa quyền. Cần tài khoản Google thứ hai
  nhận lời mời local để kiểm chứng thực tế; không giả lập kết quả đăng nhập đó.

## Chính sách lời mời mới — thay thế kích hoạt thủ công, 04/10/2026

- Chủ dự án đã chọn: tự bắt đầu tháng thử + 100 Credit khi đăng nhập lần đầu
  qua lời mời hợp lệ. Thay thế bước nghiệm thu kích hoạt thủ công bên trên.
- Backend thực hiện sử dụng lời mời, enrollment, chu kỳ, cấp Credit, audit và
  tạo phiên trong cùng transaction. Đăng nhập lại không cấp lặp; có chu kỳ trước
  đó thì không được mở thêm tháng thử qua lời mời.
- Local source-wallet mặc định có quyền tra cứu cho tài khoản đang hoạt động,
  đã được mời và gán tỉnh/cơ quan. Không phải bật capability riêng. Admin quản lý
  Credit bỏ ô quyền khai thác; khóa tài khoản vẫn chặn truy cập, phạm vi vẫn giữ.
- Không bỏ kiểm tra subscription, Credit, CSRF, giới hạn 2 yêu cầu hoặc quyền
  sở hữu thư viện. Credit bằng 0 vẫn có nút để hiển thị thông báo thiếu Credit.
- Đã áp dụng một lượt cho 1 tài khoản local đã dùng lời mời nhưng chưa có chu kỳ:
  cấp 100 Credit subscription; chạy lại kích hoạt 0 tài khoản. Không đổi số dư
  legacy hoặc thời hạn/số dư các tài khoản đã có tháng thử.
- 186 kiểm thử backend và kiểm tra kiểu frontend đạt. 8771 đang dùng chính sách
  mới; production chưa bật. Các kiểm thử quyền riêng cũ còn giữ cho production
  chưa deploy để không vô tình thay hành vi của môi trường đó.

## Chu kỳ nền local — 04/10/2026

- Local 8771 đã bật vòng lặp xử lý Credit trong lifespan, không bật worker cào
  dữ liệu. Lần đầu đã xử lý 4 tài khoản opt-in thành công.
- 190 tests đạt; PostgreSQL riêng tiếp tục đạt các kiểm chứng chống thu/hoàn/
  cấp chu kỳ/quy đổi trùng, chia sẻ job và giới hạn yêu cầu.
- Không yêu cầu UI tạo job để cấp Credit. Không gọi payment, đăng ký Task
  Scheduler hoặc thay đổi public backend/production.

## Ca xuyên suốt mới — 04/10/2026

- Đã kiểm chứng qua API từ tạo/đổi lời mời, tự cấp 100, dùng chung job/thu riêng,
  dữ liệu cache cho tài khoản khác, xem lại, 6 nhóm, giới hạn hàng chờ, hoàn
  thất bại, đăng nhập lại và khóa tài khoản. Google/dữ liệu được mock.
- 191 tests backend đạt; ca xuyên suốt PostgreSQL riêng đạt; kiểm tra kiểu và
  test trình bày Credit/thông báo đạt. Không thay tài khoản đang dùng hoặc deploy.
- Báo cáo: LOCAL_TRIAL_JOURNEY_ACCEPTANCE.md. Không coi callback mock là đã thử
  toàn bộ UI Google thật hoặc khả năng truy cập DVCQG của worker production.
