# Cấu hình phân tích AI

## Sử dụng

Quản trị → Cấu hình phân tích AI → chọn một trong sáu Nhóm chỉ tiêu. Mỗi nhóm có Hướng dẫn phân tích (tối đa 4.000 ký tự), Kiến thức nghiệp vụ đã duyệt (tối đa 10.000 ký tự) và bản nháp riêng. Nhập Ghi chú thay đổi rồi Lưu nhóm đang chọn. Cấu hình áp dụng cho nhóm đó trên hệ thống, không phải riêng từng tài khoản/tỉnh. Chuyển nhóm giữ bản nháp trong tab; Lưu một nhóm không lưu hoặc ghi đè các nhóm khác.

Mỗi yêu cầu Gemini chỉ nhận số liệu, phát hiện, bằng chứng so sánh, hướng dẫn và kiến thức của một nhóm do người dùng chọn. Không gửi cấu hình nhóm khác hoặc prompt chung cũ. Mỗi nhóm đã chọn có nhận định tổng quan, tối đa sáu yêu cầu nội bộ tuần tự rồi ghép kết quả đúng thứ tự. Quy tắc bảo vệ số liệu vẫn cố định. Không tự nhập lịch sử Gemini web, không tự học từ đầu ra chưa duyệt. Không nhập khóa API, mật khẩu, dữ liệu cá nhân hoặc hồ sơ cá nhân vào đây.

Người dùng chủ động bấm Phân tích, chọn 1–6 nhóm có dữ liệu rồi xác nhận: 5 Credit/nhóm, cả sáu là 30 Credit. Backend kiểm tra danh sách nhóm, dữ liệu và tính giá, không tin giá do trình duyệt gửi; mã lượt chống thu trùng. Giữ một khoản cho cả lượt, chỉ thu sau khi lưu thành công toàn bộ kết quả. Một nhóm lỗi hoặc kết quả không hợp lệ: cả lượt thất bại và hoàn đủ Credit, không công bố kết quả thiếu. Lượt cũ đã queued/running và kết quả cũ vẫn giữ giá đã xác nhận (20 Credit); không tính lại giá. Giá mới ghim trong bằng chứng JSON hiện có, không cần migration ví. Giữ hai slot toàn hệ thống, không tạo thêm luồng gọi provider. Có ngân sách thời gian 180 giây cho lượt cấu hình theo nhóm và retry 503 có giới hạn; cần đo độ trễ thực tế sau khi thử Gemini bằng lượt được người dùng xác nhận. Kiểm thử hiện tại dùng provider giả lập, không gọi API thật.

Cấu hình chung cũ và các phiên bản đã lưu được giữ nguyên. Lượt mới có lựa chọn nhóm luôn dùng cấu hình riêng từng nhóm; các nhóm chưa chỉnh sử dụng mặc định riêng, không tự nhân prompt chung dài vào cả sáu nhóm. Lượt cũ trong hàng chờ giữ cấu hình đã ghim. Có thể xem cấu hình chung cũ ở lịch sử (chỉ đọc); khôi phục chỉ đưa nhóm đang chọn vào bản nháp. Client cũ không được ghi cấu hình chung trở lại sau khi đã bật chế độ nhóm.

## Bằng chứng so sánh trong phân tích AI

Giao diện kết quả tách hai khối: “Vấn đề cần ưu tiên” chỉ hiển thị thực trạng/bằng chứng của các phát hiện ưu tiên; “Hành động cần thực hiện” hiển thị khuyến nghị Gemini gắn với từng phát hiện, bao gồm hành động khắc phục và duy trì. Không lặp khuyến nghị ở khối thực trạng, không tự coi điểm thấp là lỗi đã xác minh. Đổi cách trình bày không sửa kết quả đã lưu, giá hay hàng chờ.

Kết quả hiển thị thành từng khối theo nhóm của lượt đã lưu, mỗi nhóm có hai phần thực trạng và hành động. Không dùng bản nháp lựa chọn của lượt tiếp theo để lọc kết quả cũ; bản cũ chưa ghi danh sách nhóm được phân khối theo groupId của các nhận định. Nút chủ động chạy mang tên “Phân tích điểm số”; chưa có kết quả thì không tạo các khối kết quả trống. Padding chỉ thu gọn trong khu vực phân tích, không thay giao diện khác. Cấu hình vẫn dùng hai trường riêng cho từng nhóm, không cần đổi schema hay tự ghi lại prompt đã lưu.

