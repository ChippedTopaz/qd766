# Biến động chỉ tiêu theo ngày — 13/10/2026

Trạng thái: bản thử nghiệm đã thực hiện, kiểm thử tự động PASS; chưa commit/push/deploy, chưa restart backend hoặc thay database production.

## Phạm vi

- Tổng quan → Chi tiết điểm số → chọn nhóm: thêm hai tab **Chi tiết hiện tại** (mặc định, giữ bảng chi tiết/so sánh cùng cấp) và **Biến động theo ngày** (bảng trái, biểu đồ thanh ngang phải thay vị trí bảng so sánh).
- Chỉ hiển thị với **Tất cả TTHC**. Không áp dụng cho dữ liệu cào theo một TTHC, không sửa lịch sử yêu cầu tra cứu hoặc chính sách Credit.
- Chọn Ngày làm mốc / Ngày đánh giá trong cùng kỳ và cùng cơ quan, nhóm chỉ tiêu. Mặc định ngày dữ liệu mới nhất và ngày liền trước theo lịch; thiếu ngày thì báo thiếu, không thay bằng ngày khác.
- Tử số, mẫu số, tỷ lệ, điểm: trước → sau và chênh lệch. Ngày theo dd/mm/yyyy; tỷ lệ chênh lệch là điểm phần trăm. Bấm tên chỉ tiêu để đổi biểu đồ bên phải, không mở bảng giải thích trùng lặp bên dưới nữa.
- Biểu đồ có một thanh cho từng ngày từ ngày làm mốc đến ngày đánh giá, bao gồm hai đầu mốc. Ví dụ 06–12/10 hiện đủ 7 dòng theo thứ tự ngày tăng dần. Thanh cao 6 px, ngày/thanh/số lượng cùng một hàng; dùng cùng thang đo từ 0 theo cực đại của toàn khoảng ngày. Dải dài giới hạn vùng cao 520 px và cuộn dọc, không kéo dài vô hạn trang.
- Độ dài biểu thị số lượng đạt lũy kế; tooltip cho biết chênh lệch với ngày liền trước nếu cả hai có dữ liệu, phần tổng bên dưới cho biết chênh lệch giữa hai mốc. Thiếu ngày giữ dòng ngày với dấu `—`, không coi là 0, không tính chênh lệch qua khoảng trống. Số 0 vẫn là thanh độ dài 0, không chia 0. Nhãn chung "Số lượng đạt", không gọi nhầm TTHC/PAKN là hồ sơ.
- Chọn chỉ tiêu vẽ chart không tạo request; đổi ngày giữ chỉ tiêu đã chọn nếu còn trong bảng. Màn hình hẹp xếp chart dưới bảng, không ảnh hưởng sidebar/Trivia. Cả khoảng ngày được đọc trong cùng GET, không một request cho mỗi thanh.
- Dùng cùng tên/thứ tự/phép chiếu dữ liệu với bảng chi tiết hiện tại. Không thay dữ liệu hoặc công thức đã lưu. Điểm nguồn giữ nguyên; các thành phần Thanh toán trực tuyến được ghi rõ là **Điểm tính đối chiếu**, không thay điểm nhóm nguồn công bố.
- Số liệu lũy kế thay đổi có thể do cập nhật hồ sơ cũ. Không khẳng định chênh lệch là hồ sơ mới phát sinh hoặc kết quả nhân quả của biện pháp bên ngoài.
- Ô không có dữ liệu chỉ hiện một dấu `—`, không có chênh lệch "Chưa đủ dữ liệu" bên dưới. Chênh lệch tỷ lệ/điểm bằng 0 theo độ chính xác hiển thị ghi **Không đổi**, không kèm hậu tố điểm/điểm %; số lượng trước/sau thực bằng 0 vẫn giữ nguyên.
- Nhóm Dịch vụ công trực tuyến: cấp tỉnh có tab theo ngày; cơ quan chỉ có điểm nhóm mà không có dữ liệu chi tiết thì ẩn tab, không tạo thêm GET rỗng. Không sử dụng dữ liệu tỉnh để giả làm dữ liệu của cơ quan.
- Tăng tỷ lệ quá hạn là xấu (đỏ), giảm là tốt (xanh); các tỷ lệ đạt còn lại và điểm dùng màu xanh/đỏ đậm hiện có theo biến động. Số lượng đạt/tổng số và chữ Không đổi in đậm màu xám đậm. Không biến dữ liệu thiếu thành 0.
- Bỏ caption Số liệu tham khảo/Điểm nguồn/Điểm tính đối chiếu dưới tên chỉ tiêu. Cơ sở điểm tính đối chiếu giữ trong tooltip ô điểm; không sửa số liệu/công thức. CSS màu/độ đậm chỉ áp dụng trong `.daily-indicator-panel`.

