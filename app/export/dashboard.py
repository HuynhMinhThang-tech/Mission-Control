# -*- coding: utf-8 -*-
"""Dashboard HTML độc lập (1 file, mở offline): dùng để XEM, TRA CỨU và TRẢ LỜI câu hỏi."""
from pathlib import Path

from ..utils import E, vn
from .common import PRI_ORDER, chart_rows, facts, trunc
from .svg import chart_svg

CSS = (Path(__file__).parent / "assets" / "dashboard.css").read_text("utf-8")


def _delta_cls(d):
    d = str(d or "").strip()
    return "up" if d.startswith("+") else "dn" if d[:1] in "-−" else ""


def _badge(conf):
    c = str(conf or "").strip()
    key = "Trung" if c.startswith("Trung") else c
    return f'<span class="badge b-{E(key)}">Độ tin cậy: {E(c)}</span>' if c else ""


def _kpis(F):
    if not F["kpis"]:
        return ""
    cards = "".join(f'<div class="kpi"><b>{E(k["value"])}</b><span>{E(k["label"])}</span>'
                    f'{"<em class=%s>%s</em>" % (_delta_cls(k.get("delta")), E(k["delta"])) if k.get("delta") else ""}</div>' for k in F["kpis"])
    return f'<section id="kpi"><h2>Chỉ số chính</h2><div class="kpis">{cards}</div></section>'


def _charts(F):
    out = []
    for c in F["charts"]:
        rows = chart_rows(F["dfs"][c["task"]], c["x"], c["y"])
        head = c.get("insight") or c["title"]
        sub = c["title"] + (f" · đơn vị: {c['unit']}" if c.get("unit") else "")
        fl = "".join(f"<li>{E(x)}</li>" for x in facts(rows, c["kind"]))
        out.append(f'<figure class="card"><figcaption><h3>{E(head)}</h3><p class="sub">{E(sub)}</p></figcaption>'
                   f'{chart_svg(c["kind"], rows)}<ul class="facts">{fl}</ul>'
                   f'<p class="src">Nguồn: {E(F["table_titles"][c["task"]])} · số liệu đã làm sạch</p></figure>')
    return f'<section id="charts"><h2>Bằng chứng từ dữ liệu</h2><div class="grid">{"".join(out)}</div></section>' if out else ""


def _insights(F):
    if not F["insights"]:
        return ""
    items = "".join(f'<div class="in"><div class="n">{i + 1}</div><div><h3>{E(x["title"])}{_badge(x.get("confidence"))}</h3>'
                    f'<p class="ev"><b>Bằng chứng ({E(x.get("source", ""))}):</b> {E(x.get("evidence", ""))}</p></div></div>'
                    for i, x in enumerate(F["insights"]))
    return f'<section id="insights"><h2 class="hs ins">Insight chính</h2><div class="ins">{items}</div></section>'


def _actions(F):
    if not F["actions"]:
        return ""
    acts = sorted(F["actions"], key=lambda a: PRI_ORDER.get(a.get("priority"), 9))
    rows = "".join(f'<tr><td><span class="pr p-{"Trung" if str(a.get("priority", "")).startswith("Trung") else E(a.get("priority", ""))}">{E(a.get("priority", ""))}</span></td>'
                   f'<td><b>{E(a["text"])}</b></td><td>{E(a.get("impact", ""))}</td></tr>' for a in acts)
    return (f'<section id="actions"><h2 class="hs act">Khuyến nghị hành động</h2><div class="tw act-tbl"><table><thead><tr><th>Ưu tiên</th><th>Hành động</th>'
            f'<th>Tác động kỳ vọng</th></tr></thead><tbody>{rows}</tbody></table></div></section>')


def _risks(F):
    if not F["risks"]:
        return ""
    li = "".join(f"<li>{E(r)}</li>" for r in F["risks"])
    return f'<section id="risks"><h2 class="hs risk">Rủi ro cần lưu ý</h2><div class="card riskbox"><b>Cần theo dõi khi triển khai</b><ul>{li}</ul></div></section>'


