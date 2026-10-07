# -*- coding: utf-8 -*-
"""Dashboard TƯƠNG TÁC kiểu Power BI (1 file HTML độc lập, mở offline).

Khác `dashboard.py` (báo cáo tĩnh: bảng kết quả đã tổng hợp), ở đây nhúng DỮ LIỆU ĐÃ LÀM SẠCH vào trang
để người xem tự lọc (slicer), bấm vào biểu đồ để lọc chéo, đổi chỉ số / cách tính / chiều phân tích.
Mọi phép tính chạy trong trình duyệt, không cần máy chủ và không gọi AI.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from ..data.quality import to_dt
from ..utils import E, is_text

ASSETS = Path(__file__).parent / "assets"
MAX_ROWS = 30000       # vượt ngưỡng này thì gộp thành "khối" (nhóm theo các chiều) để trang vẫn nhẹ
MAX_CUBE = 60000
WEEK = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
ID_NAME = re.compile(r"(^|_)(id|ma|code|stt|sdt|phone|email)(_|$)", re.I)
PRICE = re.compile(r"(^|_)(don_gia|gia|price|ti_le|tl|rate|pct|percent|diem|score)($|_)", re.I)
TIER0 = re.compile(r"tien|doanh|revenue|amount|sales|chi|thu|profit|loi_nhuan|cost|gia_tri", re.I)
TIER1 = re.compile(r"so_luong|qty|quantity|sl$", re.I)
HINT = re.compile(r"tien|doanh|revenue|amount|sales|gia_tri|chi|thu|profit|loi_nhuan|cost|price|don_gia|so_luong|qty|quantity", re.I)
MONEY = re.compile(r"tien|doanh|revenue|amount|sales|gia|chi|thu|profit|loi_nhuan|cost|price|vnd|đ", re.I)


def _pretty(c):
    t = str(c).replace("_", " ").strip()
    return t[:1].upper() + t[1:]


def _nums(s):
    return pd.to_numeric(s, errors="coerce")


def _clean_list(s, nd=2):
    return s.round(nd).astype(object).where(s.notna(), None).tolist()


def _spec(name, df):
    df = df.copy()
    n_src = len(df)
    if n_src < 2 or df.shape[1] < 2:
        return None
    # ---- cột thời gian
    tcol = next((c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])), None)
    if tcol is None:
        for c in df.columns:
            if is_text(df[c]) and re.search(r"ngay|date|thang|time|ky|day", str(c), re.I):
                p = to_dt(df[c])
                if p.notna().mean() >= .9:
                    df[c], tcol = p, c
                    break
    # ---- chỉ số (đo lường)
    meas = []
    for c in df.columns:
        if c == tcol or str(c).endswith("_nghi_van") or pd.api.types.is_bool_dtype(df[c]) or pd.api.types.is_datetime64_any_dtype(df[c]):
            continue
        s = _nums(df[c]) if is_text(df[c]) and df[c].notna().any() and _nums(df[c]).notna().mean() >= .95 else df[c]
        if not pd.api.types.is_numeric_dtype(s) or s.nunique() < 2 or ID_NAME.search(str(c)):
            continue
        if pd.api.types.is_integer_dtype(s) and s.nunique() / max(1, s.notna().sum()) > .95 and not HINT.search(str(c)):
            continue                                   # số nguyên gần như duy nhất = mã định danh
        meas.append((c, s))
    meas.sort(key=lambda x: 3 if PRICE.search(str(x[0])) else 0 if TIER0.search(str(x[0])) else 1 if TIER1.search(str(x[0])) else 2)
    meas = meas[:6]
    # ---- chiều phân tích
    dims = []
    for c in df.columns:
        if c == tcol or c in [m[0] for m in meas] or ID_NAME.search(str(c)):
            continue
        s = df[c]
        if pd.api.types.is_datetime64_any_dtype(s) or pd.api.types.is_float_dtype(s):
            continue
        k = s.nunique(dropna=True)
        if 2 <= k <= 40 and (k <= .5 * n_src or n_src <= 20):
            if is_text(s) and s.dropna().astype(str).str.len().mean() > 40:
                continue
            dims.append((k, c))
    dims = [c for _, c in sorted(dims, key=lambda x: x[0])][:6]

    cols, labels = {}, {}
    out_dims = []
    for j, c in enumerate(dims):
        s = df[c].astype(object).where(df[c].notna(), "(trống)").astype(str)
        codes, uniq = pd.factorize(s, sort=True)
        cols[f"d{j}"] = codes
        out_dims.append({"k": f"d{j}", "label": _pretty(c), "vals": [str(u) for u in uniq]})
    time = None
    if tcol is not None:
        p = df[tcol]
        mo = p.dt.strftime("%Y-%m")
        codes, uniq = pd.factorize(mo.where(p.notna()), sort=True)
        cols["t"] = codes
        time = {"label": f"Tháng ({_pretty(tcol).lower()})", "vals": [str(u) for u in uniq]}
        if p.dt.date.nunique() >= 14:
            cols["wd"] = p.dt.dayofweek.fillna(-1).astype(int).to_numpy()
            out_dims.append({"k": "wd", "label": "Thứ trong tuần", "vals": WEEK})
    if not out_dims and time is None:
        return None
    mvals = {f"m{j}": s.astype(float) for j, (c, s) in enumerate(meas)}
    out_meas = [{"k": f"m{j}", "label": _pretty(c), "unit": "đ" if MONEY.search(str(c)) else "", "avg": bool(PRICE.search(str(c)))} for j, (c, _) in enumerate(meas)]

    # ---- quá nhiều dòng -> gộp thành khối (sum + đếm) theo các chiều
    cube, dropped = False, []
    key_cols = [k for k in cols]
    if n_src > MAX_ROWS:
        cube = True
        g = pd.DataFrame({k: cols[k] for k in key_cols})
        while key_cols and g.groupby(key_cols, sort=False).ngroups > MAX_CUBE and len(key_cols) > 1:
            drop = key_cols.pop()
            dropped.append(next((d["label"] for d in out_dims if d["k"] == drop), drop))
        for k in list(cols):
            if k not in key_cols:
                cols.pop(k)
        out_dims = [d for d in out_dims if d["k"] in cols]
        if "t" not in cols:
            time = None
        g = pd.DataFrame({k: cols[k] for k in key_cols})
        for k, s in mvals.items():
            g[k] = s.to_numpy()
        agg = g.groupby(key_cols, sort=False, dropna=False)
        base = agg.size().rename("_w").reset_index()
        sums = agg[list(mvals)].sum(min_count=1).reset_index() if mvals else base[key_cols]
        cnts = agg[list(mvals)].count().reset_index() if mvals else None
        merged = base.merge(sums, on=key_cols) if mvals else base
        cols = {k: merged[k].to_numpy() for k in key_cols}
        w = merged["_w"].astype(int).tolist()
        mvals = {k: merged[k].astype(float) for k in mvals}
        mc = [cnts.merge(base[key_cols], on=key_cols)[k].astype(int).tolist() for k in mvals] if mvals else None
        n = len(merged)
    else:
        w, mc, n = None, None, n_src

    return {"name": str(name), "n_src": int(n_src), "n": int(n), "cube": cube, "dropped": dropped, "w": w, "mc": mc,
            "dims": [dict(d, codes=[int(x) for x in cols[d["k"]]]) for d in out_dims],
            "time": dict(time, codes=[int(x) for x in cols["t"]]) if time else None,
            "meas": [dict(m, vals=_clean_list(mvals[m["k"]].reset_index(drop=True))) for m in out_meas]}


def build_datasets(dfs):
    out = [s for s in (_spec(n, d) for n, d in dfs.items()) if s]
    out.sort(key=lambda s: -s["n_src"])
    return out[:4]


def _safe(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=lambda o: None if (isinstance(o, float) and np.isnan(o)) else str(o)) \
        .replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def build_dashboard(meta, dfs):
    """meta: title, question, ctx, date, summary, insights, actions, risks, kpis. dfs: {tên: DataFrame đã làm sạch}."""
    ds = build_datasets(dfs)
    payload = {"title": meta["title"], "question": meta["question"], "ctx": meta.get("ctx") or "", "date": meta["date"],
               "summary": meta.get("summary") or "", "insights": meta.get("insights") or [], "actions": meta.get("actions") or [],
               "risks": meta.get("risks") or [], "datasets": ds}
    css = (ASSETS / "live.css").read_text("utf-8")
    js = (ASSETS / "live.js").read_text("utf-8")
    return (f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Dashboard · {E(meta["title"])}</title><style>{css}</style></head><body>'
            f'<div id="app"><noscript>Dashboard cần bật JavaScript để lọc và tương tác.</noscript></div>'
            f'<script id="data" type="application/json">{_safe(payload)}</script><script>{js}</script></body></html>')
