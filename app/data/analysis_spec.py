# -*- coding: utf-8 -*-
"""Ghép biến để phân tích (bước Phân tích).

Người dùng chọn biến từ danh sách cột thật của dữ liệu (hoặc mô tả bằng lời để AI nhận diện) -> một `spec` có cấu trúc.
Module này: (1) liệt kê cột kèm kiểu để giao diện hiển thị, (2) KIỂM TRA spec với dữ liệu thật, (3) mô tả spec bằng một câu tiếng Việt,
(4) SINH code pandas xác định (không nhờ AI) nên kết quả đúng chính xác điều người dùng chọn.

Các loại phân tích (`type`):
  compare     So sánh theo nhóm: chỉ số (cột số + cách tính) chia theo 1-2 biến phân loại.
  trend       Xu hướng theo thời gian: chỉ số theo ngày/tuần/tháng/quý/năm, có thể tách theo 1 biến phân loại.
  cross       Phân tích chéo hai biến phân loại (bảng hàng × cột), giá trị là chỉ số hoặc số bản ghi.
  correlate   Tương quan giữa hai biến số.
  distribution Phân bố của một biến (số: theo khoảng; phân loại: theo giá trị).
  free        Yêu cầu viết tự do (không nhận diện được hết) -> chuyển nguyên văn cho AI viết code.
Code sinh ra chỉ dùng cú pháp mà sandbox cho phép (không import, không thuộc tính bắt đầu bằng gạch dưới)."""
import re

import pandas as pd

from .. import labels as lb
from .describe import KIND_LABEL, kind_of

TYPES = {
    "compare": ("So sánh theo nhóm", "Một chỉ số (tổng, trung bình...) chia theo một hoặc hai biến phân loại"),
    "trend": ("Xu hướng theo thời gian", "Chỉ số theo ngày, tuần, tháng, quý hoặc năm"),
    "cross": ("Chéo hai biến phân loại", "Bảng hàng × cột: nhóm nào đi cùng nhóm nào"),
    "correlate": ("Tương quan hai biến số", "Hai biến số có đi cùng nhau không"),
    "distribution": ("Phân bố một biến", "Giá trị của biến tập trung ở đâu"),
}
AGGS = {"sum": "Tổng", "mean": "Trung bình", "median": "Trung vị", "count": "Đếm", "nunique": "Đếm giá trị khác nhau", "min": "Nhỏ nhất", "max": "Lớn nhất"}
GRAINS = {"day": "ngày", "week": "tuần", "month": "tháng", "quarter": "quý", "year": "năm"}
MAX_BY, MAX_MEAS, MAX_ROWS = 2, 3, 30
DIM_MAX_UNIQUE = 60            # biến phân loại dùng để chia nhóm: tối đa ngần này giá trị khác nhau


# ------------------------------------------------------------------ cột của dữ liệu --
def columns_meta(clean):
    """Danh sách cột cho giao diện chọn biến: [{file, rows, cols:[{name,label,kind,kind_label,unique,missing,unit,avg,top}]}]."""
    out = []
    for fname, d in (clean or {}).items():
        cols = []
        for c in d.columns:
            s = d[c]
            kind, v, _ = kind_of(c, s)
            if kind == "empty" or str(c).endswith("_nghi_van"):
                continue
            ent = {"name": str(c), "label": lb.label(c), "kind": kind, "kind_label": KIND_LABEL[kind], "unique": int(s.nunique(dropna=True)),
                   "missing": int(s.isna().sum()), "unit": lb.unit(c), "avg": bool(lb.is_rate(c))}
            if kind == "cat":
                ent["top"] = [str(x) for x in s.dropna().astype(str).value_counts().head(3).index]
            cols.append(ent)
        out.append({"file": fname, "rows": int(len(d)), "cols": cols})
    return out


def _find_col(d, name):
    """Tìm cột theo tên đúng, không phân biệt hoa/thường, không dấu hoặc theo nhãn tiếng Việt. Trả về tên cột thật hoặc None."""
    if name is None:
        return None
    n = str(name).strip()
    if n in d.columns:
        return n
    low = {str(c).lower(): c for c in d.columns}
    if n.lower() in low:
        return low[n.lower()]
    fold = {lb.fold(c): c for c in d.columns}
    if lb.fold(n) in fold:
        return fold[lb.fold(n)]
    byl = {lb.fold(lb.label(c)): c for c in d.columns}
    return byl.get(lb.fold(n))


