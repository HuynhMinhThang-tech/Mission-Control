# -*- coding: utf-8 -*-
"""AGENT 5 · Thiết kế dashboard và báo cáo (bước 6)."""
from .. import numfmt
from ..llm import llm_json
from ..state import A, put, tick
from ..utils import J
from .base import SYS, ctx_txt, prev
from ..data.scope import data_card
from ..export import dash_plan
from ..export.common import refine_charts
from .charts import valid_charts

ROLE = "Agent Thiết kế bảng điều khiển và báo cáo"

DASH_RULE = (" Mục \"dash\": chọn 5-8 biểu đồ cho BẢNG ĐIỀU KHIỂN TƯƠNG TÁC, CHỈ dùng các bảng, chiều, chỉ số trong DANH MỤC DASHBOARD (ghi đúng nhãn). "
             "Cột/đường theo thời gian: by=Thời gian, kind=trend. Cơ cấu: kind=donut (chiều <=7 nhóm, agg=sum). Trung bình/tỷ lệ: agg=avg, KHÔNG dùng donut. Không trùng nhau, ưu tiên những biểu đồ trả lời câu hỏi. "
             "Chỉ số có nhãn bắt đầu bằng \"Tỷ lệ\" là tỷ lệ đạt/không đạt (agg=avg): dùng kind=score (bảng điểm theo từng tiêu chí, \"measures\" để trống = tất cả) hoặc kind=heat (ma trận chiều x tiêu chí, có \"by\" là NHÃN chiều) thay vì cột/tròn. "
             "Mục \"bp\" thiết kế TRANG: \"layout\" (auto|overview|rank|compliance|story: compliance cho dữ liệu đạt/không đạt; overview khi có chuỗi thời gian; rank khi câu hỏi là xếp hạng/so sánh nhóm; story khi cần nêu kết luận trước; auto nếu không chắc), "
             "\"kpis\" 3-5 thẻ HỢP VỚI DỮ LIỆU (kind: sum|avg|rate|rate_all|rate_low|distinct|latest|top|missing|count; measure/by theo NHÃN trong danh mục). KHÔNG mặc định dùng kind=count (số bản ghi): chỉ dùng khi chính câu hỏi là đếm. "
             "\"table\": true chỉ khi người xem cần tra từng nhóm với từ 2 chỉ số số trở lên.")

PROMPT = (
    'ĐỀ XUẤT 6-10 biểu đồ ứng viên để NGƯỜI DÙNG CHỌN. Trả về DUY NHẤT JSON: {"title":"tiêu đề báo cáo (nêu kết luận chính)","narrative":"2-3 đoạn tóm tắt báo cáo",'
    '"charts":[{"task":<chỉ số bảng>,"x":"cột nhãn","y":"cột số","kind":"bars|cols|line|donut","title":"tên biểu đồ",'
    '"unit":"đơn vị","insight":"1 câu KẾT LUẬN rút ra từ biểu đồ này, có số (dùng làm tiêu đề slide)","recommended":true}],'
    '"dash":[{"ds":"tên bảng","by":"NHÃN chiều phân tích hoặc Thời gian","measure":"NHÃN chỉ số hoặc Số bản ghi","agg":"sum|avg","kind":"bars|cols|donut|trend","title":"tên biểu đồ","why":"một câu: biểu đồ này trả lời điều gì"}],'
    '"bp":{"layout":"auto|overview|rank|compliance|story","kpis":[{"ds":"tên bảng","kind":"...","measure":"NHÃN chỉ số","by":"NHÃN chiều","label":"tên thẻ KPI"}],"table":false}}\n'
    "x,y phải là tên cột có thật. ĐA DẠNG loại biểu đồ và KHÔNG đề xuất 2 biểu đồ trùng bảng + cột: 'line' chuỗi thời gian (nhấn xu hướng); 'area' chuỗi thời gian khi muốn nhấn quy mô tích lũy; 'bars' xếp hạng/so sánh nhiều nhóm; 'cols' so sánh ít nhóm; 'lollipop' xếp hạng gọn khi có nhiều nhóm; 'pareto' khi cần chỉ ra ít nhóm nào tạo phần lớn tổng (80/20, giá trị không âm, từ 4 nhóm); 'donut' hoặc 'pie' cơ cấu tỷ trọng (<=7 phần, không âm); 'treemap' cơ cấu của nhiều nhóm (8-24 phần, không âm). Chọn dạng hợp với câu hỏi, đừng dùng mãi cột.")


def run(fb=""):
    tick(0)
    r3 = A["d"][3]["result"]
    tabs = r3["tables"]
    cols = {i: {"title": t["title"], "cols": t["cols"], "sample": t["rows"][:3]} for i, t in enumerate(tabs) if t["cols"]}
    cat = dash_plan.catalog(A["clean"])                      # danh mục biểu đồ KHẢ DỤNG của bảng điều khiển (chiều, chỉ số thật của dữ liệu)
    cat_txt = J([{"ds": c["name"], "dims": [f"{d['label']} ({d['n']} nhóm)" for d in c["dims"]], "thoi_gian": bool(c["time"]),
                  "chi_so": [m["label"] + (" (tỷ lệ %)" if m.get("rate") else " (trung bình)" if m["avg"] else "") for m in c["meas"]] + ["Số bản ghi"]} for c in cat], 3000)
    r = llm_json(SYS(ROLE), ctx_txt(fb) + prev(5, fb) + f"Bảng kết quả: {J(cols, 5000)}\nPhát hiện: {J(A['d'][4], 4000)}\nDANH MỤC DASHBOARD: {cat_txt}\n\n" + data_card(A["clean"]) + PROMPT + DASH_RULE)
    charts = valid_charts(r.get("charts", []), tabs) or valid_charts(r3["charts"], tabs)
    tick(1)
    known = numfmt.Known.from_dfs(A["x"][3], A.get("names"))
    r = numfmt.fix_payload(r, known)
    charts = refine_charts(numfmt.fix_payload(charts, known), A["x"][3])        # tiêu đề biểu đồ không khớp số liệu -> thay bằng câu tính từ dữ liệu
    ai = dash_plan.suggest(r.get("dash"), cat)                # gợi ý của AI (đã loại cột bịa) + bổ sung bằng luật nếu quá ít
    put(5, {"title": r.get("title") or "Báo cáo phân tích", "narrative": r.get("narrative", A["d"][4]["summary"]), "charts": charts,
            "dash": {"catalog": cat, "ai": ai, "bp": dash_plan.bp_from_ai(r.get("bp"), cat)}})