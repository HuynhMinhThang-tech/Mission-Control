# -*- coding: utf-8 -*-
"""BẤT BIẾN không phụ thuộc lĩnh vực: những điều phải đúng với MỌI bộ dữ liệu và MỌI câu hỏi.

Mỗi bất biến là một hàm nhận `Run` (kết quả một lần chạy trọn luồng) và trả về danh sách vi phạm (rỗng = đạt).
Phần cuối có CA ĐỐI CHỨNG: cố ý làm hỏng một kết quả sạch theo từng cách, mỗi cách phải bị đúng bất biến tương ứng bắt.
Bất biến mà tự nó không bắt được lỗi thì vô dụng; ca đối chứng chạy ngay cả khi không có LLM.

Chưa làm (cần các hạng mục sau của kế hoạch): "mọi số truy ngược về sổ sự kiện" (HM-05; ở đây mới kiểm ô được trích và số lớn),
"tổng các phần = tổng chung" (HM-04 R12), "không so khác độ chi tiết thời gian" (HM-04 R3), "không dùng cột thiếu nhiều làm cơ cấu" (HM-04 R8)."""
import copy
import json
import os
import re
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # gốc kho mã, để chạy trực tiếp tệp này

from app import labels as lb, numfmt as nf

# Từ vựng NGÔN NGỮ (không phải từ vựng ngành): cách nói chỉ quan hệ nhân quả. Phát hiện chỉ có tương quan thì không được dùng.
CAUSAL = ("làm tăng", "làm giảm", "dẫn đến", "nhờ vào", "gây ra", "bởi vì", "là do ", "nguyên nhân là", "kéo theo")
GAP = re.compile(r"[a-z] [àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ]")
HARD_CLAIMS = ("mỗi phát hiện đều có bằng chứng truy ngược", "Mọi con số được tính từ dữ liệu đã làm sạch")
CITE = re.compile(r"\[([^\[\]]+)\]\s*=\s*(-?\d[\d.,]*)")


@dataclass
class Run:
    truth: dict                       # {"additive", "non_additive", "absent_terms"} của bộ dữ liệu
    question: str = ""
    summary: str = ""
    insights: list = field(default_factory=list)      # sau kiểm tra (numfmt.audit_insights)
    actions: list = field(default_factory=list)
    risks: list = field(default_factory=list)
    tables: list = field(default_factory=list)        # bảng kết quả bước 4: [{"title","cols","rows"}]
    pptx: str = ""
    md: str = ""
    html: str = ""
    dash: dict = field(default_factory=dict)          # dữ liệu nhúng trong dashboard.html (datasets, plan, insights...)
    chart_titles: list = field(default_factory=list)


def _texts(r, skip_flagged=False):
    out = [r.summary] + [f"{x.get('title', '')} {x.get('evidence', '')}" for x in r.insights if not (skip_flagged and x.get("verify") == "mismatch")] \
        + [f"{a.get('text', '')} {a.get('impact', '')}" for a in r.actions]
    return [t for t in out if t]


def _num(s):
    s = s.strip().rstrip(".,")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", s):
        return float(s.replace(".", "").replace(",", "."))
    return float(s.replace(",", ".")) if re.fullmatch(r"-?\d+([.,]\d+)?", s) else None


# ------------------------------------------------------------------ các bất biến --
def i01_no_trusted_error(r):
    """Phát hiện có phép tính/số liệu sai không được còn độ tin cậy 'Cao'."""
    return [f"«{x.get('title', '')[:50]}» sai số liệu nhưng vẫn 'Cao'" for x in r.insights if x.get("verify") == "mismatch" and x.get("confidence") == "Cao"]


def i02_cited_cells_exist(r):
    """Ô được trích dạng [bảng, hàng, cột] = giá trị phải có thật trong một bảng kết quả, đúng hàng, đúng cột, đúng giá trị (bản nhỏ của 'sổ sự kiện')."""
    bad = []
    for x in r.insights:
        for ref, val in CITE.findall(str(x.get("evidence", ""))):
            parts = [p.strip() for p in ref.split(",")]
            v = _num(val)
            if len(parts) < 3 or v is None:
                bad.append(f"không đọc được trích dẫn [{ref}]")
                continue
            row_key, col = parts[-2], parts[-1]
            found = False
            for t in r.tables:
                cols = [lb.fold(c) for c in t.get("cols", [])]
                if lb.fold(col) not in cols:
                    continue
                j = cols.index(lb.fold(col))
                for row in t.get("rows", []):
                    if any(lb.fold(str(c)) == lb.fold(row_key) for c in row) and isinstance(row[j], (int, float)) and abs(row[j] - v) <= max(0.5, abs(v) * 0.005):
                        found = True
            if not found:
                bad.append(f"ô [{ref}] = {val} không có trong bảng kết quả nào")
    return bad