def _method(F):
    q = F.get("quality") or {}
    qb = ", ".join(f"{k}: {vn(v, 0)}" for k, v in (q.get("before") or {}).items() if v) or "không có"
    qa = ", ".join(f"{k}: {vn(v, 0)}" for k, v in (q.get("after") or {}).items() if v) or "không còn"
    files = "".join(f"<li>{E(f['name'])} · {vn(f['rows'], 0)} dòng</li>" for f in F["files"])
    cl = "".join(f"<li>{E(x)}</li>" for x in F["applied"]) or "<li>Không áp dụng thao tác nào</li>"
    an = "".join(f"<li><b>{E(t['title'])}</b> — {E(t.get('goal', ''))}</li>" for t in F["tasks"])
    tabs = "".join(f"<details><summary>{E(t['title'])}</summary><div class='tw'>{_tbl(t)}</div></details>" for t in F["tables"])
    return (f'<section id="method"><h2>Phương pháp và dữ liệu</h2><div class="two">'
            f'<div class="card"><b>Dữ liệu nguồn</b><ul>{files}</ul>{"<p>Khoảng thời gian: " + E(F["period"]) + "</p>" if F.get("period") else ""}</div>'
            f'<div class="card"><b>Làm sạch dữ liệu</b><ul>{cl}</ul><p class="ev">Vấn đề trước: {E(qb)}<br>Sau: {E(qa)}</p></div>'
            f'<div class="card"><b>Phân tích đã chạy</b><ul>{an}</ul></div></div>'
            f'<h2 style="margin-top:24px">Bảng số liệu chi tiết</h2>{tabs}</section>')


def _tbl(t):
    if not t["cols"]:
        return ""
    head = "".join(f"<th>{E(c)}</th>" for c in t["cols"])
    body = "".join("<tr>" + "".join(f"<td>{E(vn(c, 2) if isinstance(c, (int, float)) and not isinstance(c, bool) else ('' if c is None else c))}</td>" for c in r) + "</tr>"
                   for r in t["rows"][:30])
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_html(F):
    chips = "".join(f'<span class="chip">{E(x)}</span>' for x in [F.get("period"), f"{len(F['files'])} tệp dữ liệu", f"{len(F['insights'])} insight"] if x)
    narrative = "".join(f"<p>{E(p)}</p>" for p in str(F["narrative"]).split("\n") if p.strip())
    nav = "".join(f'<a href="#{a}">{t}</a>' for a, t in [("answer", "Câu trả lời"), ("kpi", "Chỉ số"), ("charts", "Biểu đồ"), ("insights", "Insight"),
                                                         ("actions", "Hành động")] + ([("risks", "Rủi ro")] if F["risks"] else []) + [("method", "Phương pháp")])
    return (f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{E(F["title"])}</title><style>{CSS}</style></head><body>'
            f'<header class="hd"><div class="wrap"><p class="eyebrow">Báo cáo phân tích · {E(F["date"])}</p><h1>{E(F["title"])}</h1>'
            f'<p class="q"><b>Câu hỏi kinh doanh:</b> {E(F["question"])}</p>'
            f'{"<p class=q style=margin-top:6px><b>Bối cảnh:</b> " + E(F["ctx"]) + "</p>" if F["ctx"] else ""}<div class="chips">{chips}</div></div></header>'
            f'<nav class="tabs"><div class="wrap">{nav}</div></nav><main class="wrap">'
            f'<section id="answer"><h2>Câu trả lời ngắn</h2><div class="card answer"><p class="big">{E(F["summary"])}</p>{narrative}</div></section>'
            f'{_kpis(F)}{_charts(F)}{_insights(F)}{_actions(F)}{_risks(F)}{_method(F)}'
            f'<footer class="ft">Tạo bởi Mission Control · {E(F["date"])} · Mọi con số được tính từ dữ liệu đã làm sạch, bằng chứng truy ngược được ở mục Phương pháp.</footer>'
            f'</main></body></html>')