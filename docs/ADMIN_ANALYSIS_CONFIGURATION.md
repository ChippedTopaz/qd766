# Cấu hình phân tích AI

## Sử dụng

Quản trị → Cấu hình phân tích AI. Chỉnh Hướng dẫn phân tích (tối đa mười nghìn ký tự), Kiến thức nghiệp vụ đã duyệt (tối đa ba mươi nghìn ký tự), nhập Ghi chú thay đổi, rồi Lưu cấu hình. Áp dụng chung cho hệ thống; không phải cấu hình riêng từng tài khoản/tỉnh.

Hướng dẫn bổ sung được gửi cùng quy tắc cố định của hệ thống. Kiến thức được gửi làm tài liệu tham khảo cùng số liệu trong kỳ; không tự nhập lịch sử Gemini web, không tự học từ đầu ra chưa duyệt. Không nhập khóa API, mật khẩu, dữ liệu cá nhân hoặc hồ sơ cá nhân vào đây.

Không cần restart/upcode sau mỗi lần lưu. Giá, model, khóa API, giới hạn hàng chờ, điều kiện phân quyền, schema đầu ra và các kiểm tra số liệu vẫn do code kiểm soát. Cấu hình không tự chạy Gemini và không sử dụng Credit.

## Phiên bản và an toàn

- Chỉ admin đang có phiên hợp lệ, được mời, được phép xem/sửa; ghi cần CSRF.
- Lưu tạo revision mới và audit chỉ ghi số phiên bản, không chép toàn bộ nội dung vào nhật ký chung.
- Kiểm tra expectedVersion và khóa PostgreSQL ngăn ghi đè khi hai phiên quản trị cùng lưu.
- Bản mặc định có số phiên bản không; migration không tạo nội dung mới hoặc thay cấu hình đang áp dụng.
- Lịch sử hiển thị hai mươi bản gần nhất; mọi phiên bản được giữ trong DB. Có thể đưa bản cũ/mặc định vào nháp rồi lưu thành phiên bản mới. Xem hoặc khôi phục nháp không tự áp dụng.
- Khi xác nhận phân tích, cấu hình được chụp cùng bằng chứng. Lượt queued/running và kết quả cũ không bị thay đổi khi admin cập nhật; kết quả lưu có configurationVersion để đối soát.
- Thiếu bảng cấu hình: phân tích vẫn dùng mặc định để tương thích schema 0019; giao diện admin hiển thị cần nâng schema và không cho lưu.
- Prompt không bảo đảm tuyệt đối đúng về ngữ nghĩa. Kiến thức phải được quản trị viên kiểm chứng; kết quả AI vẫn cần đối chiếu số liệu.

## Kiểm thử

305 kiểm thử Python; 41 file kiểm thử frontend, TypeScript build. Đã diễn tập migration 0020 và hai lượt lưu cùng expectedVersion trên PostgreSQL qd766_credit_test: một thành công, một bị chặn xung đột. Provider chỉ mock; không gọi Gemini thật. Chưa áp dụng migration 0020 vào DB chính thức, chưa restart backend hay deploy frontend cho tính năng này.

## Phát hành

Tạo backup mới bằng script backup_postgresql.ps1. Sau khi kiểm tra dump/checksum, nâng riêng schema:

```powershell
.\.venv\Scripts\python.exe .\tools\migrate_analysis_configuration.py --confirm --backup "DUONG_DAN_DUMP_MOI"
```

Script chỉ chấp nhận schema office 0019 hoặc 0020, backup dưới một ngày có checksum đúng. Migration chỉ thêm hai bảng, không thay ví/hold/lịch cào/lượt phân tích. Không tự restart hay tự đặt prompt.

Sau đó restart public backend bằng script đã rà soát, giữ đủ các flags task hiện hành. Build/đóng gói/push frontend theo workflow hiện có. Kiểm thử đọc, lưu, xem lại phiên bản trong tài khoản admin; xác nhận người dùng thường không truy cập được. Một lượt Gemini thật vẫn cần người dùng chủ động xác nhận trả Credit.

Local Google trial dùng schema credit_google_trial của qd766_credit_test: launcher tạo hai bảng mới qua Base.metadata.create_all khi restart; không cần đổi bảng đang có. Nâng hàng chờ local theo script prepare_local_analysis_queue nếu trial còn constraint cũ.
