# -*- coding: utf-8 -*-
"""BẢN TỔNG HỢP SAU MỖI BƯỚC (markdown) · cổng duyệt giữa hai Agent.

Sau khi bạn chấp nhận bước i, hệ thống viết một bản tổng hợp markdown về những gì đã xảy ra ở bước đó và dừng lại.
Bạn đọc, sửa tay hoặc nhờ AI viết lại, rồi duyệt; chỉ khi đó Agent của bước kế tiếp mới chạy. Các bản đã duyệt được nối vào ngữ cảnh
(`base.ctx_txt`) của mọi Agent phía sau, nên bước sau nối tiếp đúng những gì bạn đã quyết ở bước trước.

Thiết kế an toàn số liệu:
  * Phần "ghi nhận của hệ thống" do CODE ghép từ dữ liệu thật (không nhờ AI): lựa chọn của bạn, số dòng, bảng, phát hiện.
  * AI chỉ viết "Lưu ý cho bước sau" (vài gạch đầu dòng) và bị chặn nếu dùng số không có trong phần ghi nhận.
  * Bản bạn sửa tay / AI viết lại được rà số: số lạ so với phần ghi nhận hiện cảnh báo (không chặn).
  * Số liệu trích dẫn trong kết quả vẫn do `numfmt` đối chiếu với bảng; bản tổng hợp chỉ là NGỮ CẢNH."""
import re

from .. import numfmt
from ..constants import STEP_T
from ..utils import fmt_pct
from ..data.cleaning import OPL
from ..llm import llm_json
from ..state import A, LOCK, bump, log, next_gen, now_iso, start_bg
from .base import SYS

ROLE = "Agent Viết bản tổng hợp"
LABEL = "Viết bản tổng hợp để bạn duyệt"
NEXT_NAME = {1: "Làm sạch dữ liệu", 2: "Phân tích", 3: "Phát hiện và hành động", 4: "Báo cáo và bảng điều khiển", 5: "Rà soát cuối trước khi duyệt"}
MAX_MD = 20000            # giới hạn độ dài khi bạn sửa tay
PER_MEMO = 4000           # số ký tự tối đa của MỘT bản khi đưa vào prompt các Agent
CHAIN_BUDGET = 9000       # tổng số ký tự các bản đã duyệt đưa vào prompt (quá thì cắt bản cũ trước)
SEC = "## Lưu ý cho bước sau"
SEP = "\u0001"


def _n(x):
    try:
        return f"{int(round(float(x))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(x)


def _short(name):
    s = str(name)
    return s.split("::", 1)[1] if "::" in s else re.sub(r"\.[A-Za-z0-9]{1,5}$", "", s)