def _kinds(d, col):
    return kind_of(col, d[col])[0]


def _is_dim(d, col):
    k = _kinds(d, col)
    u = int(d[col].nunique(dropna=True))
    return (k == "cat" or (k == "num" and u <= 20)) and 2 <= u <= DIM_MAX_UNIQUE


def _is_meas(d, col):
    return _kinds(d, col) == "num"


def _is_time(d, col):
    return _kinds(d, col) == "date"


def _pick_file(clean, spec):
    f = spec.get("file")
    if f in clean:
        return f
    if len(clean) == 1:
        return next(iter(clean))
    want = [spec.get("x"), spec.get("y"), spec.get("col"), (spec.get("time") or {}).get("col")] + list(spec.get("by") or []) + [m.get("col") for m in spec.get("measures") or [] if isinstance(m, dict)]
    want = [w for w in want if w]
    best = max(clean, key=lambda n: sum(_find_col(clean[n], w) is not None for w in want)) if want else None
    return best


# ------------------------------------------------------------------ kiểm tra & chuẩn hóa --
def normalize(spec, clean):
    """Trả về (spec chuẩn hóa, lỗi). lỗi = None nếu hợp lệ, ngược lại là câu tiếng Việt giải thích để hiện cho người dùng."""
    if not isinstance(spec, dict):
        return None, "Yêu cầu không hợp lệ."
    t = spec.get("type")
    if t == "free":
        txt = str(spec.get("text") or "").strip()
        return ({"type": "free", "text": txt[:600], "title": txt[:70] or "Yêu cầu riêng", "goal": txt[:600], "vars": []}, None) if txt else (None, "Yêu cầu trống.")
    if t not in TYPES:
        return None, "Chưa chọn kiểu phân tích."
    f = _pick_file(clean, spec)
    if f is None or f not in clean:
        return None, "Chưa chọn bảng dữ liệu."
    d = clean[f]
    out = {"type": t, "file": f}

    def col(name, what, ok, need):
        c = _find_col(d, name)
        if c is None:
            raise ValueError(f"Không thấy cột «{name}» trong bảng {f}." if name else f"Chưa chọn {what}.")
        if not ok(d, c):
            raise ValueError(f"Cột «{lb.label(c)}» là biến {KIND_LABEL[_kinds(d, c)].lower()}, không dùng làm {what} được ({need}).")
        return c

    try:
        if t in ("compare", "trend", "cross"):
            ms = []
            for m in (spec.get("measures") or [])[:MAX_MEAS]:
                if not isinstance(m, dict):
                    continue
                agg = m.get("agg") if m.get("agg") in AGGS else "sum"
                if m.get("col") in (None, "", "*"):
                    ms.append({"col": None, "agg": "count"})
                else:
                    c = col(m.get("col"), "chỉ số", _is_meas, "cần biến định lượng")
                    ms.append({"col": c, "agg": agg})
            if not ms:
                ms = [{"col": None, "agg": "count"}]
            seen, uniq = set(), []
            for m in ms:
                k = (m["col"], m["agg"])
                if k not in seen:
                    seen.add(k)
                    uniq.append(m)
            out["measures"] = uniq
        if t == "compare":
            by = [col(b, "biến chia nhóm", _is_dim, "cần biến phân loại có từ 2 đến 60 giá trị") for b in (spec.get("by") or [])[:MAX_BY] if b]
            if not by:
                raise ValueError("Chưa chọn biến để chia nhóm.")
            out["by"] = list(dict.fromkeys(by))
        elif t == "trend":
            tm = spec.get("time") or {}
            out["time"] = {"col": col(tm.get("col"), "cột thời gian", _is_time, "cần biến thời gian"), "grain": tm.get("grain") if tm.get("grain") in GRAINS else "month"}
            by = [col(b, "biến tách đường", _is_dim, "cần biến phân loại") for b in (spec.get("by") or [])[:1] if b]
            out["by"] = by
        elif t == "cross":
            by = [col(b, "biến phân loại", _is_dim, "cần biến phân loại") for b in (spec.get("by") or [])[:2] if b]
            by = list(dict.fromkeys(by))
            if len(by) < 2:
                raise ValueError("Cần chọn đủ hai biến phân loại khác nhau (một cho hàng, một cho cột).")
            out["by"] = by
            out["measures"] = out["measures"][:1]
        elif t == "correlate":
            x = col(spec.get("x"), "biến X", _is_meas, "cần biến định lượng")
            y = col(spec.get("y"), "biến Y", _is_meas, "cần biến định lượng")
            if x == y:
                raise ValueError("Hai biến phải khác nhau.")
            out["x"], out["y"] = x, y
        elif t == "distribution":
            c = col(spec.get("col"), "biến cần xem phân bố", lambda dd, cc: _kinds(dd, cc) in ("num", "cat"), "cần biến định lượng hoặc phân loại")
            out["col"] = c
    except ValueError as e:
        return None, str(e)
    title, goal = describe(out)
    out.update(title=title, goal=goal, vars=used_vars(out))
    return out, None


