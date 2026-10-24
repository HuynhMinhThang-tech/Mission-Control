# Changelog

## 0.1.3-dev
- **Ngôn ngữ thống nhất tiếng Việt** (`app/lang.py`): mọi Agent nhận luật "viết toàn bộ bằng tiếng Việt, không xen tiếng Anh"; tên cột của bảng kết quả phân tích phải là tiếng Việt (AI đặt ngay trong code, có bước dịch lại và từ điển dự phòng nếu còn sót tên kiểu COUNT_PER_LEVEL). Đổi các nhãn còn tiếng Anh: "Insight" thành "Phát hiện", "Dashboard" thành "Bảng điều khiển", "Review và export" thành "Duyệt và xuất file".
- **Bảng điều khiển tương tác thiết kế lại** (`app/export/assets/live.js`, `live.css`): bỏ 4 ô chọn trên từng biểu đồ; chỉ còn thanh lọc chung (khoảng thời gian, tối đa 3 chiều, chọn chỉ số) và lọc chéo bằng cách bấm vào biểu đồ. Hệ thống tự chọn loại biểu đồ theo dữ liệu (đường theo tháng, vòng tròn khi ít nhóm, thanh ngang xếp hạng khi nhiều nhóm), bỏ chiều thiếu dữ liệu nhiều, tiêu đề không còn lặp ("Tổng Tổng"), ô trống ghi "Chưa có dữ liệu", trục số tròn, dòng nhận xét tự tính dưới mỗi biểu đồ, chế độ tối, hiển thị tốt trên điện thoại.
- **Báo cáo tĩnh (HTML)** làm mới cùng hệ thống thiết kế; biểu đồ SVG chữ rõ hơn, nhiều nhóm thì dùng thanh ngang.
- **Làm sạch: kiểm tra giá trị từng cột** đầy đủ hơn: nhận diện thêm viết tắt (CV = Chuyên viên), thêm/bớt chữ đầu (P. Kinh doanh = Kinh doanh) và gõ sai nhẹ; đề xuất riêng (mặc định chưa chọn) để người dùng xem. Bảng giá trị từng cột hiện sẵn, mở sẵn ở cột có vấn đề, và có ô "Gộp vào…" trên từng dòng để tự gộp thủ công (xem trước ngay). Tests: `tests/value_counts_test.py`, `tests/lang_test.py`.
- **Làm sạch: đếm giá trị từng cột** (`app/data/valuecounts.py`): Agent chạy thật `df['cột'].value_counts(dropna=False)` cho mọi cột văn bản, gom các giá trị cùng nghĩa nhưng viết khác nhau (hoa/thường, có/không dấu, thừa khoảng trắng, dấu câu; ví dụ «Ban Giám đốc» và «ban giam doc»), đưa kết quả cho AI tổng hợp. Thao tác mới `standardize_text` gộp các cách viết về một giá trị chuẩn (AI đề xuất mapping, hệ thống chặn giá trị bịa và tự bổ sung nhóm AI bỏ sót). Giao diện hiện lệnh đã chạy, bảng đếm từng cột, phần AI tổng hợp và danh sách gộp trước khi người dùng chọn. Thêm loại vấn đề "Giá trị viết khác nhau" vào bộ quét chất lượng. Test: `tests/value_counts_test.py`.
- **Tải Excel nhiều sheet**: tệp có từ 2 sheet sẽ hiện hộp chọn (dropdown tên sheet), chỉ sheet được chọn mới nạp vào; tệp 1 sheet và CSV nạp thẳng. Thêm `POST /api/inspect` (liệt kê sheet); `POST /api/upload` nhận thêm trường `sheets` = `{tên tệp: tên sheet}`. Bảng không bắt đầu ở dòng 1 vẫn được nhận diện và cắt đúng vùng như trước.
- **Chỉ báo đang tải** (`static/js/loading.js`, dùng chung cho app, đăng nhập, quản trị): thanh chạy ở mép trên + khung "Đang…" có vòng xoay cho mọi thao tác phải chờ; bước AI đang chạy có vòng xoay, tên tác vụ và số giây; nút bấm có vòng xoay và không gửi trùng khi bấm đúp; dashboard có lớp phủ "Đang tải". Thao tác dưới ~0,3 giây không hiện gì để khỏi nhấp nháy.
- **Giao diện**: ô Câu hỏi kinh doanh nằm trên thanh các bước và tự giãn nhiều dòng để hiện đủ câu hỏi dài; bỏ toàn bộ dòng phụ (sub title) dưới tiêu đề ở mọi bước và các trang Tổng quan / Lịch sử / API & Model, rút gọn placeholder; thêm favicon (`static/favicon.svg`); nền giao diện sáng dịu hơn một chút (giao diện tối giữ nguyên).

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
