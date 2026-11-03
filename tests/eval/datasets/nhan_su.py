# -*- coding: utf-8 -*-
"""Nhân sự: toàn cột KHÔNG cộng được (tuổi, thâm niên, điểm đánh giá), chỉ lương cộng được; mã nhân viên là số nguyên gần như duy nhất."""
import numpy as np
import pandas as pd


def build(seed=23):
    rng = np.random.default_rng(seed)
    n = 420
    dept = rng.choice(["Kinh doanh", "Kỹ thuật", "Vận hành", "Nhân sự", "Kế toán"], n, p=[.3, .3, .2, .1, .1])
    tuoi = rng.integers(22, 58, n)
    tn = np.clip(tuoi - 22 - rng.integers(0, 8, n), 0, None)
    luong = (9 + tn * 0.6 + rng.normal(0, 2, n)).round(1) * 1_000_000
    df = pd.DataFrame({"Mã nhân viên": np.arange(1001, 1001 + n), "Phòng ban": dept, "Giới tính": rng.choice(["Nam", "Nữ"], n),
                       "Tuổi": tuoi, "Thâm niên (năm)": tn, "Lương (đ)": luong.astype(int), "Điểm đánh giá": rng.integers(1, 6, n),
                       "Ngày vào làm": (pd.Timestamp("2026-06-30") - pd.to_timedelta(tn * 365 + rng.integers(0, 300, n), unit="D")).strftime("%Y-%m-%d")})
    return {"id": "nhan_su", "title": "Nhân sự", "tables": {"nhan_su.csv": df}, "nfd": False,
            "truth": {"additive": ["Lương (đ)"], "non_additive": ["Tuổi", "Thâm niên (năm)", "Điểm đánh giá", "Mã nhân viên"], "absent_terms": ["nghỉ việc", "tuyển dụng", "đào tạo", "phúc lợi"]},
            "mock": {"table": "nhan_su.csv", "by": "Phòng ban", "measure": "Lương (đ)", "agg": "mean", "title": "Lương trung bình theo phòng ban"}}
