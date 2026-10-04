# Chuẩn bị hai nguồn Credit và subscription — 04/10/2026

Chính sách chính: COMMERCIAL_POLICY_DECISIONS.md.
Tài liệu này là kế hoạch triển khai, không khẳng định đã thay đổi số dư hoặc schema.

Các phần tiến độ bên dưới là nhật ký theo từng bước; trạng thái mới nhất nằm
ở cuối tài liệu. Những mục "chưa nối" ở bước cũ không mô tả bản local hiện tại.

## Tiến độ lõi ngày 04/10/2026

- Đã viết credit_wallet.py và models CreditLot/CreditHold/CreditWalletEvent.
- Cấp theo nguồn, ưu tiên subscription, giữ phân bổ, thu/hoàn idempotent,
  ghi hết hạn và hoàn 7 ngày cho phần subscription đã hết hạn trong lúc chờ.
- Hết hạn chỉ xóa khả dụng của subscription, không xóa phần đang giữ hoặc mua riêng.
- Khóa dòng tài khoản trước thay đổi; caller sở hữu transaction, lõi không tự commit.
- Các mô hình mới chưa được nối vào số dư UserAccount hay API khai thác hiện tại.
  Không tạo hai cơ chế số dư cùng hoạt động.
- Migration 0013 chỉ chuẩn bị. Không chạy trên production hoặc chuyển đổi số dư cũ.
- Trong nội bộ nguồn subscription, mã hiện ưu tiên hạn gần nhất; đây là lựa chọn
  kỹ thuật chờ duyệt khi nối luồng người dùng, không tự viết thành điều khoản.
- Chưa có subscription lifecycle, scheduler cấp theo chu kỳ, đổi 300/600, API/UI
  nguồn-aware hoặc chuyển đổi ledger cũ. Đây là bước lõi, không phải bản phát hành.

## Hợp đồng dữ liệu dự kiến

- Subscription: tài khoản, cấp đơn vị/tỉnh, cách gia hạn (thanh toán/quy đổi),
  ngày bắt đầu/kết thúc, chu kỳ cấp Credit. Tháng đổi Credit không cấp Credit gói.
- Credit theo từng đợt: nguồn subscription/mua riêng/legacy, số còn khả dụng,
  đang giữ, ngày cấp, hạn dùng (mua riêng không hết hạn theo tháng).
- Phân bổ cho yêu cầu: lưu số Credit giữ từ mỗi đợt để thu/hoàn đúng nguồn.
- Ledger ghi cả nguồn và sự kiện cấp, giữ, thu, hoàn, hết hạn, quy đổi.
- Số dư hiện tại phải đối soát với tổng khả dụng của các đợt; không giữ hai số dư
  cập nhật độc lập mà không kiểm tra nhất quán.

## An toàn chuyển đổi

- Không tự coi số dư admin cấp trong thử nghiệm là Credit mua riêng có thể đổi gói.
- Số dư lịch sử chưa rõ nguồn cần bucket legacy và được chủ dự án xác nhận cách phân loại.
- Không làm thay đổi request/ledger đã hoàn thành; request đang giữ cần có phương án
  chuyển phân bổ hoặc chờ kết thúc trước migration.
- Quy đổi 300/600 khóa số dư tài khoản, chỉ dùng nguồn mua riêng, có xác nhận,
  idempotency và ledger; không cấp thêm Credit gói trong tháng quy đổi.
- Chỉ migration thử trên schema/database riêng; production cần backup và phê duyệt.

## Quy tắc bổ sung đã được xác nhận

- Mọi tài khoản cấp đơn vị áp dụng 300 Credit mua riêng đổi một tháng.
- Credit subscription hết hạn trong lúc chờ nếu hoàn trả được dùng thêm 7 ngày
  từ khi hoàn, vẫn thuộc nguồn subscription, không được quy đổi gia hạn.
- Dùng Credit subscription trước, Credit mua riêng sau.
- Cấp Credit tại đầu mỗi chu kỳ tháng của subscription. Gói 6/12 tháng cấp
  từng tháng, không cấp toàn bộ khi thanh toán; chu kỳ đổi Credit không cấp thêm.

## Còn cần xác nhận

- Mốc bắt đầu dùng thử đã chốt là admin chủ động kích hoạt. Ngày 29–31 dùng ngày cuối tháng và quay lại
  ngày gốc ở tháng sau; giữ giờ Việt Nam, không tính cố định 30 ngày.
- Thứ tự giữa nhiều đợt Credit subscription có hạn khác nhau.

## Nghiệm thu bắt buộc

- Cấp chu kỳ một lần kể cả scheduler chạy lại; thanh toán gói dài không cấp Credit
  toàn bộ ngay nếu chính sách cấp từng tháng được duyệt.
- Chỉ Credit subscription hết hạn, không trừ Credit mua riêng.
- Hết hạn không làm mất phần đã giữ trong job chưa kết thúc.
- Thu/hoàn đúng phân bổ, kể cả job dùng chung; không hoàn hai lần.
- Đổi gói không dùng Credit subscription/legacy chưa xác định; không đổi hai lần
  khi nhiều tab gửi đồng thời.
