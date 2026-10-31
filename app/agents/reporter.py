# -*- coding: utf-8 -*-
"""AGENT 5 · Thiết kế dashboard và báo cáo (bước 6)."""
from .. import numfmt
from ..llm import llm_json
from ..state import A, put, tick
from ..utils import J
from .base import SYS, ctx_txt, prev
from ..export import dash_plan
from ..export.common import refine_charts
from .charts import valid_charts

ROLE = "Agent Thiết kế bảng điều khiển và báo cáo"

DASH_RULE = (" Mục \"dash\": chọn 5-8 biểu đồ cho BẢNG ĐIỀU KHIỂN TƯƠNG TÁC, CHỈ dùng các bảng, chiều, chỉ số trong DANH MỤC DASHBOARD (ghi đúng nhãn). "
             "Cột/đường theo thời gian: by=Thời gian, kind=trend. Cơ cấu: kind=donut (chiều <=7 nhóm, agg=sum). Trung bình/tỷ lệ: agg=avg, KHÔNG dùng donut. Không trùng nhau, ưu tiên những biểu đồ trả lời câu hỏi kinh doanh.")

PROMPT = (
    'ĐỀ XUẤT 6-10 biểu đồ ứng viên để NGƯỜI DÙNG CHỌN. Trả về DUY NHẤT JSON: {"title":"tiêu đề báo cáo (nêu kết luận chính)","narrative":"2-3 đoạn tóm tắt báo cáo",'
    '"charts":[{"task":<chỉ số bảng>,"x":"cột nhãn","y":"cột số","kind":"bars|cols|line|donut","title":"tên biểu đồ",'
    '"unit":"đơn vị","insight":"1 câu KẾT LUẬN rút ra từ biểu đồ này, có số (dùng làm tiêu đề slide)","recommended":true}],'
    '"dash":[{"ds":"tên bảng","by":"NHÃN chiều phân tích hoặc Thời gian","measure":"NHÃN chỉ số hoặc Số bản ghi","agg":"sum|avg","kind":"bars|cols|donut|trend","title":"tên biểu đồ","why":"một câu: biểu đồ này trả lời điều gì"}]}\n'
    "x,y phải là tên cột có thật. ĐA DẠNG loại biểu đồ và KHÔNG đề xuất 2 biểu đồ trùng bảng + cột: 'line' cho chuỗi thời gian; 'bars' xếp hạng/so sánh; 'cols' so sánh ít nhóm; 'donut' cơ cấu tỷ trọng (<=7 phần, không âm).")


def run(fb=""):
    tick(0)
    r3 = A["d"][3]["result"]
    tabs = r3["tables"]
    cols = {i: {"title": t["title"], "cols": t["cols"], "sample": t["rows"][:3]} for i, t in enumerate(tabs) if t["cols"]}
    cat = dash_plan.catalog(A["clean"])                      # danh mục biểu đồ KHẢ DỤNG của bảng điều khiển (chiều, chỉ số thật của dữ liệu)
    cat_txt = J([{"ds": c["name"], "dims": [f"{d['label']} ({d['n']} nhóm)" for d in c["dims"]], "thoi_gian": bool(c["time"]),
                  "chi_so": [m["label"] + (" (trung bình)" if m["avg"] else "") for m in c["meas"]] + ["Số bản ghi"]} for c in cat], 3000)
    r = llm_json(SYS(ROLE), ctx_txt(fb) + prev(5, fb) + f"Bảng kết quả: {J(cols, 5000)}\nPhát hiện: {J(A['d'][4], 4000)}\nDANH MỤC DASHBOARD: {cat_txt}\n\n" + PROMPT + DASH_RULE)
    charts = valid_charts(r.get("charts", []), tabs) or valid_charts(r3["charts"], tabs)
    tick(1)
    known = numfmt.Known.from_dfs(A["x"][3])
    r = numfmt.fix_payload(r, known)
    charts = refine_charts(numfmt.fix_payload(charts, known), A["x"][3])        # tiêu đề biểu đồ không khớp số liệu -> thay bằng câu tính từ dữ liệu
    ai = dash_plan.suggest(r.get("dash"), cat)                # gợi ý của AI (đã loại cột bịa) + bổ sung bằng luật nếu quá ít
    put(5, {"title": r.get("title") or "Báo cáo phân tích", "narrative": r.get("narrative", A["d"][4]["summary"]), "charts": charts,
            "dash": {"catalog": cat, "ai": ai}})