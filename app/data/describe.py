# -*- coding: utf-8 -*-
"""Mô tả PHÂN BỐ từng biến (bước 2: Kiểm tra và mô tả dữ liệu), do CODE tính, không nhờ AI.

 - Biến ĐỊNH LƯỢNG (num): histogram + thống kê (nhỏ nhất, Q1, trung vị, trung bình, Q3, lớn nhất, độ lệch chuẩn) + hình dạng phân bố.
 - Biến PHÂN LOẠI (cat): giá trị duy nhất kèm số lần và tỷ lệ (tối đa TOP giá trị, phần còn lại gộp "khác").
 - Biến THỜI GIAN (date): số bản ghi theo ngày / tháng / năm tùy độ dài khoảng thời gian.
 - Mã định danh (id) và cột chữ dài (text): chỉ nêu số giá trị duy nhất và ví dụ, không vẽ biểu đồ (vẽ ra không có nghĩa).
Chạy trên dữ liệu đang dùng (có thể còn bẩn: số lưu dạng chữ, ngày lưu dạng chữ) nên có bước nhận diện lại kiểu thật của cột."""
import numpy as np
import pandas as pd

from .. import labels as lb
from .quality import date_like, is_text, to_dt

MAX_COLS = 60          # tối đa số cột mô tả cho mỗi bảng (bảng quá rộng: bỏ các cột cuối, ghi rõ số cột bị bỏ)
TOP = 10               # số giá trị duy nhất hiển thị của biến phân loại
BINS = 20              # số khoảng tối đa của histogram
DISCRETE_MAX = 20      # số nguyên có ≤ ngần này giá trị khác nhau: mỗi giá trị một cột (vd số lượng 1..7)
CAT_MAX = 50           # văn bản có ≤ ngần này giá trị khác nhau luôn là phân loại

KIND_LABEL = {"num": "Định lượng", "cat": "Phân loại", "date": "Thời gian", "id": "Mã / định danh", "text": "Văn bản", "empty": "Trống"}


