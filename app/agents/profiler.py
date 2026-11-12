# -*- coding: utf-8 -*-
"""AGENT 1 · Thống kê và kiểm tra chất lượng dữ liệu (bước 2)."""
import json

from ..data import relations as R
from ..data.datecols import ROLE_LABEL, date_cols, group, pick_period, short
from ..data.describe import brief, distributions
from ..data.quality import profile_rows, quality, schema
from ..llm import llm_json
from ..state import A, put, tick
from ..utils import J, fmt_pct, vn
from .base import SYS, ctx_txt, prev

ROLE = "Agent Thống kê và kiểm tra chất lượng dữ liệu"

PROMPT = (
    'Trả về DUY NHẤT JSON {"findings":[{"tag":"Chất lượng|Cấu trúc|Phù hợp|Ghép tệp|Mô tả|Lưu ý","text":"1-2 câu, có số liệu"}]} gồm 4-6 nhận định: '
    "chất lượng (kèm điểm 0-100), cấu trúc tệp (dựa vào kết quả kiểm tra cấu trúc bên dưới), PHÙ HỢP (dữ liệu này có đủ cột/kỳ/đơn vị để trả lời câu hỏi kinh doanh không; "
    "nếu thiếu thì nói rõ thiếu gì và câu hỏi nào chỉ trả lời được một phần), ghép tệp, cột/tệp liên quan nhất, hạn chế dữ liệu. "
    "Nếu dữ liệu không thể trả lời câu hỏi, hãy nói thẳng điều đó, không cố bịa ra phân tích. "
    "Dữ liệu có thể gồm NHIỀU bảng (sheet): nhận định phải nói đúng số bảng và số dòng của TỪNG bảng, không chỉ bảng lớn nhất. "
    "Khi nói về khoảng thời gian của dữ liệu, CHỈ dùng cột ngày được ghi là «ngày phát sinh» (ngày đặt hàng, giao dịch...). "
    "Ngày sinh và ngày đăng ký là thuộc tính của khách hàng, KHÔNG phải kỳ của dữ liệu, tuyệt đối không dùng chúng làm khoảng thời gian.")


TAGS = ("Chất lượng", "Cấu trúc", "Phù hợp", "Ghép tệp", "Mô tả", "Lưu ý")


def clean_tag(tag, text=""):
    """AI đôi khi chép nguyên khuôn «Chất lượng|Cấu trúc|…» vào nhãn. Chỉ nhận một nhãn hợp lệ: đúng nhãn thì giữ, không thì đoán theo chữ đầu câu, không đoán được thì «Lưu ý»."""
    tag = " ".join(str(tag or "").split())
    if tag in TAGS:
        return tag
    head = str(text or "").strip().casefold()
    for t in TAGS:
        if head.startswith(t.casefold()):
            return t
    return "Lưu ý"


def clean_findings(f):
    out = []
    for x in f or []:
        if isinstance(x, dict) and str(x.get("text") or "").strip():
            out.append({**x, "tag": clean_tag(x.get("tag"), x.get("text"))})
    return out


def overview(dfs, rels, dates):
    """KPI quy mô theo TẤT CẢ các bảng (không chỉ bảng lớn nhất) và kỳ dữ liệu lấy từ ngày PHÁT SINH."""
    names = list(dfs)
    rows, cols = [len(dfs[n]) for n in names], [dfs[n].shape[1] for n in names]
    lst = lambda v: " · ".join(vn(x, 0) for x in v[:6]) + (" …" if len(v) > 6 else "")                 # noqa: E731
    if len(names) > 1:
        kp = [{"label": "Số bảng", "value": str(len(names)), "delta": f"{len({group(n) for n in names})} tệp"},
              {"label": "Tổng số dòng", "value": vn(sum(rows), 0), "delta": "từng bảng: " + lst(rows)},
              {"label": "Tổng số cột", "value": str(sum(cols)), "delta": "từng bảng: " + lst(cols)}]
    else:
        kp = [{"label": "Số dòng", "value": vn(rows[0], 0), "delta": names[0]}, {"label": "Số cột", "value": str(cols[0]), "delta": ""}]
    per = pick_period(dates)
    if per:
        note = "" if per["role"] == "event" else " · tên cột chưa rõ nghĩa"
        kp.append({"label": "Kỳ dữ liệu", "key": "period", "value": f"{per['min']} → {per['max']}", "delta": f"{per['label']} · {per['table']}{note}"})
    elif dates:
        kp.append({"label": "Kỳ dữ liệu", "key": "period", "value": "Chưa xác định", "delta": "chỉ có " + ", ".join(sorted({ROLE_LABEL[x['role']].lower() for x in dates})) + " (thuộc tính, không phải thời gian dữ liệu)"})
    if rels:
        kp.append({"label": "Khóa ghép", "value": " · ".join(dict.fromkeys(r["key"] for r in rels[:3])),
                   "delta": f"{len(rels)} liên kết, khớp thấp nhất {fmt_pct(min(r['match'] for r in rels))}" if len(rels) > 1 else f"khớp {fmt_pct(rels[0]['match'])}"})
    return kp, per


