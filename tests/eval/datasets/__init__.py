# -*- coding: utf-8 -*-
"""Các bộ dữ liệu MÔ PHỎNG cho bộ đánh giá (có seed cố định, tái lập được). Mỗi bộ thuộc một lĩnh vực khác hẳn nhau và cố ý cài lỗi thực tế
(kỳ cuối thiếu ngày, cột thiếu nhiều, nhóm rất nhỏ, cột không cộng được, dấu tiếng Việt dạng tổ hợp).

Mỗi bộ là một dict:
  id, title, tables {tên tệp: DataFrame}, nfd (True = ghi CSV với dấu dạng tổ hợp NFD), question (mặc định; xem questions.json),
  truth  : {"additive": [cột cộng được], "non_additive": [cột KHÔNG được cộng], "absent_terms": [từ chỉ thứ KHÔNG có trong dữ liệu]}
  mock   : {"table", "by", "measure", "agg", "title"}  cách LLM giả phân tích (dùng cho chế độ --mock)
Thêm bộ mới = thêm một tệp và một dòng trong ALL; không cần sửa chỗ nào khác."""
from . import chi_tieu, nhan_su, san_xuat

ALL = {m.build()["id"]: m.build for m in (chi_tieu, nhan_su, san_xuat)}
