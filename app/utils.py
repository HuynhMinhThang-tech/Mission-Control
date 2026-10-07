# -*- coding: utf-8 -*-
import html
import json

import numpy as np


def J(x, n=12000):
    """Dump JSON gọn để đưa vào prompt."""
    return json.dumps(x, ensure_ascii=False, default=str)[:n]


def vn(v, nd=2):
    """Định dạng số kiểu Việt Nam: 1.234,5"""
    try:
        s = f"{float(v):,.{nd}f}"
    except Exception:
        return str(v)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def compact(v, nd=1):
    """1.250.000.000 -> '1,3 tỷ'"""
    try:
        x = float(v)
    except Exception:
        return str(v)
    a = abs(x)
    for d, u in ((1e9, " tỷ"), (1e6, " triệu"), (1e3, " nghìn")):
        if a >= d:
            return vn(x / d, nd) + u
    return vn(x, nd)


def E(t):
    return html.escape(str(t if t is not None else ""))


def clean_json(o):
    if isinstance(o, dict):
        return {str(k): clean_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean_json(v) for v in o]
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if (np.isnan(o) or np.isinf(o)) else float(o)
    return o


def is_text(s):
    """Cột chữ: pandas 2 dùng object, pandas 3 dùng kiểu str riêng -> kiểm tra cả hai."""
    import pandas as pd
    return pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)


def to_num_if_mostly(s, ratio=.9):
    """Đổi cột chữ sang số nếu >= ratio giá trị không rỗng đọc được thành số (thay cho to_numeric(errors='ignore') đã bị bỏ)."""
    import pandas as pd
    if not is_text(s):
        return s
    nn = s.notna().sum()
    n = pd.to_numeric(s, errors="coerce")
    return n if nn and n.notna().sum() >= ratio * nn else s
