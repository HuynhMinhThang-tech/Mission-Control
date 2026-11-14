# -*- coding: utf-8 -*-
"""KẾ HOẠCH BIỂU ĐỒ của bảng điều khiển: biểu đồ nào hiện lên, với chiều / chỉ số / cách tính / loại nào.

Trước đây bố cục do trình duyệt tự chọn theo dữ liệu, người dùng không can thiệp được. Nay:
  - `catalog`   : những gì CHỌN ĐƯỢC của từng bảng (chiều phân tích, thời gian, chỉ số) để giao diện hiện danh sách chọn;
  - `auto_plan` : gợi ý dự phòng bằng luật (cùng cách chọn với live.js khi chưa có plan);
  - `from_ai`   : đổi gợi ý của AI (viết theo NHÃN tiếng Việt) thành plan theo khóa kỹ thuật, bỏ gợi ý không có thật trong dữ liệu;
  - `validate`  : kiểm tra plan do người dùng/trình duyệt gửi lên (không tin dữ liệu từ trình duyệt).
Một phần tử plan: {id, ds (tên bảng), by ('d0'.. hoặc 't' = thời gian), m ('m0'.. | '' = đếm bản ghi | '*' = theo chỉ số đang chọn trên dashboard),
agg ('sum'|'avg'|'count'|'*'), kind ('bars'|'cols'|'donut'|'trend'), title, why, src ('ai'|'user'), on}.
Ngoài biểu đồ thường (type 'chart'), plan còn có: 'score' (bảng điểm tỷ lệ đạt theo từng tiêu chí), 'heat' (ma trận nhóm × tiêu chí),
'static' (biểu đồ lấy từ kết quả phân tích bước 4, đã tổng hợp sẵn nên không lọc chéo được).

BẢN THIẾT KẾ (`bp`) quyết định phần còn lại của trang, trước đây cứng trong live.js: các thẻ KPI nào (không bắt buộc có "Số bản ghi"),
kiểu bố cục, có bảng chi tiết hay không, những khối chữ nào hiện. AI đề xuất, người duyệt bật/tắt; không có `bp` thì trang dựng như trước."""
from .. import labels as lb
from . import fonts
from .interactive import build_datasets

KINDS = ("bars", "cols", "donut", "trend")
KIND_LABEL = {"bars": "Cột ngang", "cols": "Cột dọc", "donut": "Tròn (cơ cấu)", "trend": "Đường (theo thời gian)"}
MAX_CHARTS = 16
TYPES = ("chart", "score", "heat", "static")
STATIC_KINDS = ("bars", "cols", "line", "area", "donut", "pie", "lollipop", "pareto", "treemap")       # dạng biểu đồ của thẻ lấy từ kết quả phân tích
LAYOUTS = {"auto": "Tự động", "overview": "Tổng quan và xu hướng", "rank": "Xếp hạng các nhóm", "compliance": "Tuân thủ đạt / không đạt", "story": "Kể chuyện (kết luận trước)"}
KPI_KINDS = ("sum", "avg", "rate", "rate_all", "rate_low", "count", "distinct", "latest", "top", "missing")
KPI_LABEL = {"sum": "Tổng", "avg": "Trung bình", "rate": "Tỷ lệ của một tiêu chí", "rate_all": "Tỷ lệ đạt chung", "rate_low": "Tiêu chí thấp nhất", "count": "Số bản ghi",
             "distinct": "Số nhóm khác nhau", "latest": "Kỳ gần nhất (so với kỳ trước)", "top": "Nhóm cao nhất", "missing": "Tỷ lệ chưa có dữ liệu"}
MAX_KPIS = 6
MAX_STATIC = 40


