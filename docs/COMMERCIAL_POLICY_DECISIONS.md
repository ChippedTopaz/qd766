# Chính sách subscription và Credit — nguồn soạn điều khoản sử dụng

Cập nhật: 04/10/2026 (giờ Việt Nam).
Nguồn: các quyết định trực tiếp của chủ dự án trong cuộc trò chuyện QĐ766.
Đây là tài liệu quyết định sản phẩm, chưa phải điều khoản pháp lý công bố và
không khẳng định các chức năng dưới đây đã được triển khai production.
Không tự thay đổi chính sách khi sửa code; thay đổi cần chủ dự án xác nhận.

## 1. Các quyết định đã chốt

### Tên gọi và tính phí khai thác

- Dùng thống nhất tên **Credit** trong giao diện và điều khoản.
- Một yêu cầu khai thác: một TTHC, một tỉnh, một kỳ tháng/quý/năm.
- Giá khai thác theo phương án thương mại: **5 Credit mỗi yêu cầu**.
- Các trường hợp thử trước đây dùng 3 Credit là mô phỏng, không phải giá thương mại.
- Dữ liệu tổng hợp tất cả TTHC theo tháng/quý/năm do hệ thống tự lấy; người dùng
  không tạo yêu cầu cập nhật dữ liệu này.
- Người dùng chọn bộ lọc không tự tạo yêu cầu. Phải bấm lấy dữ liệu, xem chi phí
  và xác nhận trước khi giữ Credit.

### Dữ liệu dùng chung và quyền cá nhân

- Người dùng mới yêu cầu bộ dữ liệu đã có hoặc đang được lấy vẫn trả Credit riêng.
  Không tạo thêm job cào trùng nếu đã có job phù hợp hoặc dữ liệu dùng được.
- Chỉ hiển thị thủ tục đã thuộc quyền khai thác của chính tài khoản trong thư viện.
  Dữ liệu do người khác yêu cầu không tự xuất hiện trong thư viện tài khoản này.
- Mở lại bộ dữ liệu đã được tài khoản khai thác thành công, kể cả sau F5,
  không thu thêm Credit và không tự cào lại.
- Không thu theo mỗi cơ quan được chọn để xem trong bộ dữ liệu; quyền xem vẫn
  tuân theo phạm vi tài khoản được cấp.

### Giữ, thu và hoàn Credit

- Khi xác nhận yêu cầu, giữ Credit; chỉ ghi nhận thu sau khi dữ liệu được lấy
  và lưu thành công hoặc dữ liệu có sẵn đã sẵn sàng cấp quyền cho người dùng.
- Thất bại, bị circuit ngăn chặn hoặc hủy: hoàn toàn bộ Credit đã giữ.
- Mọi thay đổi Credit phải có sổ giao dịch, không chỉ sửa trực tiếp số dư.
- Thông báo cho từng người dùng khi dữ liệu sẵn sàng hoặc yêu cầu thất bại.

### Hai nguồn Credit

- Credit cấp theo subscription hàng tháng không sử dụng hết sẽ hết hạn,
  không cộng dồn sang tháng sau.
- Credit mua riêng chưa sử dụng được cộng dồn sang tháng sau.
- Credit subscription được cấp vào ngày bắt đầu mỗi chu kỳ tháng của subscription,
  không mặc định cấp vào ngày đầu tháng dương lịch.
- Gói thanh toán 6/12 tháng vẫn cấp Credit từng tháng, không cấp toàn bộ ngay
  khi thanh toán. Tháng subscription đổi bằng Credit không phát sinh Credit gói.
- Phải phân biệt nguồn Credit trong hệ thống để chỉ Credit mua riêng được đổi gói.
- Ưu tiên sử dụng Credit subscription trước, sau đó mới đến Credit mua riêng.
- Hoàn về đúng nguồn đã giữ. Nếu Credit subscription đã hết hạn trong lúc job
  đang chờ và yêu cầu thất bại/hủy, phần hoàn được dùng thêm **7 ngày** từ lúc hoàn,
  không chuyển thành Credit mua riêng và không được dùng để quy đổi subscription.

### Đổi Credit mua riêng khi subscription hết hạn

- Mọi tài khoản cấp đơn vị, bao gồm xã/phường và Sở/ngành phạm vi một cơ quan:
  **300 Credit mua riêng → 1 tháng subscription mới**.
- Cấp tỉnh: **600 Credit mua riêng → 1 tháng subscription mới**.
- Không sử dụng Credit cấp theo subscription để quy đổi.
- Tháng subscription nhận bằng quy đổi **không cấp thêm 100/200 Credit**.
  Quy đổi chỉ gia hạn quyền sử dụng; Credit khai thác tính riêng.
- Không tự thực hiện quy đổi; luồng quy đổi cần xác nhận rõ chi phí của người dùng.

### Giới hạn yêu cầu đồng thời

- Mỗi tài khoản tối đa **2 yêu cầu đang chờ hoặc đang xử lý**.
- Tính theo yêu cầu của từng tài khoản, không theo số job dùng chung của hệ thống.
- Khi đã có 2 yêu cầu đang hoạt động, không nhận yêu cầu mới cho đến khi có chỗ trống.
- Yêu cầu hoàn thành, thất bại hoặc hủy đều giải phóng chỗ để gửi yêu cầu mới.
- Giới hạn cần được kiểm tra phía server, kể cả khi gửi từ nhiều tab hoặc thiết bị.

## 2. Bảng giá và ưu đãi chủ dự án đề xuất

