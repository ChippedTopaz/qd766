# Hỏi - đáp nhanh

Khung nằm ngay trên tên tài khoản trong sidebar.
Trên desktop, khung lấp khoảng trống dưới menu cuối (cách 18px) và trên tên tài
khoản. Header/thống kê ở trên, câu hỏi/đáp án căn giữa, nút gửi/chuyển câu ở đáy.
Nội dung dài cuộn riêng, không đẩy nút; mobile dùng khung gọn 300px.
Điểm độc lập với Credit: đúng +1, sai +0 và chuỗi đúng về 0; giữ kỷ lục.
Mỗi câu có 60 giây theo hạn máy chủ. Câu hỏi đã
giao giữ nguyên qua tải lại/đăng nhập lại cho đến khi gửi đáp án hoặc hết hạn (trừ khi quản trị thu hồi).
Sau trả lời, hiển thị giải thích và nút Câu tiếp theo. Tự chuyển sau 15 giây kể từ
khi nhận kết quả; vẫn có thể bấm chuyển ngay. Đồng hồ header hiển thị thời gian
chờ. Tab ẩn không giao câu mới; khi quay lại, chuyển nếu đã đủ 15 giây. Chỉ GET
câu tiếp theo, không gửi lại đáp án/cộng điểm. Lỗi mạng retry có backoff 10 giây.
Mỗi tài khoản trả lời một câu
hỏi một lần mỗi lượt. Hết ngân hàng có nút Trả lời lại từ đầu: điểm/chuỗi/lượng câu
đã trả lời đặt về 0, giữ kỷ lục, tạo lượt mới và không xóa lịch sử cũ. Mỗi người chọn
ngẫu nhiên câu chưa làm trong lượt, không lặp; không xáo đáp án. Hết 60 giây nhận
0 điểm, mất chuỗi và chuyển câu kế. Tab ẩn không tự lấy thêm câu; khi quay lại xử
lý hạn cũ rồi giao câu tiếp. Không tải lại dashboard mỗi giây: chỉ cập nhật đồng hồ
trong khung Trivia; gọi API lúc chuyển câu, gửi đáp án hoặc làm lại.

Quản trị > Ngân hàng Hỏi - đáp nhanh: nhập câu hỏi, 2–3 đáp án A–C, một đáp án đúng,
giải thích tùy chọn, trạng thái Nháp/Công khai/Thu hồi. Sau công khai, khóa nội dung
để không thay đổi đáp án của người đã trả lời. Có thể thu hồi hoặc tạo câu mới.
Ngân hàng tải khi mở menu, không chặn tải dashboard; Trivia không polling nền.
Tạo mới/Mở dùng hộp thoại; lưu thành công đóng hộp, lỗi giữ nguyên nội dung.
Lỗi xác thực/tải ngân hàng không được báo nhầm là thiếu schema.
Menu sidebar tên Hỏi đáp nhanh. Danh mục có STT theo trang/kết quả tìm kiếm, tìm
theo nội dung câu hỏi, lọc Công khai/Nháp/Thu hồi và phân trang 10 câu. Câu Nháp
có nút Duyệt công khai, lưu và khóa nội dung ngay trong một giao dịch có kiểm tra
revision/CSRF/quyền quản trị. Câu cũ đã công khai giữ nguyên nội dung/lịch sử.
Lượt đúng cộng tất cả các lượt chơi,
người đúng đếm tài khoản duy nhất; mở danh sách để xem tên, email, số lượt đúng và
lần đúng gần nhất. Danh sách người trả lời đúng giữ 100 người/trang.
Dữ liệu danh sách chỉ trả qua API quản trị đã xác thực, không đưa vào API
câu hỏi/điểm của người chơi. Đồng hồ nằm bên phải cùng hàng tiêu đề.

## Nhập Excel

Quản trị > Hỏi đáp nhanh > Nhập câu hỏi từ Excel: tải file mẫu, điền sheet
`CauHoi`, giữ dòng tiêu đề 6 cột: Câu hỏi, Đáp án A–C, Đáp án đúng, Giải thích.
File mẫu cũ 9 cột vẫn được nhận nếu D, E, F để trống.
Xóa/thay câu ví dụ ở dòng 2. Đáp án đúng ghi một chữ A–C; ít nhất hai đáp án,
không bỏ trống ở giữa. Tối đa 500 câu, file .xlsx tối đa 2 MB.

