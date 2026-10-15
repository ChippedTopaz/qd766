# Thống nhất đăng ký và duyệt tài khoản (15/10/2026)

## Phạm vi được duyệt

- Bỏ menu Mời dùng thử, form tạo link một người và link đăng ký dùng chung.
- Giữ Đăng ký chờ duyệt độc lập; người dùng tự đăng ký tài khoản cơ quan,
  admin duyệt rồi điều chỉnh phạm vi xem trong Quản lý tài khoản nếu cần.
- Form phân quyền tài khoản không còn dùng chung với tạo lời mời: chỉ mở
  khi chọn một tài khoản, có Lưu quyền/Hủy. Không có nhánh POST tạo link.
- Không tự duyệt khi sửa quyền, không cấp vai trò admin. Cơ quan/cả tỉnh/
  toàn quốc vẫn được kiểm tra bằng dữ liệu danh mục, admin + CSRF và audit;
  phiên cũ bị thu hồi, người dùng đăng nhập lại sau khi đổi quyền.

## Tương thích và an toàn

- Hai endpoint tạo mới `/admin/invitations`, `/admin/registration-links`
  trả HTTP 410 cho yêu cầu hợp lệ có quyền admin/CSRF. Frontend cũ không
  thể tiếp tục tạo link. Không có INSERT hoặc cấp Credit từ hai endpoint này.
- Không xóa bảng, bản ghi lời mời, hồ sơ, audit, subscription, Credit hay
  thu hồi link cũ hàng loạt. API đọc lịch sử/thu hồi link cũ vẫn giữ.
- Link cũ đã cấp vẫn theo hạn và điều kiện cũ. Hồ sơ qua link chung đang
  chờ duyệt tiếp tục được duyệt. Cơ chế tạo bản ghi invitation đã dùng
  nội bộ khi phê duyệt không bị thay đổi.
- Sửa phạm vi xem không kích hoạt lại dùng thử, không tạo chu kỳ mới,
  không cấp lại Credit, không thay đổi ngày hết hạn hiện có.
- Không thay cấu hình đăng ký công khai, OAuth, quyền quản trị, schema,
  worker, lịch cào hay nội dung công thức đã lưu. Chưa deploy.

## Kiểm thử

- 58 kiểm thử backend PASS: đăng ký công khai, duyệt/từ chối, link cũ,
  giới hạn quyền/cross-province, CSRF, phiên đăng nhập, Credit/subscription,
  quản lý tài khoản phân trang và nhật ký hệ thống/cảnh báo theo đợt.
- Kiểm thử mới chứng minh nâng cơ quan → tỉnh → toàn quốc → cơ quan
  không thay số Credit, ngày bắt đầu/kết thúc, số chu kỳ, sự kiện ví,
  hoặc vai trò user. Người chưa duyệt vẫn chưa được nhận quyền truy cập.
- TypeScript compile và 4 bộ frontend PASS. Không có yêu cầu đọc/tạo
  lời mời lúc khởi động quản trị hoặc làm mới tài khoản.
- Google và dữ liệu đều giả lập/SQLite; không phải kiểm thử OAuth Google
  thật, không truy cập nguồn hoặc thay đổi database production.
- Preview chỉ đọc đã bật hiển thị Đăng ký chờ duyệt, vẫn từ chối mọi POST.
  Đã xác nhận trực tiếp sau khi người dùng khởi động lại preview.
- UI xác nhận: không có menu Mời dùng thử; Đăng ký chờ duyệt mở đúng,
  hiện đủ tiêu đề cột và trạng thái rỗng của dữ liệu mô phỏng. Form phân
  quyền mở được, chọn tỉnh/phạm vi cơ quan tải đúng danh sách; Hủy đóng
  form, không gửi POST lưu quyền/cấp Credit/duyệt hồ sơ.
- Sửa thêm lỗi mở tài khoản chưa gán tỉnh: không gọi directory với UUID
  rỗng; yêu cầu chọn tỉnh trước. Xác nhận trực tiếp trên tài khoản mô phỏng.
- Không tràn ngang tại viewport 1254px. Ảnh: `outputs/admin-registration-no-invites-20261015.jpg`.
- Có một phản hồi Internal Server Error khi reload preview; reload tiếp
  theo vào lại được. Chưa có traceback để kết luận nguyên nhân; đây không
  phải xác nhận tải ổn định lâu dài hay kết quả kiểm thử production.
