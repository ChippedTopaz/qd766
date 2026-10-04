# Chuẩn bị chuyển ví Credit — chưa triển khai

## Đối soát chỉ đọc ngày 04/10/2026

Chạy `tools/audit_credit_transition.py --connection-file .env` lúc
02:08:37 UTC (09:08:37 Việt Nam). Chỉ đọc PostgreSQL được cấu hình trong
`.env`, schema public, transaction REPEATABLE READ / READ ONLY.
Không gọi Google, DVCQG; không tạo bảng, cấp Credit hay sửa tài khoản.
Chưa xác nhận tiến trình public/worker đang chạy dùng chính database này.

| Mục | Kết quả |
|---|---:|
| Tài khoản | 3 |
| Credit legacy khả dụng / đang giữ | 0 / 0 |
| Yêu cầu đang chờ / Credit tương ứng | 0 / 0 |
| Tài khoản lệch tổng delta sổ giao dịch | 0 |
| Tài khoản lệch Credit đang giữ với yêu cầu chờ | 0 |
| Sổ/yêu cầu chờ không có tài khoản | 0 / 0 |
| Migration hiện tại | 20261003_0010 |

Chưa có bảng credit_lots, credit_holds, credit_wallet_events,
subscription_cycles, credit_wallet_enrollments. Số liệu chỉ là ảnh chụp
tại thời điểm đọc, không bảo đảm trạng thái giữ nguyên khi triển khai.
Đối soát delta không phải kiểm toán đầy đủ từng giao dịch/job.

## Quy tắc chuyển đổi

- Không tự coi Credit legacy là Credit mua riêng: cần chứng từ/duyệt nguồn
  của admin nếu có số dư phát sinh trước lúc chuyển. Báo cáo không phân loại nguồn.
- Ở thời điểm hiện tại không có số dư legacy cần chuyển; không có lý do
  tạo một khoản Credit mua riêng từ dữ liệu này.
- Giữ nguyên toàn bộ sổ giao dịch, yêu cầu, dữ liệu đã khai thác và phân quyền.
- Không cấp lại 100 cho tài khoản đã có chu kỳ thử. Không reset ngày hết hạn.
- Tài khoản mới: lời mời hợp lệ + đăng nhập lần đầu → tháng thử +100,
  một transaction, chống cấp lặp theo chính sách đã chốt.
- Tài khoản cũ chưa có chu kỳ: cần admin duyệt danh sách và thời điểm bắt đầu
  trước khi backfill; đề xuất bắt đầu tại thời điểm kích hoạt chính sách mới,
  không truy hồi về lần đăng nhập cũ. Đây là đề xuất, chưa được áp dụng.
  Không tự mở khóa tài khoản hoặc đổi vai trò admin/phạm vi.
- Nếu xuất hiện Credit đang giữ/yêu cầu chờ, chờ worker kết thúc và đối soát
  trước enrollment. Không ép hoàn hoặc chỉnh số dư để vượt chặn.

## Thứ tự triển khai sau khi được duyệt

1. Xác minh cấu hình database/schema của public backend và worker, bản mã
   đang chạy, cấu hình giá, migration. Không in URL/password ra báo cáo.
2. Chuẩn bị chế độ ví thật độc lập cờ local; giá 5 Credit, quyền mặc định,
   lịch cấp/hết hạn có báo lỗi; payment vẫn tắt. Kiểm thử trước triển khai.
3. Trong cửa sổ chuyển đổi, ngừng nhận yêu cầu có phí mới, để các yêu cầu
   đã nhận kết thúc; không chặn đọc dữ liệu đã mua. Đối soát lại.
4. Backup mới bằng công cụ hiện có, lưu SHA256 và cấu hình riêng tư ngoài Git.
   Restore thử vào database riêng được admin cho phép, kiểm tra migration,
   số lượng dữ liệu, tài khoản, ledger và quyền sở hữu. SHA256 hoặc đọc danh
   sách dump thành công không thay thế kiểm tra phục hồi. Không restore đè.
5. Nâng có kiểm soát 0011 → 0012 → 0013 → 0014 → 0015 trên bản phục hồi thử
   trước, rồi mới database thực đã xác minh. Các migration này chưa chạy
   trong lượt chuẩn bị. Công cụ migrate_trial_access cũ chỉ đến 0010,
   không dùng nó như công cụ nâng ví mới.
6. Áp dụng danh sách enrollment/backfill đã duyệt, khóa tài khoản trong
   transaction, có operation key + audit; chạy lại không cấp thêm.
   Lưu báo cáo trước/sau, không sửa trực tiếp số dư legacy.
