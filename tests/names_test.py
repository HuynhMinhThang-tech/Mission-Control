# -*- coding: utf-8 -*-
"""Báo cáo gọi đối tượng bằng TÊN, không bằng MÃ: SP003 -> «Điện thoại Viet-Tech Pro».
Dựng lại đúng lỗi người dùng thấy: «Sản phẩm SP003 ... cao hơn 41.911.487 đ so với sản phẩm SP001».
Chạy: python tests/names_test.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from app import numfmt  # noqa: E402
from app.data import names as N  # noqa: E402
from app.data.scope import data_card  # noqa: E402

bad = []


def check(ok, msg):
    print(("OK   " if ok else "FAIL ") + msg)
    if not ok:
        bad.append(msg)


sp = pd.DataFrame({"MaSP": ["SP001", "SP002", "SP003", "SP004", "SP005"],
                   "TenSP": ["Điện thoại Sunrise Basic", "Điện thoại Hanoi Co. Lite", "Điện thoại Viet-Tech Pro", "Điện thoại Sunrise Lite", "Ốp lưng Bamboo Pro"],
                   "DanhMuc": ["Điện thoại & Phụ kiện"] * 5, "ThuongHieu": ["Sunrise", "Hanoi Co.", "Viet-Tech", "Sunrise", "Bamboo"]})
ct = pd.DataFrame({"MaDH": ["DH0001", "DH0002", "DH0003"], "MaSP": ["SP001", "SP003", "SP003"], "SoLuong": [1, 2, 3]})
clean = {"SanPham": sp, "ChiTietDonHang": ct}

nm = N.code_names(clean)
check(nm["cols"] == {"MaSP": "TenSP"} and nm["map"]["SP003"] == "Điện thoại Viet-Tech Pro" and len(nm["map"]) == 5, f"tìm đúng cặp MaSP -> TenSP, 5 mã ({nm['cols']})")
check("DH0001" not in nm["map"], "mã đơn hàng (không có cột tên) không bị đổi")

# mã trùng tên -> không đổi (tránh gộp hai đối tượng làm một)
dup = pd.DataFrame({"MaKH": ["KH001", "KH002", "KH003"], "TenKH": ["An", "An", "Bình"]})
check("KH001" not in N.code_names({"K": dup})["map"] and "KH003" not in N.code_names({"K": dup})["map"], "cột tên trùng nhiều -> không đổi mã (giữ nguyên, tránh gộp nhầm)")
# mã chỉ gồm số không đổi (dễ nhầm với số liệu)
num = pd.DataFrame({"MaDon": ["1001", "1002", "1003"], "TenDon": ["a", "b", "c"]})
check(N.code_names({"D": num})["map"] == {}, "mã chỉ gồm số không bị đổi")

# bảng kết quả
res = pd.DataFrame({"MaSP": ["SP003", "SP001"], "Lợi nhuận": [70909812.0, 29000325.0]})
out = N.decode_frame(res, nm)
check(list(out.iloc[:, 0]) == ["Điện thoại Viet-Tech Pro", "Điện thoại Sunrise Basic"] and out.columns[0] == "Tên SP" and out.columns[1] == "Lợi nhuận", f"bảng kết quả: cột mã đổi thành tên, tiêu đề thành «Tên SP» ({list(out.columns)})")
check(list(res.iloc[:, 0]) == ["SP003", "SP001"], "không sửa bảng gốc")
nocode = pd.DataFrame({"Tỉnh": ["Cần Thơ", "Bình Dương"], "Tổng": [1.0, 2.0]})
check(N.decode_frame(nocode, nm).equals(nocode), "bảng không có mã giữ nguyên")

# văn bản AI
t = "Sản phẩm SP003 trong danh mục Điện thoại & Phụ kiện mang lại lợi nhuận 70.909.812 đ, cao hơn 41.911.487 đ so với sản phẩm SP001."
k = numfmt.Known.from_dfs([out], nm)
r = numfmt.fix_text(t, k)
check("SP003" not in r and "SP001" not in r and "Điện thoại Viet-Tech Pro" in r and "Điện thoại Sunrise Basic" in r and "70.909.812 đ" in r and "41.911.487 đ" in r, f"văn bản: mã đổi thành tên, số tiền giữ nguyên ({r})")
r2 = numfmt.fix_text("SP003 (Điện thoại Viet-Tech Pro) và Ốp lưng Bamboo Pro (SP005) bán chạy, đơn DH0001 lớn nhất.", k)
check(r2.count("Điện thoại Viet-Tech Pro") == 1 and r2.count("Ốp lưng Bamboo Pro") == 1 and "SP00" not in r2 and "DH0001" in r2, f"không lặp tên khi AI đã ghi cả mã lẫn tên ({r2})")
check(numfmt.fix_text(r, k) == r, "idempotent")
check(numfmt.fix_text(t, numfmt.Known.from_dfs([out])) == numfmt.fix_text(t), "không có bảng mã thì văn bản giữ nguyên mã (không phá hành vi cũ)")
kp = numfmt.fix_kpi({"label": "Lợi nhuận sản phẩm SP003", "value": 70909812.0, "delta": "+28,34%"}, k)
check(kp["label"] == "Lợi nhuận sản phẩm Điện thoại Viet-Tech Pro" and kp["value"] == "70.909.812 đ", f"nhãn KPI cũng đổi mã thành tên ({kp})")
check(numfmt.fix_payload({"summary": t, "code": "SP003"}, k)["summary"] == r, "fix_payload đổi mã trong văn bản")

# thẻ dữ liệu đưa cho AI
card = data_card(clean)
check("QUY ƯỚC GỌI TÊN" in card and "MaSP -> TenSP" in card and "KHÔNG viết mã" in card, "thẻ dữ liệu nói rõ mã nào là tên nào và cấm viết mã")
check("QUY ƯỚC GỌI TÊN" not in data_card({"X": nocode}), "dữ liệu không có cặp mã - tên thì không thêm quy ước")

print()
if bad:
    print(f"CÓ {len(bad)} LỖI")
    sys.exit(1)
print("TẤT CẢ ĐẠT")
