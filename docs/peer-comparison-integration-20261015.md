# Hai bảng so sánh cùng cấp · đã tích hợp, chưa deploy

- Tích hợp vào tổng điểm, nhóm chỉ tiêu và chỉ tiêu con, cả tỉnh và cơ quan.
  Danh sách có STT/name/điểm, không lặp hạng từng dòng; highlight và cuộn
  riêng vào giữa đơn vị được chọn giữ nguyên. STT không thay thế hạng thật.
- Header sau tiêu đề (Excel vẫn được ghép cùng dòng với tiêu đề) hiển thị
  phạm vi bên trái, hạng/biến động đơn vị đang xem bên phải dưới Excel.
  Giữ trung vị/chênh lệch hiện có, không thay tính điểm.
- Tháng/quý so kỳ liền trước cùng loại đã lưu. Năm/all dùng endpoint
  score-only ranking-history; mốc là ngày ở Đồng hồ hoặc ngày liền trước.
  Truy vấn ngày mốc chính xác, không thay bằng ngày gần nhất. Cache tối đa
  8 ngữ cảnh, không polling, không cào/ghi Credit. Backend kiểm tra phạm vi
  trước cache như bảng xếp hạng, cache key thêm baseline_date.
- Chỉ hiển thị biến động khi cùng tập đơn vị có điểm và, với dữ liệu ngày,
  toàn bộ điểm hiện tại khớp bản lưu tương ứng. Thiếu dữ liệu, đổi tập đơn vị
  hoặc snapshot mới hơn ngày đã lưu thì chỉ hiện hạng hiện tại.
  Chỉ tiêu con không có lịch sử điểm con theo ngày thì không suy từ hạng nhóm.
- Excel so sánh đọc đúng ba cột STT/cơ quan/điểm đang hiển thị, không bị lệch
  tên cột sau thay đổi DOM. Không thay export bảng khác hay phân quyền.
- Preview view=rankings chuyển sang renderer peer-list/context thực tế,
  dữ liệu minh họa 8 đơn vị mỗi bảng, không phải hạng của toàn bộ tỉnh thật.
- Kiểm thử pure list/đồng hạng/cohort/mốc/mismatch/null/escape/centering,
  export, payment scope, drilldown và 5 tests API (10 SQL đọc trên fixture).
  Không migrate, không restart worker/backend, không deploy trong bước này.
