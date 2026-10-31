# -*- coding: utf-8 -*-
"""Điểm nổi bật của MỖI bảng kết quả phân tích, do CODE tính từ chính bảng (không nhờ AI): cao nhất, thấp nhất, tỷ trọng, thay đổi đầu → cuối.
Dùng ở bước Phân tích để người đọc thấy ngay bảng nói gì, thay vì phải tự đọc từng dòng."""
import re

import pandas as pd

from ..export.common import chart_rows, facts, is_time_like

SKIP = re.compile(r"tỷ trọng|tỷ lệ|%|số bản ghi|thay đổi", re.I)


def measure_col(df):
    num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])]
    pick = [c for c in num if not SKIP.search(str(c))] or num
    tot = [c for c in pick if str(c).lower().startswith("tổng")]
    return (tot[-1] if len(pick) > 2 and tot else pick[0]) if pick else None


def label_col(df, meas):
    for c in df.columns:
        if c != meas and not pd.api.types.is_numeric_dtype(df[c]):
            return c
    return df.columns[0] if len(df.columns) else None


def table_facts(df):
    """Tối đa 4 câu ngắn. Bảng 1 dòng, không có cột số hoặc quá ít dữ liệu thì trả danh sách rỗng."""
    try:
        if df is None or len(df) < 2:
            return []
        m = measure_col(df)
        if m is None:
            return []
        x = label_col(df, m)
        if x is None or x == m:
            return []
        rows = chart_rows(df, str(x), str(m), limit=60)
        if len(rows) < 2:
            return []
        out = facts(rows, "line" if is_time_like(rows) else "bars")
        ncol = [c for c in df.columns if SKIP.search(str(c)) and "thay đổi" in str(c).lower()]
        if ncol and len(rows) >= 4 and is_time_like(rows):
            ch = pd.to_numeric(df[ncol[0]], errors="coerce").dropna()
            if len(ch):
                up = int((ch > 0).sum())
                out.append(f"{up}/{len(ch)} kỳ tăng so với kỳ trước")
        pre = f"Theo «{m}»: " if len(df.columns) > 3 else ""
        return [pre + out[0]] + out[1:4] if out else []
    except Exception:                                    # noqa: BLE001  điểm nổi bật chỉ là phần thêm, không được làm hỏng bước phân tích
        return []