def catalog(dfs):
    """Danh mục chọn được, rút gọn (không kèm dữ liệu từng dòng)."""
    out = []
    for s in build_datasets(dfs):
        dims = []
        for d in s["dims"]:
            k = len(d["vals"]) - (1 if d["na"] >= 0 else 0)
            dims.append({"k": d["k"], "label": d["label"], "n": k, "miss": d["miss"], "ord": bool(d.get("ord")),
                         "len": round(sum(len(v) for v in d["vals"]) / max(1, len(d["vals"])), 1), "sample": d["vals"][:3]})
        out.append({"name": s["name"], "title": s["title"], "n": s["n_src"], "dims": dims,
                    "time": {"label": s["time"]["label"], "n": len(s["time"]["vals"])} if s.get("time") else None,
                    "meas": [{"k": m["k"], "label": m["label"], "unit": m["unit"], "avg": bool(m["avg"]), "add": bool(m.get("add", not m["avg"])),
                           "rate": bool(m.get("rate")), "short": m.get("short") or m["label"]} for m in s["meas"]]})
    return out


def cid(it):
    ty = it.get("type") or "chart"
    if ty == "score":
        return "score|" + str(it.get("ds")) + "|" + ",".join(it.get("ms") or [])
    if ty == "heat":
        return "heat|" + str(it.get("ds")) + "|" + str(it.get("by")) + "|" + ",".join(it.get("ms") or [])
    if ty == "static":
        return "static|" + str(it.get("sid") or it.get("title"))
    return "|".join(str(it.get(k, "")) for k in ("ds", "by", "m", "agg", "kind"))


def _item(ds, by, m, agg, kind, title="", why="", src="ai", on=True):
    it = {"ds": ds, "by": by, "m": m, "agg": agg, "kind": kind, "title": str(title or "")[:90], "why": str(why or "")[:200], "src": src, "on": bool(on)}
    it["id"] = cid(it)
    return it


def validate(plan, cat, src_default="user"):
    """Giữ phần tử hợp lệ, sửa các tổ hợp vô nghĩa (đường cho biến không phải thời gian, tròn cho trung bình...), bỏ trùng, tối đa MAX_CHARTS."""
    names = {c["name"]: c for c in cat}
    out, seen = [], set()
    for it in plan or []:
        if not isinstance(it, dict):
            continue
        ty = it.get("type") if it.get("type") in TYPES else "chart"
        if ty == "static":
            n = _static(it)
            if n and n["id"] not in seen:
                seen.add(n["id"])
                out.append(n)
            continue
        c = names.get(it.get("ds")) or (cat[0] if len(cat) == 1 else None)
        if c is None:
            continue
        if ty in ("score", "heat"):
            n = _rate_card(ty, c, it, src_default)
            if n and n["id"] not in seen:
                seen.add(n["id"])
                out.append(n)
            continue
        by = it.get("by")
        dims = {d["k"] for d in c["dims"]}
        if by == "t":
            if not c["time"]:
                continue
        elif by not in dims:
            continue
        meas = {m["k"]: m for m in c["meas"]}
        m = it.get("m", "*")
        if m not in ("", "*") and m not in meas:
            continue
        if m == "":
            agg = "count"
        elif m == "*":
            agg = "*"
        else:
            agg = it.get("agg") if it.get("agg") in ("sum", "avg") else ("avg" if meas[m]["avg"] else "sum")
            src = it.get("src") if it.get("src") in ("ai", "user") else src_default
            if agg == "sum" and src == "ai" and not meas[m].get("add", not meas[m]["avg"]):
                agg = "avg"            # AI tự chọn "tổng" cho chỉ số không cộng được (tuổi, điểm, đơn giá...) -> đổi sang trung bình; người dùng tự chọn thì giữ
                it = dict(it, title=None)   # tiêu đề AI viết theo phép "tổng" ("Tổng tuổi theo phòng ban") không còn đúng: dùng tiêu đề tự tính theo phép tổng hợp thật
        if m not in ("", "*") and meas[m].get("rate"):
            agg = "avg"                    # tỷ lệ chỉ có nghĩa khi lấy trung bình của 0/1, không cộng
        kind = it.get("kind") if it.get("kind") in KINDS else ("trend" if by == "t" else "bars")
        if by == "t":
            kind = "trend" if kind == "trend" else "cols"
        elif kind == "trend":
            kind = "bars"
        if kind == "donut" and agg == "avg":
            kind = "bars"
        n = _item(c["name"], by, m, agg, kind, it.get("title"), it.get("why"), it.get("src") if it.get("src") in ("ai", "user") else src_default, it.get("on", True))
        if n["id"] in seen:
            continue
        seen.add(n["id"])
        out.append(n)
    return out[:MAX_CHARTS]


