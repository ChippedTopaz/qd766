# Bảng xếp hạng · bản cập nhật chưa deploy

## Điều chỉnh bố cục theo phản hồi

### Bố cục mới nhất

- Tên đơn vị trong bảng tích hợp là link mở Tổng quan (không phải tab
  Chi tiết điểm số), đúng đơn vị/tỉnh, kỳ dialog và ngày nguồn nếu có.
  Dùng chung registry điều hướng và kiểm tra quyền với link điểm số;
  không có quyền thì tên là chữ bình thường. Link điểm vẫn giữ đích cũ.
- Kiểm thử tên đơn vị với tỉnh/cơ quan/toàn quốc, đổi kỳ dialog trước
  khi mở, giữ GET-only và chuyển đúng tab Tổng quan.

- Bộ chọn kỳ được sửa thành ba ô giống trang chủ: Loại kỳ / Kỳ cụ thể /
  Năm. Kỳ cụ thể phụ thuộc loại và năm, năm chỉ có các giá trị tương ứng
  trong danh mục hiện có; loại Năm hiện Cả năm. Đặt giữa toolbar, không
  thay đổi state/URL của trang nền. Có kiểm thử đổi loại/năm và fallback
  kỳ phù hợp, không tạo yêu cầu mới khi thay lựa chọn.

- Thêm bộ chọn kỳ (nhóm Năm/Quý/Tháng, kỳ mới trước) ở giữa toolbar.
  Kỳ trong dialog độc lập với main state/URL/snapshot; đóng không đổi
  lựa chọn trang sau. Khi hẹp toolbar xuống hai hàng để tránh chồng chữ.
- Đổi kỳ dùng GET selection và, nếu cần, province-rankings/ranking-history;
  không gọi luồng tạo yêu cầu, không fallback về latest khi 404/thiếu quyền.
  Cache riêng giới hạn 8 ngữ cảnh, kết quả về trễ không thay kỳ mới chọn.
- Điểm bấm mở chi tiết và Excel dùng đúng kỳ dialog, không dùng kỳ nền.
  Kỳ năm so ngày; tháng/quý không bị ghép biến động của năm.
- Kiểm thử UI tháng/quý/năm độc lập, link chi tiết đúng kỳ, 404 và race
  PASS cho ba phạm vi tỉnh/cơ quan/toàn quốc, tất cả requests GET.
  Preview kiểm tra trực tiếp đổi Năm 2026 sang Tháng 9/2026 và trở lại.

- Sửa riêng viền hàng cuối của leadership-table vì CSS chung
  `tr:last-child td { border:0 }` làm hàng cuối mất khung.
- Header tên 6 nhóm là nút sort: lần đầu giảm dần, lặp lại tăng dần;
  bằng điểm nhóm luôn xét Tổng điểm giảm dần, rồi tên/ID để ổn định.
  Null luôn nằm cuối; không sửa số hạng nguồn/tính toán hay biến động.
  Có aria-sort và dấu hướng trên header; giữ vị trí cuộn ngang khi sort.
  Excel lấy cùng thứ tự hàng đang xem. Preview dùng cùng hàm sort/render.
  TypeScript và kiểm thử ranking/Excel PASS, bao gồm tie-break cả hai chiều.

- Giữ cột Tăng/Giảm độc lập, tăng chữ lên 13px (Excel 11pt).
- Khôi phục 6 cột Hạng nhóm, chỉ hiện số hạng màu trung tính,
  không mũi tên, số bậc hay ghi chú biến động trong các cột nhóm.
- Căn giữa cột Thứ hạng tổng và hạng nhóm. Header dài tiếp tục wrap.
  Excel có 16 cột, đồng bộ thứ tự với giao diện.
- TypeScript và hai bộ kiểm thử ranking/Excel PASS sau điều chỉnh.

- Tách biến động hạng thành cột Tăng/Giảm ngay sau Tổng điểm: ▲ xanh,
  ▼ đỏ kèm số bậc; không đổi là — xám đậm. Thiếu dữ liệu cũng là —,
  nhưng tooltip phân biệt “Chưa có dữ liệu so sánh”.
