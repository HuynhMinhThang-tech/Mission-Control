# -*- coding: utf-8 -*-
"""Kiểm tra biểu đồ AI đề xuất có trỏ đúng cột thật hay không, và loại bỏ biểu đồ trùng."""

from .. import labels as lb

# Các dạng biểu đồ. Ba nhóm: so sánh (bars, cols, lollipop, pareto), xu hướng (line, area), cơ cấu (donut, pie, treemap).
KINDS = ("bars", "cols", "line", "area", "donut", "pie", "lollipop", "pareto", "treemap")
_UNIT_ALIAS = {"đồng": "đ", "vnd": "đ", "vnđ": "đ", "₫": "đ", "phần trăm": "%"}


def unit_for(c, t=None):
    """Đơn vị của biểu đồ: theo AI ghi, nếu AI để trống thì suy từ tên cột giá trị (tiền -> đ) để số trên biểu đồ theo đúng quy tắc của đơn vị."""
    u = str(c.get("unit") or "").strip()
    u = _UNIT_ALIAS.get(u.lower(), u)
    if u:
        return u
    try:
        i = t["cols"].index(c["y"])
        return (t.get("units") or [])[i] if t.get("units") else lb.unit(c["y"])
    except (KeyError, ValueError, IndexError, TypeError):
        return ""


def is_num(t, c):
    i = t["cols"].index(c)
    return any(isinstance(r[i], (int, float)) and not isinstance(r[i], bool) for r in t["rows"])


def valid_charts(cs, tabs):
    out, seen = [], set()
    for c in cs:
        try:
            t = tabs[int(c["task"])]
            key = (int(c["task"]), c["x"], c["y"])
            if key in seen:      # cùng bảng + cùng cột = biểu đồ trùng
                continue
            if c["x"] in t["cols"] and c["y"] in t["cols"] and is_num(t, c["y"]):
                seen.add(key)
                out.append({"task": int(c["task"]), "x": c["x"], "y": c["y"],
                            "kind": c.get("kind") if c.get("kind") in KINDS else "bars",
                            "title": c.get("title", ""), "unit": unit_for(c, t), "insight": c.get("insight", ""),
                            "recommended": bool(c.get("recommended", True))})
        except Exception:
            continue
    return out