Bấm Kiểm tra file để xem trước, lỗi theo dòng và các câu trùng. Có lỗi thì không
lưu bất kỳ câu nào. Sau xác nhận, câu mới lưu Nháp; mở từng câu để công khai.
Trùng nội dung câu hỏi (chuẩn Unicode, bỏ khác biệt hoa/thường và khoảng trắng)
trong file hoặc ngân hàng sẽ bị bỏ qua; không sửa câu đã có. Gửi lại cùng file
không nhân đôi câu hỏi. Nếu nội dung đã có nhưng cần đáp án khác, hãy sửa bản
nháp hoặc tạo câu hỏi khác, không dùng import để ghi đè.

Import chỉ quản trị và CSRF, giới hạn body/giải nén/số dòng; không chạy công thức,
macro hoặc tải tài nguyên ngoài. Kiểm tra và lưu trong một giao dịch; ghi audit.
Không thay đổi Credit, quyền tài khoản, lịch cào hay điểm/lượt chơi đã có.
File chỉ xử lý trong bộ nhớ, không lưu file gốc. Không cần migration bổ sung
ngoài schema Trivia 0023.

## Xóa câu hỏi

Nút Xóa ở từng dòng ngân hàng mở hộp xác nhận, yêu cầu tích xác nhận trước khi
xóa vĩnh viễn. Chỉ quản trị, CSRF, kiểm tra revision chống xóa bản đã thay đổi.
Xóa câu hỏi và mọi lịch sử của câu đó ở tất cả các lượt; xóa câu đang giao thì
hủy hạn của câu đó và giao câu khác ở lần tải tiếp theo. Không ảnh hưởng Credit.

Tính lại điểm/số câu trong lượt hiện tại, chuỗi hiện tại và kỷ lục trên tất cả
các lượt còn lại. Mỗi câu đúng bị xóa mất đóng góp một điểm và một mắt xích trong
chuỗi. Kỷ lục ở lượt khác không có câu bị xóa được giữ. Xóa câu sai/hết hạn không
nối các chuỗi đã bị ngắt hoặc phục hồi chuỗi đã mất. Xóa nhiều lần liên tiếp vẫn
giữ ranh giới này. Snapshot điểm trong lịch sử còn lại được cập nhật tương ứng.
Người chơi thấy số mới khi tải câu tiếp theo/tải lại trang, không polling thêm.
Giao dịch xóa/tính lại/audit là nguyên khối; PostgreSQL dùng khóa độc quyền Trivia
khi xóa, các giao dịch người chơi vẫn đồng thời với nhau qua khóa chia sẻ.

## Ranh giới bảo mật chi tiết

- Đăng nhập, tài khoản hoạt động và đã duyệt; lưu tiến trình theo tài khoản của phiên.
- Chỉ quản trị được xem đáp án trước trả lời hoặc ghi ngân hàng; ghi phải có CSRF.
- API giao câu hỏi không trả đáp án đúng/giải thích. Sau gửi đáp án mới trả kết quả.
- Chấm backend, khóa tài khoản trong PostgreSQL và khóa chính kép chống cộng điểm
  lại qua nhiều tab/gửi lại. Câu không được giao không thể được chấm.
- Nội dung HTML được escape. Không thay đổi quyền tỉnh/cơ quan, ví, phân tích AI,
  lịch cào dữ liệu hoặc tạo yêu cầu khai thác.

## Chuẩn bị deploy (chưa thực hiện lên thật)

1. Backup PostgreSQL, giữ file .dump và .sha256.
2. Chạy `.venv\Scripts\python.exe tools\migrate_trivia.py --confirm --backup "ĐƯỜNG_DẪN_BACKUP.dump"`.
   Chỉ nâng từ schema 0022 lên 0023, thêm ba bảng Trivia; không ghi dữ liệu tài khoản/Credit.
3. Kiểm tra cấu hình, restart backend bằng script đã duyệt, rồi triển khai frontend.
4. Tạo câu hỏi nháp, kiểm tra trước khi công khai. Không tự seed câu hỏi ví dụ lên thật.

Nếu schema chưa nâng, hai trang hiển thị chưa sẵn sàng cho Trivia, không làm hỏng
dashboard hiện có. Bản xem trước 8812 dùng SQLite riêng trong bộ nhớ và câu hỏi mẫu;
khởi động lại preview sẽ xóa điểm/câu hỏi mô phỏng, không ảnh hưởng dữ liệu thật.
