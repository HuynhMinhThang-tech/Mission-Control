# Changelog

## 0.1.2-dev
- **Xem trước dữ liệu nạp vào** cho mọi tệp (sạch hay xấu): bản đang dùng, bản gốc, bản chuẩn hóa, bản sau làm sạch; kèm kiểu dữ liệu và số ô thiếu từng cột.
- **Làm sạch**: mỗi cột là một khối; các cách xử lý thiếu được gộp vào một thẻ có chọn cách (trung vị / trung bình / phổ biến nhất / xóa dòng / giá trị cố định) và hiện kết quả áp dụng tính thật ("1.876 ô thiếu → 0 · giữ 12.497 dòng").
- **Agent phân tích**: góp ý áp đúng pha đang xem (danh sách → code → kết quả; ở pha kết quả sẽ viết lại code và chạy lại). Các agent khác nhận thêm bản trước khi góp ý. Hiển thị lịch sử góp ý.
- **Đọc JSON chịu lỗi** (`llm.py`): ép chế độ JSON, chấp nhận xuống dòng trong chuỗi, dấu phẩy thừa, JSON bị cắt cụt; tự thử lại tối đa 3 lần và báo rõ lỗi cho model.
- **Dashboard tương tác** (`dashboard.html`): bộ lọc, lọc chéo, KPI tính lại theo bộ lọc, đổi chỉ số / cách tính / chiều / loại biểu đồ, bảng chi tiết, chế độ sáng/tối. Báo cáo tĩnh có bằng chứng chuyển sang `bao_cao.html`; PPTX và Markdown giữ nguyên.
- **Lịch sử**: nút Xem lại / ZIP / Xóa canh thẳng hàng; Xóa gỡ cả luồng và thư mục tệp xuất.
- Sửa tương thích pandas 3 (kiểu `str`, bỏ `to_numeric(errors="ignore")`).

## 0.1.1-dev
- Tự nhận diện bảng trong sheet (Excel Table + dò theo bố cục), xếp hạng ưu tiên.
