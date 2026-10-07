# Đối chiếu Công thức tính ngày 07/10/2026

Nguồn: file `Mô tả công thức tính chỉ số 766.docx` do quản trị viên gửi lại.
SHA256: `41A27E55E251C616408D310EE7467CC831D373ED95B108FD65D5832A337087AF`.
File trùng bản ngày 03/10; thay đổi lần này sửa nội dung trang tra cứu đã bị tóm tắt,
không thay đổi công thức chấm điểm, dữ liệu đã cào, quyền truy cập hoặc Credit.

## Nội dung và trình bày

- Trích nguyên các đoạn ở 5 cột của 20 dòng chỉ tiêu vào `formula-document.ts`.
  Công cụ đọc lại: `tools/extract_formula_document.py`, chạy bằng Python tài liệu
  được cung cấp trong runtime. Công cụ chỉ đọc DOCX và xuất JSON ra stdout.
- Tên chỉ tiêu lấy từ tài liệu, không dùng tên rút gọn. Mục 4.5 được tách thành
  hai tỷ lệ với tên tỷ lệ trong mô tả gốc, giữ phạm vi từng tỷ lệ và các cờ dữ liệu.
- Công thức chính dùng phân số; những mục có ngưỡng trình bày quy đổi điểm theo
  hai trường hợp. Bổ sung phân số toàn trình/một phần và trực tiếp/bưu chính.
- Mỗi khung có Mô tả nghiệp vụ, Lưu ý, Nguồn dữ liệu. Các mục ghi chưa có thông
  tin trong tài liệu hiển thị **Chưa có thông tin**, không thêm quy tắc suy đoán.
- Mô tả gốc giữ nguyên, kể cả các tham chiếu/chỗ lỗi văn bản trong nguồn. Nhận
  xét kỹ thuật tách trong mục thu gọn Điểm cần đối chiếu trong tài liệu. Mục 3.2
  phân biệt công thức theo Update với mô tả trước cập nhật, không xóa đoạn cũ.
- Giữ chính sách đã duyệt: mục phân loại PAKN 5.1 chỉ theo dõi, không hiển thị
  trong trang công thức chấm điểm. Không khôi phục bảng điểm tối đa riêng.
- Giữ 6 thẻ nhóm trên cùng, sổ tay gộp thu gọn bên dưới, chỉ mở nhóm đã chọn
  và cuộn mượt đến công thức. Chế độ giảm chuyển động vẫn được tôn trọng.

## Điểm tối đa và phạm vi an toàn

Giữ nguyên `formula-maximums.ts`, đối chiếu với METRICS và fixture điểm tối đa
API trong kiểm thử. Chưa biết phân bổ điểm riêng ghi **Chưa xác định**, không
gán toàn bộ điểm nhóm cho một chỉ tiêu con. Biết điểm tối đa không đồng nghĩa
biết công thức quy đổi; không thêm công thức khi DOCX không nêu.

Toàn bộ chuỗi nguồn đều escape trước khi đưa vào HTML. Không có request API
ở trang công thức/bản xem thử, không gửi nội dung sang Gemini. Bản xem thử
`formula-reference-preview.html` bị loại khỏi gói Netlify bởi allowlist có sẵn.

## Kiểm thử

Kiểm thử công thức kiểm tra mọi tên, đoạn mô tả, lưu ý, nguồn dữ liệu của các
mục hiển thị so với dữ liệu trích từ tài liệu, giữ nguyên ngưỡng và điểm tối đa,
chỉ mở một nhóm, không sinh script từ nội dung nguồn.

Chưa deploy hoặc cập nhật cơ sở dữ liệu trong đợt chỉnh sửa này.

Kết quả: TypeScript compile thành công; 41 file kiểm thử frontend đạt; kiểm thử
gói Netlify mới đạt (không fixture, secret, source map hoặc trang preview).
Đã xem bản thử trên trình duyệt ở chiều rộng mặc định và mobile 390px;
không tràn ngang khi hiển thị phân số và đổi nhóm DVCTT.

## Bố cục thu gọn theo mẫu đã duyệt

Thẻ chọn nhóm chỉ còn icon, tên và số điểm tối đa ở mép phải. Số điểm và icon
theo màu của nhóm; bỏ dòng “điểm nhóm”, căn giữa icon với tên và tăng chữ.
Giá trị tối đa vẫn có nhãn đầy đủ cho trình đọc màn hình.

Thẻ công thức có mã lớn, tên đầy đủ, điểm tối đa và phân số nổi bật. Bốn mục
Giải thích thành phần, Cách tính và nghiệp vụ, Nguồn dữ liệu, Lưu ý khi đánh
giá dùng details/summary hỗ trợ bàn phím. Thành phần mở sẵn; các mục dài thu
gọn mặc định. Toàn bộ nội dung nguồn và quy đổi điểm vẫn có trong các mục;
không bổ sung nút Lưu/Chia sẻ hoặc tải thư viện bên ngoài. HTML độc lập đã
được xuất lại cùng thiết kế mới. 41 file kiểm thử frontend tiếp tục đạt.

Tinh chỉnh tiếp: font công thức trở về sans-serif không nghiêng; Điểm tối đa
và Ngưỡng đạt chuyển vào mép phải của hàng tiêu đề. Đường kẻ phân số co theo
nội dung, không flex giãn hết khung; trên mobile giữ nhãn, phân số và hệ số
trong cùng bố cục ba cột có xuống dòng trong nội dung khi cần. Giải thích
hiển thị Tử số/Mẫu số cùng dòng với nội dung. Kiểm tra thực tế mobile 390px
các nhóm DVCTT, Thanh toán, Số hóa, Hài lòng không tràn ngang; phân số đầu
rộng khoảng 163px trong khung desktop 898px, không còn giãn hết khung.
