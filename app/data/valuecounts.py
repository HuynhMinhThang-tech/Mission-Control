# -*- coding: utf-8 -*-
"""Đếm giá trị từng cột văn bản (value_counts) rồi gom các giá trị thực chất là MỘT nhưng viết khác nhau
(khác hoa/thường, có/không dấu, thừa khoảng trắng, khác dấu câu). Ví dụ «Ban Giám đốc» và «ban giam doc»."""
import difflib
import re

import pandas as pd

from .quality import is_text, norm_key

CMD = "df['cột'].value_counts(dropna=False)"
MAX_DISTINCT = 300      # cột có nhiều giá trị khác nhau hơn mức này là mã/tên riêng/văn bản tự do -> chỉ đếm, không gom nhóm
TOP = 40                # số dòng đếm giữ lại để hiển thị cho mỗi cột
GENERIC = {"p", "pb", "bp", "phong", "ban", "khoi"}      # từ đứng đầu tên bộ phận: "P. Kinh doanh" = "Phòng Kinh doanh" = "Kinh doanh"
MAX_COLS = 80
MAX_MAP = 300           # số cặp "giá trị cũ -> giá trị chuẩn" tối đa trong một thao tác


def _is_cat(s):
    return is_text(s) and not pd.api.types.is_datetime64_any_dtype(s)


def _canon(items):
    """Cách viết chuẩn của một nhóm: cách xuất hiện nhiều nhất; ngang nhau thì ưu tiên bản có dấu tiếng Việt."""
    return sorted(items, key=lambda x: (-x[1], -sum(ord(ch) > 127 for ch in x[0]), x[0]))[0][0].strip()


def _groups(vc):
    g = {}
    for k, n in vc.items():
        if isinstance(k, str):
            g.setdefault(norm_key(k) or k, []).append((k, int(n)))
    out = []
    for key, items in g.items():
        items.sort(key=lambda x: -x[1])
        out.append({"key": key, "items": items, "n": sum(n for _, n in items), "canon": _canon(items)})
    return out


def variant_groups(vc):
    """Các cách viết của CÙNG một giá trị (chỉ khác hoa/thường, dấu, khoảng trắng, dấu câu): chắc chắn là một."""
    out = [{"canon": g["canon"], "items": [[k, n] for k, n in g["items"]]} for g in _groups(vc) if len(g["items"]) > 1]
    out.sort(key=lambda g: -sum(n for _, n in g["items"]))
    return out


def _core(key):
    t = key.split()
    while len(t) > 1 and t[0] in GENERIC:
        t.pop(0)
    return " ".join(t)


def weak_clusters(groups):
    """Giá trị NGHI là một nhưng cần người xem lại: viết tắt (CV = Chuyên viên), thêm/bớt chữ đầu (P. Kinh doanh = Kinh doanh), gõ sai nhẹ.
    Không tự gộp; chỉ đưa ra để AI và người dùng quyết định."""
    n = len(groups)
    if n < 2 or n > 200:
        return []
    keys = [g["key"] for g in groups]
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    links, abbr = [], set()
    init = {}
    for j, k in enumerate(keys):
        if len(k.split()) >= 2:
            init.setdefault("".join(w[0] for w in k.split()), []).append(j)
    for i, k in enumerate(keys):                                    # viết tắt: chữ cái đầu của một giá trị dài khớp đúng với giá trị ngắn
        if " " not in k and 2 <= len(k) <= 6 and k.isalnum():
            cand = [j for j in init.get(k, []) if j != i]
            if len(cand) == 1:                                       # nếu khớp nhiều giá trị (vd TP) thì mơ hồ, bỏ qua
                links.append((i, cand[0], "viết tắt"))
                abbr.add(i)
    cores = {}
    for i, k in enumerate(keys):
        cores.setdefault(_core(k), []).append(i)
    for c, idx in cores.items():
        if c and len(idx) > 1:
            links += [(idx[0], j, "thêm/bớt chữ đầu") for j in idx[1:]]
    for i in range(n):                                                # gõ sai nhẹ
        for j in range(i + 1, n):
            a, b = keys[i], keys[j]
            if min(len(a), len(b)) < 6 or abs(len(a) - len(b)) > 2:
                continue
            if re.sub(r"\d", "", a) == re.sub(r"\d", "", b):         # chỉ khác chữ số (Chi nhánh 1 / Chi nhánh 2): là hai đối tượng khác nhau
                continue
            sm = difflib.SequenceMatcher(None, a, b)
            if sm.real_quick_ratio() >= .9 and sm.quick_ratio() >= .9 and sm.ratio() >= .9:
                links.append((i, j, "gần giống"))
    why = {}
    for i, j, w in links:
        parent[find(i)] = find(j)
    for i, j, w in links:
        why.setdefault(find(i), set()).add(w)
    mem = {}
    for i in range(n):
        mem.setdefault(find(i), []).append(i)
    out = []
    for r, idx in mem.items():
        if len(idx) < 2:
            continue
        pool = [i for i in idx if i not in abbr] or idx
        t = max(pool, key=lambda i: groups[i]["n"])
        canon = groups[t]["canon"]
        items = sorted((it for i in idx for it in groups[i]["items"]), key=lambda x: -x[1])
        mp = {k: canon for i in idx if i != t for k, _ in groups[i]["items"] if k != canon}
        if mp:
            out.append({"canon": canon, "items": [[k, c] for k, c in items], "why": sorted(why.get(r, [])), "map": mp})
    out.sort(key=lambda g: -sum(c for _, c in g["items"]))
    return out[:30]


