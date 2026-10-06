# -*- coding: utf-8 -*-
"""Cổng kiểm tra CẤU TRÚC tệp ngay khi tải lên (xác định, không dùng AI → nhanh, ổn định, giải thích được).

Phát hiện: dòng tiêu đề/ghi chú phía trên, tiêu đề cột nằm sai dòng, nhiều bảng xếp chồng, dòng nhãn nhóm,
dòng TỔNG lẫn trong dữ liệu, ô gộp, cột là kỳ thời gian (T1..T12). Nếu nhận ra kiểu "báo cáo nhiều khối"
thì tự chuẩn hóa thành bảng dài (tidy) và đối chiếu lại với cột Tổng.
"""
import json
import re
import unicodedata

import numpy as np
import pandas as pd

PERIOD = re.compile(r"^(t|th|q|quý|tháng)\s?\d{1,2}$|^(19|20)\d{2}$", re.I)
TOTAL = re.compile(r"^\s*(tổng|tong|total|cộng|cong|grand total|subtotal)\b", re.I)
YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
MONTH = re.compile(r"(\d{1,2})\s*$")


def slug(s):
    s = unicodedata.normalize("NFD", str(s).replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "cot"


def _num(v):
    return isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, (bool, np.bool_)) and not pd.isna(v)


def _txt(v):
    return isinstance(v, str) and v.strip() != ""


def _clean(s):
    return re.sub(r"^[▸►▶•\-\s]+", "", str(s)).strip()


