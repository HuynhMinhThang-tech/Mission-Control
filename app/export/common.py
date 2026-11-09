# -*- coding: utf-8 -*-
"""Tiện ích dùng chung cho dashboard / PPTX / Markdown."""
import re

import pandas as pd

from .. import labels, numfmt
from ..utils import fmt_pct, fmt_val, vn

pp = numfmt.pretty_period          # 2026-03-01 -> T3/2026 (nhãn kỳ gọn, không bị chồng chữ trên trục)

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


def refine_charts(charts, dfs):
    """Tiêu đề (insight) do AI viết phải KHỚP số liệu của chính biểu đồ; sai hướng tăng/giảm hay sai tỷ lệ % thì thay bằng câu tính từ dữ liệu."""
    out = []
    for c in charts or []:
        c = dict(c)
        try:
            rows = chart_rows(dfs[c["task"]], c["x"], c["y"])
        except Exception:
            rows = []
        if rows:
            tl = is_time_like(rows)
            if not numfmt.consistent(c.get("insight"), rows, tl):
                c["insight"] = numfmt.headline(rows, c.get("kind"), c["y"], tl)
                c["insight_src"] = "tính từ dữ liệu"
        out.append(c)
    return out


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


_UNIT_ALIAS = {"đồng": "đ", "vnd": "đ", "vnđ": "đ", "đ": "đ", "phần trăm": "%", "%": "%"}


def unit_of(c):
    """Đơn vị của biểu đồ theo DỮ LIỆU (đ, %, kg...). Mọi cách viết tiền (đồng, VNĐ) gộp về một ký hiệu 'đ'."""
    u = str((c or {}).get("unit") or "").strip()
    return _UNIT_ALIAS.get(u.lower(), u)


def facts(rows, kind="bars", unit=""):
    """Vài con số nổi bật TÍNH TRỰC TIẾP từ dữ liệu biểu đồ (không do AI viết). Số ghi đủ, theo quy tắc số chung (utils.py), kèm đơn vị của dữ liệu."""
    if not rows:
        return []
    f = lambda v: fmt_val(v, unit)          # noqa: E731
    out = []
    if is_time_like(rows) and kind in ("cols", "line"):
        a, b = rows[0], rows[-1]
        s = f"{pp(a[0])} → {pp(b[0])}: {f(a[1])} → {f(b[1])}"
        if a[1]:
            ch = (b[1] / a[1] - 1) * 100
            s += f" ({'+' if ch > 0 else ''}{fmt_pct(ch)})"
        out.append(s)
        hi = max(rows, key=lambda r: r[1])
        lo = min(rows, key=lambda r: r[1])
        out.append(f"Cao nhất: {pp(hi[0])} ({f(hi[1])})")
        out.append(f"Thấp nhất: {pp(lo[0])} ({f(lo[1])})")
        return out
    hi = max(rows, key=lambda r: r[1])
    lo = min(rows, key=lambda r: r[1])
    out.append(f"Cao nhất: {hi[0]} ({f(hi[1])})")
    out.append(f"Thấp nhất: {lo[0]} ({f(lo[1])})")
    tot = sum(v for _, v in rows)
    if all(v >= 0 for _, v in rows) and tot > 0 and len(rows) > 1:
        out.append(f"{hi[0]} chiếm {fmt_pct(hi[1] / tot * 100)} tổng ({f(tot)})")
    return out