7. Kiểm chứng worker settle/refund đúng nguồn và lịch chu kỳ trên ví thật;
   bật nhận yêu cầu sau khi health, phân quyền và đối soát đạt.
8. Chỉ deploy frontend Netlify một đợt khi chủ dự án duyệt. Kiểm tra người
   dùng thật theo phạm vi, cache/shared-job, hoàn Credit và Excel.

## Rollback

Tắt nhận yêu cầu mới khi lỗi. Giữ ledger, ví, quyền sở hữu và các yêu cầu
đã phát sinh; để phiên bản xử lý tương thích giải quyết Credit đang giữ.
Không bật lại ví legacy để chi tiêu trùng, không downgrade/xóa bảng ví.
Rollback frontend riêng được phép theo bản deploy trước. Restore toàn DB
chỉ khi có kế hoạch đối soát mọi giao dịch từ thời điểm backup, không phải
phương án mặc định. Chưa tạo backup mới hoặc thử restore trong lượt này.

## Chuẩn bị runtime ví thật — cập nhật 04/10/2026

- Đã thêm `real_wallet_enabled` độc lập local, chỉ truyền tường minh trong
  Settings; chưa có launcher bật cờ, không đọc cờ này từ môi trường.
  Public launcher hiện tại vẫn tắt ví thật và paid requests.
- Runtime từ chối trộn mô phỏng với ví thật, thiếu login/invite/public boundary,
  thiếu quyền quản lý Credit thử, giá khác 5, SQL echo, callback ngoài domain
  được duyệt hoặc database test/remote/URL có tùy chọn schema.
- Engine ví thật cố định search_path=public. Trước khi phục vụ, lifespan đọc
  schema ở transaction READ ONLY, kiểm tra các cột ví và revision 0015.
  Không tự migration; sai schema thì không khởi chạy vòng xử lý Credit.
- Vòng chu kỳ dùng lại core đã kiểm thử, log REAL_CREDIT_CYCLES riêng;
  không chạy worker cào. Chưa bật vòng này trên database thực, chưa có
  theo dõi/hiển thị trạng thái production hay launcher phát hành được duyệt.
- Tài khoản chưa enrollment không tạo yêu cầu có phí hoặc được cấp Credit
  vào ví legacy. Quyền khai thác cũ vẫn xem lại, không thu lại Credit.
  Lời mời hợp lệ ở chế độ ví thật sẽ dùng transaction auto-trial như local.
- Công cụ check_credit_database_alignment báo MATCH khi so sánh cấu hình
  `.env`/`.env.public` với Settings mà worker nạp trong tiến trình kiểm tra.
  Chưa chứng minh worker/public đang chạy dùng cấu hình đó. Không đọc được
  metadata hai Scheduled Tasks trong môi trường hiện tại.
- Quyền ghi F:\QD766\backups chưa được cấp cho phiên này, nên chưa tạo
  backup mới hoặc restore. Có thể chủ dự án chạy backup_postgresql.ps1
  bằng PowerShell của mình rồi cung cấp đường dẫn dump để tiếp tục.
- Kiểm thử runtime/scheduler dùng dependency mock, không thay cho restore
  và migration thật trên database riêng. Chưa restart 8771/8769, chưa
  thay cấu hình hoặc deploy Netlify.
- 202 tests backend đạt, bao gồm chặn fallback ví legacy và giữ quyền
  khai thác cũ; kiểm tra diff không có lỗi khoảng trắng.

## Lệnh kiểm tra chỉ đọc

## Backup mới và công cụ diễn tập phục hồi

Chủ dự án đã tạo backup `F:\QD766\backups\qd766-20261004-092135.dump`,
6.788.955 bytes. Đã đọc và xác nhận SHA256:
`E85B01C2E848C6CD12FEE12B7787AD581F067A9AF9EC5A9C519568326FFC6A0C`.
Tài khoản cấu hình qd766_app không có CREATEDB/superuser; chưa phục hồi
hoặc migration thật. Cần admin PostgreSQL tạo database riêng:

```sql
CREATE DATABASE qd766_restore_20261004_092135 OWNER qd766_app;
```