def used_vars(sp):
    v = []
    for m in sp.get("measures") or []:
        if m.get("col"):
            v.append(m["col"])
    v += list(sp.get("by") or [])
    if sp.get("time"):
        v.append(sp["time"]["col"])
    for k in ("x", "y", "col"):
        if sp.get(k):
            v.append(sp[k])
    return list(dict.fromkeys(v))


# ------------------------------------------------------------------ mô tả bằng lời --
def _mname(m):
    if not m.get("col"):
        return "Số bản ghi"
    base = lb.label(m["col"])
    low = base[:1].lower() + base[1:]
    a = m["agg"]
    if a == "sum":
        return base if re.match(r"(?i)^(tổng|số)(\s|$)", base) else f"Tổng {low}"
    if a == "mean":
        return base if re.match(r"(?i)^trung bình", base) else f"Trung bình {low}"
    if a == "median":
        return f"Trung vị {low}"
    if a == "count":
        return f"Số bản ghi có {low}"
    if a == "nunique":
        return f"Số {low} khác nhau"
    return f"{AGGS[a]} {low}"


def _mnames(ms):
    names, seen = [], {}
    for m in ms:
        n = _mname(m)
        seen[n] = seen.get(n, 0) + 1
        names.append(n if seen[n] == 1 else f"{n} ({seen[n]})")
    return names


def describe(sp):
    """(tiêu đề ngắn, một câu mô tả) của spec."""
    t = sp["type"]
    ms = _mnames(sp.get("measures") or [])
    lab = lambda c: lb.label(c)                          # noqa: E731
    if t == "compare":
        by = " và ".join(lab(b) for b in sp["by"])
        mm = ", ".join(ms)
        sums = [m for m in sp["measures"] if m["agg"] in ("sum",) or not m.get("col")]
        return (f"{mm} theo {by.lower()}", f"So sánh {mm.lower()} giữa các nhóm {by}; xếp giảm dần theo chỉ số đầu tiên"
                + (", kèm tỷ trọng (%) trên tổng." if sums else "."))
    if t == "trend":
        g = GRAINS[sp["time"]["grain"]]
        sp_by = f", tách theo {lab(sp['by'][0]).lower()} (tối đa 5 nhóm lớn nhất)" if sp.get("by") else ""
        return (f"{ms[0]} theo {g}" + (f" và {lab(sp['by'][0]).lower()}" if sp.get("by") else ""),
                f"Diễn biến {ms[0].lower()} theo {g} dựa trên cột {lab(sp['time']['col'])}{sp_by}; kèm % thay đổi so với kỳ trước.")
    if t == "cross":
        a, b = sp["by"]
        return (f"{ms[0]}: {lab(a).lower()} × {lab(b).lower()}", f"Bảng chéo: hàng là {lab(a)}, cột là {lab(b)}, ô là {ms[0].lower()}.")
    if t == "correlate":
        return (f"{lab(sp['x'])} và {lab(sp['y']).lower()}", f"Chia {lab(sp['x'])} thành 10 nhóm bằng nhau về số bản ghi rồi xem {lab(sp['y'])} trung bình của từng nhóm; kèm hệ số tương quan.")
    if t == "distribution":
        return (f"Phân bố {lab(sp['col']).lower()}", f"Số bản ghi theo từng khoảng giá trị (hoặc từng giá trị) của {lab(sp['col'])}.")
    return ("Yêu cầu riêng", "")