def run(fb=""):
    dfs = A["raw"]
    tick(0)
    desc = {n: d.describe().round(2).to_dict() for n, d in dfs.items() if d.select_dtypes("number").shape[1]}
    tick(1)
    q = quality(dfs, with_fix=True)               # có cột `fix`: phương án đề xuất xử lý của từng vấn đề (hiện ở bảng «Danh sách vấn đề phát hiện»)
    rels = R.relations(dfs)
    dates = date_cols(dfs, R.dim_tables(rels))
    kp, per = overview(dfs, rels, dates)
    tables = [{"file": n, "group": group(n), "table": short(n), "rows": int(len(d)), "cols": int(d.shape[1]), "dates": sum(1 for x in dates if x["file"] == n)} for n, d in dfs.items()]
    dist = distributions(dfs)                       # phân bố từng biến (histogram / giá trị duy nhất / theo thời gian): code tính, không nhờ AI
    tick(2)
    jtxt = "; ".join(f"{short(r['many'])} → {short(r['one'])} theo {r['key']}, khớp {fmt_pct(r['match'])}" for r in rels) or "không phát hiện khóa ghép"
    ttxt = "\n".join(f"- {t['table']} ({t['group']}): {vn(t['rows'], 0)} dòng × {t['cols']} cột" for t in tables)
    dtxt = "\n".join(f"- {x['label']} ({x['table']}): {x['min']} → {x['max']}; ý nghĩa: {x['role_label'].lower()}" + (" (là kỳ của dữ liệu)" if per and x['file'] == per['file'] and x['col'] == per['col'] else "") for x in dates) or "không có cột ngày"
    st = {n: m for n, m in A.get("struct", {}).items() if m["verdict"] != "tidy"}
    stxt = "\n".join(f"- {n}: {m['verdict']} (điểm cấu trúc gốc {m['score']}/100); vấn đề: {'; '.join(m['issues'][:4])}; đã xử lý: {'; '.join(m['actions'][:4]) or 'chưa'}" for n, m in st.items()) or "tất cả tệp đều có cấu trúc bảng chuẩn"
    f = llm_json(SYS(ROLE),
                 ctx_txt(fb) + prev(1, fb) + f"Kết quả kiểm tra cấu trúc tệp:\n{stxt}\n" + f"Schema:\n{J(schema(dfs, 2), 4000)}\nThống kê số:\n{J(desc, 3000)}\n"
                 f"Phân bố từng biến (máy tính toán):\n{brief(dist)}\n"
                 f"Các bảng ({len(tables)}):\n{ttxt}\nCác cột ngày:\n{dtxt}\n"
                 f"Vấn đề phát hiện:\n{q.drop(columns=['fix']).to_csv(index=False)[:4000]}\nQuan hệ giữa các bảng: {jtxt}\n\n" + PROMPT)["findings"]
    f = clean_findings(f)
    samples = [{"file": n, "cols": [str(c) for c in d.columns[:7]], "rows": json.loads(d.iloc[:5, :7].to_json(orient="values", date_format="iso"))} for n, d in dfs.items()]
    A["dirty"] = sorted(set(q["file"])) if len(q) else []
    put(1, {"structure": [dict(file=n, verdict=m["verdict"], score=m["score"], issues=m["issues"], actions=m["actions"]) for n, m in st.items()], "kpis": kp, "sample": samples[0], "samples": samples,
            "tables": tables, "relations": rels, "dates": dates, "period": per, "findings": f, "profile": profile_rows(dfs), "issues": q.to_dict("records"), "dist": dist})