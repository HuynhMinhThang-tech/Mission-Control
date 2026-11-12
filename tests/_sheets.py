# -*- coding: utf-8 -*-
"""Dữ liệu mẫu dùng chung cho các test nhiều sheet: tệp Excel 4 sheet giống ca thực tế (chi tiết đơn hàng, đơn hàng, khách hàng, sản phẩm)."""
import io

import numpy as np
import pandas as pd

NAME = "du_lieu_thuong_mai_dien_tu.xlsx"
SHEETS = ["ChiTietDonHang", "DonHang", "KhachHang", "SanPham"]


def make_xlsx():
    rng = np.random.default_rng(7)
    sp = pd.DataFrame({"MaSP": [f"SP{i:03d}" for i in range(69)], "TenSP": [f"San pham {i}" for i in range(69)], "DanhMuc": rng.choice(["Dien thoai", "Laptop", "Phu kien", "Gia dung"], 69),
                       "GiaNiemYet": rng.integers(100, 900, 69) * 1000, "GiaVon": rng.integers(50, 700, 69) * 1000})
    kh = pd.DataFrame({"MaKH": [f"KH{i:04d}" for i in range(499)], "HoTen": [f"Khach {i}" for i in range(499)], "ThanhPho": rng.choice(["HN", "HCM", "DN"], 499),
                       "NgaySinh": pd.Timestamp("1955-11-18") + pd.to_timedelta(rng.integers(0, 365 * 49, 499), unit="D"),
                       "NgayDangKy": pd.Timestamp("2021-01-01") + pd.to_timedelta(rng.integers(0, 1200, 499), unit="D")})
    dh = pd.DataFrame({"MaDH": [f"DH{i:05d}" for i in range(3000)], "MaKH": rng.choice(kh.MaKH, 3000), "PhuongThuc": rng.choice(["COD", "The", "Vi"], 3000),
                       "NgayDat": pd.Timestamp("2023-01-01") + pd.to_timedelta(rng.integers(0, 700, 3000), unit="D")})
    ct = pd.DataFrame({"MaDH": rng.choice(dh.MaDH, 5320), "MaSP": rng.choice(sp.MaSP, 5320), "SoLuong": rng.integers(1, 6, 5320), "DonGia": rng.integers(100, 900, 5320) * 1000})
    ct["ThanhTien"] = ct.SoLuong * ct.DonGia
    b = io.BytesIO()
    with pd.ExcelWriter(b, engine="openpyxl") as w:
        for n, d in (("ChiTietDonHang", ct), ("DonHang", dh), ("KhachHang", kh), ("SanPham", sp)):
            d.to_excel(w, sheet_name=n, index=False)
    return b.getvalue(), {"ct": ct, "dh": dh, "kh": kh, "sp": sp}