def _static(it):
    """Biểu đồ lấy từ bảng kết quả bước 4: nhãn + số đã tổng hợp sẵn (không lọc chéo được). Không tin dữ liệu từ trình duyệt: kiểm lại kiểu, độ dài, số hữu hạn."""
    labels = [str(x)[:60] for x in (it.get("labels") or [])][:MAX_STATIC]
    vals = []
    for v in (it.get("values") or [])[: len(labels)]:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        if f != f or f in (float("inf"), float("-inf")):
            return None
        vals.append(round(f, 4))
    if len(labels) < 2 or len(labels) != len(vals):
        return None
    sid = str(it.get("sid") or it.get("title") or "")[:80]
    if not sid:
        return None
    n = {"type": "static", "sid": sid, "ds": "", "by": "", "m": "", "agg": "", "kind": it.get("kind") if it.get("kind") in STATIC_KINDS else "bars",
         "title": str(it.get("title") or "")[:90], "why": str(it.get("why") or "")[:200], "labels": labels, "values": vals, "unit": str(it.get("unit") or "")[:20],
         "src": "analysis", "on": bool(it.get("on", True))}
    n["id"] = cid(n)
    return n


def _rate_card(ty, c, it, src_default):
    """Bảng điểm (score) hoặc ma trận nhiệt (heat) cho các chỉ số TỶ LỆ của một bảng."""
    rates = [m["k"] for m in c["meas"] if m.get("rate")]
    if not rates:
        return None
    ms = [k for k in (it.get("ms") or []) if k in rates][:8 if ty == "heat" else 20]
    by = it.get("by") if ty == "heat" else ""
    if ty == "heat" and by not in {d["k"] for d in c["dims"]}:
        return None
    n = {"type": ty, "ds": c["name"], "by": by, "m": "", "agg": "avg", "kind": ty, "ms": ms, "title": str(it.get("title") or "")[:90], "why": str(it.get("why") or "")[:200],
         "src": it.get("src") if it.get("src") in ("ai", "user") else src_default, "on": bool(it.get("on", True))}
    n["id"] = cid(n)
    return n


def auto_plan(cat):
    """Gợi ý bằng luật (cùng cách chọn với live.js): xu hướng theo tháng, một biểu đồ cơ cấu, vài biểu đồ xếp hạng. Chỉ số 'theo lựa chọn trên dashboard'."""
    out = []
    for c in cat:
        def rank(d):
            k = d["n"]
            return (0 if 3 <= k <= 12 else 2 if k == 2 else 1 if k <= 20 else 3) + (1 if d["len"] > 26 else 0) + (2 if d["miss"] > .3 else 0)
        ok = sorted([(rank(d), i, d) for i, d in enumerate(c["dims"]) if d["miss"] < .6 and d["n"] >= 2], key=lambda x: (x[0], x[1]))
        time_ok = bool(c["time"]) and c["time"]["n"] >= 3
        dn = next((d for r, _, d in ok if r < 3 and d["n"] <= 6 and d["miss"] <= .3 and not d["ord"]), None)
        bars = [d for r, _, d in ok if r < 3 and d is not dn][: 3 if (time_ok and dn) else 4]
        if sum(1 for m in c["meas"] if m.get("rate")) >= 2:
            sc = {"type": "score", "ds": c["name"], "ms": [], "by": "", "m": "", "agg": "avg", "kind": "score", "title": "", "why": "", "src": "ai", "on": True}
            sc["id"] = cid(sc)
            out.append(sc)
            if ok:
                hm = dict(sc, type="heat", kind="heat", by=ok[0][2]["k"])
                hm["id"] = cid(hm)
                out.append(hm)
        if time_ok:
            out.append(_item(c["name"], "t", "*", "*", "trend"))
        if dn:
            out.append(_item(c["name"], dn["k"], "*", "*", "donut"))
        out += [_item(c["name"], d["k"], "*", "*", "bars") for d in bars]
    return out[:MAX_CHARTS]