# ------------------------------------------------------------------ sinh code --
def _q(s):
    return repr(str(s))


def _agg_name(a):
    return {"sum": "sum", "mean": "mean", "median": "median", "count": "count", "nunique": "nunique", "min": "min", "max": "max"}[a]


def _num_fmt(d, c):
    """Số chữ số thập phân khi in ranh giới khoảng, theo độ lớn của dữ liệu."""
    v = pd.to_numeric(d[c], errors="coerce").dropna()
    if not len(v):
        return 0
    m = float(max(abs(v.min()), abs(v.max())))
    return 0 if m >= 100 else 1 if m >= 10 else 2


def build_code(sp, clean):
    """Code pandas cho spec (đã chuẩn hóa). Đọc được, có chú thích; kết quả gán vào `result`."""
    t, f = sp["type"], sp.get("file")
    one = lambda t: " ".join(str(t).split())                 # một dòng: tên cột lạ có thể chứa xuống dòng, không để nó thoát khỏi comment  # noqa: E731
    L = [f"# {one(sp['title'])}", f"# {one(sp['goal'])}", f"df = dfs[{_q(f)}]"]
    ms = sp.get("measures") or []
    names = _mnames(ms)

    def meas_frame(prefix_cols):
        """DataFrame x gồm các cột khóa + v0..vn (đã ép số)."""
        L.append("x = pd.DataFrame({")
        for k, v in prefix_cols:
            L.append(f"    {_q(k)}: {v},")
        for j, m in enumerate(ms):
            L.append(f"    'v{j}': " + (f"pd.to_numeric(df[{_q(m['col'])}], errors='coerce')," if m.get("col") else "1,"))
        L.append("})")

    def eff(j):
        m = ms[j]
        return "sum" if not m.get("col") else _agg_name(m["agg"])

    if t == "compare":
        by = sp["by"]
        meas_frame([(f"k{i}", f"df[{_q(b)}]") for i, b in enumerate(by)])
        keys = [f"k{i}" for i in range(len(by))]
        has_rows = any(not m.get("col") for m in ms)             # đã có chỉ số "Số bản ghi" thì không thêm cột đếm nữa (tránh trùng tên)
        aggs = ", ".join(f"a{j}=('v{j}', {_q(eff(j))})" for j in range(len(ms))) + ("" if has_rows else ", n=('v0', 'size')")
        L.append(f"g = x.groupby({keys!r}).agg({aggs}).reset_index()")
        L.append("g = g.sort_values('a0', ascending=False)")
        share = eff(0) == "sum"
        if share:
            L.append("g['share'] = (g['a0'] / g['a0'].sum() * 100).round(2)")
        L.append(f"g = g.head({MAX_ROWS})")
        ren = {**{f"k{i}": lb.label(b) for i, b in enumerate(by)}, **{f"a{j}": names[j] for j in range(len(ms))}, "share": "Tỷ trọng (%)", "n": "Số bản ghi"}
        order = [lb.label(b) for b in by] + names + (["Tỷ trọng (%)"] if share else []) + ([] if has_rows else ["Số bản ghi"])
        L.append(f"result = g.rename(columns={ren!r})[{order!r}].round(2).reset_index(drop=True)")
    elif t == "trend":
        tc, grain = sp["time"]["col"], sp["time"]["grain"]
        fr = {"day": "D", "week": "W", "month": "M", "quarter": "Q", "year": "Y"}[grain]
        fmt = {"day": "%Y-%m-%d", "week": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}.get(grain)
        L.append(f"t = pd.to_datetime(df[{_q(tc)}], errors='coerce', format='mixed')")
        by = sp.get("by") or []
        cols = [("t", f"t.dt.to_period({_q(fr)})")] + ([("k0", f"df[{_q(by[0])}]")] if by else [])
        meas_frame(cols)
        L.append("x = x.dropna(subset=['t'])")
        # nhãn kỳ: dùng hàm vectorized trên PeriodIndex (thuộc tính từng phần tử như Period.start_time cần __import__, mà sandbox không có)
        lab_idx = lambda v: (f"[f'Q{{p.quarter}}/{{p.year}}' for p in {v}]" if grain == "quarter"           # noqa: E731
                             else f"{v}.to_timestamp().strftime({_q(fmt)})" if grain == "week" else f"{v}.strftime({_q(fmt)})")
        period_name = "Kỳ (" + GRAINS[grain] + ")"
        if not by:
            has_rows = any(not m.get("col") for m in ms)
            aggs = ", ".join(f"a{j}=('v{j}', {_q(eff(j))})" for j in range(len(ms))) + ("" if has_rows else ", n=('v0', 'size')")
            L.append(f"g = x.groupby('t').agg({aggs}).sort_index()")
            L.append("g['chg'] = (g['a0'].pct_change() * 100).round(2)")
            L.append(f"g.index = {lab_idx('g.index')}")
            ren = {"index": period_name, "t": period_name, **{f"a{j}": names[j] for j in range(len(ms))}, "chg": "% thay đổi so với kỳ trước", "n": "Số bản ghi"}
            L.append(f"result = g.reset_index().rename(columns={ren!r}).round(2).reset_index(drop=True)")
        else:
            L.append("top = x.groupby('k0')['v0'].agg('sum').sort_values(ascending=False).head(5).index")
            L.append(f"w = x[x['k0'].isin(top)].pivot_table(index='t', columns='k0', values='v0', aggfunc={_q(eff(0))}).sort_index()")
            if eff(0) in ("sum",):
                L.append("w['Tổng'] = w.sum(axis=1)")
            L.append("w.columns = [str(c) for c in w.columns]")
            L.append(f"w.index = {lab_idx('w.index')}")
            L.append(f"result = w.reset_index().rename(columns={{'index': {_q(period_name)}, 't': {_q(period_name)}}}).round(2).reset_index(drop=True)")
    elif t == "cross":
        a, b = sp["by"]
        meas_frame([("r", f"df[{_q(a)}]"), ("c", f"df[{_q(b)}]")])
        L.append("rows_top = x['r'].value_counts().head(12).index")
        L.append("cols_top = x['c'].value_counts().head(8).index")
        L.append("x = x[x['r'].isin(rows_top) & x['c'].isin(cols_top)]")
        L.append(f"w = x.pivot_table(index='r', columns='c', values='v0', aggfunc={_q(eff(0))}).fillna(0)")
        L.append("w.columns = [str(c) for c in w.columns]")
        L.append(f"result = w.reset_index().rename(columns={{'r': {_q(lb.label(a))}}}).round(2).reset_index(drop=True)")
    elif t == "correlate":
        xc, yc = sp["x"], sp["y"]
        nd = _num_fmt(clean[f], xc)
        L.append(f"x = pd.DataFrame({{'x': pd.to_numeric(df[{_q(xc)}], errors='coerce'), 'y': pd.to_numeric(df[{_q(yc)}], errors='coerce')}}).dropna()")
        L.append("x['bin'] = pd.qcut(x['x'], q=10, duplicates='drop')")
        L.append("g = x.groupby('bin', observed=True).agg(xm=('x', 'mean'), ym=('y', 'mean'), n=('y', 'size')).reset_index()")
        L.append(f"g['rng'] = [f'{{b.left:,.{nd}f}} – {{b.right:,.{nd}f}}'.replace(',', '.') for b in g['bin']]")
        ren = {"rng": f"Khoảng {lb.label(xc)}", "xm": f"{lb.label(xc)} trung bình", "ym": f"{lb.label(yc)} trung bình", "n": "Số bản ghi"}
        L.append(f"result = g[['rng', 'xm', 'ym', 'n']].rename(columns={ren!r}).round(2)")
    elif t == "distribution":
        c = sp["col"]
        # tính tỷ lệ bằng phép chia trên Series của pandas (chia thẳng trên mảng numpy .values bị sandbox chặn ở một số bản numpy/pandas)
        if _kinds(clean[f], c) == "num" and clean[f][c].nunique() > 12:
            nd = _num_fmt(clean[f], c)
            L.append(f"v = pd.to_numeric(df[{_q(c)}], errors='coerce').dropna()")
            L.append("cnt = pd.cut(v, bins=12).value_counts(sort=False)")
            L.append(f"labs = [f'{{b.left:,.{nd}f}} – {{b.right:,.{nd}f}}'.replace(',', '.') for b in cnt.index]")
            L.append(f"r = pd.DataFrame({{{_q('Khoảng ' + lb.label(c))}: labs, 'Số bản ghi': cnt.values}})")
            L.append("r['Tỷ lệ (%)'] = (r['Số bản ghi'] / r['Số bản ghi'].sum() * 100).round(2)")
            L.append("result = r")
        else:
            L.append(f"vc = df[{_q(c)}].dropna().value_counts()")
            L.append("r = vc.head(20).reset_index()")
            L.append(f"r.columns = [{_q(lb.label(c))}, 'Số bản ghi']")
            L.append("r['Tỷ lệ (%)'] = (r['Số bản ghi'] / vc.sum() * 100).round(2)")
            L.append("result = r")
    else:
        raise ValueError("Loại phân tích không sinh được code trực tiếp.")
    return "\n".join(L)


