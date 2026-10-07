# -*- coding: utf-8 -*-
"""AGENT 1 · Thống kê và kiểm tra chất lượng dữ liệu (bước 2)."""
import json

from ..data.quality import date_range, join_info, profile_rows, quality, schema
from ..llm import llm_json
from ..state import A, put, tick
from ..utils import J, vn
from .base import SYS, ctx_txt, prev

ROLE = "Agent Thống kê và kiểm tra chất lượng dữ liệu"

PROMPT = (
    'Trả về DUY NHẤT JSON {"findings":[{"tag":"Chất lượng|Cấu trúc|Phù hợp|Ghép tệp|Mô tả|Lưu ý","text":"1-2 câu, có số liệu"}]} gồm 4-6 nhận định: '
    "chất lượng (kèm điểm 0-100), cấu trúc tệp (dựa vào kết quả kiểm tra cấu trúc bên dưới), PHÙ HỢP (dữ liệu này có đủ cột/kỳ/đơn vị để trả lời câu hỏi kinh doanh không; "
    "nếu thiếu thì nói rõ thiếu gì và câu hỏi nào chỉ trả lời được một phần), ghép tệp, cột/tệp liên quan nhất, hạn chế dữ liệu. "
    "Nếu dữ liệu không thể trả lời câu hỏi, hãy nói thẳng điều đó, không cố bịa ra phân tích.")


def run(fb=""):
    dfs = A["raw"]
    tick(0)
    main = max(dfs, key=lambda n: len(dfs[n]))
    m = dfs[main]
    desc = {n: d.describe().round(2).to_dict() for n, d in dfs.items() if d.select_dtypes("number").shape[1]}
    tick(1)
    q = quality(dfs)
    ji = join_info(dfs)
    dr = date_range(dfs)
    kp = [{"label": "Số dòng", "value": vn(len(m), 0), "delta": main}, {"label": "Số cột", "value": str(m.shape[1]), "delta": ""}]
    if dr:
        kp.append({"label": "Khoảng ngày", "value": dr, "delta": ""})
    if ji:
        kp.append({"label": "Khóa ghép", "value": ji[2], "delta": f"khớp {vn(ji[3], 1)}%"})
    tick(2)
    jtxt = f"{ji[0]} ↔ {ji[1]} theo {ji[2]}, khớp {vn(ji[3], 1)}%" if ji else "không phát hiện khóa ghép"
    st = {n: m for n, m in A.get("struct", {}).items() if m["verdict"] != "tidy"}
    stxt = "\n".join(f"- {n}: {m['verdict']} (điểm cấu trúc gốc {m['score']}/100); vấn đề: {'; '.join(m['issues'][:4])}; đã xử lý: {'; '.join(m['actions'][:4]) or 'chưa'}" for n, m in st.items()) or "tất cả tệp đều có cấu trúc bảng chuẩn"
    f = llm_json(SYS(ROLE),
                 ctx_txt(fb) + prev(1, fb) + f"Kết quả kiểm tra cấu trúc tệp:\n{stxt}\n" + f"Schema:\n{J(schema(dfs, 2), 4000)}\nThống kê số:\n{J(desc, 3000)}\n"
                 f"Vấn đề phát hiện:\n{q.to_csv(index=False)[:4000]}\nKhóa ghép: {jtxt}\n\n" + PROMPT)["findings"]
    sample = {"cols": [str(c) for c in m.columns[:7]], "rows": json.loads(m.iloc[:5, :7].to_json(orient="values", date_format="iso"))}
    A["dirty"] = sorted(set(q["file"])) if len(q) else []
    put(1, {"structure": [dict(file=n, verdict=m["verdict"], score=m["score"], issues=m["issues"], actions=m["actions"]) for n, m in st.items()], "kpis": kp, "sample": sample, "findings": f, "profile": profile_rows(dfs), "issues": q.to_dict("records")})