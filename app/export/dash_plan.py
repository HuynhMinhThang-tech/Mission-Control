# -*- coding: utf-8 -*-
"""KẾ HOẠCH BIỂU ĐỒ của bảng điều khiển: biểu đồ nào hiện lên, với chiều / chỉ số / cách tính / loại nào.

Trước đây bố cục do trình duyệt tự chọn theo dữ liệu, người dùng không can thiệp được. Nay:
  - `catalog`   : những gì CHỌN ĐƯỢC của từng bảng (chiều phân tích, thời gian, chỉ số) để giao diện hiện danh sách chọn;
  - `auto_plan` : gợi ý dự phòng bằng luật (cùng cách chọn với live.js khi chưa có plan);
  - `from_ai`   : đổi gợi ý của AI (viết theo NHÃN tiếng Việt) thành plan theo khóa kỹ thuật, bỏ gợi ý không có thật trong dữ liệu;
  - `validate`  : kiểm tra plan do người dùng/trình duyệt gửi lên (không tin dữ liệu từ trình duyệt).
Một phần tử plan: {id, ds (tên bảng), by ('d0'.. hoặc 't' = thời gian), m ('m0'.. | '' = đếm bản ghi | '*' = theo chỉ số đang chọn trên dashboard),
agg ('sum'|'avg'|'count'|'*'), kind ('bars'|'cols'|'donut'|'trend'), title, why, src ('ai'|'user'), on}."""
from .. import labels as lb
from .interactive import build_datasets

KINDS = ("bars", "cols", "donut", "trend")
KIND_LABEL = {"bars": "Cột ngang", "cols": "Cột dọc", "donut": "Tròn (cơ cấu)", "trend": "Đường (theo thời gian)"}
MAX_CHARTS = 12


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
                    "meas": [{"k": m["k"], "label": m["label"], "unit": m["unit"], "avg": bool(m["avg"])} for m in s["meas"]]})
    return out


def cid(it):
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
        c = names.get(it.get("ds")) or (cat[0] if len(cat) == 1 else None)
        if c is None:
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
    c = next((x for x in cat if x["name"] == it.get("ds")), None)
    if c is None:
        return it.get("title") or ""
    by = "tháng" if it.get("by") == "t" else _lc(next((d["label"] for d in c["dims"] if d["k"] == it.get("by")), str(it.get("by"))))
    m = it.get("m", "*")
    if m == "":
        name = "Số bản ghi"
    elif m == "*":
        name = "Chỉ số đang chọn"
    else:
        x = next((y for y in c["meas"] if y["k"] == m), None)
        lab = x["label"] if x else "?"
        low = lab[:1].lower() + lab[1:]
        if it.get("agg") == "avg":
            name = lab if lab.lower().startswith("trung bình") else "Trung bình " + (low[6:].strip() if low.startswith("tổng ") else low)
        else:
            name = lab if lb.fold(lab).split(" ")[0] in ("tong", "so") else "Tổng " + low
    return f"{name} theo {by}"
