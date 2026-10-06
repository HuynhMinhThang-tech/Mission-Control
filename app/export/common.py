# -*- coding: utf-8 -*-
"""Tiện ích dùng chung cho dashboard / PPTX / Markdown."""
import re

import pandas as pd

from ..utils import compact, vn

PRI_ORDER = {"Cao": 0, "Trung bình": 1, "Thấp": 2}


def trunc(s, n):
    s = str(s or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def chart_rows(df, x, y, limit=24):
    """Lấy (nhãn, giá trị) cho biểu đồ: bỏ dòng trùng hệt nhau, gộp nhãn lặp (trừ chuỗi thời gian)."""
    if x == y:
        return []
    d = df[[x, y]].copy()
    d[x] = d[x].astype(str)
    d[y] = pd.to_numeric(d[y], errors="coerce").fillna(0)
    rows = list(dict.fromkeys(zip(d[x], d[y].astype(float))))
    labels = [l for l, _ in rows]
    if len(set(labels)) < len(labels) and not is_time_like(rows):
        agg = {}
        for l, v in rows:
            agg[l] = agg.get(l, 0) + v
        rows = list(agg.items())
    return [(l, float(v)) for l, v in rows[:limit]]


def dedupe_charts(charts, dfs):
    """Bỏ biểu đồ có cùng bảng+cột hoặc cùng bộ số liệu với biểu đồ trước đó."""
    out, seen = [], set()
    for c in charts:
        rows = chart_rows(dfs[c["task"]], c["x"], c["y"])
        sig = tuple(rows)
        if not rows or (c["task"], c["x"], c["y"]) in seen or sig in seen:
            continue
        seen.add((c["task"], c["x"], c["y"]))
        seen.add(sig)
        out.append(c)
    return out


_TIME = re.compile(r"^(\d{4}[-/]\d{1,2}|\d{1,2}[-/]\d{4}|Q[1-4]|T\d{1,2}|Tháng|W\d|\d{4}$)", re.I)


def is_time_like(rows):
    if len(rows) < 4:
        return False
    return sum(bool(_TIME.match(l)) for l, _ in rows) / len(rows) >= 0.6


def scale(rows):
    """Chọn mẫu số để nhãn số trên slide gọn (tỷ / triệu / nghìn)."""
    m = max([abs(v) for _, v in rows] or [0])
    if m >= 1e9:
        return 1e9, "tỷ"
    if m >= 1e6:
        return 1e6, "triệu"
    if m >= 1e4:
        return 1e3, "nghìn"
    return 1.0, ""


def facts(rows, kind="bars"):
    """Vài con số nổi bật TÍNH TRỰC TIẾP từ dữ liệu biểu đồ (không do AI viết)."""
    if not rows:
        return []
    out = []
    if is_time_like(rows) and kind in ("cols", "line"):
        a, b = rows[0], rows[-1]
        s = f"{a[0]} → {b[0]}: {compact(a[1])} → {compact(b[1])}"
        if a[1]:
            s += f" ({(b[1] / a[1] - 1) * 100:+.1f}%)".replace(".", ",")
        out.append(s)
        hi = max(rows, key=lambda r: r[1])
        lo = min(rows, key=lambda r: r[1])
        out.append(f"Cao nhất: {hi[0]} ({compact(hi[1])})")
        out.append(f"Thấp nhất: {lo[0]} ({compact(lo[1])})")
        return out
    hi = max(rows, key=lambda r: r[1])
    lo = min(rows, key=lambda r: r[1])
    out.append(f"Cao nhất: {hi[0]} ({compact(hi[1])})")
    out.append(f"Thấp nhất: {lo[0]} ({compact(lo[1])})")
    tot = sum(v for _, v in rows)
    if all(v >= 0 for _, v in rows) and tot > 0 and len(rows) > 1:
        out.append(f"{hi[0]} chiếm {vn(hi[1] / tot * 100, 1)}% tổng ({compact(tot)})")
    return out