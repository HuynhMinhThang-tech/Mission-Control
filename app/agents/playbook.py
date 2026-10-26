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
    "(6) Nếu câu hỏi có MỤC TIÊU định lượng (tăng/giảm thêm X), thêm một bảng 'khoảng cách tới mục tiêu': cơ sở, mức thay đổi hợp lý theo dữ liệu, tác động ước tính. ")

SUM_RULES = (
    "\nKPI: giá trị phải khớp một ô hoặc tổng của bảng, nêu phạm vi tính (vd 'chỉ đơn hoàn thành') và delta so với mốc nào; KPI không tính được thì BỎ, tuyệt đối không để value rỗng. "
    "Mỗi finding nêu mốc so sánh, tránh ngôn ngữ nhân quả khi chỉ có tương quan (dùng 'đi cùng với', 'tập trung ở').")

INSIGHT_RULES = (
    "\nQUY TẮC NGHỀ: "
    "(a) summary: câu đầu TRẢ LỜI THẲNG câu hỏi kèm MỘT con số then chốt có mốc so sánh. "
    "(b) Mỗi phát hiện gồm: sự kiện + so sánh + ý nghĩa với quyết định. 'Cao' chỉ khi bằng chứng là số trực tiếp từ bảng, kỳ đủ, nhóm đủ lớn; kỳ chưa đủ hoặc suy diễn thì 'Thấp'. "
    "(c) Khuyến nghị chỉ xét thứ NGƯỜI DÙNG KIỂM SOÁT ĐƯỢC; tác động ước tính = cơ sở trong bảng × mức thay đổi hợp lý (nêu giả định), xếp ưu tiên theo tác động và độ dễ làm; mỗi hành động kèm chỉ số theo dõi. "
    "Nếu câu hỏi có mục tiêu định lượng: tính khoảng cách tới mục tiêu và đưa 2-3 phương án (thận trọng / cân bằng / quyết liệt) với tổng tác động so với mục tiêu. "
    "(d) risks: nêu kỳ chưa đủ, cột thiếu nhiều, mẫu nhỏ, phạm vi chỉ số còn mơ hồ. "
    "(e) Mọi con số PHẢI sao chép từ bảng, không tự cộng trừ nhẩm.")