- Đối chiếu tối đa ba kỳ liền trước cùng loại (tháng/quý/năm), đúng thứ tự kể cả khi có khoảng trống. Không lấy kỳ xa hơn thay kỳ thiếu. Chỉ dùng bản complete của kỳ/cơ quan, thời điểm thu thập không mới hơn bản đang phân tích.
- Khác điểm tối đa, cấu trúc chỉ tiêu hoặc phiên bản công thức đã biết: không tính chênh lệch kỳ. Không bảo đảm phát hiện được thay đổi công thức nếu nguồn không cung cấp dấu hiệu/version; luôn cần đối chiếu nghiệp vụ.
- Cơ quan trực thuộc: cùng tỉnh, cùng cấp xác định trong danh mục (xã với xã, sở với sở), cùng kỳ. Tổng hợp cấp tỉnh: chỉ so các tổng hợp tỉnh cùng kỳ và cùng ngày thu thập theo giờ Việt Nam, không dùng bản thu sau bản đang phân tích.
- Lọc cứng `80% × totalReceived ≤ totalReceived của đơn vị đối chiếu ≤ 120% × totalReceived`. Hai biên được nhận; khác cấp, khác thang điểm hoặc phiên bản công thức đã biết thì loại. Tổng hồ sơ thiếu, bằng 0 hoặc mâu thuẫn với `totalOnTime + totalOverdue`: không lập nhóm tương đồng.
- Gemini chỉ nhận chuẩn tổng hợp của nhóm tương đồng (số đơn vị, trung vị, trung bình, khoảng điểm và vị trí tương đối), không nhận tên hay thông số/hồ sơ của các đơn vị khác. Không mở rộng quyền truy cập dữ liệu của tài khoản cơ quan.
- Thiếu kỳ hoặc không có đơn vị phù hợp được ghi rõ, không suy đoán. Kỳ chưa kết thúc phải phân biệt ảnh hưởng hồ sơ đang xử lý với nguyên nhân đã xác minh; kiến thức nghiệp vụ theo nhóm hỗ trợ lời khuyên, không thay số liệu nguồn.
- Chỉ tạo bằng chứng khi người dùng xác nhận phân tích. Không thêm cào dữ liệu hoặc đổi logic hai menu So sánh theo thời gian/So sánh theo cơ quan.

Không cần restart/upcode sau mỗi lần lưu. Giá, model, khóa API, giới hạn hàng chờ, điều kiện phân quyền, schema đầu ra và các kiểm tra số liệu vẫn do code kiểm soát. Cấu hình không tự chạy Gemini và không sử dụng Credit.

## Phiên bản và an toàn

- Chỉ admin đang có phiên hợp lệ, được mời, được phép xem/sửa; ghi cần CSRF.
- Lưu tạo revision mới và audit chỉ ghi số phiên bản, không chép toàn bộ nội dung vào nhật ký chung.
- Kiểm tra expectedVersion và khóa PostgreSQL ngăn ghi đè khi hai phiên quản trị cùng lưu.
- Bản mặc định có số phiên bản không; migration không tạo nội dung mới hoặc thay cấu hình đang áp dụng.
- Lịch sử hiển thị hai mươi bản gần nhất; mọi phiên bản được giữ trong DB. Có thể đưa bản cũ/mặc định vào nháp rồi lưu thành phiên bản mới. Xem hoặc khôi phục nháp không tự áp dụng.
- Khi xác nhận phân tích, cấu hình được chụp cùng bằng chứng. Lượt queued/running và kết quả cũ không bị thay đổi khi admin cập nhật; kết quả lưu có configurationVersion để đối soát.
- Thiếu bảng prompt: mặc định riêng vẫn đọc được; giao diện admin không cho lưu. Tuy nhiên bản mới yêu cầu bảng bật/tắt (0022) trước khi nhận lượt phân tích mới: thiếu bảng này sẽ chặn an toàn, không giữ Credit.
- Thiếu bảng cấu hình nhóm: lượt mới chọn nhóm dùng mặc định riêng; chỉ chặn lưu cấu hình nhóm, lượt cũ giữ cấu hình đã ghim. Migration 0021 chỉ thêm bảng `analysis_group_config_revisions`, không thay dữ liệu cũ, ví, lịch cào hay hàng chờ.
- Prompt không bảo đảm tuyệt đối đúng về ngữ nghĩa. Kiến thức phải được quản trị viên kiểm chứng; kết quả AI vẫn cần đối chiếu số liệu.

## Kiểm thử

