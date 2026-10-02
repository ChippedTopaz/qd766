# Kiểm kê dữ liệu QĐ766 — 02/10/2026

Kiểm tra trực tiếp PostgreSQL máy cơ quan lúc 22:18 2/10/26 (giờ Việt Nam).
Transaction REPEATABLE READ, READ ONLY; không tạo job, không gọi DVCQG,
không sửa dữ liệu, lịch, circuit hoặc cấu hình server. Không xuất secret/tài khoản.

## Kết quả chính

- Danh mục đối chiếu: 34 tỉnh; 48 cặp tỉnh/kỳ phạm vi all có snapshot; 3 kỳ có bản tổng hợp quốc gia.
- Năm 2026: đủ 34 tỉnh, mỗi tỉnh có điểm root của sáu nhóm; có điểm đơn vị trực thuộc theo dữ liệu nguồn lưu.
- Tổng hợp quốc gia tháng 10, quý IV, năm 2026 đều kiểm tra nội dung đủ 34 tỉnh và sáu nhóm, không chỉ dựa vào nhãn complete trong DB.
- Tổng hợp quốc gia tháng 1–9 và quý I–III chưa có trong bảng national_summary_snapshots. Có thể so sánh hạn chế các tỉnh có snapshot chi tiết, không phải đủ 34 tỉnh.
- Chưa có kỳ năm 2025 để so sánh năm trước.
- Các số này xác nhận độ phủ bản đã lưu, không xác nhận khớp với DVCQG tại thời điểm kiểm kê.

## Ma trận độ phủ năm 2026

| Kỳ | Tổng hợp quốc gia 34 × 6 | Tỉnh có snapshot đủ điểm 6 nhóm | Tỉnh có chi tiết kỳ liền trước | Chi tiết quá 72h trong kỳ đang mở |
| --- | --- | ---: | ---: | ---: |
| Tháng 1/2026 | Chưa có | 2/34 | 0 | 0 |
| Tháng 2/2026 | Chưa có | 1/34 | 1 | 0 |
| Tháng 3/2026 | Chưa có | 1/34 | 1 | 0 |
| Tháng 4/2026 | Chưa có | 1/34 | 1 | 0 |
| Tháng 5/2026 | Chưa có | 1/34 | 1 | 0 |
| Tháng 6/2026 | Chưa có | 1/34 | 1 | 0 |
| Tháng 7/2026 | Chưa có | 1/34 | 1 | 0 |
| Tháng 8/2026 | Chưa có | 1/34 | 1 | 0 |
| Tháng 9/2026 | Chưa có | 2/34 | 1 | 0 |
| Tháng 10/2026 | Đủ, nhưng quá 2h | 0/34 | 0 | 0 |
| Quý 1/2026 | Chưa có | 1/34 | 0 | 0 |
| Quý 2/2026 | Chưa có | 1/34 | 1 | 0 |
| Quý 3/2026 | Chưa có | 1/34 | 1 | 0 |
| Quý 4/2026 | Đủ, nhưng quá 2h | 0/34 | 0 | 0 |
| Năm 2026 | Đủ, nhưng quá 2h | 34/34 | 0 | 1 |

Quá hạn chỉ áp dụng kỳ đang diễn ra theo chính sách hiện tại; không tự kết luận
bản cũ của kỳ đã đóng là dữ liệu đã chốt. Có thời gian thu thập khác nhau giữa tỉnh.

## Dữ liệu lịch sử đang có

- Phú Thọ: tháng 1–9, quý I–III và năm 2026; điểm 15 sở/ngành và 148 xã/phường đủ sáu nhóm trong từng snapshot.
- Cao Bằng: tháng 1, tháng 9 và năm 2026; điểm 16 sở/ngành và 56 xã/phường đủ sáu nhóm.
- 32 tỉnh còn lại: mới có snapshot chi tiết năm 2026.
- Phú Thọ tháng 2–9 có tháng liền trước; quý II–III có quý liền trước. Cao Bằng tháng 9 thiếu tháng 8 nên chưa so sánh biến động tháng liền trước.
- Tổng hợp quốc gia tháng 10 thiếu tháng 9; quý IV thiếu quý III; năm 2026 thiếu năm 2025. Chưa tính biến động/xếp hạng quốc gia với kỳ liền trước.

## Cảnh báo dữ liệu chưa chốt và quá hạn

- Phú Thọ Tháng 9/2026: lấy lúc 21:50 28/9/26, trước khi kỳ kết thúc. Cần lượt chốt sau kỳ, không tự coi là bản cuối.
- Tháng 10/2026: bản tổng hợp cập nhật 09:27 2/10/26, đã quá hạn 2 giờ tại thời điểm kiểm kê.
- Phú Thọ Quý 3/2026: lấy lúc 09:37 28/9/26, trước khi kỳ kết thúc. Cần lượt chốt sau kỳ, không tự coi là bản cuối.
- Quý 4/2026: bản tổng hợp cập nhật 11:23 2/10/26, đã quá hạn 2 giờ tại thời điểm kiểm kê.
- Năm 2026: bản tổng hợp cập nhật 10:13 2/10/26, đã quá hạn 2 giờ tại thời điểm kiểm kê.
- Phú Thọ Năm 2026: chi tiết cập nhật 09:37 28/9/26, quá hạn 72 giờ.

