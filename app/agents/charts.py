# -*- coding: utf-8 -*-
"""Kiểm tra biểu đồ AI đề xuất có trỏ đúng cột thật hay không, và loại bỏ biểu đồ trùng."""

KINDS = ("bars", "cols", "line", "donut")


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
                            "title": c.get("title", ""), "unit": c.get("unit", ""), "insight": c.get("insight", ""),
                            "recommended": bool(c.get("recommended", True))})
        except Exception:
            continue
    return out