def i03_no_sum_of_non_additive(r):
    """Chỉ số KHÔNG cộng được (tuổi, điểm, tỷ lệ, đơn giá...) không bao giờ mặc định 'tổng' ở bảng điều khiển, kể cả khi AI đề xuất 'tổng'."""
    bad, non = [], {lb.label(c) for c in r.truth.get("non_additive", [])}
    mk = {}
    for ds in r.dash.get("datasets", []):
        for m in ds.get("meas", []):
            mk[(ds["name"], m["k"])] = m["label"]
            if m["label"] in non and not m.get("avg", False):
                bad.append(f"«{m['label']}» mặc định là tổng trong bảng «{ds['name']}»")
    for p in r.dash.get("plan") or []:
        lab = mk.get((p.get("ds"), p.get("m")))
        if lab in non and p.get("agg") == "sum" and p.get("src") != "user":
            bad.append(f"biểu đồ AI «{p.get('title') or lab}» dùng tổng cho «{lab}»")
    for t in r.chart_titles:
        if any(t.lower().startswith("tổng " + n.lower()) for n in non):
            bad.append(f"tiêu đề «{t}» cộng chỉ số không cộng được")
    return bad


def i04_labels_clean(r):
    """Nhãn hiển thị không có khoảng trắng chen giữa chữ có dấu ('Lo ại', 'Danh m ục')."""
    labs = [x for ds in r.dash.get("datasets", []) for x in [ds.get("title", "")] + [d["label"] for d in ds.get("dims", [])] + [m["label"] for m in ds.get("meas", [])]]
    labs += r.chart_titles + [c for t in r.tables for c in t.get("cols", [])]
    return [f"nhãn «{x}» bị tách chữ" for x in labs if GAP.search(str(x))]


def i05_no_forced_fill(r):
    """Không ép số lượng: tối đa 5 phát hiện; hành động chỉ có khi có phát hiện để gắn vào."""
    bad = []
    if len(r.insights) > 5:
        bad.append(f"{len(r.insights)} phát hiện (tối đa 5)")
    if r.actions and not r.insights:
        bad.append(f"{len(r.actions)} hành động nhưng không có phát hiện nào để gắn")
    return bad


def i06_no_absent_terms(r):
    """Không nhắc yếu tố KHÔNG có trong dữ liệu như một điều đã biết; chỉ được nêu trong risks dưới dạng giả thuyết (trừ khi chính câu hỏi nhắc tới)."""
    bad, q = [], (r.question or "").lower()
    for term in r.truth.get("absent_terms", []):
        t = term.lower()
        if t in q:
            continue
        for txt in _texts(r):
            if t in txt.lower():
                bad.append(f"nhắc «{term}» (không có trong dữ liệu) như một điều đã biết: «{txt[:60]}»")
        for rk in r.risks:
            if t in str(rk).lower() and "giả thuyết" not in str(rk).lower():
                bad.append(f"nhắc «{term}» trong rủi ro mà không gắn nhãn giả thuyết")
    return bad


def i07_no_causal_claims(r):
    """Phát hiện (chỉ có dữ liệu mô tả) không dùng ngôn ngữ nhân quả; giả thuyết thì được, nhưng phải nằm ở risks."""
    return [f"«{x.get('title', '')[:60]}» dùng từ nhân quả «{w.strip()}»" for x in r.insights for w in CAUSAL if w in (x.get("title", "") + " ").lower()]


def i08_no_hard_claim_if_unverified(r):
    """Còn phát hiện chưa kiểm được/sai thì không tệp xuất nào được khẳng định 'mỗi phát hiện đều có bằng chứng'."""
    if nf.all_verified(r.insights):
        return []
    return [f"{name} vẫn có câu khẳng định «{c[:40]}…»" for name, txt in (("PPT", r.pptx), ("Markdown", r.md), ("báo cáo HTML", r.html)) for c in HARD_CLAIMS if c in txt]