def report(dfs):
    """Chạy value_counts(dropna=False) cho TỪNG cột văn bản của từng bảng, kèm các nhóm giá trị nghi trùng nghĩa."""
    cols = []
    for f, d in dfs.items():
        for c in d.columns:
            s = d[c]
            if not _is_cat(s) or len(cols) >= MAX_COLS:
                continue
            vc = s.value_counts(dropna=False)
            distinct = int(s.nunique())
            item = {"file": f, "col": str(c), "cmd": f"df['{c}'].value_counts(dropna=False)", "total": int(len(s)), "distinct": distinct,
                    "missing": int(s.isna().sum()), "more": max(0, len(vc) - TOP), "variants": [], "skipped": None,
                    "top": [["(thiếu)" if pd.isna(k) else str(k)[:80], int(n)] for k, n in vc.head(TOP).items()], "weak": []}
            if distinct > MAX_DISTINCT:
                item["skipped"] = "Quá nhiều giá trị khác nhau (mã, tên riêng hoặc văn bản tự do) nên không gom nhóm"
            else:
                item["variants"] = variant_groups(vc)
                item["weak"] = weak_clusters(_groups(vc))
            cols.append(item)
    return cols


def auto_mapping(item):
    return {k: g["canon"] for g in item["variants"] for k, _ in g["items"] if k != g["canon"]}


def resolve(mp):
    """Nếu A->B mà B->C thì đưa A thẳng về C (phép gộp chỉ chạy một lượt, không đi theo chuỗi)."""
    out = {}
    for k, v in mp.items():
        seen = {k}
        while v in mp and mp[v] != v and v not in seen:
            seen.add(v)
            v = mp[v]
        if v != k:
            out[k] = v
    return out


def clean_mapping(raw, valid):
    """Chỉ giữ các cặp mà giá trị cũ CÓ THẬT trong cột (chặn AI bịa), giá trị chuẩn là chuỗi không rỗng."""
    if isinstance(raw, list):
        raw = {x.get("from"): x.get("to") for x in raw if isinstance(x, dict)}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in raw.items():
        if isinstance(k, str) and k in valid and isinstance(v, str) and v.strip() and v != k:
            out[k] = v.strip()
    return out


def for_llm(rep, budget=9000):
    """Kết quả đếm giá trị dạng văn bản gọn để đưa cho AI tổng hợp."""
    lines = []
    for c in rep:
        if c["skipped"]:
            lines.append(f"- {c['file']} · {c['col']}: {c['distinct']} giá trị khác nhau trên {c['total']} dòng (bỏ qua, quá nhiều giá trị)")
            continue
        tops = " | ".join(f"{v} ({n})" for v, n in c["top"])
        lines.append(f"- {c['file']} · {c['col']}: {c['distinct']} giá trị khác nhau, {c['missing']} thiếu. Đếm: {tops}" + (f" | …còn {c['more']} giá trị" if c["more"] else ""))
    txt = "\n".join(lines)[:budget]
    gr = [f"- {c['file']} · {c['col']}: " + " ; ".join(" = ".join(f"«{k}» ×{n}" for k, n in g["items"]) for g in c["variants"][:15])
          for c in rep if c["variants"]]
    wk = [f"- {c['file']} · {c['col']}: " + " ; ".join(" ~ ".join(f"«{k}» ×{n}" for k, n in g["items"][:5]) + f" ({'/'.join(g['why'])})" for g in c["weak"][:12])
          for c in rep if c["weak"]]
    return (txt + "\n\nNhóm giá trị CHẮC CHẮN là MỘT (chỉ khác hoa/thường, dấu, khoảng trắng):\n" + ("\n".join(gr)[:4500] if gr else "không có")
            + "\n\nNhóm giá trị NGHI là một (viết tắt, thêm/bớt chữ đầu, gõ sai nhẹ) - hãy xét từng nhóm, gộp nếu đúng là cùng nghĩa:\n" + ("\n".join(wk)[:4500] if wk else "không có"))


def auto_text(c):
    g = c["variants"][0]
    ex = " và ".join(f"«{k}» ({n})" for k, n in g["items"][:3])
    return f"Có {len(c['variants'])} nhóm giá trị viết khác nhau nhưng cùng nghĩa, nên bị đếm thành nhiều giá trị riêng. Ví dụ: {ex}."


def weak_text(c):
    g = c["weak"][0]
    ex = " ~ ".join(f"«{k}» ({n})" for k, n in g["items"][:3])
    return f"Có {len(c['weak'])} nhóm giá trị nghi là một ({'/'.join(g['why'])}), ví dụ: {ex}. Cần bạn xem lại trước khi gộp."


def view(rep, ai):
    """Dữ liệu hiển thị ở giao diện: lệnh đã chạy, bảng đếm, và phần AI tổng hợp (có dự phòng tự sinh nếu AI bỏ sót)."""
    ai = ai if isinstance(ai, dict) else {}
    said = {}
    for x in ai.get("columns") or []:
        if isinstance(x, dict) and isinstance(x.get("finding"), str):
            said[(x.get("file"), x.get("column"))] = x["finding"].strip()
    finds = []
    for c in rep:
        t = said.get((c["file"], c["col"]))
        if c["variants"] or c["weak"] or t:
            finds.append({"file": c["file"], "col": c["col"], "text": t or (auto_text(c) if c["variants"] else weak_text(c)), "ng": len(c["variants"]), "groups": c["variants"][:6],
                          "nw": len(c["weak"]), "weak": c["weak"][:6]})
    finds.sort(key=lambda f: -(f["ng"] + f["nw"]))
    ov = ai.get("overview") if isinstance(ai.get("overview"), str) else ""
    return {"cmd": CMD, "ncols": len(rep), "overview": ov.strip(), "findings": finds[:30], "cols": rep}