def spec_facts(sp, clean):
    """Vài con số kèm kết quả mà bảng không tự thể hiện (hiện hệ số tương quan của spec 'correlate')."""
    if sp.get("type") != "correlate" or sp.get("file") not in clean:
        return []
    d = clean[sp["file"]]
    x = pd.DataFrame({"x": pd.to_numeric(d[sp["x"]], errors="coerce"), "y": pd.to_numeric(d[sp["y"]], errors="coerce")}).dropna()
    if len(x) < 8 or x["x"].nunique() < 2 or x["y"].nunique() < 2:
        return ["Chưa đủ dữ liệu để tính hệ số tương quan."]
    r = float(x["x"].corr(x["y"]))
    a = abs(r)
    lvl = "rất yếu hoặc không có" if a < .2 else "yếu" if a < .4 else "trung bình" if a < .6 else "mạnh" if a < .8 else "rất mạnh"
    dr = "thuận (cùng tăng)" if r > 0 else "nghịch (một bên tăng, bên kia giảm)"
    n = f"{len(x):,}".replace(",", ".")
    txt = f"Hệ số tương quan Pearson r = {r:.2f}".replace(".", ",", 1) + f" trên {n} bản ghi: tương quan {lvl}"
    return [txt + ("" if a < .2 else f", chiều {dr}") + ". Tương quan không đồng nghĩa nhân quả."]


