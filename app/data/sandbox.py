# -*- coding: utf-8 -*-
"""Chạy code pandas do AI viết trong môi trường hạn chế + chuyển DataFrame thành bảng JSON."""
import json
import re

import numpy as np
import pandas as pd

SAFE = dict(len=len, range=range, sum=sum, min=min, max=max, abs=abs, round=round, sorted=sorted, enumerate=enumerate, zip=zip,
            list=list, dict=dict, set=set, float=float, int=int, str=str, bool=bool, tuple=tuple, isinstance=isinstance, any=any,
            all=all, map=map, filter=filter, reversed=reversed, print=print, pow=pow, divmod=divmod, slice=slice, Exception=Exception,
            ValueError=ValueError, KeyError=KeyError)
BAD = re.compile(r"\b(import|__\w+__|open|eval|exec|compile|subprocess|socket|shutil|input|globals|locals|getattr|setattr)\b|\bos\.|\bsys\.|pd\.read_|\.to_(csv|excel|pickle|sql|json|parquet|html|clipboard|feather)\b")


def run_code(code, dfs):
    m = BAD.search(code)
    if m:
        raise ValueError(f"Code bị chặn vì chứa '{m.group(0)}'")
    env = {"__builtins__": SAFE, "pd": pd, "np": np, "dfs": {k: v.copy() for k, v in dfs.items()}}
    exec(code, env)
    r = env.get("result")
    if isinstance(r, pd.Series):
        r = r.reset_index()
    if not isinstance(r, pd.DataFrame):
        raise ValueError("Biến `result` phải là DataFrame")
    if isinstance(r.columns, pd.MultiIndex):
        r.columns = ["_".join(map(str, c)) for c in r.columns]
    if not isinstance(r.index, pd.RangeIndex):
        r = r.reset_index()
    r.columns = [str(c) for c in r.columns]
    return r.head(200)


def df_table(df, title, err=None):
    if df is None:
        return {"title": title, "cols": [], "rows": [], "err": err}
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[c]):
            d[c] = d[c].dt.strftime("%Y-%m-%d")
    return {"title": title, "cols": list(d.columns), "rows": json.loads(d.head(200).to_json(orient="values")), "err": err}