def _find(items, label):
    f = lb.fold(label or "")
    return next((x for x in items if lb.fold(x["label"]) == f), None) or next((x for x in items if f and (f in lb.fold(x["label"]) or lb.fold(x["label"]) in f)), None)


def from_ai(raw, cat):
    """Gợi ý của AI theo NHÃN ({ds, by, measure, agg, kind, title, why}) -> plan theo khóa. Nhãn không khớp dữ liệu thật thì bỏ (AI không được bịa cột)."""
    out = []
    for r in raw or []:
        if not isinstance(r, dict):
            continue
        f = lb.fold(str(r.get("ds") or ""))
        c = next((x for x in cat if lb.fold(x["name"]) == f or lb.fold(x["title"]) == f), None) or (cat[0] if len(cat) == 1 else None)
        if c is None:
            continue
        if str(r.get("kind") or "") in ("score", "heat"):
            rates = [m for m in c["meas"] if m.get("rate")]
            ms = [x["k"] for x in (_find(rates, str(l)) for l in (r.get("measures") or [])) if x]
            dd = _find(c["dims"], str(r.get("by") or "")) if r.get("kind") == "heat" else None
            out.append({"type": r["kind"], "ds": c["name"], "by": dd["k"] if dd else (c["dims"][0]["k"] if c["dims"] else ""), "ms": ms, "title": r.get("title"), "why": r.get("why"), "src": "ai"})
            continue
        bl = str(r.get("by") or "")
        if lb.fold(bl) in ("thoi gian", "thang", "time", "ngay", "theo thang", "thang nam"):
            by = "t" if c["time"] else None
        else:
            d = _find(c["dims"], bl)
            by = d["k"] if d else None
        if by is None:
            continue
        ml = str(r.get("measure") or "")
        if lb.fold(ml) in ("so ban ghi", "dem", "dem so ban ghi", "count", ""):
            m = ""
        else:
            mm = _find(c["meas"], ml)
            if mm is None:
                continue
            m = mm["k"]
        out.append({"ds": c["name"], "by": by, "m": m, "agg": r.get("agg"), "kind": r.get("kind"), "title": r.get("title"), "why": r.get("why"), "src": "ai"})
    return validate(out, cat, "ai")


def suggest(raw, cat, minimum=4):
    """Gợi ý của AI, bổ sung bằng luật nếu AI đưa quá ít (để bảng điều khiển luôn có bố cục dùng được)."""
    plan = from_ai(raw, cat)
    if len(plan) < minimum:
        have = {(p["ds"], p["by"], p["kind"]) for p in plan}
        for a in auto_plan(cat):
            if (a["ds"], a["by"], a["kind"]) not in have and len(plan) < 8:
                plan.append(a)
    return plan[:MAX_CHARTS]


def _lc(t):
    return t[:1].lower() + t[1:]


def title(it, cat):
    """Tên biểu đồ bằng tiếng Việt, cùng cách đặt tên với giao diện: 'Tổng doanh thu theo khu vực'."""
    ty = it.get("type") or "chart"
    if ty == "static":
        return it.get("title") or "Biểu đồ từ phân tích"
    c = next((x for x in cat if x["name"] == it.get("ds")), None)
    if c is None:
        return it.get("title") or ""
    if ty == "score":
        return it.get("title") or "Tỷ lệ đạt theo từng tiêu chí"
    if ty == "heat":
        return it.get("title") or "Tỷ lệ đạt theo " + _lc(next((d["label"] for d in c["dims"] if d["k"] == it.get("by")), "nhóm")) + " và tiêu chí"
    by = "tháng" if it.get("by") == "t" else _lc(next((d["label"] for d in c["dims"] if d["k"] == it.get("by")), str(it.get("by"))))
    m = it.get("m", "*")
    if m == "":
        name = "Số bản ghi"
    elif m == "*":
        name = "Chỉ số đang chọn"
    else:
        x = next((y for y in c["meas"] if y["k"] == m), None)
        lab = x["label"] if x else "?"
        if x and x.get("rate"):
            return f"{lab} theo {by}"
        low = lab[:1].lower() + lab[1:]
        if it.get("agg") == "avg":
            name = lab if lab.lower().startswith("trung bình") else "Trung bình " + (low[6:].strip() if low.startswith("tổng ") else low)
        else:
            name = lab if lb.fold(lab).split(" ")[0] in ("tong", "so") else "Tổng " + low
    return f"{name} theo {by}"