## Điểm đơn vị trực thuộc năm 2026

“Đủ” dưới đây là có điểm sáu nhóm, không có nghĩa mọi chỉ tiêu thành phần đều có tham số hoặc công thức.
Các đơn vị hoàn toàn không xuất hiện trong response không thể được chứng nhận bằng dữ liệu này.

| Tỉnh | Sở/ngành đủ 6 nhóm / có điểm bất kỳ | Xã/phường đủ 6 nhóm / có điểm bất kỳ | Cập nhật chi tiết |
| --- | ---: | ---: | --- |
| An Giang | 15/15 | 102/102 | 13:24 1/10/26 |
| Bắc Ninh | 14/14 | 99/99 | 18:54 1/10/26 |
| Cao Bằng | 16/16 | 56/56 | 18:42 1/10/26 |
| Cà Mau | 13/13 | 64/64 | 19:08 1/10/26 |
| Cần Thơ | 15/15 | 103/103 | 19:07 1/10/26 |
| Gia Lai | 14/14 | 135/135 | 19:02 1/10/26 |
| Huế | 15/15 | 40/40 | 18:59 1/10/26 |
| Hà Nội | 16/16 | 126/126 | 08:21 1/10/26 |
| Hà Tĩnh | 14/14 | 69/69 | 18:58 1/10/26 |
| Hưng Yên | 12/12 | 104/104 | 18:55 1/10/26 |
| Hải Phòng | 12/12 | 114/114 | 18:55 1/10/26 |
| Khánh Hòa | 26/26 | 64/64 | 19:03 1/10/26 |
| Lai Châu | 18/18 | 39/39 | 18:49 1/10/26 |
| Lào Cai | 15/15 | 99/99 | 18:50 1/10/26 |
| Lâm Đồng | 14/14 | 124/124 | 19:04 1/10/26 |
| Lạng Sơn | 14/14 | 66/66 | 18:52 1/10/26 |
| Nghệ An | 13/13 | 130/130 | 10:05 1/10/26 |
| Ninh Bình | 14/14 | 129/129 | 18:56 1/10/26 |
| Phú Thọ | 15/15 | 148/148 | 09:37 28/9/26 |
| Quảng Ngãi | 31/31 | 96/96 | 19:01 1/10/26 |
| Quảng Ninh | 16/16 | 54/54 | 18:53 1/10/26 |
| Quảng Trị | 17/17 | 78/78 | 18:58 1/10/26 |
| Sơn La | 13/13 | 75/75 | 18:50 1/10/26 |
| Thanh Hóa | 14/14 | 166/166 | 18:57 1/10/26 |
| Thành phố Hồ Chí Minh | 19/19 | 169/169 | 19:06 1/10/26 |
| Thái Nguyên | 15/15 | 92/92 | 18:51 1/10/26 |
| Tuyên Quang | 13/13 | 124/124 | 18:46 1/10/26 |
| Tây Ninh | 14/14 | 96/96 | 21:19 30/9/26 |
| Vĩnh Long | 13/13 | 124/124 | 19:07 1/10/26 |
| Điện Biên | 14/14 | 45/45 | 18:48 1/10/26 |
| Đà Nẵng | 14/14 | 93/93 | 19:00 1/10/26 |
| Đắk Lắk | 15/16 | 102/102 | 19:03 1/10/26 |
| Đồng Nai | 13/13 | 95/95 | 19:05 1/10/26 |
| Đồng Tháp | 14/14 | 102/102 | 08:34 1/10/26 |

Đắk Lắk: Ban Quản lý các khu công nghiệp tỉnh thiếu điểm Công khai minh bạch,
Số hóa hồ sơ, Mức độ hài lòng trong snapshot đã lưu. Chưa xác định nguyên nhân
nguồn/chuẩn hóa; không gán 0, không xếp hạng tổng điểm. Không tự cào lại.

DVCTT đơn vị con: số tham số có thể bao gồm thông tin điểm/metadata; không dùng
sự hiện diện parameters để kết luận có chi tiết thành phần. Giữ giới hạn nguồn
đã chốt với người dùng. Công thức Thanh toán vẫn chưa được xác minh.

## Đề xuất bước tiếp theo (chưa thực hiện lấy dữ liệu)

1. Kiểm tra lịch tổng hợp đang không làm mới đúng hạn; audit không khẳng định nguyên nhân hay tự restart.
2. Bổ sung tổng hợp quốc gia tháng 1–9 và quý I–III (12 kỳ) theo lịch an toàn, tuần tự, có checkpoint và circuit. Không phải cào chi tiết 34 tỉnh cho các kỳ này.
3. Chốt lại Phú Thọ tháng 9, quý III và làm mới chi tiết năm đã quá 72h qua luồng quản trị.
4. Bổ sung chi tiết lịch sử các tỉnh theo nhu cầu phân tích, không tải hàng loạt mọi tỉnh/mọi kỳ ngay.
5. Kiểm tra nguyên nhân thiếu điểm đơn vị Đắk Lắk từ bản nguồn đã lưu trước khi cân nhắc request mới.

Script kiểm kê: tools/audit_data_coverage.py. Chỉ chạy với PostgreSQL có transaction
READ ONLY được cưỡng chế. Báo cáo này là ảnh chụp lúc kiểm tra, không cập nhật tự động.
