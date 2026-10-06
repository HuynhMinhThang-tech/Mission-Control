# -*- coding: utf-8 -*-
STEP_T = ["Dữ liệu và bối cảnh", "Kiểm tra và mô tả dữ liệu", "Làm sạch dữ liệu", "Phân tích",
          "Insight và hành động", "Báo cáo", "Review và export"]

# Nhãn tác vụ hiển thị ở bảng AI Agent cho từng bước
AG = {1: ["Đọc tệp và nhận diện kiểu cột", "Quét thiếu, trùng, sai định dạng", "Viết nhận định sơ bộ"],
      2: ["Chuẩn bị đề xuất xử lý", "Tính trước và sau"], 3: ["Đề xuất phân tích và chỉ số"],
      4: ["Đọc kết quả phân tích", "Gắn bằng chứng và đề xuất hành động"],
      5: ["Dựng đề xuất biểu đồ và báo cáo", "Lắp slide"], 6: ["Tổng hợp để bạn duyệt"]}