- Usage hiển thị hai nguồn, hạn dùng và lịch sử quy đổi; dữ liệu người khác bị chặn.

## Thông báo yêu cầu trùng đã triển khai local

- Đã sẵn sàng: Dữ liệu đã có trong thư viện; xem lại không phát sinh Credit.
- Đang chờ: Yêu cầu đã được tiếp nhận; không tạo trùng hoặc giữ thêm Credit.
- Chưa thuộc tài khoản: vẫn xác nhận chi phí, không tiết lộ cache của tài khoản khác.

## Tiến độ lõi ngày 04/10/2026

- Đã xây dựng các đợt Credit theo nguồn, phân bổ giữ/thu/hoàn và sổ giao dịch riêng.
- Credit subscription được dùng trước; Credit mua riêng không hết hạn. Phần đã giữ
  không bị mất khi đợt hết hạn; hoàn phần subscription đã hết hạn tạo đợt cùng nguồn
  dùng thêm 7 ngày, không khôi phục phần khả dụng đã hết hạn trước đó.
- Cấp và kết thúc giữ Credit có chống xử lý lặp; khóa tài khoản để tránh chi vượt
  số dư khi gửi đồng thời. Trong nguồn subscription, lõi hiện ưu tiên đợt hết hạn
  sớm nhất; đây là lựa chọn kỹ thuật cần chốt trước khi đưa vào điều khoản.
- Migration 20261004_0013 đã chuẩn bị nhưng chưa áp dụng vào production hay schema
  đang phục vụ 8771. Không tự phân loại số dư thử nghiệm hiện có thành Credit mua riêng.
- Kiểm chứng: 157 kiểm thử tự động đạt; kiểm thử PostgreSQL trên schema riêng đạt,
  gồm 6 yêu cầu đồng thời chỉ giữ được 2 lượt với ví 10 Credit, mỗi lượt 5 Credit.
  Không gọi nguồn DVCQG và không thay đổi database production.
- Chưa nối lõi mới vào yêu cầu khai thác, số dư hoặc Usage hiện hành. Còn triển khai
  vòng đời subscription, cấp từng chu kỳ, quy đổi 300/600 Credit và giao diện hai nguồn.

## Lõi chu kỳ và quy đổi — ngày 04/10/2026

- Đã bổ sung `SubscriptionCycle`, dịch vụ ghi nhận gói 1/6/12 tháng và cấp Credit
  khi chu kỳ tháng bắt đầu; chạy lại không cấp lặp. Tháng chưa đến chưa được cấp.
- Ranh giới tháng lấy từ ngày gốc theo giờ Việt Nam; tháng thiếu ngày đó dùng
  ngày cuối tháng. Dịch vụ bắt kịp chỉ cấp chu kỳ còn hiệu lực, không hồi sinh Credit
  của tháng đã hết hạn. Việc vận hành phải theo dõi lịch cấp để không bỏ lỡ chu kỳ.
- Tháng thử cấp 100 Credit; tháng trả phí đơn vị 100, tỉnh 200. Mốc bắt đầu dùng
  thử vẫn do bên gọi cung cấp, chưa tự kích hoạt cho người dùng.
- Quy đổi dùng duy nhất phần Credit mua riêng khả dụng: đơn vị 300, tỉnh 600;
  không dùng phần đang giữ cho job. Tạo chu kỳ gia hạn và ghi thu trong cùng
  transaction; tháng này không cấp thêm Credit. Chỉ đổi khi không còn chu kỳ
  subscription hiện tại hoặc tương lai; phạm vi toàn quốc không được tự quy đổi.
- Migration 0014 chỉ chuẩn bị. Chưa đăng ký lịch cấp, chưa áp dụng migration vào
  8771/production, chưa chuyển số dư cũ hoặc bật thanh toán. Cần nối lõi vào
  yêu cầu khai thác/quyền truy cập và giao diện Usage sau khi đối soát dữ liệu.
- Kiểm chứng: 165 tests đạt. PostgreSQL schema riêng kiểm chứng 6 lượt quy đổi
  gửi đồng thời chỉ thu một lượt và 6 lượt cấp chu kỳ đồng thời chỉ cấp một lần.
  Không gọi DVCQG và không thay đổi database production.

## Nối luồng và Usage local — ngày 04/10/2026

- Đã nối vào xác nhận yêu cầu, thu/hoàn qua worker, báo giá và số dư tài khoản.
  Opt-in riêng qua bảng enrollment và cờ local Google; Settings không nhận cờ
  nguồn ví từ môi trường. Production không tự truy vấn hoặc bật bảng mới.
