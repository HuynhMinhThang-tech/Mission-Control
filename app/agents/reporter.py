# -*- coding: utf-8 -*-
"""AGENT 5 · Thiết kế dashboard và báo cáo (bước 6)."""
from ..llm import llm_json
from ..state import A, put, tick
from ..utils import J
from .base import SYS, ctx_txt
from .charts import valid_charts

ROLE = "Agent Thiết kế dashboard và báo cáo"

PROMPT = (
    'ĐỀ XUẤT 6-10 biểu đồ ứng viên để NGƯỜI DÙNG CHỌN. Trả về DUY NHẤT JSON: {"title":"tiêu đề báo cáo (nêu kết luận chính)","narrative":"2-3 đoạn tóm tắt báo cáo",'
    '"charts":[{"task":<chỉ số bảng>,"x":"cột nhãn","y":"cột số","kind":"bars|cols|line|donut","title":"tên biểu đồ",'
    '"unit":"đơn vị","insight":"1 câu KẾT LUẬN rút ra từ biểu đồ này, có số (dùng làm tiêu đề slide)","recommended":true}]}\n'
    "x,y phải là tên cột có thật. ĐA DẠNG loại biểu đồ và KHÔNG đề xuất 2 biểu đồ trùng bảng + cột: 'line' cho chuỗi thời gian; 'bars' xếp hạng/so sánh; 'cols' so sánh ít nhóm; 'donut' cơ cấu tỷ trọng (<=7 phần, không âm).")


def run(fb=""):
    tick(0)
    r3 = A["d"][3]["result"]
    tabs = r3["tables"]
    cols = {i: {"title": t["title"], "cols": t["cols"], "sample": t["rows"][:3]} for i, t in enumerate(tabs) if t["cols"]}
    r = llm_json(SYS(ROLE), ctx_txt(fb) + f"Bảng kết quả: {J(cols, 5000)}\nInsight: {J(A['d'][4], 4000)}\n\n" + PROMPT)
    charts = valid_charts(r.get("charts", []), tabs) or valid_charts(r3["charts"], tabs)
    tick(1)
    put(5, {"title": r.get("title") or "Báo cáo phân tích", "narrative": r.get("narrative", A["d"][4]["summary"]), "charts": charts})