# ------------------------------------------------------------------ biến được dùng trong một đoạn code bất kỳ --
def vars_in_code(code, clean):
    """Cột (của mọi bảng) được nhắc tới trong code dưới dạng chuỗi 'tên cột' hoặc "tên cột": để giao diện hiện 'Biến dùng' cho cả code do AI viết."""
    found = []
    quoted = set(re.findall(r"""['"]([^'"\n]{1,80})['"]""", code or ""))
    for d in (clean or {}).values():
        for c in d.columns:
            if str(c) in quoted and str(c) not in found and not str(c).endswith("_nghi_van"):
                found.append(str(c))
    return found[:12]


def vars_in_text(text, clean):
    """Cột được nhắc tới trong một đoạn chữ (tên cột hoặc nhãn tiếng Việt, không phân biệt hoa/thường): để hiện 'Biến dùng' cho các đề xuất của AI."""
    t = " " + lb.fold(text or "") + " "
    found = []
    for d in (clean or {}).values():
        for c in d.columns:
            for nm in {lb.fold(c), lb.fold(lb.label(c))}:
                if len(nm) >= 3 and re.search(r"(?<![a-z0-9_])" + re.escape(nm) + r"(?![a-z0-9_])", t) and str(c) not in found and not str(c).endswith("_nghi_van"):
                    found.append(str(c))
                    break
    return found[:8]


def data_words(clean, per_col=200):
    """Giá trị thật của các cột phân loại (HCM, Online, SP-A...): kết quả pivot lấy chúng làm TÊN CỘT, không được coi là 'tên tiếng Anh' rồi dịch nhầm."""
    out = set()
    for d in (clean or {}).values():
        for c in d.columns:
            s = d[c]
            if not (pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s)) and s.nunique(dropna=True) <= per_col:
                out.update(str(v).strip() for v in s.dropna().unique())
    return out
