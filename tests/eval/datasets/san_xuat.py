# -*- coding: utf-8 -*-
"""Sản xuất theo 3 năm (3 bảng cùng cấu trúc, như tệp 2024/2025/2026 của người dùng): sản lượng cộng được, hiệu suất (%) và kế hoạch năm (lặp ở mọi dòng) thì không,
bảng 2026 mới đến giữa tháng 9. Cố ý KHÔNG có cột bảo trì, máy móc, nguyên liệu: AI không được viết như thể có."""
import numpy as np
import pandas as pd


def _year(y, end, rng, plan):
    days = pd.date_range(f"{y}-01-01", end)
    rows = []
    for d in days:
        for nm in ("NM1", "NM2", "NM3", "NM4", "NM5"):
            base = {"NM1": 120, "NM2": 95, "NM3": 80, "NM4": 60, "NM5": 40}[nm]
            rows.append({"Ngày": d.strftime("%Y-%m-%d"), "Nhà máy": nm, "Sản lượng (tấn)": round(base * (1 + 0.12 * np.sin(d.dayofyear / 58)) + rng.normal(0, 6), 1),
                         "Hiệu suất (%)": round(float(np.clip(rng.normal(86 if nm != "NM5" else 71, 5), 40, 100)), 1), "Kế hoạch năm (tấn)": plan[nm]})
    return pd.DataFrame(rows)


def build(seed=37):
    rng = np.random.default_rng(seed)
    tables = {"san_xuat_2024.csv": _year(2024, "2024-12-31", rng, {"NM1": 41000, "NM2": 33000, "NM3": 28000, "NM4": 21000, "NM5": 14000}),
              "san_xuat_2025.csv": _year(2025, "2025-12-31", rng, {"NM1": 43000, "NM2": 34000, "NM3": 29000, "NM4": 22000, "NM5": 15000}),
              "san_xuat_2026.csv": _year(2026, "2026-09-14", rng, {"NM1": 45000, "NM2": 35500, "NM3": 30000, "NM4": 23000, "NM5": 16000})}
    return {"id": "san_xuat", "title": "Sản xuất 2024-2026 (3 bảng)", "tables": tables, "nfd": False,
            "truth": {"additive": ["Sản lượng (tấn)"], "non_additive": ["Hiệu suất (%)", "Kế hoạch năm (tấn)"], "absent_terms": ["bảo trì", "máy móc", "thiết bị", "nguyên liệu", "nhân công"]},
            "mock": {"table": "san_xuat_2026.csv", "by": "Nhà máy", "measure": "Sản lượng (tấn)", "agg": "sum", "title": "Sản lượng theo nhà máy"}}
