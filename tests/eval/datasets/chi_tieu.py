# -*- coding: utf-8 -*-
"""Chi tiêu cá nhân: thu và chi lẫn trong một cột số tiền, số dư là chỉ số không cộng được, nhóm 'Từ thiện' chỉ vài dòng, ghi chú thiếu ~60%, tháng cuối thiếu ngày."""
import numpy as np
import pandas as pd


def build(seed=11):
    rng = np.random.default_rng(seed)
    days = pd.date_range("2026-08-01", "2026-10-19")                      # tháng 10 mới có 19/31 ngày
    rows = []
    for d in days:
        for _ in range(rng.integers(1, 4)):
            chi = rng.random() < 0.8
            cat = rng.choice(["Sinh hoạt", "Di chuyển", "Giải trí", "Ăn uống"], p=[.4, .2, .15, .25]) if chi else "Lương"
            rows.append({"Ngày": d.strftime("%Y-%m-%d"), "Loại": "Chi tiêu" if chi else "Thu nhập", "Danh mục": cat,
                         "Số tiền (đ)": int(rng.integers(20, 600) * 1000 if chi else rng.integers(5, 15) * 1_000_000)})
    df = pd.DataFrame(rows)
    df.loc[df.sample(3, random_state=seed).index, ["Loại", "Danh mục"]] = ["Chi tiêu", "Từ thiện"]      # nhóm rất nhỏ (3 dòng)
    df["Số dư sau giao dịch"] = (8_000_000 + np.cumsum(np.where(df["Loại"] == "Chi tiêu", -df["Số tiền (đ)"], df["Số tiền (đ)"]))).astype(int)
    df["Ghi chú"] = np.where(rng.random(len(df)) < 0.4, "có ghi chú", None)                              # thiếu ~60%
    return {"id": "chi_tieu", "title": "Chi tiêu cá nhân", "tables": {"chi_tieu.csv": df}, "nfd": True,
            "truth": {"additive": ["Số tiền (đ)"], "non_additive": ["Số dư sau giao dịch"], "absent_terms": ["đầu tư", "bảo hiểm", "cổ phiếu", "tiết kiệm lãi suất"]},
            "mock": {"table": "chi_tieu.csv", "by": "Danh mục", "measure": "Số tiền (đ)", "agg": "sum", "title": "Số tiền theo danh mục"}}