Kiểm thử gồm giá 5/30 Credit, giữ/thu/hoàn và chống thu trùng, xác thực nhóm/giá, chọn nhóm frontend, quyền cấu hình, kỳ liền trước/khoảng trống, đổi công thức, đúng cấp và biên ±20%, không gửi dữ liệu đơn vị khác. Provider chỉ mock; không gọi Gemini thật. Đã diễn tập migration 0020 và hai lượt lưu cùng expectedVersion trên PostgreSQL qd766_credit_test: một thành công, một bị chặn xung đột. Chưa áp dụng migration 0020/0021 vào DB chính thức, chưa restart backend hay deploy frontend cho tính năng này.

## Phát hành

### Bật/tắt Phân tích điểm số (0022)

- Nút trong Cấu hình phân tích AI lưu vào bảng singleton `analysis_feature_control`, độc lập với phiên bản prompt. Không cần upcode/restart sau mỗi lần bật/tắt; bản nháp các nhóm không mất.
- Khi tắt, bấm Phân tích điểm số kiểm tra trạng thái bằng GET không cache, hiển thị: **Tính năng tạm thời không khả dụng do đang trong quá trình nâng cấp.** Không mở xác nhận trả Credit. Backend kiểm tra lại khi POST để chặn cả trường hợp tắt sau khi mở dialog.
- Lượt đã bắt đầu được hoàn tất theo xác nhận cũ. Worker không bắt đầu lượt queued mới khi tắt; hoàn khoản đã giữ khi xử lý lượt đó. Có thể hủy lượt chờ thủ công; kết quả và lịch sử cũ vẫn đọc được. Runtime pause/worker ngừng có thể trì hoãn xử lý hoàn cho lượt chờ; không hứa hoàn tức thì.
- Auth admin, CSRF, revision chống ghi đè, khóa admission chung và audit bảo vệ thao tác. Khôi phục prompt không tự bật tính năng. Bật trong DB không thay thế điều kiện `--gemini-analysis`, API key/model và flags ví/hàng chờ hiện hành.
- Migration 0022 chỉ thêm bảng, không sửa prompt, ví hoặc dữ liệu cào. Mặc định bật khi bảng đã có nhưng chưa lưu công tắc, giữ hành vi cũ; thiếu bảng thì chặn an toàn.
- Từ schema 0020/0021, dùng script mới `tools/migrate_analysis_feature_control.py --confirm --backup "DUONG_DAN_DUMP_MOI"` để nâng đúng tới 0022 (bao gồm 0021 nếu thiếu). Nếu còn 0019, chạy migration cấu hình 0020 đã duyệt trước. Không dùng lệnh upgrade head tùy tiện.
- Sau khi backend mới hoạt động: tắt tính năng, cập nhật prompt từng nhóm, deploy frontend và kiểm thử thông báo tắt; sau đó bật để thử một lượt có xác nhận Credit. Chưa thực hiện thao tác này trên hệ thống thật trong phiên rà soát.

Đợt cấu hình theo nhóm chưa deploy, chưa chạy migration trên DB chính thức. Trước khi deploy phải đối chiếu diff với bản chính thức, chỉ đóng gói thay đổi đã duyệt; không đưa nội dung không được yêu cầu vào đợt này. Trang preview dùng dữ liệu giả và không nằm trong allowlist Netlify.

Sau khi có backup mới đã kiểm tra, nâng riêng schema từ 0020 lên 0021 bằng `tools/migrate_analysis_group_configuration.py --confirm --backup "DUONG_DAN_DUMP_MOI"`. Không chạy migration chỉ để xem preview. Script không restart hay tự lưu cấu hình. DB trial tạo bảng qua launcher khi được restart; phiên này không restart backend đang chạy.

Tạo backup mới bằng script backup_postgresql.ps1. Sau khi kiểm tra dump/checksum, nâng riêng schema:

```powershell
.\.venv\Scripts\python.exe .\tools\migrate_analysis_configuration.py --confirm --backup "DUONG_DAN_DUMP_MOI"
```

Script chỉ chấp nhận schema office 0019 hoặc 0020, backup dưới một ngày có checksum đúng. Migration chỉ thêm hai bảng, không thay ví/hold/lịch cào/lượt phân tích. Không tự restart hay tự đặt prompt.

Sau đó restart public backend bằng script đã rà soát, giữ đủ các flags task hiện hành. Build/đóng gói/push frontend theo workflow hiện có. Kiểm thử đọc, lưu, xem lại phiên bản trong tài khoản admin; xác nhận người dùng thường không truy cập được. Một lượt Gemini thật vẫn cần người dùng chủ động xác nhận trả Credit.

Local Google trial dùng schema credit_google_trial của qd766_credit_test: launcher tạo hai bảng mới qua Base.metadata.create_all khi restart; không cần đổi bảng đang có. Nâng hàng chờ local theo script prepare_local_analysis_queue nếu trial còn constraint cũ.
