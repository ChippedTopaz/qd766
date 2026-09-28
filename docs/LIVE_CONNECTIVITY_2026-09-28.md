# Kiểm tra kết nối DVCQG ngày 28/09/2026

Môi trường: máy cơ quan. Probe được người vận hành xác nhận trước khi chạy.

## Phạm vi

- đúng một DNS lookup và một HTTPS GET tới `https://dichvucong.gov.vn/`;
- không POST endpoint dữ liệu;
- không theo redirect;
- không retry;
- không proxy rotation hoặc biện pháp vượt WAF.

## Kết quả

```text
DNS: OK, 14.238.3.76, khoảng 0,01 giây
HTTPS status: không nhận được
Bytes: 0
Thời gian HTTPS: khoảng 18,96 giây
Lỗi: URLError / WinError 10054 — remote host forcibly closed the connection
```

Kết luận: **BLOCKED**. Probe dừng ngay sau lần GET duy nhất. Không có bằng chứng
cho phép bật collector hoặc gửi POST tới API DVCQG từ môi trường hiện tại.

Circuit breaker PostgreSQL đã chuyển sang `open` với lý do
`connectivity-probe-stop`; không có worker giữ lease. Không tự đóng circuit chỉ
dựa trên một lần GET thành công trong tương lai. Cần người vận hành xem xét kết
quả trước mọi lần thử mới.
