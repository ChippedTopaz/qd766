# Điểm tối đa trong Công thức tính

Bổ sung nhãn điểm tối đa tại từng thẻ công thức, không tạo bảng điểm riêng.
Sáu thẻ chọn nhóm nằm trên cùng; nguồn và nguyên tắc đọc kết quả gộp trong
một khối mở rộng thu gọn bên dưới. Chọn nhóm cuộn mượt tới nhóm vừa chọn.
Không hiển thị lại chỉ tiêu phân loại PAKN chỉ theo dõi/không chấm điểm.
Không thay đổi điểm nguồn, thuật toán chấm điểm, quyền truy cập,
snapshot hoặc lịch cào. Không gọi API bổ sung khi mở menu Công thức tính.

Nguồn phân bổ: docs/metrics.m0.json trích bảng METRICS, Công thức 766.xlsx.
Nguồn mô tả nghiệp vụ vẫn là Mô tả công thức tính chỉ số 766.docx. Tài liệu
mô tả không nêu điểm không có nghĩa bảng METRICS/API chưa có mức điểm đó.

- Công khai: 6 / 4 / 2 / 6, đủ 18.
- Tiến độ: tỷ lệ trước hạn/đúng hạn 20 theo METRICS. Không suy ra 18+2 từ
  website khác; thời gian trung bình 2.2 chưa xác định điểm riêng.
- Số hóa: 6 / 4 / 2 / 2 / 4 / 2 / 2, đủ 22 trong danh mục nguồn. Không tự
  bổ sung thẻ cho chỉ tiêu không có trong danh sách công thức hiện hành.
- Hài lòng: đúng hạn PAKN / hài lòng PAKN / hài lòng TTHC mỗi mục 6 điểm.
  Hai metric phân loại PAKN có maxScore=0 là chỉ theo dõi, không phải thiếu số liệu.
- Thanh toán: hồ sơ thanh toán trực tuyến 10 theo METRICS; không chia trọng số
  cho tích hợp TTHC 3.5 nếu chưa có căn cứ.
- DVCTT: bảng nguồn ghi 12 cho hồ sơ toàn trình/đủ điều kiện toàn trình. Không
  ánh xạ nhầm sang công thức DVCTT 3.1–3.3 hoặc tự phân bổ 2–4–6. Hiển thị
  mức chưa xác định tại thẻ công thức 3.1–3.3, không chèn thêm chỉ tiêu riêng.

Các mức không có trong nguồn giữ null, nhãn “Chưa xác định”; không biến thành
0. Bảng phân bổ có sourceRow/metricCode để kiểm thử đối chiếu với JSON nguồn.
Các mức đã có metricCode cũng được kiểm thử với apiMaxScore trong fixture.
Việc xác định mức điểm không đồng nghĩa xác nhận cách quy đổi điểm/điều kiện
nghiệp vụ. Chưa khẳng định tính pháp lý hoặc ngày hiệu lực của tài liệu.

Chỉ cập nhật bản thử local; chưa commit/push/deploy Netlify trong lần này.