def _cut(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _lines(title, items):
    return ["", title] + items if items else []


# ------------------------------------------------------------------ phần ghi nhận của hệ thống (code ghép) --
def facts_0():
    b = A.get("brief") or {}
    L = ["## Câu hỏi", A.get("question") or "—", "", "## Bối cảnh", b.get("ctx") or "—"]
    if b.get("decision"):
        L += ["", "## Quyết định cần đưa ra", b["decision"]]
    if b.get("levers"):
        L += ["", "## Những gì có thể thay đổi", b["levers"]]
    L += ["", "## Dữ liệu"] + [f"- {f['name']}: {_n(f['rows'])} dòng" + (" (dữ liệu mẫu)" if f.get("demo") else "") for f in A.get("files") or []]
    st = [(n, m) for n, m in (A.get("struct") or {}).items() if m.get("verdict") not in (None, "tidy")]
    L += _lines("## Cấu trúc tệp cần lưu ý", [f"- {n}: {m['verdict']}" + (f" — {_cut('; '.join(m.get('issues') or []), 160)}" if m.get("issues") else "") for n, m in st])
    return "\n".join(L)


def facts_1():
    d = A["d"][1]
    L = ["## Quy mô dữ liệu"] + [f"- {k['label']}: {k['value']}" + (f" ({k['delta']})" if k.get("delta") else "") for k in d.get("kpis") or []]
    tb = d.get("tables") or []
    L += _lines(f"## Các bảng dữ liệu ({len(tb)})", [f"- {t['table']} ({t['group']}): {_n(t['rows'])} dòng × {_n(t['cols'])} cột" for t in tb]) if len(tb) > 1 else []
    rl = d.get("relations") or []
    L += _lines("## Liên kết giữa các bảng", [f"- {_short(r['many'])} → {_short(r['one'])} theo cột {r['key']} (khớp {fmt_pct(r['match'])})" for r in rl])
    per = d.get("period") or {}
    dt = d.get("dates") or []
    L += _lines("## Các cột ngày", [f"- {x['label']} ({x['table']}): {x['min']} → {x['max']} · {x['role_label'].lower()}"
                                   + (" · dùng làm kỳ của dữ liệu" if per and x["file"] == per.get("file") and x["col"] == per.get("col") else " · thuộc tính, không phải kỳ của dữ liệu" if x["role"] in ("birth", "signup") else "")
                                   for x in dt])
    L += _lines("## Cấu trúc tệp", [f"- {x['file']}: {x['verdict']} — {_cut('; '.join(x.get('issues') or []) or 'ổn', 160)}" + (f"; đã xử lý: {_cut('; '.join(x['actions']), 120)}" if x.get("actions") else "")
                                   for x in d.get("structure") or []])
    from .profiler import clean_tag                    # nạp muộn: tránh vòng import
    L += ["", "## Nhận định về dữ liệu"] + [f"- [{clean_tag(f.get('tag'), f.get('text'))}] {_cut(f.get('text'), 400)}" for f in d.get("findings") or []]
    iss = d.get("issues") or []
    L += _lines(f"## Vấn đề phát hiện ({_n(len(iss))})", [f"- {r['file']} · {r['col']}: {r['issue']} ({_n(r['n'])})" + (f" → đề xuất: {_cut(r['fix'], 150)}" if r.get("fix") else "")
                                                       for r in sorted(iss, key=lambda r: -r["n"])[:12]])
    return "\n".join(L)


def facts_2():
    d = A["d"][2]
    ops = d.get("ops") or []
    on = [o for o in ops if o.get("chosen") and o["op"] != "standardize_text"]
    L = ["## Thao tác làm sạch đã áp dụng"]
    L += [f"- {OPL[o['op']]}" + (f" · cột «{o['column']}»" if o.get("column") else " · toàn bảng") + f" ({o['file']})"
          + (f" — cách xử lý: {o.get('method')}" + (f" = {o.get('value')}" if o.get("method") == "value" else "") if o["op"] == "fill_missing" else "") for o in on] or ["- Không áp dụng thao tác nào"]
    merged = d.get("merged") or {}
    mg = []
    for key, mp in merged.items():
        f, c = key.split(SEP)
        cnt = A["raw"][f][c].value_counts() if f in A.get("raw", {}) and c in A["raw"][f].columns else {}
        pairs = [f"«{a}» → «{b}» ({_n(cnt.get(a, 0))} ô)" for a, b in list(mp.items())[:8]]
        mg.append(f"- Cột «{c}» ({f}): " + "; ".join(pairs) + (f"; …và {len(mp) - 8} cặp khác" if len(mp) > 8 else ""))
    L += _lines("## Gộp giá trị viết khác nhau", mg)
    skipped = []
    for o in ops:
        if o["op"] == "standardize_text":
            got = merged.get(o["file"] + SEP + str(o.get("column")), {})
            rest = [(a, b) for a, b in (o.get("mapping") or {}).items() if got.get(a) != b]
            if rest:
                skipped.append(f"- Cột «{o.get('column')}» ({o['file']}): " + "; ".join(f"«{a}» ~ «{b}»" for a, b in rest[:5]) + (f"; …và {len(rest) - 5} cặp khác" if len(rest) > 5 else ""))
    L += _lines("## Giá trị nghi trùng nhưng KHÔNG gộp (vẫn là giá trị riêng)", skipped)
    L += _lines("## Đề xuất chưa áp dụng", [f"- {o.get('title') or OPL.get(o['op'])}" + (f": {_cut(o.get('reason'), 110)}" if o.get("reason") else "") for o in ops if not o.get("chosen") and o["op"] != "standardize_text"])
    pv = d.get("pv") or {}
    L += _lines("## Vấn đề chất lượng trước → sau", [f"- {k}: {_n(pv['before'].get(k, 0))} → {_n(pv['after'].get(k, 0))}" for k in (pv.get("before") or {}) if pv["before"].get(k) or (pv.get("after") or {}).get(k)])
    cl = A.get("clean") or {}
    L += _lines("## Dữ liệu sau làm sạch", [f"- {n}: {_n(len(x))} dòng × {x.shape[1]} cột" for n, x in cl.items()])
    miss = []
    for n, x in cl.items():
        for c in x.columns:
            p = float(x[c].isna().mean())
            if p > 0:
                miss.append((p, f"- {n} · {c}: còn {fmt_pct(p * 100)} ô thiếu"))
    L += _lines("## Cột còn thiếu dữ liệu (cần thận trọng khi phân tích)", [t for _, t in sorted(miss, reverse=True)[:8]])
    return "\n".join(L)


def facts_3():
    d = A["d"][3]
    r = d.get("result") or {}
    tasks = d.get("tasks") or []
    L = [f"## Phân tích đã chạy ({len(tasks)})"] + [f"{k + 1}. {t['title']}" + (f" — {_cut(t.get('goal'), 140)}" if t.get("goal") else "") for k, t in enumerate(tasks)]
    L += _lines("## Chỉ số chính", [f"- {k['label']}: {k['value']}" + (f" ({k['delta']})" if k.get("delta") else "") for k in r.get("kpis") or []])
    L += _lines("## Kết quả nổi bật", [f"- [{f.get('tag', '')}] {_cut(f.get('text'), 300)}" for f in r.get("findings") or []])
    L += _lines("## Bảng kết quả", [f"- {t['title']}: {_n(len(t.get('rows') or []))} dòng, cột: {', '.join(str(c) for c in (t.get('cols') or [])[:6])}" for t in r.get("tables") or []])
    return "\n".join(L)


def facts_4():
    d = A["d"][4]
    ins, acts = d.get("insights") or [], d.get("actions") or []
    L = ["## Tóm tắt điều hành", d.get("summary") or "—"]
    rows = []
    for k, x in enumerate(ins, 1):
        try:
            vl = numfmt.verify_label(x)
            vl = vl[1] if vl else ""
        except Exception:                                  # noqa: BLE001
            vl = ""
        rows.append(f"{k}. {x.get('title')} (độ tin cậy: {x.get('confidence', '')}{'; ' + vl.lower() if vl else ''}) — nguồn: {x.get('source', '')}")
    L += _lines(f"## Phát hiện được giữ lại ({len(ins)})", rows)
    L += _lines(f"## Hành động được giữ lại ({len(acts)})", [f"- [{a.get('priority', '')}] {a.get('text')}" + (f" — tác động: {a['impact']}" if a.get("impact") else "") for a in acts])
    L += _lines("## Rủi ro và dữ liệu cần thu thêm", [f"- {_cut(r, 250)}" for r in d.get("risks") or []])
    return "\n".join(L)


def facts_5():
    d = A["d"][5]
    fin = d.get("final") or {}
    L = ["## Tiêu đề báo cáo", fin.get("title") or d.get("title") or "—", "", "## Lời dẫn", _cut(d.get("narrative"), 700) or "—"]
    kp = (A["d"][3].get("result") or {}).get("kpis") or []
    L += _lines("## Chỉ số đưa lên báo cáo", [f"- {kp[i]['label']}: {kp[i]['value']}" for i in fin.get("kpis") or [] if i < len(kp)])
    ch = fin.get("charts") or []
    L += _lines(f"## Biểu đồ trong báo cáo và slide ({len(ch)})", [f"- {c.get('title')} ({c.get('kind')})" for c in ch])
    dash = fin.get("dash")
    items = dash.get("charts") if isinstance(dash, dict) else dash
    items = [x for x in (items or []) if x.get("on", True)]
    if items:
        try:
            from ..export import dash_plan
            cat = (d.get("dash") or {}).get("catalog") or []
            names = [f"- {dash_plan.title(x, cat)}" for x in items]
        except Exception:                                  # noqa: BLE001
            names = [f"- {x.get('title') or x.get('by')}" for x in items]
        L += _lines(f"## Bảng điều khiển tương tác ({len(items)} biểu đồ)", names)
    return "\n".join(L)


FACTS = {0: facts_0, 1: facts_1, 2: facts_2, 3: facts_3, 4: facts_4, 5: facts_5}
TITLE = {0: "Đề bài", **{i: f"Bước {i}: {STEP_T[i]}" for i in range(1, 6)}}


def compose(i, facts, notes=()):
    L = [f"# Bản tổng hợp · {TITLE[i]}", "", facts.strip()]
    notes = [n for n in notes if n]
    if notes:
        L += ["", SEC] + [f"- {n}" for n in notes]
    return "\n".join(L).strip() + "\n"


# ------------------------------------------------------------------ AI chỉ viết phần "lưu ý", bị chặn nếu bịa số --
_NUM = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+[.,]\d+|\d{3,}")


def _nums(text):
    return set(_NUM.findall(str(text)))


def odd_numbers(md, facts):
    """Số trong bản tổng hợp không có trong phần ghi nhận của hệ thống (và không có trong câu hỏi/bối cảnh bạn đã viết)."""
    ok = _nums(facts) | _nums(A.get("question")) | _nums(A.get("ctx"))
    return sorted(_nums(md) - ok)[:8]


def ai_notes(i, facts, fb=""):
    nxt = NEXT_NAME.get(i, "bước kế tiếp")
    try:
        r = llm_json(SYS(ROLE), f"Câu hỏi: {A.get('question')}\nBối cảnh: {A.get('ctx') or 'không có'}\n{chain_txt()}"
                     f"Bước vừa xong: {TITLE[i]}\nBước kế tiếp: {nxt}\nGHI NHẬN CỦA HỆ THỐNG VỀ BƯỚC VỪA XONG:\n{facts[:6000]}\n\n"
                     f'Trả về DUY NHẤT JSON {{"notes":["..."]}}: 3-6 gạch đầu dòng NGẮN (mỗi dòng tối đa 200 ký tự) là điều Agent ở bước «{nxt}» cần biết hoặc cần thận trọng, '
                     "rút ra TỪ ghi nhận ở trên (hạn chế dữ liệu, thứ đã hoặc chưa được xử lý, cột/giá trị không nên tin, điều người dùng đã quyết). "
                     "CHỈ dùng số có trong ghi nhận; không thêm số liệu hay nhận định mới; không chép lại cả ghi nhận.", 900)
        out = []
        for n in r.get("notes") or []:
            n = _cut(n, 220)
            if n and not (_nums(n) - _nums(facts) - _nums(A.get("question")) - _nums(A.get("ctx"))):      # câu nào có số lạ thì bỏ
                out.append(n)
        return out[:6]
    except Exception:                                      # noqa: BLE001  (AI lỗi thì bản tổng hợp vẫn có đủ phần của code)
        return []


# ------------------------------------------------------------------ chuỗi bản tổng hợp đưa vào prompt Agent --
def _body(md):
    lines = str(md or "").strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def chain_txt():
    """Các bản tổng hợp ĐÃ DUYỆT của bước 1..5. Rỗng nếu chưa có. Đặt trong ctx_txt() nên mọi Agent đều nhận."""
    memos = [(i, m) for i, m in sorted((A.get("memo") or {}).items()) if isinstance(i, int) and i >= 1 and m.get("status") == "approved" and m.get("md")]
    if not memos:
        return ""
    parts = [(i, _body(m["md"])) for i, m in memos]
    cap = PER_MEMO
    while sum(min(len(b), cap) for _, b in parts) > CHAIN_BUDGET and cap > 500:
        cap = int(cap * 0.8)
    body = "\n\n".join(f"[Bước {i}: {STEP_T[i]}]\n{b[:cap]}" for i, b in parts)
    return ("BẢN TỔNG HỢP CÁC BƯỚC TRƯỚC (người dùng đã duyệt; là NGỮ CẢNH và các quyết định của họ, hãy bám theo. "
            "Con số trích dẫn trong kết quả vẫn phải lấy từ bảng kết quả, không lấy từ đây):\n" + body + "\n")


# ------------------------------------------------------------------ tác vụ nền và cổng duyệt --
def _put(i, **kw):
    with LOCK:
        m = A.setdefault("memo", {}).setdefault(i, {})
        m.update(kw)
        m["gen"] = next_gen()
        bump()


def init_brief():
    """Bước 0 (đề bài do chính bạn nhập): ghép tự động, không chặn."""
    md = compose(0, facts_0())
    A.setdefault("memo", {})[0] = {"status": "approved", "md": md, "orig": md, "edited": False, "ai": False, "warn": [], "src": "auto", "ts": now_iso(), "gen": next_gen()}


def _write(i, fb=""):
    try:
        facts = FACTS[i]()
    except Exception as e:                                 # noqa: BLE001
        _put(i, status="draft", md=f"# Bản tổng hợp · {TITLE[i]}\n\n> Hệ thống không tự ghép được phần ghi nhận ({type(e).__name__}). Hãy viết tay những điều bước sau cần biết.\n", orig="", ai=False, warn=[], edited=False, ts=now_iso())
        return
    notes = ai_notes(i, facts, fb)
    md = compose(i, facts, notes)
    _put(i, status="draft", md=md, orig=md, prev="", ai=bool(notes), warn=[], edited=False, err="", ts=now_iso())
    log(f"Đã viết bản tổng hợp: {STEP_T[i]}")


def begin(i):
    """Gọi sau khi bạn chấp nhận bước i: viết bản tổng hợp ở luồng nền, chưa chạy bước kế tiếp."""
    with LOCK:
        A.setdefault("memo", {})[i] = {"status": "writing", "md": "", "ts": now_iso()}
        bump()
    try:
        start_bg(i, LABEL, _write, i)
    except RuntimeError:
        with LOCK:
            A["memo"].pop(i, None)
        raise


def _rewrite(i, fb):
    m = A["memo"][i]
    cur = m.get("md", "")
    try:
        facts = FACTS[i]()
        r = llm_json(SYS(ROLE), f"Câu hỏi: {A.get('question')}\nBối cảnh: {A.get('ctx') or 'không có'}\n{chain_txt()}"
                     f"BẢN TỔNG HỢP HIỆN TẠI của «{TITLE[i]}» (người dùng có thể đã sửa tay, phần họ sửa PHẢI được giữ):\n{cur[:9000]}\n\n"
                     f"GHI NHẬN CỦA HỆ THỐNG (nguồn số liệu duy nhất):\n{facts[:5000]}\n\nGóp ý của người dùng cho bản tổng hợp: {fb}\n\n"
                     'Viết lại bản tổng hợp theo góp ý. Trả về DUY NHẤT JSON {"md":"toàn bộ bản tổng hợp mới, markdown, bắt đầu bằng dòng \'# Bản tổng hợp · ...\'"}. '
                     "Giữ cấu trúc các mục, giữ phần người dùng đã sửa, KHÔNG thêm số liệu không có trong ghi nhận hoặc trong góp ý.", 3500)
        md = str(r.get("md") or "").strip()
        if len(md) < 40:
            raise ValueError("AI không trả về bản tổng hợp mới")
        md = md[:MAX_MD] + "\n"
        _put(i, status="draft", md=md, prev=cur, edited=True, ai=True, warn=odd_numbers(md, facts), err="")
        log(f"AI đã viết lại bản tổng hợp theo góp ý: {STEP_T[i]}")
    except Exception as e:                                 # noqa: BLE001
        _put(i, status="draft", err=f"AI chưa viết lại được ({e}). Bản hiện tại được giữ nguyên.")


def rewrite(i, fb):
    with LOCK:
        A["memo"][i]["status"] = "writing"
        bump()
    try:
        start_bg(i, "Viết lại bản tổng hợp theo góp ý", _rewrite, i, fb)
    except RuntimeError:
        with LOCK:
            A["memo"][i]["status"] = "draft"
        raise


def save(i, md):
    """Bạn sửa tay. Trả về danh sách số lạ (so với phần ghi nhận của hệ thống) để cảnh báo."""
    md = str(md or "").strip()[:MAX_MD]
    if len(md) < 3:
        raise ValueError("Bản tổng hợp không được để trống.")
    m = A["memo"][i]
    try:
        warn = odd_numbers(md, FACTS[i]())
    except Exception:                                      # noqa: BLE001
        warn = []
    _put(i, md=md + "\n", prev=m.get("md", "") if md + "\n" != m.get("md") else m.get("prev", ""), edited=(md + "\n" != m.get("orig")), warn=warn, err="")


def approve(i):
    _put(i, status="approved", approved=now_iso())
    log(f"Đã duyệt bản tổng hợp: {STEP_T[i]}")


def drop_from(i):
    """Làm lại từ bước i: bản tổng hợp của bước i trở đi không còn đúng nữa."""
    for j in [k for k in (A.get("memo") or {}) if isinstance(k, int) and k >= i]:
        A["memo"].pop(j, None)


def approved_count():
    return sum(1 for k, m in (A.get("memo") or {}).items() if isinstance(k, int) and 1 <= k <= 5 and m.get("status") == "approved")


def zip_files():
    """{đường dẫn trong ZIP: nội dung} của các bản tổng hợp đã có."""
    out = {}
    for k, m in sorted((A.get("memo") or {}).items()):
        if isinstance(k, int) and m.get("md"):
            out[f"tong_hop/{k:02d}_{'de_bai' if k == 0 else 'buoc_' + str(k)}.md"] = m["md"]
    return out
