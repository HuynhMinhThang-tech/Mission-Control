# -*- coding: utf-8 -*-
"""Cột nhị phân kiểu Đạt / Không đạt, Có / Không, Yes / No...

Dùng chung cho bảng điều khiển (chỉ số "tỷ lệ") và bước Phân tích (kiểu "Tỷ lệ đạt"): cùng một cách nhận diện nên hai nơi cho cùng một con số."""
import pandas as pd

from .quality import norm_key

POS = {"dat", "co", "yes", "true", "dung", "hoan thanh", "pass", "y", "tot", "tuan thu", "thuc hien"}
NEG = {"khong dat", "khong", "no", "false", "sai", "chua hoan thanh", "chua dat", "fail", "n", "chua", "khong tuan thu", "khong thuc hien"}
NEUTRAL = {"na", "n a", "khong ap dung", "kad", "khong co du lieu", "khong danh gia"}      # trả lời "không áp dụng": không tính vào tử số lẫn mẫu số


def sides(s):
    """(khóa dương, khóa âm, giá trị gốc dương, giá trị gốc âm) nếu s là cột nhị phân; không phải thì None.
    Giá trị gốc = đúng cách viết trong dữ liệu (để code sinh ra so khớp được mà không cần chuẩn hóa chữ)."""
    if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s) or pd.api.types.is_datetime64_any_dtype(s):
        return None
    x = s.dropna().astype(str)
    if len(x) < 5:
        return None
    f = x.map(norm_key)
    kinds = {v for v in f.unique() if v not in NEUTRAL}
    pos, neg = [v for v in kinds if v in POS], [v for v in kinds if v in NEG]
    if len(kinds) != 2 or len(pos) != 1 or len(neg) != 1:
        return None
    raw = lambda k: sorted({v.strip() for v in x[f == k].unique()})      # noqa: E731
    return pos[0], neg[0], raw(pos[0]), raw(neg[0])


def binary(s):
    """(chuỗi 1.0 / 0.0 / NaN, nhãn giá trị dương) nếu s là cột nhị phân, không phải thì None. NaN: ô thiếu hoặc 'không áp dụng'."""
    sd = sides(s)
    if sd is None:
        return None
    pos, neg, _, _ = sd
    fk = s.map(lambda v: norm_key(v) if pd.notna(v) else None)
    x = s.dropna().astype(str)
    label = str(x[x.map(norm_key) == pos].value_counts().index[0]).strip()
    return fk.map({pos: 1.0, neg: 0.0}).astype(float), label
