# -*- coding: utf-8 -*-
"""AGENT 6 · Rà soát cuối trước khi người dùng duyệt (bước 7)."""
from .. import numfmt
from ..state import A, put, tick
from . import memo


def _insight_line(ins):
    """Chỉ nói số phát hiện ĐÃ KIỂM ĐƯỢC trên tổng số; dòng bắt đầu bằng ⚠ khi còn phát hiện chưa kiểm được (giao diện không thêm dấu ✓ cho dòng này)."""
    ins = numfmt.audit_insights(ins, numfmt.Known.from_dfs(A["x"].get(3) or {}))
    ok, n = numfmt.verify_counts(ins)
    if not n:
        return "Chưa có phát hiện nào đủ chắc để nêu từ dữ liệu này"
    return f"{ok}/{n} phát hiện đã kiểm được số liệu" if ok == n else f"⚠ Chỉ {ok}/{n} phát hiện đã kiểm được số liệu; phần còn lại cần bạn tự đối chiếu"


def _memo_line():
    n = memo.approved_count()
    ed = sum(1 for k, m in (A.get("memo") or {}).items() if isinstance(k, int) and 1 <= k <= 5 and m.get("edited"))
    base = f"Bản tổng hợp từng bước đã duyệt ({n}/5)" + (f", trong đó {ed} bản do bạn chỉnh sửa" if ed else "")
    return base if n == 5 else "⚠ " + base


def run(fb=""):
    tick(0)
    a = A["d"]
    ap = A.get("applied", [])
    put(6, {"checks": ["Câu hỏi và bối cảnh", f"Cách làm sạch dữ liệu ({len(ap)} thao tác)",
                       f"Phân tích và dự báo ({len(a[3]['tasks'])} phân tích)", _insight_line(a[4]["insights"]),
                       f"Bảng điều khiển ({len(a[5]['final']['charts'])} biểu đồ), báo cáo, slide", _memo_line()]})