## Bảo mật và hiệu năng

- GET mới `/api/v1/dashboard/daily-indicator-comparison`: middleware kiểm tra đăng nhập, quyền tỉnh/cơ quan; route xác minh cơ quan thực sự thuộc tỉnh **trước cache lookup**. Cache khóa riêng theo tỉnh, cơ quan, kỳ, nhóm và cặp ngày.
- Tài khoản cơ quan chỉ đọc chi tiết cơ quan được gán. Không trả dữ liệu chi tiết đơn vị khác, cây children, raw response, đường dẫn snapshot hoặc chuỗi tham số tùy ý. Chặn scope formality, formality_id và POST.
- Hai entity ở hai đầu mốc giữ nguyên cho bảng. Dữ liệu ngày giữa hai mốc được đọc theo lô cho cùng cơ quan/nhóm/kỳ, dùng row_number chọn đúng phiên mới nhất mỗi ngày, một batch entity query và selectin metrics; không N+1 theo ngày. Cả khoảng lịch giới hạn tối đa 366 ngày, dùng index lịch sử có sẵn. Không đổi schema; không tạo job, không gọi DVCQG, không giữ/thu Credit.
- Không thêm polling. Một GET khi mở tab lần đầu; thay ngày hoặc bấm thử lại mới gọi thêm. Cache frontend giới hạn 36 ngữ cảnh, hết hạn 5 phút kiểm tra khi người dùng mở lại; HTML được tái sử dụng giữa các render không đổi dữ liệu/chỉ tiêu. Cache backend riêng tối đa 64 mục, TTL 60 giây, expiry pruning và single-flight; cache dashboard/catalog cũ giữ mặc định không đổi.
- Hủy request và bỏ response đến muộn khi rời tab; không sửa snapshot, URL hoặc kỳ đang chọn ở trang chính.
- Module mới 21.380 byte, gzip 6.701 byte sau chốt cache HTML. Đây là tài nguyên frontend thêm vào, không phải ước lượng traffic toàn website.
- Tab mới dùng ID riêng để không bị CSS bảng chi tiết cũ áp bố cục grid điện thoại. Không thay CSS sidebar, Trivia, motion hoặc bảng hiện tại.

## Kiểm chứng