- Đã thêm Usage hai nguồn/hạn dùng và xác nhận quy đổi; API kiểm tra phiên,
  CSRF, phạm vi tài khoản, số dư mua riêng và chống xử lý lặp. Admin cấp thử chọn
  nguồn và ghi nhật ký; không cấp vào số dư cũ của tài khoản đã bật nguồn ví.
- 3 tài khoản local được cấp một lần 100 subscription + 600 mua riêng mô phỏng;
  số dư cũ không đổi. Chưa xác nhận lịch sử đó là nguồn nào để chuyển sang ví mới.
- Chưa mở payment, lịch cấp chu kỳ production hoặc chính sách chặn toàn bộ
  quyền xem khi subscription hết hạn. Hiện chỉ chặn yêu cầu khai thác mới có phí;
  cách xử lý quyền đọc lịch sử khi hết hạn còn cần chủ dự án chốt.
- Kiểm chứng: 170 tests backend đạt; kiểm tra kiểu và các test giao diện Usage/
  thông báo yêu cầu đạt. PostgreSQL riêng kiểm chứng 6 lượt gửi đồng thời của
  2 tài khoản chỉ có 1 job, mỗi tài khoản thu riêng từ đúng phân bổ và số dư cũ
  không thay đổi. Đã kiểm tra Usage trong trình duyệt tại 8771 với 100/600 Credit.

## Kích hoạt và quản trị subscription — ngày 04/10/2026

- Quản lý tài khoản hiển thị trạng thái subscription, loại chu kỳ và ngày kết
  thúc cùng số dư hai nguồn. API chỉ đọc, không cấp Credit khi mở bảng.
- Admin có nút Kích hoạt dùng thử cho tài khoản đang hoạt động, đã được mời,
  phạm vi đơn vị/tỉnh và chưa có chu kỳ nào. Bắt đầu từ lúc bấm, cấp một tháng
  lịch và 100 Credit subscription một lần; không chuyển Credit cũ, không thay
  phân quyền xem hoặc quyền khai thác. Tài khoản test đã có chu kỳ giữ nguyên.
- Có xác thực admin, CSRF, chống gửi lặp và ghi nhật ký. API kích hoạt chỉ bật
  trên local source-wallet; chưa bật production hoặc mở thanh toán.
- Chính sách hết hạn đã chốt và kiểm thử: cho xem lại thư viện của chính tài
  khoản, không tính thêm Credit; chặn báo giá/yêu cầu có phí mới trước gia hạn.
- 173 tests backend đạt; kiểm tra kiểu và test trình bày admin đạt. PostgreSQL
  riêng kiểm chứng 6 thao tác kích hoạt đồng thời chỉ có một tháng thử và cấp
  100 Credit đúng một lần, số dư thử nghiệm cũ không đổi.

## Xử lý chu kỳ độc lập — ngày 04/10/2026

- Bổ sung service maintenance phân trang các tài khoản đã opt-in, khóa từng
  tài khoản và commit độc lập. Cấp tháng hiện hành đã được ghi nhận, ghi hết hạn
  subscription; không tự tạo trial/gói, không chạm Credit mua riêng/legacy/hold.
- Có kết quả số tài khoản đã xử lý, số chu kỳ được cấp, Credit hết hạn và lỗi
  đã lược thông tin riêng tư. Tài khoản lỗi rollback đầy đủ, chạy lại an toàn.
- Launcher chỉ cho chạy một lượt tại schema local Google với cờ source-wallet;
  không cho trộn với thao tác seed, worker hoặc khởi tạo lời mời.
- 179 tests đạt. PostgreSQL riêng: 6 lượt maintenance chạy đồng thời chỉ cấp
  chu kỳ một lần; các kiểm chứng chia sẻ job/thu/hoàn/quy đổi vẫn đạt.
- Đã chạy một lượt trên 3 tài khoản Google local: không lỗi, không cấp thêm
  hoặc ghi hết hạn vì chưa đến mốc. Không đổi kỳ trial đang dùng thử.
- Chưa đăng ký lịch chạy nền, chưa áp dụng migrations hay deploy production.

## Nghiệm thu gia hạn qua UI — 04/10/2026

- Đọc schema ca cấp đơn vị sau thao tác của chủ dự án: có đúng một chu kỳ
  quy đổi, 300 Credit mua riêng còn lại, 0 subscription và 0 Credit đang giữ.
  Không reset ca này. Đây là đối soát trạng thái, không thay xác nhận UI của người dùng.
- Chuẩn bị schema `credit_expiry_province` tách biệt và chuyển 8771 sang ca tỉnh:
  ban đầu hết hạn, 600 Credit mua riêng mô phỏng, thủ tục TEST.001 đã thuộc thư viện.
- Chờ nghiệm thu: hủy xác nhận không trừ; đổi 600 còn 0; có tháng mới nhưng
  không được cấp Credit; F5 không thu lặp; dữ liệu cũ vẫn xem được. Yêu cầu mới
  vẫn cần đủ 5 Credit, không nhầm quyền subscription với số dư Credit.
- Không thay ca Google local gốc, tài khoản thật hoặc production.