- Cột Thứ hạng chỉ giữ số hạng, không nhét biến động cạnh số hạng.
  Bỏ 6 cột hạng nhóm khỏi giao diện và Excel, giữ điểm của cả 6 nhóm.
  Tính hạng nội bộ giữ nguyên, không thay đổi logic nguồn.
- Header chỉ tiêu xuống dòng theo từ, căn giữa và cân đối chiều rộng.
  Excel có 10 cột; header wrap và cao 42pt, các cột nhóm giới hạn 24 ký tự.
  Cột Tăng/Giảm Excel giữ số để sort và format tam giác/dấu gạch.

- Đổi nhãn Báo cáo lãnh đạo thành Bảng xếp hạng tại thanh công cụ,
  dialog và trung tâm xuất dữ liệu; đưa Tổng điểm sau tên cơ quan.
- Cột đầu là thứ hạng tổng điểm, không phải STT; giữ đồng hạng 1,2,2,4.
- Kỳ năm / Tất cả TTHC: dùng bản lưu ngày mới nhất và ngày liền trước
  trong cùng năm. Nếu đang mở ngày lịch sử thì giữ đúng ngày đó.
  Ghi rõ ngày dữ liệu và ngày mốc để tránh nhầm ngày cào với ngày dữ liệu.
- Điểm tăng xanh đậm, giảm đỏ đậm, không đổi xám đậm. Thứ hạng có
  mũi tên nhỏ và số bậc thay đổi. Thiếu ngày/điểm không giả thành 0;
  thay tập đơn vị đủ điểm thì không suy ra biến động hạng tương ứng.
- `/dashboard/ranking-history` chỉ GET, kiểm tra đăng nhập/phạm vi trước
  cache; chỉ trả tên, ID và điểm tổng/6 nhóm cùng cấp (hoặc 34 tỉnh).
  Không trả tử số/mẫu số, parameters, metrics hay hồ sơ của đơn vị khác.
  Truy vấn tối đa hai bản lưu ngày và hai tập điểm dạng scalar,
  không tải quan hệ dữ liệu chi tiết. Tận dụng cache TTL single-flight
  giới hạn 64 mục đã có. Không migration, không collection/Credit writes.
- Client gọi một GET khi mở dialog kỳ năm; không polling, không lấy
  từng đơn vị riêng. Cache client tối đa 8 ngữ cảnh, chặn phản hồi khác
  ngữ cảnh. Không thay logic tháng/quý hay tra cứu từng TTHC.
- Dùng xếp hạng nhị phân trên dãy điểm đã sắp xếp thay vì tính lại
  percentile/quantile cho từng ô; giữ sai số đồng điểm 0,005 như trước.
- Điểm trong bảng vẫn mở chi tiết theo phân quyền và đúng ngày nguồn;
  giữ nguyên kiểm tra tài khoản cơ quan/chéo tỉnh, không mở rộng quyền.
- Excel đổi thứ tự cột và giá trị hạng tương ứng, màu biến động;
  số thứ hạng vẫn là số để lọc/sort, số bậc được ghi chú ô Excel.
- Kiểm thử: 4 API mới PASS (10 SQL, 1.152 byte trên fixture cơ quan,
  không writes; cache, 34 tỉnh, số Decimal, ngày thiếu, auth/scope);
  13 backend tests tổng hợp PASS; TypeScript PASS; 4 frontend suites
  xếp hạng/Excel/so sánh ngày PASS. Drilldown UI PASS cho tỉnh, tài khoản
  cơ quan và toàn quốc. Test 1.500 đơn vị kiểm tra đường tính hạng.
  Các con số tải là fixture, không phải benchmark production.
- Preview `service-feedback-preview.html?view=leaderboard` dùng renderer
  bảng thực tế với dữ liệu minh họa; không gọi API và không nằm gói public.
  Kiểm tra giao diện desktop bằng Computer Use. Không restart/deploy.