Chỉ tạo database mới; nếu tên đã tồn tại, không xóa/reset/ghi đè.
Công cụ `tools/rehearse_credit_restore.py` đã chuẩn bị và 4 kiểm thử bảo vệ
đạt. Chỉ chấp nhận tên restore dạng timestamp, PostgreSQL loopback,
database khác nguồn, đúng owner và chưa có object/schema riêng. Kiểm tra
checksum trước, restore public trong một transaction, không --clean/--create.
Sau phục hồi, nâng bản thử từ 0010 đến 0015, so sánh số hàng và fingerprint
của mọi bảng cũ (trừ revision), kiểm tra bảng mới rỗng và runtime schema.
Không đăng nhập Google, tạo trial, cấp Credit, chạy worker hay web server.
Lưu database thử để đối soát, không tự xóa khi thất bại. Database phục hồi
có dữ liệu tài khoản/phiên riêng tư: không đưa lên Internet hoặc vào Git.

```powershell
.\.venv\Scripts\python.exe .\tools\rehearse_credit_restore.py --backup "F:\QD766\backups\qd766-20261004-092135.dump" --sha256 E85B01C2E848C6CD12FEE12B7787AD581F067A9AF9EC5A9C519568326FFC6A0C --database qd766_restore_20261004_092135 --connection-file .env
```

Chỉ chạy sau khi admin tạo database. Công cụ từ chối database không trống;
chạy lại trên database đã phục hồi không phải là thao tác reset.

## Đối soát cấu hình và Credit chỉ đọc

## Diễn tập phục hồi thực tế đã đạt — 04/10/2026

Sau khi chủ dự án tạo database mới với owner qd766_app, đã chạy công cụ
phục hồi trên `qd766_restore_20261004_092135`:

- Checksum dump khớp; restore public thành công trong một transaction.
- Baseline phục hồi 0010; nâng tuần tự 0011–0015 thành công.
- 22 bảng cũ (không tính alembic_version) giữ nguyên số hàng và fingerprint
  giữa thời điểm sau restore và sau migration; không tuyên bố database nguồn
  đang chạy còn khớp từng hàng với snapshot backup.
- 6 bảng mới đều trống; không seed, enrollment, mở tháng thử hay cấp Credit.
- 3 tài khoản; Credit legacy khả dụng/đang giữ 0/0; không lệch ledger hoặc
  Credit đang giữ so với yêu cầu chờ.
- Guard schema ví thật kiểm tra đạt trên PostgreSQL thực.
- Database thử giữ lại để kiểm tra. Có tài khoản/phiên từ backup, không
  được dùng để phục vụ Internet. Không khởi chạy web/worker/Google login,
  không cào DVCQG, không thay cấu hình hoặc deploy production.

Đã đối soát lại database cấu hình .env sau diễn tập: revision vẫn 0010.
Diễn tập này xác nhận phục hồi/migration và bảo toàn hàng dữ liệu, chưa
nghiệm thu toàn bộ nghiệp vụ ví thật hoặc worker production.

## Kiểm chứng core ví trên bản phục hồi — 04/10/2026

Đã chạy `tools/rehearse_restored_wallet.py` trên database phục hồi có
migration 0015. PostgreSQL thật, core ví thật; không thông qua giao diện,
OAuth hoặc worker lấy dữ liệu. Các ca dùng UUID/tài khoản kiểm thử mới,
toàn bộ writes cùng transaction được rollback cuối lượt, không commit.

8 nhóm kiểm chứng đạt:

1. Tháng thử cấp đúng 100; giữ 5 và thu đúng một lần khi gọi lại.
2. Hoàn một lần; thiếu Credit không tạo hold/ledger; Credit tháng chưa dùng
   hết hạn, chạy hết hạn lại không ghi lặp.
3. Subscription được dùng trước purchased; hết hạn không mất khoản đang
   giữ; hoàn về đúng hai nguồn, phần subscription thêm 7 ngày; purchased
   không hết hạn theo tháng.
4. Cấp đơn vị quy đổi đúng 300 purchased Credit, không thu lặp.
5. Cấp tỉnh quy đổi đúng 600 purchased Credit, không thu lặp.
6. Subscription 6 tháng cấp đơn vị chỉ cấp 100 cho tháng đến hạn, không
   cấp trước cả 6 tháng; mốc 31/1 → 28/2 → 31/3 giữ giờ Việt Nam.
7. Cấp tỉnh tương tự với 200 Credit/tháng.
8. Số dư legacy sentinel của tài khoản kiểm thử không bị core ví sửa.

Số hàng/fingerprint mọi bảng public trước và sau rollback khớp hoàn toàn,
bao gồm cả tài khoản, ledger, dữ liệu và bảng ví. Không tạo tài khoản thử
tồn tại lâu dài; không đổi tài khoản thật trên bản phục hồi hoặc production.
Kiểm thử này không giả lập kết quả của cào dữ liệu: không chạy cào, không
gửi Google/payment, không mở phiên web. Các ngày hết hạn được truyền vào
core để kiểm tra ranh giới, không thay đồng hồ máy chủ.