def i09_numbers_in_tables(r):
    """Số lớn (từ 1 triệu) trong tóm tắt/phát hiện/hành động phải có trong một bảng kết quả (ô hoặc tổng cột). Phát hiện ĐÃ bị gắn cờ sai thì bỏ qua (hệ thống đã báo rồi)."""
    vals = []
    for t in r.tables:
        for j in range(len(t.get("cols", []))):
            col = [row[j] for row in t.get("rows", []) if j < len(row) and isinstance(row[j], (int, float)) and not isinstance(row[j], bool)]
            vals += col + ([sum(col)] if col else [])
    known = nf.Known(vals)
    return [f"số {s} không có trong bảng kết quả nào" for txt in _texts(r, skip_flagged=True) for s in nf.audit(txt, known)] if known else []


def i10_every_insight_checked(r):
    """Mọi phát hiện đều đã qua kiểm tra (có `verify`), và 'ok' thì không kèm cờ sai."""
    bad = [f"«{x.get('title', '')[:50]}» chưa qua kiểm tra" for x in r.insights if "verify" not in x]
    return bad + [f"«{x.get('title', '')[:50]}» ok nhưng còn cờ sai" for x in r.insights if x.get("verify") == "ok" and (x.get("check") or x.get("calc_mismatch"))]


def i11_exports_match(r):
    """Cùng một số phát hiện ở mọi đầu ra (Markdown, báo cáo HTML, bảng điều khiển)."""
    n = len(r.insights)
    got = {"Markdown": len(re.findall(r"^\d+\. \*\*", r.md.split("## Phát hiện chính")[-1].split("## ")[0], re.M)) if "## Phát hiện chính" in r.md else 0,
           "báo cáo HTML": r.html.count('<div class="in">'), "bảng điều khiển": len(r.dash.get("insights", []))}
    return [f"{k} có {v} phát hiện, kết quả có {n}" for k, v in got.items() if v != n]


INVARIANTS = [("I01", "phát hiện sai số liệu không còn 'Cao'", i01_no_trusted_error), ("I02", "ô được trích có thật trong bảng kết quả", i02_cited_cells_exist),
              ("I03", "không cộng chỉ số không cộng được", i03_no_sum_of_non_additive), ("I04", "nhãn không bị tách chữ", i04_labels_clean),
              ("I05", "không ép số lượng phát hiện/hành động", i05_no_forced_fill), ("I06", "không nhắc thứ không có trong dữ liệu", i06_no_absent_terms),
              ("I07", "không ngôn ngữ nhân quả trong phát hiện", i07_no_causal_claims), ("I08", "không khẳng định cứng khi chưa kiểm hết", i08_no_hard_claim_if_unverified),
              ("I09", "số lớn có trong bảng kết quả", i09_numbers_in_tables), ("I10", "mọi phát hiện đã qua kiểm tra", i10_every_insight_checked),
              ("I11", "mọi đầu ra cùng số phát hiện", i11_exports_match)]


def check_all(run, only=None):
    """{mã: [vi phạm]} cho mọi bất biến (chỉ những bất biến có vi phạm nằm trong kết quả)."""
    out = {}
    for code, _, fn in INVARIANTS:
        if only and code not in only:
            continue
        v = fn(run)
        if v:
            out[code] = v
    return out


# ------------------------------------------------------------------ ca đối chứng: cố ý làm hỏng, bất biến PHẢI bắt --
def _bad_insight(**kw):
    return {"title": "Một phát hiện", "confidence": "Cao", "evidence": "x", "source": "s", "verify": "ok", **kw}


