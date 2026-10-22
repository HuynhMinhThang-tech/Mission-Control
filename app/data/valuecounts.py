# -*- coding: utf-8 -*-
"""Đếm giá trị từng cột văn bản (value_counts) rồi gom các giá trị thực chất là MỘT nhưng viết khác nhau
(khác hoa/thường, có/không dấu, thừa khoảng trắng, khác dấu câu). Ví dụ «Ban Giám đốc» và «ban giam doc»."""
import pandas as pd

from .quality import is_text, norm_key

CMD = "df['cột'].value_counts(dropna=False)"
MAX_DISTINCT = 300      # cột có nhiều giá trị khác nhau hơn mức này là mã/tên riêng/văn bản tự do -> chỉ đếm, không gom nhóm
TOP = 15                # số dòng đếm giữ lại để hiển thị cho mỗi cột
MAX_COLS = 80
MAX_MAP = 300           # số cặp "giá trị cũ -> giá trị chuẩn" tối đa trong một thao tác


def _is_cat(s):
    return is_text(s) and not pd.api.types.is_datetime64_any_dtype(s)


def _canon(items):
    """Cách viết chuẩn của một nhóm: cách xuất hiện nhiều nhất; ngang nhau thì ưu tiên bản có dấu tiếng Việt."""
    return sorted(items, key=lambda x: (-x[1], -sum(ord(ch) > 127 for ch in x[0]), x[0]))[0][0].strip()


def variant_groups(vc):
    groups = {}
    for k, n in vc.items():
        if isinstance(k, str):
            groups.setdefault(norm_key(k) or k, []).append((k, int(n)))
    out = []
    for items in groups.values():
        if len(items) > 1:
            items.sort(key=lambda x: -x[1])
            out.append({"canon": _canon(items), "items": [[k, n] for k, n in items]})
    out.sort(key=lambda g: -sum(n for _, n in g["items"]))
    return out


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
                    "top": [["(thiếu)" if pd.isna(k) else str(k)[:80], int(n)] for k, n in vc.head(TOP).items()]}
            if distinct > MAX_DISTINCT:
                item["skipped"] = "Quá nhiều giá trị khác nhau (mã, tên riêng hoặc văn bản tự do) nên không gom nhóm"
            else:
                item["variants"] = variant_groups(vc)
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
    return txt + "\n\nNhóm giá trị nghi là MỘT (giống nhau sau khi bỏ hoa/thường, dấu, khoảng trắng):\n" + ("\n".join(gr)[:4500] if gr else "không có")


def auto_text(c):
    g = c["variants"][0]
    ex = " và ".join(f"«{k}» ({n})" for k, n in g["items"][:3])
    return f"Có {len(c['variants'])} nhóm giá trị viết khác nhau nhưng cùng nghĩa, nên bị đếm thành nhiều giá trị riêng. Ví dụ: {ex}."


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
        if c["variants"] or t:
            finds.append({"file": c["file"], "col": c["col"], "text": t or auto_text(c), "ng": len(c["variants"]), "groups": c["variants"][:6]})
    finds.sort(key=lambda f: -f["ng"])
    ov = ai.get("overview") if isinstance(ai.get("overview"), str) else ""
    return {"cmd": CMD, "ncols": len(rep), "overview": ov.strip(), "findings": finds[:30], "cols": rep}
