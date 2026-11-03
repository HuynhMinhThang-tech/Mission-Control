# -*- coding: utf-8 -*-
"""AGENT 4 · Insight và tư vấn kinh doanh (bước 5)."""
from .. import numfmt
from ..data.scope import data_card, scope_block
from .playbook import INSIGHT_RULES
from ..state import A, put, tick
from ..llm import llm_json
from ..utils import J
from .base import SYS, ctx_txt, prev

ROLE = "Agent Phát hiện và tư vấn kinh doanh"

PROMPT = (
    'Trả về DUY NHẤT JSON: {"summary":"tóm tắt điều hành 2-3 câu, câu đầu TRẢ LỜI THẲNG câu hỏi kinh doanh",'
    '"insights":[{"title":"câu khẳng định đầy đủ, có số","confidence":"Cao|Trung bình|Thấp",'
    '"evidence":"CHỈ chép các ô nguồn dạng [bảng, hàng, cột] = giá trị (bảng = tiêu đề bảng; hàng = giá trị nhóm ở cột đầu; cột = tên cột; chép ĐÚNG như trong bảng), ngăn cách bằng dấu chấm phẩy; KHÔNG viết phép tính","source":"bảng/biểu đồ nguồn"}],'
    '"actions":[{"text":"hành động cụ thể, bắt đầu bằng động từ","priority":"Cao|Trung bình|Thấp","impact":"tác động theo số có sẵn trong bảng, hoặc chưa ước tính được"}],"risks":["..."]}\n'
    "Tối đa 5 phát hiện, ÍT HƠN nếu dữ liệu không đủ (được phép 0); mỗi phát hiện phải truy ngược được về ô trong bảng kết quả. "
    "Hành động chỉ đưa khi gắn với một phát hiện đã nêu; được phép bỏ trống. "
    "Chỉ khẳng định điều suy ra được từ các cột và bảng được cung cấp. Yếu tố nào không có trong dữ liệu (vd nguyên nhân, chi phí, thiết bị) "
    "chỉ được nêu như giả thuyết cần kiểm chứng, kèm dữ liệu cần thu thêm (đưa vào risks)." + INSIGHT_RULES)


def run(fb=""):
    tick(0)
    r3 = A["d"][3]["result"]
    txt = "\n\n".join(f"### [{i}] {t['title']}\n{A['x'][3][i].head(30).to_csv(index=False)}"
                      for i, t in enumerate(r3["tables"]) if A["x"][3][i] is not None)
    tick(1)
    r = llm_json(SYS(ROLE), ctx_txt(fb) + prev(4, fb) + f"Kết quả phân tích:\n{txt[:12000]}\nPhát hiện sơ bộ: {J(r3['findings'], 3000)}\n\n" + data_card(A["clean"]) + scope_block(A["clean"]) + PROMPT)
    known = numfmt.Known.from_dfs(A["x"][3])
    r = numfmt.fix_payload(r, known)
    ins = numfmt.audit_insights(r.get("insights", []), known)                     # số lớn không có trong bảng nào -> không để "Độ tin cậy: Cao"
    put(4, {"summary": r.get("summary", ""), "insights": ins, "actions": r.get("actions", []), "risks": r.get("risks", [])})
