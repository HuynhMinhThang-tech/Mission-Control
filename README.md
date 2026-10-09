# Mission Control

Phân tích dữ liệu kinh doanh với nhóm AI agent. Nhiều người dùng, đăng ký chờ admin duyệt, mỗi người dùng API key riêng.

## Chạy máy cá nhân
1. `python -m pip install -r requirements.txt`
2. `python run.py` rồi mở http://localhost:8000 (dùng SQLite, không cần cấu hình).
3. Bấm **Đăng ký** bằng email của bạn, sau đó cấp quyền admin cho email đó (xem "Cấp quyền admin").
4. Đăng nhập, mở tab **API & Model**, nhập API key + model của bạn rồi bấm "Lưu và kiểm tra kết nối".

## Deploy (Railway / Render)
1. Tạo web service từ repo này + một PostgreSQL.
2. Biến môi trường: `APP_ENV=production`, `SECRET_KEY`, `MASTER_KEY` (xem `.env.example`; **sao lưu MASTER_KEY**), `DATABASE_URL` (thường tự điền).
3. Chạy `sql/schema.sql` trên database (SQL Editor của nhà cung cấp, hoặc `psql "$DATABASE_URL" -f sql/schema.sql`).
4. Lệnh khởi động nằm trong `Procfile` (**phải 1 worker**, vì phiên phân tích đang dở nằm trong RAM).

## Cấp quyền admin
Đăng ký trên web bằng email của bạn → mở `sql/schema.sql`, sửa dòng `admin_email` ở phần 3 → chạy lại file (hoặc chỉ khối `DO`).
Admin quên mật khẩu: `python manage.py set-password email@gmail.com` (chạy trên máy chủ).

## Quy tắc
- Tài khoản mới và yêu cầu đặt lại mật khẩu đều chờ admin duyệt; admin chỉ thấy tên hiển thị và email.
- Mật khẩu được băm một chiều; API key được mã hóa (Fernet, khóa chủ `MASTER_KEY`) và không bao giờ trả lại cho trình duyệt.
- Chỉ phân tích đã duyệt xong mới được lưu vào lịch sử; phân tích đang dở sẽ mất nếu đóng phiên hoặc server khởi động lại.

## Sandbox chạy code phân tích (mức tối giản, khoảng 6/10)
Code pandas do AI viết (hoặc người dùng sửa) KHÔNG chạy trong tiến trình web. Ba lớp bảo vệ:
1. `ast` chặn trước: import, thuộc tính riêng `_x`, module hệ thống/mạng, hàm đọc/ghi tệp, `.query()/.eval()`, `.format()` đi sâu thuộc tính.
2. Tiến trình con: môi trường rỗng (không có `MASTER_KEY`, `DATABASE_URL`...), thư mục tạm riêng, giới hạn thời gian / CPU / RAM / dung lượng ghi, tối đa `SANDBOX_PARALLEL` cùng lúc, bị giết khi vượt giới hạn.
3. Audit hook trong tiến trình con: chặn mạng, sinh tiến trình, đọc tệp ngoài thư viện Python (gồm `/proc`, `.env`), ghi/xóa tệp ngoài thư mục tạm.

Hạn chế còn lại (chưa phải cô lập mức container): tiến trình con vẫn cùng người dùng hệ điều hành, cùng nhân và cùng container với máy chủ web; chặn mạng và chặn đọc tệp chỉ ở tầng Python (mã gốc/lỗ hổng trong thư viện C vẫn là rủi ro); không có hạn mức theo người dùng; Windows/macOS chỉ có timeout, không có giới hạn RAM/CPU của hệ điều hành. Dùng cho nhóm nhỏ quen biết; trước khi cho người lạ dùng nên chuyển sang dịch vụ sandbox riêng không có mạng.

## Kiểm thử
`python tests/smoke_test.py` (SQLite) · `TEST_DATABASE_URL=postgresql://... python tests/smoke_test.py` (PostgreSQL, tự áp dụng `sql/schema.sql`) · `python tests/publish_test.py` · `python tests/sandbox_test.py` (cần Linux)
