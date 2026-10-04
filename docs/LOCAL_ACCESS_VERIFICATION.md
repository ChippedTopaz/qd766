# Kiểm chứng phân quyền bản thử — 03/10/2026

## Kết quả

Bộ kiểm thử backend: 146 tests đạt; frontend typecheck đạt.
Đây là kiểm thử tự động bằng tài khoản/phiên giả trong database SQLite riêng,
qua API và middleware của ứng dụng. Không phải kiểm toán bảo mật toàn diện,
không thực hiện đăng nhập Google mới hoặc sửa các tài khoản trên 8771/production.

| Trường hợp | Bằng chứng kiểm thử | Kết quả |
| --- | --- | --- |
| Cơ quan chỉ xem chi tiết của đơn vị được gán; đổi tỉnh bị chặn | test_trial_admin: agency_data_filtered_outside_shared_cache_and_cross_root_denied; test_local_credit_trial: agency_paid_data_stays_scoped_and_shared_cache_is_not_redacted | Đạt |
| Không tự nâng quyền admin hoặc cấp credit | test_trial_admin: user_cannot_admin_or_self_promote; test_local_credit_trial: ledger_read_and_csrf_on_grant | Đạt |
| Sửa account_id trên URL không đọc lịch sử/credit của người khác | test_local_credit_trial: url_account_injection_does_not_expose_other_history_or_credit | Đạt |
| Không đánh dấu thông báo của người khác đã đọc | test_user_collection: notifications_persist_and_acknowledgement_is_account_scoped; test_local_credit_trial: url_account_injection_does_not_expose_other_history_or_credit | Đạt |
| Khóa tài khoản vô hiệu hóa phiên cũ trên dashboard, lịch sử, credit và yêu cầu mới | test_local_credit_trial: locked_account_cannot_reuse_session_to_read_or_request | Đạt |
| Thu hồi quyền giữa báo giá và xác nhận không tạo job | test_local_credit_trial: revoke_between_quote_and_submit | Đạt |
| Thu hồi quyền tạo mới không xóa quyền đọc dữ liệu đã mua, không bỏ yêu cầu đang xử lý | test_local_credit_trial: revoked_permission_keeps_previously_purchased_library; revoke_new_collection_permission_does_not_drop_pending_request | Đạt |

Điểm tổng hợp đơn vị cùng cấp dùng để so sánh vẫn được phép; dữ liệu thành phần
ngoài cơ quan được gán bị lọc. Không đồng nhất quyền so sánh với quyền xem chi tiết.

## Bước còn lại trước triển khai

- Kiểm tra trực quan trang tài khoản và Usage trên desktop/mobile.
- Chốt gói thay đổi local, sao lưu, cấu hình và kế hoạch rollback trước khi người dùng duyệt deploy.
- Kiểm chứng cấu hình bản public sau khi bật credit; các PASS local không tự chứng minh production đúng.
- Chưa triển khai thanh toán, không push/deploy trong đợt kiểm tra này.