Bước còn lại trước production: kiểm chứng launcher/lịch chu kỳ và tích hợp
API/worker ở chế độ ví thật; xác minh tác vụ thực đang chạy, duyệt xử lý các
tài khoản cũ chưa có chu kỳ. Chưa cho phép deploy hoặc bật ví thực.

Sau lượt này, toàn bộ 207 tests backend đạt; diff không có lỗi khoảng trắng.

```powershell
.\.venv\Scripts\python.exe .\tools\rehearse_restored_wallet.py --database qd766_restore_20261004_092135 --connection-file .env
```

## Lệnh đối soát nguồn (chỉ đọc)

## Tích hợp API/worker/lịch chu kỳ — 04/10/2026

Đã chạy `tools/test_real_wallet_integration.py` trên PostgreSQL của database
phục hồi, trong schema thử mới `real_wallet_integration_bb1b7f875993466fa3abf19474f8240d`.
Giữ lại schema để đối soát; chỉ chứa tài khoản/dữ liệu giả. Schema public
được kiểm tra guard revision/cột chỉ đọc; fingerprint mọi bảng public
trước và sau lượt kiểm tra khớp, không thay bản phục hồi gốc.

Chế độ Settings là real_wallet_enabled=True, hai cờ local/source-wallet-trial
đều False. Test cố ý thay binding engine sang schema riêng; không chứng
minh public launcher đang chạy ví thật. Production engine luôn cố định
public và launcher hiện tại vẫn tắt ví/paid requests. Không mở port/server.

- API tạo/đổi lời mời, OAuth callback (mock identity), tự mở tháng thử +100.
- Hai tài khoản dùng chung một job; worker xử lý qua run_one_job, thu riêng
  5 mỗi tài khoản, có snapshot đủ 6 nhóm. Payload processor được mock,
  không vận chuyển HTTP/cào DVCQG.
- Cache cho tài khoản thứ ba vẫn cần xác nhận/thu 5; xem lại của chính
  tài khoản không thu lại; 2 pending, thất bại hoàn và giải phóng slot.
- Khóa tài khoản thu hồi phiên; phạm vi cơ quan và admin boundary giữ đúng.
- TestClient vào actual lifespan: schema guard chạy, vòng chu kỳ tick đầu
  đạt. Đã chờ tick tự động thứ hai theo thời gian thật 60 giây, không ép
  đổi interval hoặc đồng hồ: cấp 100 tháng thử đang hiệu lực, hết hạn 95
  còn dư của tháng trước, giữ nguyên 5 đang giữ và 70 purchased Credit.
- Chạy maintenance thêm hai lần không cấp/hết hạn lại; health còn ok;
  API thay đổi circuit vẫn 403 kể cả tài khoản admin thử.
- Shutdown context dừng vòng nền trước khi đóng engine. Không thay task
  Windows, đăng nhập Google thật, bật payment, cào hoặc deploy Netlify.

207 tests backend vẫn đạt sau khi điều chỉnh helper ca xuyên suốt.
Lượt sơ bộ (chưa chờ tick 60 giây) được giữ trong schema
`real_wallet_integration_23f2652424cd40449f56f3e218e3d39c`.

Chưa chứng minh triển khai end-to-end qua Netlify/Cloudflare, Google thật
và dữ liệu thật; còn cần launcher opt-in được duyệt, kiểm tra cấu hình
các tiến trình thực và danh sách backfill tài khoản cũ trước production.

```powershell
.\.venv\Scripts\python.exe .\tools\test_real_wallet_integration.py --database qd766_restore_20261004_092135 --connection-file .env
```

## Đọc lại đối soát nguồn

Tại thư mục dự án trong PowerShell:

```powershell
.\.venv\Scripts\python.exe .\tools\audit_credit_transition.py --connection-file .env
.\.venv\Scripts\python.exe .\tools\check_credit_database_alignment.py --office-file .env --public-file .env.public
```

Công cụ chỉ cho PostgreSQL loopback, timeout 15 giây mỗi truy vấn, không
in email, mã tài khoản, cấu hình bí mật hoặc traceback. Kết quả luôn
`activationReady: false`: đọc đối soát thành công không cấp quyền deploy.
Biến môi trường tiến trình có ưu tiên hơn file cấu hình theo loader hiện có;
cần xác minh nơi chạy công cụ trước khi dùng báo cáo cho production.
