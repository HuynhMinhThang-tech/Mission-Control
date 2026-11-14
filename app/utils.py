# -*- coding: utf-8 -*-
import html
import json
import math

import numpy as np


def J(x, n=12000):
    """Dump JSON gọn để đưa vào prompt."""
    return json.dumps(x, ensure_ascii=False, default=str)[:n]


def _sep(s):
    """'1,234.50' (kiểu Mỹ) -> '1.234,50' (kiểu Việt Nam)."""
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _finite(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if np.isfinite(x) else None


# ------------------------------------------------------------------ QUY TẮC SỐ DUY NHẤT (mọi nơi hiển thị đều đi qua đây) --
#   số nguyên           -> 1.234.567                (không có phần thập phân)
#   số thập phân        -> 1.234,50                 (luôn đúng 2 chữ số sau dấu phẩy)
#   tỷ lệ / phần trăm   -> 54,20%                   (luôn đúng 2 chữ số sau dấu phẩy)
#   tiền                -> 1.234.567 đ              (ghi ĐỦ số, có dấu ngăn nghìn, đơn vị theo dữ liệu; KHÔNG viết tắt nghìn/triệu/tỷ;
#                                                 KHÔNG có phần thập phân: 3.724.488.031,25 đ hiện là 3.724.488.031 đ)
# Chỉ TIỀN bị bỏ phần thập phân. Số thập phân không phải tiền (trọng lượng, điểm, trung bình...) giữ nguyên 2 chữ số: 0,41 · 3,63.
# Bản JavaScript của cùng quy tắc nằm ở static/js/fmt.js và export/assets/live.js; sửa ở đâu thì sửa cả ba.
MONEY_UNITS = {"đ", "đồng", "vnd", "vnđ", "₫"}


def is_money_unit(unit):
    """Đơn vị này là TIỀN (đồng Việt Nam) không? Tiền ghi nguyên đồng, không có phần thập phân."""
    return str(unit or "").strip().lower() in MONEY_UNITS


def _round_half_away(x):
    """Làm tròn nửa ra xa số 0 (2,5 -> 3 · -2,5 -> -3), giống Intl.NumberFormat của trình duyệt. round() của Python làm tròn nửa về số chẵn
    (651418562,5 -> 651418562) nên sẽ lệch một đồng so với màn hình."""
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


def vn(v, nd=2):
    """Số kiểu Việt Nam: nguyên thì không có phần thập phân, lẻ thì đúng `nd` chữ số sau dấu phẩy (1.234,50)."""
    x = _finite(v)
    if x is None:
        return str(v)
    if nd <= 0 or abs(x - round(x)) < 1e-9:           # số nguyên THẬT thì không có phần thập phân; 99,999 là số lẻ nên hiện 100,00
        return _sep(f"{_round_half_away(x):,}")
    return _sep(f"{x:,.{nd}f}")


def fmt_dec(v, nd=2):
    """Số thập phân LUÔN đủ `nd` chữ số sau dấu phẩy (dùng cho cả cột số lẻ để các dòng thẳng hàng)."""
    x = _finite(v)
    return str(v) if x is None else _sep(f"{x:,.{nd}f}")


def fmt_pct(p, nd=2):
    """p tính theo đơn vị phần trăm (54.2 -> '54,20%')."""
    x = _finite(p)
    return str(p) if x is None else fmt_dec(x, nd) + "%"


def fmt_val(v, unit=""):
    """Giá trị kèm đơn vị của dữ liệu: '%' -> 54,20% · 'đ' -> 1.234.567 đ (tiền: không có phần thập phân) · 'kg' -> 12,50 kg."""
    if unit == "%":
        return fmt_pct(v)
    s = vn(v, 0) if is_money_unit(unit) else vn(v)
    return f"{s} {unit}" if unit and _finite(v) is not None else s


def fmt_num(v, unit=""):
    """Số KHÔNG kèm đơn vị (nhãn trên biểu đồ đã có đơn vị ở tiêu đề), nhưng vẫn theo quy tắc của đơn vị: tiền thì nguyên đồng, còn lại như vn()."""
    return vn(v, 0) if is_money_unit(unit) else vn(v)


def fmt_money(v, unit="đ"):
    return fmt_val(v, unit)


def col_fmt(values, unit=""):
    """Hàm định dạng CHUNG cho một cột bảng: cột có số lẻ thì mọi ô đều 2 chữ số thập phân, cột toàn số nguyên thì không có phần thập phân.
    Cột TIỀN (unit 'đ') luôn nguyên đồng, kể cả khi có ô lẻ."""
    if is_money_unit(unit):
        return lambda v: vn(v, 0)
    frac = False
    for v in values:
        x = _finite(v) if not isinstance(v, bool) else None
        if x is not None and abs(x - round(x)) >= 1e-9:
            frac = True
            break
    return (lambda v: fmt_dec(v)) if frac else (lambda v: vn(v, 0))


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
