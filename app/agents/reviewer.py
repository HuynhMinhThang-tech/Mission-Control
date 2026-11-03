# -*- coding: utf-8 -*-
"""AGENT 6 · Rà soát cuối trước khi người dùng duyệt (bước 7)."""
from .. import numfmt
from ..state import A, put, tick


def _insight_line(ins):
    """Chỉ nói số phát hiện ĐÃ KIỂM ĐƯỢC trên tổng số; dòng bắt đầu bằng ⚠ khi còn phát hiện chưa kiểm được (giao diện không thêm dấu ✓ cho dòng này)."""
    ins = numfmt.audit_insights(ins, numfmt.Known.from_dfs(A["x"].get(3) or {}))
    ok, n = numfmt.verify_counts(ins)
    if not n:
        return "Chưa có phát hiện nào đủ chắc để nêu từ dữ liệu này"
    return f"{ok}/{n} phát hiện đã kiểm được số liệu" if ok == n else f"⚠ Chỉ {ok}/{n} phát hiện đã kiểm được số liệu; phần còn lại cần bạn tự đối chiếu"


def run(fb=""):
    tick(0)
    a = A["d"]
    ap = A.get("applied", [])
    put(6, {"checks": ["Câu hỏi và bối cảnh", f"Cách làm sạch dữ liệu ({len(ap)} thao tác)",
                       f"Phân tích và dự báo ({len(a[3]['tasks'])} phân tích)", _insight_line(a[4]["insights"]),
                       f"Bảng điều khiển ({len(a[5]['final']['charts'])} biểu đồ), báo cáo, slide"]})
