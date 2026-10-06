# Hàng chờ phân tích thử nghiệm

## Chính sách

- Người dùng xác nhận mới tạo lượt; không chạy tự động khi tải trang.
- 20 Credit được giữ khi nhận lượt; chỉ ghi nhận thu cùng giao dịch lưu kết quả thành công.
- PostgreSQL lưu FIFO và checkpoint; tối đa 20 lượt đang chờ, hai lượt chạy toàn hệ thống, một lượt chờ/chạy mỗi tài khoản.
- Hủy khi còn chờ hoàn Credit. Đang chạy không cho hủy. Hết 10 phút chờ hoàn Credit; lượt chạy gián đoạn được đối soát khi lease 10 phút hết hạn, không tự gọi Gemini lại.
- Hai khóa phiên PostgreSQL giới hạn suất gọi nhà cung cấp; không giữ transaction qua HTTP. Token xử lý ngăn kết quả muộn thu Credit sau khi đã hoàn.
- Kiểm tra lại tài khoản, phạm vi và subscription khi bắt đầu xử lý.
- Chỉ đọc trạng thái mỗi 5 giây khi tab Phân tích đang hiển thị và có lượt chưa xong; dừng khi rời tab, đăng xuất, ẩn cửa sổ hoặc hoàn tất. Ẩn cửa sổ vẫn giữ timer kiểm tra visibility nhưng không gửi HTTP.
- Lượt chờ tồn tại qua restart. Không bảo đảm thứ tự hoàn thành của hai lượt chạy đồng thời.

## Trạng thái kiểm tra

Schema chính thức chưa nâng từ 0018 lên 0019, backend chính thức chưa restart theo bản queue. Không gọi Gemini thật trong kiểm thử hàng chờ.
Diễn tập PostgreSQL dùng qd766_credit_test với schema mới riêng; giữ lại schema để kiểm tra.

Đã đạt 297 kiểm thử Python, 40 file kiểm thử frontend (gồm kiểm thử polling/cancel), TypeScript build và đóng gói Netlify allowlist. Diễn tập migration 0019 và hai provider slot đồng thời trên PostgreSQL đạt; suất thứ ba bị chặn. Cấu hình public paused đạt kiểm tra chỉ đọc, cấu hình bật queue trên schema office 0018 bị từ chối đúng thiết kế. Chưa kiểm thử gọi Gemini thật với hàng chờ, chưa deploy.

## Thử nghiệm local

Khi không còn lượt phân tích local đang chạy:

```powershell
.\.venv\Scripts\python.exe .\tools\prepare_local_analysis_queue.py --confirm
```

Sau đó dùng script restart local đã rà soát để chạy `--source-wallet --gemini-analysis`. Không dùng thao tác kill rộng hoặc thay schema office để sửa bản local.

## Cổng phát hành chính thức — thực hiện theo thứ tự

1. Chờ các phân tích đang chạy hoàn tất. Tạm dừng nhận lượt trả Credit bằng task có đủ `-RealWallet -SharedRegistration -GeminiAnalysis -PausePaidRequests`, rồi restart backend bằng script đã rà soát. Bản paused tắt consumer hàng chờ và tương thích schema 0018. Chỉ là cửa sổ bảo trì; không tắt lịch cào 04:00.
2. Tạo dump mới bằng `tools/backup_postgresql.ps1`, giữ checksum sidecar; không ghi token/key trong terminal hay Git.
3. Chạy `python tools/migrate_analysis_queue.py --confirm --requests-paused --backup "DUONG_DAN_DUMP_MOI"`. Script từ chối nếu schema khác 0018/0019, backup quá 24h/checksum sai hoặc vẫn còn lượt queued/running. Không tự kích hoạt tính năng hay restart.
4. Đăng ký lại task đủ `-ReplaceExisting -RealWallet -SharedRegistration -GeminiAnalysis` (không PausePaidRequests), rồi `restart_public_backend.ps1`. Launcher từ chối bật queue nếu schema/constraint chưa chuẩn.
5. Build TypeScript, đóng gói Netlify theo workflow hiện có, push commit đã rà soát. Kiểm tra runtime policy có `geminiAnalysisQueueEnabled=true` và log `ANALYSIS_QUEUE_ENABLED workers=2`.
6. Người dùng kiểm thử một lượt thật, trạng thái chờ → đang phân tích → kết quả, một lần thu 20 Credit; hủy một lượt còn chờ và xác nhận hoàn Credit. Không chạy load test trả phí trên production.

Không downgrade tự động: bảo toàn lịch sử và đối soát các hold trước mọi rollback.
