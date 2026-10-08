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

## Kiểm thử
`python tests/smoke_test.py` (SQLite) · `TEST_DATABASE_URL=postgresql://... python tests/smoke_test.py` (PostgreSQL, tự áp dụng `sql/schema.sql`) · `python tests/publish_test.py`