# ====================================================================== BẢN THIẾT KẾ (KPI, bố cục, bảng, khối chữ)
def _kid(it):
    return "kpi|" + "|".join(str(it.get(k, "")) for k in ("ds", "kind", "m", "by"))


def kpi_title(it, cat):
    """Tên thẻ KPI bằng tiếng Việt (giao diện chọn KPI dùng cùng cách đặt tên)."""
    if it.get("label"):
        return it["label"]
    c = next((x for x in cat if x["name"] == it.get("ds")), None) or {"dims": [], "meas": [], "time": None}
    m = next((x for x in c["meas"] if x["k"] == it.get("m")), None)
    d = next((x for x in c["dims"] if x["k"] == it.get("by")), None)
    k = it.get("kind")
    if k == "count":
        return "Số bản ghi"
    if k == "rate_all":
        return "Tỷ lệ đạt chung"
    if k == "rate_low":
        return "Tiêu chí có tỷ lệ thấp nhất"
    if k == "distinct":
        return "Số " + _lc(d["label"]) if d else "Số nhóm"
    if k == "missing":
        return "Chưa có dữ liệu" + (": " + m["short"] if m else "")
    if not m:
        return KPI_LABEL.get(k, "KPI")
    base = m["label"]
    if k == "rate":
        return base
    if k == "top":
        return (d["label"] if d else "Nhóm") + " cao nhất theo " + _lc(base)
    if k == "latest":
        return base + " kỳ gần nhất"
    return ("Trung bình " + _lc(base) if k == "avg" else "Tổng " + _lc(base)) if not base.lower().startswith(("tổng", "trung bình", "số", "tỷ lệ")) else base


def _kpi(c, it):
    """Một thẻ KPI hợp lệ với bảng c, hoặc None."""
    kind = it.get("kind")
    if kind not in KPI_KINDS:
        return None
    meas = {m["k"]: m for m in c["meas"]}
    dims = {d["k"] for d in c["dims"]}
    rates = [m["k"] for m in c["meas"] if m.get("rate")]
    m, by = it.get("m") or "", it.get("by") or ""
    if kind in ("sum", "avg", "latest", "top"):
        if m not in meas or meas[m].get("rate") and kind in ("sum",):
            return None
    if kind == "rate" and m not in rates:
        return None
    if kind in ("rate_all", "rate_low") and not rates:
        return None
    if kind == "missing" and m not in rates and m not in meas:
        return None
    if kind in ("distinct", "top") and by not in dims:
        return None
    if kind == "latest" and not c["time"]:
        return None
    out = {"ds": c["name"], "kind": kind, "m": m if kind in ("sum", "avg", "rate", "latest", "top", "missing") else "", "by": by if kind in ("distinct", "top") else "",
           "label": str(it.get("label") or "")[:60], "on": bool(it.get("on", True))}
    out["id"] = _kid(out)
    return out


def validate_bp(bp, cat):
    """Chuẩn hóa bản thiết kế do AI/trình duyệt gửi lên: bỏ KPI trỏ tới cột không có thật, bố cục lạ -> 'auto'. Không có bp -> None."""
    if not isinstance(bp, dict):
        return None
    names = {c["name"]: c for c in cat}
    kp, seen = [], set()
    for it in bp.get("kpis") or []:
        if not isinstance(it, dict):
            continue
        c = names.get(it.get("ds")) or (cat[0] if len(cat) == 1 else None)
        n = _kpi(c, it) if c else None
        if n and n["id"] not in seen:
            seen.add(n["id"])
            kp.append(n)
    tb = bp.get("table")
    blocks = bp.get("blocks") if isinstance(bp.get("blocks"), dict) else {}
    return {"layout": bp.get("layout") if bp.get("layout") in LAYOUTS else "auto", "kpis": kp[: MAX_KPIS * max(1, len(cat))],
            "table": {"on": bool(tb.get("on", True)) if isinstance(tb, dict) else bool(tb) if tb is not None else True},
            "blocks": {k: bool(blocks.get(k, True)) for k in ("ans", "ins", "act", "risk")},
            "font": fonts.norm(bp.get("font"))}                # phông của báo cáo HTML và bảng điều khiển (xem export/fonts.py)