def find_header_rows(raw):
    """Dòng tiêu đề = toàn chữ, >=3 ô, và ngay bên dưới (trong 5 dòng) có số ở các cột tương ứng."""
    n, out = len(raw), []
    for i in range(n):
        vals = [(j, v) for j, v in enumerate(raw.iloc[i]) if not pd.isna(v)]
        if len(vals) < 3 or not all(_txt(v) for _, v in vals):
            continue
        cols = [j for j, _ in vals[1:]]
        for k in range(i + 1, min(i + 6, n)):
            if sum(_num(raw.iat[k, j]) for j in cols) >= max(1, len(cols) // 3):
                out.append(i)
                break
    return out


def _single(raw, i):
    return raw.iloc[i].notna().sum() <= 1


def to_long(raw, hdr):
    """Bảng kiểu báo cáo (nhiều khối) -> bảng dài. Trả về (df, ghi_chú, số dòng tổng đã tách, (khớp, kiểm))."""
    n, hset = len(raw), set(hdr)
    title = next((str(raw.iat[i, 0]) for i in range(min(n, 3)) if _single(raw, i) and _txt(raw.iat[i, 0])), "")
    m = re.search(r"đơn vị\s*[:：]?\s*([^)\]]+)", title, re.I)
    unit = m.group(1).strip() if m else None
    ent = year = group = header = None
    rows = []
    totals = ok = checked = labels = 0
    first_name = None

    def next_is_header(i):
        k = i + 1
        while k < n and (raw.iloc[k].isna().all() or _single(raw, k)):
            if k in hset:
                return True
            k += 1
        return k in hset

    for i in range(n):
        row = raw.iloc[i]
        if i in hset:
            header = {j: str(v).strip() for j, v in enumerate(row) if not pd.isna(v)}
            first_name = first_name or header.get(0, "Hạng mục")
            group = None
            continue
        nn = int(row.notna().sum())
        if nn == 0:
            continue
        if nn <= 1 and _txt(row.iat[0]):
            lab = str(row.iat[0])
            hdr_next = next_is_header(i)
            prev_blank = i == 0 or raw.iloc[i - 1].isna().all()
            if header is None and i == 0:
                continue                                   # tiêu đề trang
            if hdr_next and YEAR.search(lab):
                year = YEAR.search(lab).group(1)           # "▸ Năm 2025" ngay trước dòng tiêu đề
            elif hdr_next and (prev_blank or header is None):
                ent = _clean(lab)                          # tên đối tượng: sau dòng trống, trước khối mới
            elif header is not None:
                group = _clean(lab)                        # nhãn nhóm xen giữa dữ liệu
                labels += 1
            continue
        if header is None or not _txt(row.iat[0]):
            continue
        label = str(row.iat[0]).strip()
        if TOTAL.match(label):
            totals += 1
            continue
        tot_j = next((j for j, p in header.items() if j and TOTAL.match(p)), None)
        vals, s = [], 0.0
        for j, p in header.items():
            if j == 0 or TOTAL.match(p):
                continue
            v = row.iat[j] if j < len(row) else np.nan
            if _num(v):
                s += float(v)
                mm = MONTH.search(p)
                mo = int(mm.group(1)) if mm and re.match(r"^(t|th|tháng)\s?\d", p, re.I) and 1 <= int(mm.group(1)) <= 12 else None
                vals.append((p, mo, float(v)))
        if tot_j is not None and tot_j < len(row) and _num(row.iat[tot_j]) and vals:
            checked += 1
            ok += abs(s - float(row.iat[tot_j])) <= max(1.0, .01 * abs(float(row.iat[tot_j])))
        for p, mo, v in vals:
            rows.append({"doi_tuong": ent, "nam": int(year) if year else None, "nhom": group, slug(first_name): label, "ky": p, "thang": mo,
                         "thang_nam": f"{year}-{mo:02d}" if (year and mo) else None, "gia_tri": v, "don_vi_tinh": unit})
    df = pd.DataFrame(rows)
    if len(df):
        df = df.dropna(axis=1, how="all")
    notes = []
    if labels:
        notes.append(f"{labels} dòng nhãn nhóm (không có số) được dùng làm cột 'nhom'")
    return df, notes, totals, (ok, checked)


def analyze(raw, plain, merged=0):
    """raw: đọc header=None; plain: đọc bình thường. Trả dict kết quả + (fixed|None)."""
    issues, score, actions, fixed = [], 100, [], None
    if plain.shape[0] < 5 or plain.shape[1] < 2:
        return dict(verdict="bad", score=20, issues=[f"Quá ít dữ liệu ({plain.shape[0]} dòng × {plain.shape[1]} cột) để phân tích"], actions=[], plain=plain, fixed=None)
    unnamed = sum(str(c).startswith("Unnamed") for c in plain.columns) / plain.shape[1]
    hdr = find_header_rows(raw) if raw is not None else [0]
    blocks = len(hdr)
    top = hdr[0] if hdr else 0
    body_labels = 0
    totals_in = 0
    if raw is not None:
        hs = set(hdr)
        for i in range(len(raw)):
            if i in hs:
                continue
            if _single(raw, i) and _txt(raw.iat[i, 0]) and i > top:
                body_labels += 1
            elif _txt(raw.iat[i, 0]) and TOTAL.match(raw.iat[i, 0]) and raw.iloc[i, 1:].notna().sum() >= 1:
                totals_in += 1
    period_cols = sum(bool(PERIOD.match(str(c).strip())) for c in (raw.iloc[top] if raw is not None and blocks else plain.columns) if not pd.isna(c))

    if unnamed >= .5:
        score -= 35
        issues.append(f"Tiêu đề cột không nằm ở dòng đầu tiên: {int(unnamed * plain.shape[1])}/{plain.shape[1]} cột bị đặt tên 'Unnamed'")
    if top > 0:
        score -= 10
        issues.append(f"Có {top} dòng tiêu đề/ghi chú phía trên bảng")
    if blocks >= 2:
        score -= 25
        issues.append(f"Nhiều bảng nhỏ xếp chồng trong một sheet ({blocks} khối, tiêu đề lặp lại)")
    if body_labels > 2:
        score -= 15
        issues.append(f"{body_labels} dòng nhãn (chỉ có 1 ô chữ, không có số) xen giữa dữ liệu")
    if totals_in:
        score -= 10
        issues.append(f"{totals_in} dòng tổng (TỔNG/Total) lẫn trong dữ liệu, dễ bị cộng trùng")
    if merged:
        score -= 5
        issues.append(f"{merged} vùng ô gộp (merged cells)")
    if period_cols >= 3:
        score -= 5
        issues.append("Các kỳ thời gian (T1…T12) đang nằm ở dạng cột, không phải dạng dòng")
    if raw is not None:
        empty_r = float(raw.isna().all(axis=1).mean())
        if empty_r > .3:
            score -= 10
            issues.append(f"{int(empty_r * 100)}% dòng trống")
    if not plain.select_dtypes("number").shape[1] and blocks == 0:
        score -= 30
        issues.append("Không tìm thấy cột số nào, có thể đây không phải dữ liệu bảng")
    score = max(0, score)

    if score >= 85 and unnamed < .5 and blocks <= 1 and top == 0:
        return dict(verdict="tidy", score=score, issues=issues, actions=[], plain=plain, fixed=None)

    # ---- thử tự chuẩn hóa
    if raw is not None and blocks >= 1:
        try:
            if blocks == 1 and body_labels <= 2 and not totals_in:
                hrow = raw.iloc[top]
                keep = [j for j, v in enumerate(hrow) if not pd.isna(v)]
                df = raw.iloc[top + 1:, keep].copy()
                df.columns = [str(hrow.iat[j]).strip() for j in keep]
                df = df.dropna(how="all").reset_index(drop=True)
                df = df.apply(lambda s: pd.to_numeric(s, errors="ignore") if s.dtype == object else s)
                fixed = df
                actions.append(f"Dùng dòng {top + 1} làm tiêu đề cột, bỏ {top} dòng phía trên")
            else:
                df, notes, totals, (ok, checked) = to_long(raw, hdr)
                if len(df) >= 10:
                    fixed = df
                    actions.append(f"Tách {blocks} khối thành MỘT bảng dài ({len(df):,} dòng): mỗi dòng = 1 hạng mục × 1 kỳ".replace(",", "."))
                    ctx = [c for c in ("doi_tuong", "nam", "nhom") if c in df.columns]
                    if ctx:
                        actions.append("Điền tên đối tượng / năm / nhóm của từng khối thành cột: " + ", ".join(ctx))
                    if totals:
                        actions.append(f"Tách {totals} dòng TỔNG ra khỏi dữ liệu để không cộng trùng")
                    if "gia_tri" in df.columns and period_cols:
                        actions.append("Đưa các cột kỳ (T1…T12) thành dòng; cột 'Tổng' dùng để đối chiếu rồi bỏ")
                    actions += notes
                    if checked:
                        pct = ok / checked * 100
                        actions.append(f"Đối chiếu với cột Tổng: {ok}/{checked} dòng khớp ({pct:.0f}%)")
                        if pct < 80:
                            issues.append(f"Cột Tổng không khớp tổng các kỳ ở {checked - ok}/{checked} dòng, cần kiểm tra lại số liệu gốc")
        except Exception as e:  # noqa: BLE001
            fixed = None
            issues.append(f"Tự chuẩn hóa thất bại: {type(e).__name__}")
    if fixed is not None and len(fixed) >= 5:
        return dict(verdict="fixed", score=score, issues=issues, actions=actions, plain=plain, fixed=fixed)
    return dict(verdict="bad" if score < 60 else "warn", score=score, issues=issues + ["Không nhận ra được quy luật để tự chuẩn hóa"], actions=[], plain=plain, fixed=None)


def meta(res):
    """Phần gửi cho giao diện (không chứa DataFrame)."""
    d = res["fixed"] if res["fixed"] is not None else res["plain"]
    pv = d.head(6).copy()
    for c in pv.columns:
        if str(c).lower() in ("nam", "year"):   # tránh hiển thị 2.024
            pv[c] = pv[c].astype(str).str.replace(r"\.0$", "", regex=True)
    return {"verdict": res["verdict"], "score": res["score"], "issues": res["issues"], "actions": res["actions"],
            "mode": "fixed" if res["fixed"] is not None else "original", "ack": False,
            "preview": {"cols": [str(c) for c in pv.columns], "rows": json.loads(pv.to_json(orient="values", date_format="iso"))}}