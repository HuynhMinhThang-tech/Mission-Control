# -*- coding: utf-8 -*-
"""Đọc tệp người dùng tải lên + bộ dữ liệu mẫu (chỉ dùng khi người dùng chủ động bấm)."""
import io

import numpy as np
import pandas as pd

from .structure import analyze, meta


def _merged_count(b, sheet):
    try:
        import openpyxl
        return len(openpyxl.load_workbook(io.BytesIO(b), read_only=False)[sheet].merged_cells.ranges)
    except Exception:
        return 0


def load_files(fs):
    """Đọc tệp + chạy cổng kiểm tra cấu trúc. Trả về (dfs đang dùng, báo cáo cấu trúc, bản gốc/bản chuẩn hóa)."""
    dfs, reports, alts = {}, {}, {}
    for f in fs:
        b = f.read()
        name = f.filename
        items = []
        if name.lower().endswith((".xlsx", ".xls", ".xlsm")):
            xl = pd.ExcelFile(io.BytesIO(b))
            for sh in xl.sheet_names:
                key = f"{name}::{sh}" if len(xl.sheet_names) > 1 else name
                items.append((key, xl.parse(sh, header=None), xl.parse(sh), _merged_count(b, sh) if name.lower().endswith("x") or name.lower().endswith("m") else 0))
        else:
            kw = dict(sep=None, engine="python", encoding="utf-8-sig", encoding_errors="replace")
            try:
                plain = pd.read_csv(io.BytesIO(b), **kw)
            except Exception:
                # không đọc được thành bảng (văn bản thuần, số cột lộn xộn...) -> vẫn nhận để cổng cấu trúc đánh giá
                lines = [l for l in b.decode("utf-8-sig", "replace").splitlines() if l.strip()]
                plain = pd.DataFrame({"noi_dung": lines})
            try:
                raw = pd.read_csv(io.BytesIO(b), header=None, **kw)
            except Exception:
                raw = None
            items.append((name, raw, plain, 0))
        for key, raw, plain, merged in items:
            res = analyze(raw, plain, merged)
            dfs[key] = res["fixed"] if res["fixed"] is not None else res["plain"]
            reports[key] = meta(res)
            alts[key] = {"plain": res["plain"], "fixed": res["fixed"]}
    return dfs, reports, alts


def make_sample():
    rng = np.random.default_rng(7)
    n = 14500
    day = pd.Timestamp("2026-01-01") + pd.to_timedelta(rng.integers(0, 273, n), unit="D")
    reg = rng.choice(["HCM", "HN", "ĐN", "Khác"], n, p=[.42, .28, .14, .16])
    prod = rng.choice(["SP-A", "SP-B", "SP-C", "SP-D"], n, p=[.35, .3, .2, .15])
    base = pd.Series(prod).map({"SP-A": 1.0e6, "SP-B": .8e6, "SP-C": .6e6, "SP-D": .4e6}).to_numpy()
    q3 = np.asarray(day >= pd.Timestamp("2026-07-01"))
    hcm = reg == "HCM"
    price = base * rng.normal(1, .06, n) * np.where(q3 & hcm, .9, 1)
    keep = ~(q3 & hcm & (rng.random(n) < .14))
    d = pd.DataFrame({"ngay": day.strftime("%Y-%m-%d"), "ma_don": [f"O-{88000 + i}" for i in range(n)], "khu_vuc": reg,
                      "san_pham": prod, "customer_id": rng.integers(1, 2175, n), "so_luong": rng.integers(1, 8, n),
                      "don_gia": price.round(-3), "kenh": rng.choice(["Online", "Cửa hàng", "Đại lý"], n)})[keep].head(12480).reset_index(drop=True)
    d["doanh_thu"] = d["so_luong"] * d["don_gia"]
    d.loc[rng.choice(len(d), 1872, replace=False), "doanh_thu"] = np.nan
    d.loc[rng.choice(len(d), 42, replace=False), "ngay"] = "15/08/2026"
    d.loc[rng.choice(len(d), 9, replace=False), "doanh_thu"] = -500000
    d = pd.concat([d, d.sample(17, random_state=1)], ignore_index=True)
    cust = pd.DataFrame({"customer_id": range(1, 2141), "phan_khuc": rng.choice(["Lẻ", "Doanh nghiệp", "Đại lý"], 2140),
                         "thanh_pho": rng.choice(["HCM", "HN", "ĐN", "Khác"], 2140)})
    prods = pd.DataFrame({"san_pham": ["SP-A", "SP-B", "SP-C", "SP-D"], "nhom": ["Chủ lực", "Chủ lực", "Phổ thông", "Phụ kiện"]})
    return {"sales_q3.csv": d, "customers.csv": cust, "products.csv": prods}