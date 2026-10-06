# -*- coding: utf-8 -*-
"""AGENT 6 · Rà soát cuối trước khi người dùng duyệt (bước 7)."""
from ..state import A, put, tick


def run(fb=""):
    tick(0)
    a = A["d"]
    ap = A.get("applied", [])
    put(6, {"checks": ["Câu hỏi và bối cảnh", f"Cách làm sạch dữ liệu ({len(ap)} thao tác)",
                       f"Phân tích và dự báo ({len(a[3]['tasks'])} phân tích)", f"{len(a[4]['insights'])} insight kèm bằng chứng",
                       f"Dashboard ({len(a[5]['final']['charts'])} biểu đồ), báo cáo, slide"]})