- TypeScript compile PASS.
- Kiểm tra cuối chuẩn bị deploy: 521 backend tests cấu hình release PASS (47,235 giây); loại các bộ 2-job/watchdog đang gác lại.
- 95 frontend test files PASS; actual-app drilldown chạy riêng chế độ agency và national PASS.
- 13 bài endpoint mới: mặc định đúng ngày, thiếu ngày không fallback, ranh giới kỳ, chọn ngày không cùng/đảo thứ tự, đơn vị thật thuộc tỉnh, quyền/cache isolation, chỉ một đơn vị/nhóm, giữ điểm tổng hợp tỉnh từ cùng national summary, GET không ghi database; bổ sung dải 7 ngày/phiên mới nhất/ngày giữa bị thiếu/năm nhuận tối đa 366 ngày.
- Actual-app harness: tải lười, đúng cơ quan, đổi ngày/chọn chỉ tiêu chart, giữ bảng hiện tại/peer pane, giữ snapshot/URL, đổi nhóm reset tab, response đến muộn, scope all-only.
- Bổ sung actual-app profile `--province`: PASS DVC trực tuyến cấp tỉnh có tab và đọc đúng root; profile agency PASS không hiện tab/call khi thiếu chi tiết. Model tests PASS dấu gạch đơn, không dòng "Chưa đủ dữ liệu", chữ "Không đổi" ở tỷ lệ/điểm nhóm/thành phần.
- Chart tests PASS: 7 ngày 06–12/10 có đủ 7 thanh đúng thứ tự và số lượng; cực đại ngày giữa cũng tham gia thang đo; +200 giữa hai mốc; chọn chỉ tiêu khác không gọi API; giữ lựa chọn khi đổi ngày; giảm, bằng 0, không đổi, thiếu ngày giữa không coi là 0/không nối chênh lệch qua khoảng trống; thanh mảnh 6 px, CSS hai cột/stack màn hình hẹp; không còn khối bảng mở rộng.
- Sửa lỗi browser `Window.fetch: Illegal invocation`: không lưu native fetch rồi gọi như method của panel; dùng wrapper gọi `globalThis.fetch` đúng receiver. Bổ sung kiểm thử brand-check receiver vì mock arrow trước đây không phát hiện lỗi này. Không thay endpoint, dữ liệu, quyền hoặc Credit.
- Ví dụ 1.000/1.300 → 1.200/1.400: +200 đạt, +100 tổng số; tỷ lệ +8,79 điểm phần trăm; thành phần thanh toán max 6 điểm hiển thị 4,62 → 5,14 (+0,52).
- 100 lượt GET cache trên SQLite cô lập: cold 44,02 ms / 13 SQL; warm p95 6,16 ms / 4 SQL gồm xác thực quyền; response fixture 3.066 byte; không lỗi và không SQL ghi. Dải 7 ngày: 15 SQL, 5.647 byte, 0 writes; truy vấn theo lô không tăng theo từng thanh. Đây không phải đánh giá tải production hay benchmark dữ liệu năm đầy đủ.
- Gói frontend sau thêm dải ngày `outputs/daily-indicator-range-20261013-231037484/netlify-public`: PASS allowlist, không fixture/secrets/source maps. Thay thế gói preview trước đó.
- `git diff --check`: PASS.
- Preview HTTP chạy cùng process: PASS HTML, module, auth fixture, dữ liệu thanh toán mô phỏng. Không database production.

## Preview và hạn chế kiểm tra trực quan

Đã sử dụng computer-use skill, nhưng CUA không khởi tạo được do `failed to write kernel assets` (Windows error 3). Server background của phiên cũng không kết nối được từ công cụ localhost, dù kiểm thử HTTP trong cùng process PASS. Không tuyên bố đã xác minh trực quan desktop/mobile. Không sửa firewall hoặc thiết lập hệ thống để vượt giới hạn này.

Đã dừng server background của phiên để không chiếm cổng. Tại thư mục qd766 chạy:

```powershell
.\.venv\Scripts\python.exe -X utf8 .tmp-daily-indicator-preview.py
```

Mở `http://127.0.0.1:8837/?period=month-2026-10`, chọn nhóm Thanh toán trực tuyến → Biến động theo ngày để xem ví dụ. Giữ terminal mở; Ctrl+C dừng preview. Dùng frontend thực tế, auth cấp tỉnh để chọn được cơ quan hoặc điểm chung tỉnh và dữ liệu GET mô phỏng, từ chối POST. Cơ quan không có chi tiết DVC trực tuyến; chọn UBND tỉnh để thử tab ngày của nhóm này. Khi đổi script preview cần dừng terminal cũ bằng Ctrl+C rồi chạy lại.

Backup trước sửa: `.tmp-daily-indicator-backup-20261013-202255404`.

Khi có phép deploy, dùng allowlist bản gộp trong `docs/release-preparation-daily-20261013.md`, gồm helper/route/cache riêng, source+dist frontend, tests/doc tương ứng và score-drilldown. Không `git add -A`, không gộp prototype hoặc 2-job/watchdog chưa được duyệt.
