# -*- coding: utf-8 -*-
"""Áp dụng kế hoạch làm sạch do người dùng chọn."""
import re  # noqa: F401

import pandas as pd

from .quality import to_dt

OPL = {"drop_duplicates": "Xóa dòng trùng", "drop_column": "Bỏ cột", "strip_text": "Cắt khoảng trắng", "lowercase": "Chuẩn hóa chữ thường",
       "to_numeric": "Chuyển sang số", "to_datetime": "Chuẩn hóa ngày", "clip_outliers": "Cắt ngoại lai",
       "fill_missing": "Xử lý giá trị thiếu", "flag_nonpositive": "Gắn cờ giá trị âm"}


def apply_plan(dfs, ops):
    out = {k: v.copy() for k, v in dfs.items()}
    log = []
    for op in ops:
        try:
            n, o, c, m = op["file"], op["op"], op.get("column"), op.get("method")
            d = out[n]
            before = d.shape
            if o == "drop_duplicates":
                d = d.drop_duplicates()
            elif o == "drop_column":
                d = d.drop(columns=[c])
            elif o == "strip_text":
                d[c] = d[c].where(d[c].isna(), d[c].astype(str).str.strip())
            elif o == "lowercase":
                d[c] = d[c].where(d[c].isna(), d[c].astype(str).str.strip().str.lower())
            elif o == "to_numeric":
                d[c] = pd.to_numeric(d[c].astype(str).str.replace(r"[^\d.\-]", "", regex=True), errors="coerce")
            elif o == "to_datetime":
                d[c] = to_dt(d[c])
            elif o == "flag_nonpositive":
                d[c + "_nghi_van"] = d[c] < 0
            elif o == "clip_outliers":
                q1, q3 = d[c].quantile(.25), d[c].quantile(.75)
                i = q3 - q1
                d[c] = d[c].clip(q1 - 1.5 * i, q3 + 1.5 * i)
            elif o == "fill_missing":
                if m == "drop_rows":
                    d = d.dropna(subset=[c])
                elif m == "median":
                    d[c] = d[c].fillna(d[c].median())
                elif m == "mean":
                    d[c] = d[c].fillna(d[c].mean())
                elif m == "mode":
                    d[c] = d[c].fillna(d[c].mode().iloc[0])
                else:
                    d[c] = d[c].fillna(op.get("value", "Không rõ"))
            else:
                raise ValueError(f"op không hỗ trợ: {o}")
            out[n] = d
            log.append(f"{OPL.get(o, o)} · {n} · {c or '(toàn bảng)'}: {before[0]:,} → {d.shape[0]:,} dòng".replace(",", "."))
        except Exception as e:
            log.append(f"Bỏ qua {op.get('op')} {op.get('column')}: {e}")
    return out, log
