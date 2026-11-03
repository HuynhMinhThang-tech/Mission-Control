# -*- coding: utf-8 -*-
from .. import numfmt
from .common import PRI_ORDER, chart_rows, facts


def build_md(F):
    L = [f"# {F['title']}", f"*{F['date']}*", "", f"**Câu hỏi:** {F['question']}", f"**Bối cảnh:** {F['ctx'] or '—'}", "",
         "## Câu trả lời ngắn", F["summary"], "", F["narrative"], ""]
    if F["kpis"]:
        L += ["## Chỉ số chính", "", "| Chỉ số | Giá trị | Ghi chú |", "|---|---|---|"]
        L += [f"| {k['label']} | {k['value']} | {k.get('delta', '')} |" for k in F["kpis"]] + [""]
    L += ["## Bằng chứng từ dữ liệu"]
    for c in F["charts"]:
        rows = chart_rows(F["dfs"][c["task"]], c["x"], c["y"])
        L += ["", f"### {c.get('insight') or c['title']}", f"*{c['title']}* — nguồn: {F['table_titles'][c['task']]}"]
        L += [f"- {x}" for x in facts(rows, c["kind"])]
    L += ["", "## Phát hiện chính"]
    ok, n = numfmt.verify_counts(F["insights"])
    if n:
        L += ["", f"*{ok}/{n} phát hiện đã được đối chiếu số liệu với bảng kết quả; phát hiện chưa kiểm được có ghi chú riêng.*", ""]
    else:
        L += ["", "*Chưa có phát hiện nào đủ chắc để nêu từ dữ liệu này.*"]
    for i, x in enumerate(F["insights"]):
        vl, note = numfmt.verify_label(x), numfmt.verify_note(x)
        L.append(f"{i + 1}. **{x['title']}** (độ tin cậy: {x.get('confidence', '')}{'; ' + vl[1].lower() if vl else ''}) — bằng chứng: {x.get('evidence', '')}" + (f" ⚠ {note}" if note else ""))
    if F["actions"]:
        L += ["", "## Khuyến nghị hành động", "", "| Ưu tiên | Hành động | Tác động |", "|---|---|---|"]
        L += [f"| {a.get('priority', '')} | {a['text']} | {a.get('impact', '')} |" for a in sorted(F["actions"], key=lambda a: PRI_ORDER.get(a.get("priority"), 9))]
    if F["risks"]:
        L += ["", "## Rủi ro"] + [f"- {r}" for r in F["risks"]]
    L += ["", "## Phương pháp", F["method"]]
    return "\n".join(L)