Lưu nguyên phương án để đưa vào bản điều khoản/bảng giá khi duyệt phát hành;
chưa tự bật thanh toán hay subscription production.

| Phạm vi | 1 tháng | 6 tháng | 12 tháng | Credit cấp theo tháng trả phí |
| --- | ---: | ---: | ---: | ---: |
| Đơn vị/cấp xã | 99.000đ | 499.000đ | 890.000đ | 100 |
| Tỉnh | 199.000đ | 999.000đ | 1.790.000đ | 200 |

- Tháng đầu miễn phí, có 100 Credit dùng thử.
- Toàn quốc không cho tự đăng ký mua, chỉ admin cấp quyền; không phải vai trò admin.
- Phương án mua riêng: 50.000đ/100 Credit; 100.000đ/250 Credit;
  200.000đ/600 Credit; 500.000đ/1.500 Credit.
- Đề xuất 1.600 Credit cho gói 500.000đ từ trợ lý chưa được chủ dự án chốt,
  không thay thế phương án 1.500 Credit.
- Giá gạch ngang là tổng giá nếu trả từng tháng. Gói 6 tháng giảm thực tế
  khoảng 16%, không đúng 15%; gói năm khoảng 25%.
- Giá quy đổi tháng phải ghi rõ tổng tiền thanh toán trước, không gây hiểu là trả từng tháng.

### Ranh giới chu kỳ tháng — chốt ngày 04/10/2026

- Tính theo tháng lịch, giữ ngày gốc và giờ Việt Nam tại thời điểm bắt đầu.
- Tháng không có ngày tương ứng dùng ngày cuối tháng; tháng sau quay lại ngày gốc.
  Ví dụ: 31/1 → 28/2 → 31/3 (năm nhuận: 29/2).
- Không áp dụng phương án mỗi tháng luôn bằng 30 ngày; chủ dự án đã thay thế
  lựa chọn này bằng cách tính ngày cuối tháng nêu trên.

### Dùng thử và quyền khi hết hạn — chốt ngày 04/10/2026

- Mốc bắt đầu dùng thử ban đầu (đã được thay thế bằng quyết định bổ sung bên
  dưới): thời điểm admin chủ động kích hoạt tài khoản dùng thử. Cấp một tháng
  miễn phí và 100 Credit subscription đúng một lần, không tự cấp lại khi hết hạn.
- Quyền khi hết hạn: vẫn được xem lại dữ liệu đã khai thác của chính
  tài khoản, không thu thêm Credit; phải gia hạn trước khi gửi yêu cầu có phí mới.

### Tự cấp dùng thử và quyền tra cứu mặc định — cập nhật 04/10/2026

- Chủ dự án thay thế mốc kích hoạt thủ công: đăng nhập lần đầu và sử dụng lời
  mời hợp lệ thành công sẽ bắt đầu một tháng lịch, tự cấp 100 Credit subscription.
  Không bắt đầu từ ngày tạo link. Không cần thao tác cấp Credit thủ công nữa.
- Không cấp lặp khi đăng nhập lại, dùng lại link hoặc nhận lời mời khác; tài khoản
  đã từng có subscription không được mở tháng thử mới qua lời mời.
- Tra cứu TTHC là tính năng mặc định của tài khoản hoạt động, đã được mời và
  gán phạm vi. Bỏ bước cấp quyền khai thác riêng. Nút vẫn có khi Credit bằng 0
  để người dùng thấy thông báo rõ ràng, không coi số dư là quyền xem nút.
- Xác nhận vẫn kiểm tra subscription, số dư, phạm vi, phiên và giới hạn 2 yêu cầu.
  Chính sách chặn yêu cầu mới khi subscription hết hạn vẫn giữ nguyên. Tài khoản
  bị khóa không được dùng; mặc định tra cứu không mở rộng quyền sang tỉnh khác.
- Hiện chỉ bật chính sách mới trên local source-wallet. Chưa deploy production.

## 3. Những nội dung chưa chốt — không tự đưa thành cam kết

- Cách sắp xếp sử dụng giữa nhiều đợt Credit subscription có hạn dùng khác nhau.
- Chính sách hoàn tiền subscription, chuyển gói, tài khoản dùng chung, giới hạn thiết bị.
- Giá gồm/chưa gồm thuế, hóa đơn, quyền sử dụng dữ liệu nguồn và điều kiện dịch vụ.
- Không tự động gia hạn/đổi Credit khi chưa có sự đồng ý của người dùng.

## 4. Ghi chú triển khai

- Hiện local đã kiểm chứng giữ/thu/hoàn, cache dùng chung và thư viện cá nhân.
- Giới hạn 2 yêu cầu đã triển khai trên API bản local: khóa dòng tài khoản,
  chặn vượt giới hạn và rollback toàn bộ batch bị từ chối.
  150 tests backend đạt; PostgreSQL riêng kiểm chứng 6 yêu cầu khác nhau gửi
  đồng thời chỉ nhận 2, không giữ thêm Credit cho 4 yêu cầu bị chặn.
- Replay hoặc mở lại dữ liệu đã thuộc tài khoản không chiếm chỗ mới.
  Dữ liệu có sẵn trả ngay không tạo yêu cầu đang chờ.
- Lõi Credit theo nguồn/hạn dùng, chu kỳ subscription và quy đổi đã triển khai
  riêng để kiểm thử; chưa nối vào số dư, quyền truy cập và Usage đang dùng.
- Trước khi công bố: đối chiếu code, bảng giá, Usage, xác nhận thanh toán và
  điều khoản với tài liệu này; chủ dự án duyệt bản cuối.
