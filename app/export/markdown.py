# -*- coding: utf-8 -*-
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
    L += ["", "## Insight chính"]
    L += [f"{i + 1}. **{x['title']}** (độ tin cậy: {x.get('confidence', '')}) — bằng chứng: {x.get('evidence', '')}" for i, x in enumerate(F["insights"])]
    L += ["", "## Khuyến nghị hành động", "", "| Ưu tiên | Hành động | Tác động |", "|---|---|---|"]
    L += [f"| {a.get('priority', '')} | {a['text']} | {a.get('impact', '')} |" for a in sorted(F["actions"], key=lambda a: PRI_ORDER.get(a.get("priority"), 9))]
    if F["risks"]:
        L += ["", "## Rủi ro"] + [f"- {r}" for r in F["risks"]]
    L += ["", "## Phương pháp", F["method"]]
    return "\n".join(L)
