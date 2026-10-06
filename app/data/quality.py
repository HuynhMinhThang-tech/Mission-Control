# -*- coding: utf-8 -*-
"""Mô tả dữ liệu + quét vấn đề chất lượng."""
import pandas as pd

from ..utils import vn  # noqa: F401  (giữ để các agent import chung)


def to_dt(s):
    try:
        return pd.to_datetime(s, errors="coerce", format="mixed")
    except (TypeError, ValueError):
        return pd.to_datetime(s, errors="coerce")


def is_text(s):
    return not (pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s) or pd.api.types.is_bool_dtype(s))


def date_like(s):
    t = s.dropna().astype(str).head(50)
    return len(t) > 0 and t.str.contains(r"[-/]").mean() > 0.8 and to_dt(t).notna().mean() > 0.8


def schema(dfs, sample=3):
    return {n: {"shape": list(d.shape), "columns": {c: str(d[c].dtype) for c in d.columns},
                "sample": d.head(sample).astype(str).to_dict("records")} for n, d in dfs.items()}


def profile_rows(dfs):
    return [{"file": n, "shape": list(d.shape),
             "rows": [[c, str(d[c].dtype), int(d[c].isna().sum()), round(float(d[c].isna().mean() * 100), 1), int(d[c].nunique()),
                       ", ".join(d[c].dropna().astype(str).head(3))] for c in d.columns]} for n, d in dfs.items()]


def date_range(dfs):
    for n, d in dfs.items():
        for c in d.columns:
            s = d[c]
            t = s if pd.api.types.is_datetime64_any_dtype(s) else (to_dt(s) if is_text(s) and date_like(s) else None)
            if t is not None and t.notna().any():
                return f"{t.min():%d/%m/%Y} → {t.max():%d/%m/%Y}"
    return None


def join_info(dfs):
    best = None
    names = list(dfs)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            big, small = (a, b) if len(dfs[a]) >= len(dfs[b]) else (b, a)
            for c in set(dfs[a].columns) & set(dfs[b].columns):
                if not dfs[small][c].is_unique or dfs[small][c].nunique() < 2:
                    continue
                m = float(dfs[big][c].dropna().isin(set(dfs[small][c].dropna())).mean() * 100)
                key = dfs[small][c].nunique()  # ưu tiên khóa có nhiều giá trị (vd customer_id)
                if best is None or key > best[4]:
                    best = (big, small, c, m, key)
    return best


CAT = {"Giá trị thiếu": "Thiếu", "Dòng trùng lặp": "Trùng", "Thừa khoảng trắng": "Định dạng", "Không nhất quán hoa/thường": "Định dạng",
       "Số đang lưu dạng text": "Định dạng", "Ngày đang lưu dạng text": "Định dạng", "Ngày sai định dạng": "Định dạng",
       "Ngoại lai (IQR)": "Ngoại lai", "Giá trị âm": "Giá trị âm"}


def quality(dfs):
    rows = []

    def add(f, c, i, n):
        rows.append({"file": f, "col": str(c), "issue": i, "n": int(n)})

    for n, d in dfs.items():
        if d.duplicated().sum():
            add(n, "(toàn bảng)", "Dòng trùng lặp", d.duplicated().sum())
        for c in d.columns:
            s = d[c]
            if s.isna().sum():
                add(n, c, "Giá trị thiếu", s.isna().sum())
            if is_text(s) and not pd.api.types.is_datetime64_any_dtype(s):
                t = s.dropna().astype(str)
                if len(t) == 0:
                    continue
                if (t != t.str.strip()).any():
                    add(n, c, "Thừa khoảng trắng", (t != t.str.strip()).sum())
                if t.nunique() != t.str.lower().str.strip().nunique():
                    add(n, c, "Không nhất quán hoa/thường", t.nunique() - t.str.lower().str.strip().nunique())
                if pd.to_numeric(t.str.replace(r"[,\s]", "", regex=True), errors="coerce").notna().mean() > 0.8:
                    add(n, c, "Số đang lưu dạng text", len(t))
                elif date_like(s):
                    shapes = t.str.replace(r"\d", "9", regex=True).value_counts()
                    if len(shapes) > 1:
                        add(n, c, "Ngày sai định dạng", len(t) - shapes.iloc[0])
                    else:
                        add(n, c, "Ngày đang lưu dạng text", len(t))
            elif pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
                q1, q3 = s.quantile(.25), s.quantile(.75)
                i = q3 - q1
                o = int(((s < q1 - 1.5 * i) | (s > q3 + 1.5 * i)).sum()) if i > 0 else 0
                if o:
                    add(n, c, "Ngoại lai (IQR)", o)
                if (s < 0).sum():
                    add(n, c, "Giá trị âm", (s < 0).sum())
    return pd.DataFrame(rows, columns=["file", "col", "issue", "n"])


def issue_counts(dfs):
    out = {k: 0 for k in ["Thiếu", "Trùng", "Định dạng", "Ngoại lai", "Giá trị âm"]}
    for r in quality(dfs).to_dict("records"):
        out[CAT[r["issue"]]] += r["n"]
    return out