def _f(x, nd=4):
    """Số thực gọn, an toàn cho JSON (NaN/inf -> None)."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if np.isfinite(x) else None


def _as_number(s):
    """Cột chữ nhưng thực chất là số ('1,234', '12.5'): trả về chuỗi số, nếu không phải thì trả None."""
    if not is_text(s) or pd.api.types.is_datetime64_any_dtype(s):
        return None
    t = s.dropna().astype(str)
    if len(t) < 3:
        return None
    n = pd.to_numeric(t.str.replace(r"[,\s]", "", regex=True), errors="coerce")
    if n.notna().mean() < .9:
        return None
    return pd.to_numeric(s.astype(str).str.replace(r"[,\s]", "", regex=True), errors="coerce")


def kind_of(name, s):
    """Trả về (kiểu, chuỗi đã chuẩn hóa dùng để tính, ghi chú). Kiểu: num | cat | date | id | text | empty."""
    n = int(s.notna().sum())
    if n == 0:
        return "empty", s, ""
    if pd.api.types.is_bool_dtype(s):
        return "cat", s.astype(object), ""
    if pd.api.types.is_datetime64_any_dtype(s):
        return "date", s, ""
    u = int(s.nunique(dropna=True))
    num = s if pd.api.types.is_numeric_dtype(s) else _as_number(s)
    if num is not None:
        k = int(num.nunique(dropna=True))
        nn = int(num.notna().sum())
        is_int = bool(((num.dropna() % 1) == 0).all()) if nn else False
        if lb.is_id(name):
            return "id", s, ""
        if is_int and nn > 20 and k > .95 * nn and not lb.unit(name) and not lb.is_rate(name):
            return "id", s, "Số nguyên gần như không lặp, nhiều khả năng là mã định danh"
        if k <= 2:
            return "cat", num.astype(object), ""
        return "num", num, "" if pd.api.types.is_numeric_dtype(s) else "Đang lưu dạng chữ; đã đọc thành số để thống kê"
    if is_text(s) and date_like(s):
        d = to_dt(s)
        if d.notna().mean() > .8:
            return "date", d, "Đang lưu dạng chữ; đã đọc thành ngày để thống kê"
    if lb.is_id(name):
        return "id", s, ""
    if u <= CAT_MAX or u <= .5 * n:
        return "cat", s, ""
    if u > .9 * n:
        return "id", s, "Gần như mỗi dòng một giá trị riêng, nhiều khả năng là mã định danh"
    return "text", s, ""


def _shape(skew, n):
    if n < 8 or skew is None:
        return ""
    if abs(skew) < .5:
        return "Gần đối xứng"
    if skew >= 1.5:
        return "Lệch phải mạnh: đa số giá trị nhỏ, vài giá trị rất lớn kéo trung bình lên"
    if skew > 0:
        return "Lệch phải: đuôi dài về phía giá trị lớn"
    if skew <= -1.5:
        return "Lệch trái mạnh: đa số giá trị lớn, vài giá trị rất nhỏ kéo trung bình xuống"
    return "Lệch trái: đuôi dài về phía giá trị nhỏ"


def _hist(v):
    """Histogram. Số nguyên ít giá trị -> mỗi giá trị một cột. Phân bố có đuôi cực dài -> cắt ở p1..p99 để thân phân bố không bị dẹt (ghi rõ số giá trị bị cắt)."""
    uniq = np.unique(v)
    if len(uniq) <= DISCRETE_MAX and bool(np.all(uniq % 1 == 0)):
        cnt = [int((v == u).sum()) for u in uniq]
        return {"discrete": True, "labels": [int(u) for u in uniq], "counts": cnt}
    lo, hi = float(v.min()), float(v.max())
    p1, p99 = np.percentile(v, [1, 99])
    trim = {"low": 0, "high": 0}
    if p99 > p1 and (hi - lo) > 8 * (p99 - p1):
        trim = {"low": int((v < p1).sum()), "high": int((v > p99).sum())}
        v = v[(v >= p1) & (v <= p99)]
        lo, hi = float(p1), float(p99)
    k = int(min(BINS, max(6, round(np.sqrt(len(v))))))
    cnt, edges = np.histogram(v, bins=k, range=(lo, hi if hi > lo else lo + 1))
    return {"discrete": False, "edges": [_f(e, 6) for e in edges], "counts": [int(c) for c in cnt], "trim": trim}


def _num_col(name, num):
    v = num.dropna().to_numpy(dtype=float)
    v = v[np.isfinite(v)]
    if not len(v):
        return {}
    q1, med, q3 = np.percentile(v, [25, 50, 75])
    sk = float(pd.Series(v).skew()) if len(v) >= 8 and np.std(v) > 0 else None
    iqr = q3 - q1
    out = int(((v < q1 - 1.5 * iqr) | (v > q3 + 1.5 * iqr)).sum()) if iqr > 0 else 0
    return {"stats": {"min": _f(v.min()), "q1": _f(q1), "median": _f(med), "mean": _f(v.mean()), "q3": _f(q3), "max": _f(v.max()),
                      "std": _f(v.std(ddof=1)) if len(v) > 1 else None, "sum": _f(v.sum())},
            "hist": _hist(v), "shape": _shape(sk, len(v)), "outliers": out, "negative": int((v < 0).sum()), "zero": int((v == 0).sum())}


def _cat_col(s):
    t = s.dropna()
    vc = t.value_counts()
    total = int(len(t))
    top = [[str(k), int(c)] for k, c in vc.head(TOP).items()]
    rest = int(vc.iloc[TOP:].sum()) if len(vc) > TOP else 0
    return {"top": top, "rest": rest, "rest_n": max(0, len(vc) - TOP), "total": total,
            "top_share": _f(vc.iloc[0] / total, 4) if total else None,
            "single": bool(len(vc) == 1)}


def _date_col(d):
    t = d.dropna()
    lo, hi = t.min(), t.max()
    span = (hi - lo).days
    if span <= 62:
        g, fmt, unit = t.dt.floor("D"), "%d/%m", "ngày"
    elif span <= 800:
        g, fmt, unit = t.dt.to_period("M").dt.to_timestamp(), "%m/%Y", "tháng"
    else:
        g, fmt, unit = t.dt.to_period("Y").dt.to_timestamp(), "%Y", "năm"
    vc = g.value_counts().sort_index()
    if unit == "ngày" and len(vc) > 40:
        vc = vc.iloc[-40:]
    return {"min": lo.strftime("%d/%m/%Y"), "max": hi.strftime("%d/%m/%Y"), "span_days": int(span), "unit": unit,
            "labels": [k.strftime(fmt) for k in vc.index], "counts": [int(c) for c in vc.values],
            "gaps": int(max(0, pd.date_range(g.min(), g.max(), freq={"ngày": "D", "tháng": "MS", "năm": "YS"}[unit]).size - len(vc))) if len(vc) else 0}


def describe_col(name, s):
    kind, v, note = kind_of(name, s)
    n = int(s.notna().sum())
    out = {"col": str(name), "label": lb.label(name), "kind": kind, "type": str(s.dtype), "n": n, "missing": int(s.isna().sum()),
           "unique": int(s.nunique(dropna=True)), "note": note}
    try:
        if kind == "num":
            out.update(_num_col(name, v))
        elif kind == "cat":
            out.update(_cat_col(v if isinstance(v, pd.Series) else s))
        elif kind == "date":
            out.update(_date_col(v if pd.api.types.is_datetime64_any_dtype(v) else to_dt(v)))
        elif kind in ("id", "text"):
            out["sample"] = [str(x) for x in s.dropna().astype(str).head(3)]
    except Exception as e:                                   # noqa: BLE001  một cột lỗi không được làm hỏng cả bước mô tả
        out["kind"], out["note"] = "text", f"Không mô tả được phân bố: {type(e).__name__}"
        out["sample"] = [str(x) for x in s.dropna().astype(str).head(3)]
    return out


def distributions(dfs):
    """[{file, rows, cols:[...], skipped}] cho mọi bảng."""
    res = []
    for name, d in dfs.items():
        cols = [describe_col(c, d[c]) for c in list(d.columns)[:MAX_COLS]]
        res.append({"file": name, "rows": int(len(d)), "cols": cols, "skipped": max(0, d.shape[1] - MAX_COLS)})
    return res


def counts(dist):
    """Đếm số biến theo kiểu để hiện trên bộ lọc: {'num': 5, 'cat': 6, ...}."""
    out = {}
    for f in dist:
        for c in f["cols"]:
            out[c["kind"]] = out.get(c["kind"], 0) + 1
    return out


def brief(dist, limit=3500):
    """Tóm tắt phân bố thành vài dòng chữ để đưa cho AI nhận định (hình dạng, độ lệch, nhóm áp đảo...)."""
    lines = []
    for f in dist:
        lines.append(f"[{f['file']}] {f['rows']} dòng")
        for c in f["cols"]:
            k = c["kind"]
            h = f"- {c['col']} ({KIND_LABEL[k]}; {c['unique']} giá trị khác nhau; thiếu {c['missing']})"
            if k == "num" and c.get("stats"):
                s = c["stats"]
                h += f": min {s['min']}, trung vị {s['median']}, TB {s['mean']}, max {s['max']}; {c['shape'] or 'ít dữ liệu'}; ngoại lai IQR {c['outliers']}"
            elif k == "cat" and c.get("top"):
                h += ": " + ", ".join(f"{a} {b}" for a, b in c["top"][:4]) + (f" ... (+{c['rest_n']} giá trị)" if c["rest_n"] else "")
            elif k == "date" and c.get("min"):
                h += f": {c['min']} → {c['max']}"
            lines.append(h)
    return "\n".join(lines)[:limit]
