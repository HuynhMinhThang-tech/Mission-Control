# -*- coding: utf-8 -*-
"""AGENT 4 · Insight và tư vấn kinh doanh (bước 5)."""
from ..state import A, put, tick
from ..llm import llm_json
from ..utils import J
from .base import SYS, ctx_txt

ROLE = "Agent Insight và tư vấn kinh doanh"

PROMPT = (
    'Trả về DUY NHẤT JSON: {"summary":"tóm tắt điều hành 2-3 câu, câu đầu TRẢ LỜI THẲNG câu hỏi kinh doanh",'
    '"insights":[{"title":"câu khẳng định đầy đủ, có số","confidence":"Cao|Trung bình|Thấp","evidence":"phép tính cụ thể bằng số có trong bảng","source":"bảng/biểu đồ nguồn"}],'
    '"actions":[{"text":"hành động cụ thể, bắt đầu bằng động từ","priority":"Cao|Trung bình|Thấp","impact":"tác động kỳ vọng, nêu theo số liệu nếu có"}],"risks":["..."]}\n'
    "3-5 insight; mỗi insight PHẢI có bằng chứng truy ngược được về bảng kết quả.")


def run(fb=""):
    tick(0)
    r3 = A["d"][3]["result"]
    txt = "\n\n".join(f"### [{i}] {t['title']}\n{A['x'][3][i].head(30).to_csv(index=False)}"
                      for i, t in enumerate(r3["tables"]) if A["x"][3][i] is not None)
    tick(1)
    r = llm_json(SYS(ROLE), ctx_txt(fb) + f"Kết quả phân tích:\n{txt[:12000]}\nPhát hiện sơ bộ: {J(r3['findings'], 3000)}\n\n" + PROMPT)
    put(4, {"summary": r.get("summary", ""), "insights": r.get("insights", []), "actions": r.get("actions", []), "risks": r.get("risks", [])})