def default_bp(cat):
    """Bản thiết kế bằng luật khi AI không đề xuất: KPI hợp với KIỂU dữ liệu (không mặc định 'Số bản ghi'), bảng chi tiết chỉ khi có từ 2 chỉ số số."""
    kp, layout = [], "auto"
    for c in cat:
        num = [m for m in c["meas"] if not m.get("rate")]
        rates = [m for m in c["meas"] if m.get("rate")]
        dim = c["dims"][0]["k"] if c["dims"] else ""
        if len(rates) >= 2 and len(rates) >= len(num):
            layout = "compliance" if layout == "auto" else layout
            kp += [{"ds": c["name"], "kind": "rate_all"}, {"ds": c["name"], "kind": "rate_low"}]
            if dim:
                kp.append({"ds": c["name"], "kind": "distinct", "by": dim})
            kp.append({"ds": c["name"], "kind": "missing", "m": rates[0]["k"], "label": "Tiêu chí chưa có đánh giá"})
        elif num:
            kp.append({"ds": c["name"], "kind": "avg" if num[0]["avg"] else "sum", "m": num[0]["k"]})
            if c["time"]:
                kp.append({"ds": c["name"], "kind": "latest", "m": num[0]["k"]})
            if dim:
                kp.append({"ds": c["name"], "kind": "top", "m": num[0]["k"], "by": dim})
            if len(num) > 1:
                kp.append({"ds": c["name"], "kind": "avg" if num[1]["avg"] else "sum", "m": num[1]["k"]})
            if c["time"] and layout == "auto":
                layout = "overview"
        else:
            kp.append({"ds": c["name"], "kind": "count"})                # chỉ khi dữ liệu không có gì khác để đo
    two = any(sum(1 for m in c["meas"] if not m.get("rate")) >= 2 for c in cat)
    return validate_bp({"layout": layout, "kpis": kp, "table": {"on": two}}, cat)


def bp_from_ai(raw, cat):
    """Đề xuất của AI theo NHÃN ({layout, kpis:[{ds, kind, measure, by, label}], table, blocks}) -> bản thiết kế theo khóa. Phần AI bỏ trống thì dùng luật."""
    base = default_bp(cat) or {"layout": "auto", "kpis": [], "table": {"on": False}, "blocks": {}, "font": fonts.DEFAULT}
    if not isinstance(raw, dict):
        return base
    kp = []
    for r in raw.get("kpis") or []:
        if not isinstance(r, dict):
            continue
        f = lb.fold(str(r.get("ds") or ""))
        c = next((x for x in cat if lb.fold(x["name"]) == f or lb.fold(x["title"]) == f), None) or (cat[0] if len(cat) == 1 else None)
        if c is None:
            continue
        mm = _find(c["meas"], str(r.get("measure") or "")) if r.get("measure") else None
        dd = _find(c["dims"], str(r.get("by") or "")) if r.get("by") else None
        kp.append({"ds": c["name"], "kind": r.get("kind"), "m": mm["k"] if mm else "", "by": dd["k"] if dd else "", "label": r.get("label")})
    got = validate_bp({"layout": raw.get("layout"), "kpis": kp, "table": raw.get("table", base["table"]["on"]), "blocks": raw.get("blocks")}, cat)
    if not got["kpis"]:
        got["kpis"] = base["kpis"]
    if raw.get("layout") not in LAYOUTS:
        got["layout"] = base["layout"]
    return got
