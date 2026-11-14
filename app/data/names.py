# -*- coding: utf-8 -*-
"""Mã -> tên. Báo cáo gọi đối tượng bằng TÊN (Điện thoại Viet-Tech Pro), không bằng MÃ (SP003).

Máy tự tìm các cặp «cột mã - cột tên» trong dữ liệu đã làm sạch (MaSP - TenSP, Mã khách - Tên khách...), không dùng từ khóa theo ngành:
  - cột mã: tên cột kiểu mã/id (labels.is_id), mỗi giá trị một lần, giá trị có cả chữ lẫn số (SP003, KH-012);
  - cột tên: cùng bảng, là chữ, gần như không trùng, tên cột có «tên/name»; ưu tiên cột chung danh từ với cột mã (SP ~ SP).
Dùng ở ba chỗ: (1) bảng kết quả phân tích: giá trị mã đổi thành tên; (2) văn bản AI viết: mã còn sót đổi thành tên;
(3) thẻ dữ liệu đưa cho AI: nói rõ mã nào là tên nào để AI không phải dùng mã.
"""
import re

import pandas as pd

from .. import labels as lb

MAX_CODES = 20000                                   # số mã tối đa lưu trong phiên (mã nào quá giới hạn thì giữ nguyên)
MIN_MATCH = 0.8                                     # một cột kết quả được coi là «cột mã» khi ít nhất 80% ô có trong bảng mã
_NAME_WORDS = {"ten", "name"}
# SP003, KH-012, DH_0001: bắt đầu bằng chữ, có cả chữ lẫn số. Mã chỉ gồm số (mã đơn 10234) thì KHÔNG thay vì dễ nhầm với số liệu.
_CODE_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z][A-Za-z0-9_\-./]{1,31}$")
_TOKEN_RE = re.compile(r"(?<![\w\-])[A-Za-z][A-Za-z0-9_\-]*\d[A-Za-z0-9_\-]*(?![\w\-])")


def _is_text(s):
    return pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)


def _noun(col):
    """Danh từ của tên cột (bỏ chữ mã/tên): MaSP -> {sp} · Tên sản phẩm -> {san, pham}."""
    return {t for t in lb.tokens(col) if t not in lb.ID_WORDS and t not in _NAME_WORDS}


def _name_col(df, key):
    """Cột tên đi kèm cột mã `key` trong bảng df, hoặc None."""
    best, best_score = None, 0
    for c in df.columns:
        if c == key or not _is_text(df[c]):
            continue
        toks = set(lb.tokens(c))
        if not (toks & _NAME_WORDS) or lb.is_id(c):
            continue
        s = df[c].dropna()
        if len(s) < 0.9 * len(df) or s.astype(str).str.strip().eq("").any() or s.nunique() < 0.8 * len(s):
            continue
        score = 3 + (2 if _noun(c) & _noun(key) else 0)
        if score > best_score:
            best, best_score = c, score
    return best


def code_names(clean):
    """{"map": {mã: tên}, "cols": {cột mã: cột tên}} từ các bảng đã làm sạch. Mã nào có tên trùng với mã khác thì bỏ (tránh gộp hai đối tượng làm một)."""
    out, cols = {}, {}
    for df in (clean or {}).values():
        if df is None or not hasattr(df, "columns"):
            continue
        for k in df.columns:
            if not lb.is_id(k) or not _is_text(df[k]):
                continue
            s = df[k].dropna().astype(str).str.strip()
            if len(s) < 2 or not s.is_unique or s.map(lambda v: bool(_CODE_RE.match(v))).mean() < 0.9:
                continue
            nc = _name_col(df, k)
            if nc is None:
                continue
            cols[str(k)] = str(nc)
            for code, name in zip(df[k].astype(str).str.strip(), df[nc].astype(str).str.strip()):
                if _CODE_RE.match(code) and name and name != code and len(out) < MAX_CODES:
                    out.setdefault(code, name)
    seen = {}
    for code, name in out.items():
        seen.setdefault(name.casefold(), []).append(code)
    out = {c: n for c, n in out.items() if len(seen[n.casefold()]) == 1}
    return {"map": out, "cols": {k: v for k, v in cols.items()}}


def decode_frame(df, names):
    """Bảng kết quả: cột nào gần như toàn là mã thì đổi giá trị thành tên; tiêu đề kiểu «Mã SP» đổi thành «Tên SP» nếu không trùng cột khác."""
    m = (names or {}).get("map") or {}
    if df is None or not hasattr(df, "columns") or not m:
        return df
    df, ren = df.copy(), {}
    for c in list(df.columns):
        if not _is_text(df[c]):
            continue
        s = df[c].dropna().astype(str).str.strip()
        if s.empty or s.isin(m).mean() < MIN_MATCH:
            continue
        df[c] = df[c].map(lambda v: m.get(str(v).strip(), v) if isinstance(v, str) else v)
        nc = (names.get("cols") or {}).get(str(c))
        new = lb.label(nc) if nc and lb.is_id(c) else None
        if new and new != c and new not in df.columns and new not in ren.values():
            ren[c] = new
    return df.rename(columns=ren) if ren else df


def decode_text(s, names):
    """Văn bản AI viết: mã còn sót đổi thành tên. «SP003 (Điện thoại X)» và «Điện thoại X (SP003)» đều thành «Điện thoại X», không lặp tên."""
    m = (names or {}).get("map") or {}
    if not m or not isinstance(s, str) or not s:
        return s
    found = {t for t in _TOKEN_RE.findall(s) if t in m}
    if not found:
        return s
    for code in found:
        n = re.escape(m[code])
        s = re.sub(rf"{n}\s*[\(\[]\s*{re.escape(code)}\s*[\)\]]", m[code], s)
        s = re.sub(rf"(?<![\w\-]){re.escape(code)}\s*[\(\[]\s*{n}\s*[\)\]]", lambda _m, v=m[code]: v, s)
    return _TOKEN_RE.sub(lambda t: m.get(t.group(0), t.group(0)), s)


def naming_note(clean, limit=3):
    """Câu cho thẻ dữ liệu: cột mã nào ứng với cột tên nào (kèm vài ví dụ) và quy tắc gọi tên. Rỗng nếu dữ liệu không có cặp mã - tên."""
    nm = code_names(clean)
    if not nm["cols"]:
        return ""
    parts = []
    for k, n in list(nm["cols"].items())[:limit]:
        ex = next(((c, v) for c, v in nm["map"].items() if c), None)
        for df in (clean or {}).values():
            if df is not None and hasattr(df, "columns") and k in df.columns and n in df.columns and len(df):
                r = df.dropna(subset=[k, n]).iloc[0]
                ex = (str(r[k]), str(r[n]))
                break
        parts.append(f"{k} -> {n}" + (f" (vd {ex[0]} = «{ex[1]}»)" if ex else ""))
    return ("QUY ƯỚC GỌI TÊN: " + "; ".join(parts) + ". Trong mọi câu chữ của báo cáo (tóm tắt, phát hiện, hành động, nhãn KPI, tiêu đề biểu đồ) "
            "luôn gọi đối tượng bằng TÊN, KHÔNG viết mã. Nhóm, xếp hạng và so sánh theo cột tên (nối bảng nếu cần), không theo cột mã.\n\n")
