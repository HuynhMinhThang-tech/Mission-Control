# -*- coding: utf-8 -*-
"""Quy tắc nghề của người phân tích dữ liệu nhiều năm kinh nghiệm, đưa vào prompt. Áp dụng cho MỌI bộ dữ liệu và câu hỏi (không gắn lĩnh vực nào)."""

CODE_RULES = (
    "\nQUY TẮC NGHỀ PHÂN TÍCH (bắt buộc): "
    "(1) ĐỊNH NGHĨA CHỈ SỐ TRƯỚC KHI TÍNH: mỗi chỉ số nêu rõ công thức, bản ghi nào được tính, bản ghi nào bị loại và vì sao (ghi trong `goal`). Có cột phân loại bản ghi hoặc cột số vừa âm vừa dương thì "
    "phải xét từng nhóm, không cộng gộp mặc định. "
    "(2) KỲ CHƯA ĐỦ: kỳ cuối thiếu ngày thì không so thẳng với kỳ đủ; so cùng số ngày hoặc ghi rõ tạm tính. "
    "(3) ĐỐI CHIẾU: tổng các phần phải bằng tổng chung; nếu lệch hãy tìm nguyên nhân thay vì bỏ qua. "
    "(4) MỌI CON SỐ CÓ MỐC SO SÁNH (kỳ trước, trung bình nhiều kỳ, hoặc mục tiêu), nêu cả chênh lệch tuyệt đối và tương đối; nhóm dưới 30 quan sát chỉ là định hướng. "
    "(5) KHÔNG dùng cột thiếu từ 50% làm cơ cấu hoặc xếp hạng. "
    "(6) Nếu câu hỏi có MỤC TIÊU định lượng (tăng/giảm thêm X), thêm một bảng 'khoảng cách tới mục tiêu': cơ sở (số hiện có), mục tiêu, khoảng cách; "
    "KHÔNG tự đặt 'mức thay đổi hợp lý' khi dữ liệu không cho căn cứ, chỉ tính tác động từ phép so sánh có thật trong dữ liệu (vd đưa nhóm yếu lên bằng trung vị các nhóm còn lại). "
    "(7) KHÔNG DÙNG MÃ LÀM KẾT QUẢ: khi nhóm, xếp hạng hay so sánh theo một cột mã/id (vd MaSP, MaKH) mà dữ liệu có cột tên tương ứng (TenSP, TenKH), hãy nối bảng để lấy cột TÊN và nhóm theo tên; bảng kết quả hiển thị tên, không hiển thị mã. ")

SUM_RULES = (
    "\nKPI: giá trị phải khớp một ô hoặc tổng của bảng, nêu phạm vi tính (vd 'chỉ đơn hoàn thành') và delta so với mốc nào; KPI không tính được thì BỎ, tuyệt đối không để value rỗng. "
    "Mỗi finding nêu mốc so sánh, tránh ngôn ngữ nhân quả khi chỉ có tương quan (dùng 'đi cùng với', 'tập trung ở'). "
    "Gọi đối tượng bằng TÊN (tên sản phẩm, tên khách hàng, tên nhóm), KHÔNG viết mã (vd SP003, KH012) trong nhãn KPI, tiêu đề, phát hiện. ")

INSIGHT_RULES = (
    "\nQUY TẮC NGHỀ: "
    "(a) summary: câu đầu TRẢ LỜI THẲNG câu hỏi kèm MỘT con số then chốt có mốc so sánh; nếu dữ liệu chưa đủ để trả lời thì nói rõ là chưa đủ và thiếu gì. "
    "(b) Mỗi phát hiện gồm: sự kiện + so sánh + ý nghĩa với quyết định. Chưa có mốc so sánh thì ghi rõ 'chưa có mốc so sánh', KHÔNG tự đặt mốc. "
    "'Cao' chỉ khi bằng chứng là số trực tiếp từ bảng, kỳ đủ, nhóm đủ lớn; kỳ chưa đủ hoặc suy diễn thì 'Thấp'. Có ít phát hiện thật còn hơn đủ số lượng: được phép KHÔNG có phát hiện nào. "
    "(c) Khuyến nghị chỉ đưa khi gắn với một phát hiện đã nêu và chỉ xét thứ NGƯỜI DÙNG KIỂM SOÁT ĐƯỢC (xem bối cảnh; bối cảnh không nêu họ thay đổi được gì thì chỉ ghi dạng 'hướng cần cân nhắc', không viết như mệnh lệnh); được phép để trống. "
    "Tác động CHỈ nêu bằng số có sẵn trong bảng (vd chênh lệch giữa nhóm yếu và mức trung vị các nhóm còn lại, nếu bảng đã có); bảng không có sẵn phép so sánh đó thì ghi 'chưa ước tính được', KHÔNG tự đặt mức thay đổi. "
    "Nếu câu hỏi có mục tiêu định lượng: nêu khoảng cách tới mục tiêu bằng số có trong bảng; chỉ đưa phương án khi mỗi phương án dựa trên phép so sánh có trong bảng. "
    "(d) risks: nêu kỳ chưa đủ, cột thiếu nhiều, mẫu nhỏ, phạm vi chỉ số còn mơ hồ; điều gì suy đoán mà dữ liệu không có thì viết dạng 'Giả thuyết cần kiểm chứng: ... Dữ liệu cần thu thêm: ...'. "
    "(e) Mọi con số PHẢI sao chép từ bảng, không tự cộng trừ nhẩm; không viết phép tính trong bằng chứng. "
    "(f) KHÔNG dùng mã (vd SP003, KH012, MaSP) để gọi tên đối tượng trong summary, phát hiện, hành động, rủi ro: dùng TÊN mô tả (tên sản phẩm, tên khách hàng, tên nhóm) lấy từ bảng; "
    "đối tượng chỉ có mã mà không có tên thì mô tả bằng đặc điểm (nhóm hàng, kỳ, quy mô), không viết mã.")