CONTROLS = [
    ("I01", "sai số học nhưng vẫn Cao", lambda r: r.insights.append(_bad_insight(verify="mismatch"))),
    ("I02", "trích ô không tồn tại", lambda r: r.insights.append(_bad_insight(evidence="[Phân tích 1, ZZZ, Cột không có] = 123"))),
    ("I03", "chỉ số không cộng được mặc định là tổng", lambda r: r.dash["datasets"][0]["meas"].append({"k": "m99", "label": lb.label(r.truth["non_additive"][0]), "avg": False})),
    ("I04", "nhãn bị tách chữ", lambda r: r.chart_titles.append("Số ti ền theo Lo ại")),
    ("I05", "bảy phát hiện", lambda r: r.insights.extend(_bad_insight(title=f"p{k}") for k in range(7))),
    ("I05", "hành động không gắn phát hiện", lambda r: (r.insights.clear(), r.actions.append({"text": "Làm A", "impact": "x"}))),
    ("I06", "nhắc yếu tố không có trong dữ liệu", lambda r: setattr(r, "summary", f"Cần tăng ngân sách {r.truth['absent_terms'][0]} ngay.")),
    ("I06", "yếu tố ngoài dữ liệu trong rủi ro nhưng không gắn giả thuyết", lambda r: r.risks.append(f"Có thể do {r.truth['absent_terms'][0]}.")),
    ("I07", "ngôn ngữ nhân quả trong phát hiện", lambda r: r.insights.append(_bad_insight(title="Khuyến mãi dẫn đến tăng doanh thu"))),
    ("I08", "khẳng định cứng khi còn phát hiện chưa kiểm được", lambda r: (r.insights.append(_bad_insight(verify="unverified")), setattr(r, "pptx", r.pptx + " mỗi phát hiện đều có bằng chứng truy ngược về dữ liệu"))),
    ("I09", "số lớn không có trong bảng", lambda r: setattr(r, "summary", "Tổng cộng 9.876.543.210 đồng.")),
    ("I10", "phát hiện chưa được kiểm tra", lambda r: r.insights.append({"title": "Chưa qua audit", "confidence": "Cao", "evidence": "x"})),
    ("I11", "Markdown thiếu phát hiện", lambda r: setattr(r, "md", "## Phát hiện chính\n\n## Khuyến nghị")),
]


def run_controls(base):
    """Với mỗi ca: bản sạch KHÔNG được vi phạm đúng bất biến đó, còn bản bị làm hỏng PHẢI bị bắt. Trả về (đạt, tổng, [ca trượt])."""
    miss, ok = [], 0
    for code, why, mutate in CONTROLS:
        if code in check_all(base, only={code}):
            miss.append(f"{code} «{why}»: bản sạch đã vi phạm sẵn, không dùng làm đối chứng được")
            continue
        broken = copy.deepcopy(base)
        mutate(broken)
        if code in check_all(broken, only={code}):
            ok += 1
        else:
            miss.append(f"{code} «{why}»: bất biến KHÔNG bắt được")
    return ok, len(CONTROLS), miss


def clean_run(truth):
    """Một kết quả sạch nhỏ để làm nền cho ca đối chứng (không cần chạy luồng thật)."""
    nm = truth["non_additive"][0]
    return Run(truth=truth, question="câu hỏi mẫu", summary="Nhóm A dẫn đầu.",
               insights=[{"title": "A cao hơn B 2 lần", "confidence": "Cao", "evidence": "[Phân tích 1, A, Tổng] = 200; [Phân tích 1, B, Tổng] = 100; 200 / 100 = 2", "source": "s", "verify": "ok"}],
               actions=[{"text": "Xem lại nhóm B", "priority": "Trung bình", "impact": "chưa ước tính được"}], risks=[f"Giả thuyết cần kiểm chứng: có thể liên quan {truth['absent_terms'][0]}."],
               tables=[{"title": "Phân tích 1", "cols": ["Nhóm", "Tổng"], "rows": [["A", 200.0], ["B", 100.0]]}],
               pptx="Các phát hiện chính", md="## Phát hiện chính\n\n1. **A cao hơn B 2 lần** (độ tin cậy: Cao)\n\n## Khuyến nghị", html='<div class="in"></div>',
               dash={"datasets": [{"name": "t.csv", "title": "T", "dims": [{"label": "Nhóm"}], "meas": [{"k": "m0", "label": "Tổng", "avg": False}, {"k": "m1", "label": lb.label(nm), "avg": True}]}],
                     "plan": [{"ds": "t.csv", "m": "m1", "agg": "avg", "src": "ai", "title": "Trung bình"}], "insights": [{"title": "A cao hơn B 2 lần"}]},
               chart_titles=["Tổng theo nhóm"])


if __name__ == "__main__":
    ok, n, miss = run_controls(clean_run({"non_additive": ["Tuổi"], "absent_terms": ["bảo trì"]}))
    print(f"{ok}/{n} ca đối chứng bị bắt", *miss, sep="\n  ")
    print(json.dumps({c: d for c, d, _ in INVARIANTS}, ensure_ascii=False, indent=1))
