# -*- coding: utf-8 -*-
"""Quan hệ giữa các bảng (nhiều sheet / nhiều tệp) và việc NỐI bảng khi ghép biến từ nhiều sheet.

Hai bảng có quan hệ khi cùng có một cột tên giống nhau, một bên là KHÓA (mỗi giá trị đúng một dòng: Mã sản phẩm ở bảng Sản phẩm) và bên kia
có các giá trị khớp với khóa đó (Mã sản phẩm ở bảng Chi tiết đơn hàng). Bên có khóa là «bảng một», bên kia là «bảng nhiều».

Nối chỉ đi theo chiều NHIỀU -> MỘT (mỗi dòng của bảng chính khớp tối đa một dòng bên kia) nên số dòng KHÔNG đổi và số liệu không bị nhân đôi.
Nối ngược chiều (một -> nhiều) làm nhân dòng nên bị từ chối kèm lý do rõ ràng, thay vì lặng lẽ tính sai."""
import re

import pandas as pd

from .. import labels as lb
from .datecols import short
from .quality import is_text

MIN_MATCH = 50.0                                         # % giá trị của bảng nhiều có mặt ở khóa; thấp hơn thì coi là trùng tên ngẫu nhiên
NOT_KEY = re.compile(r"^(stt|no|index|id_?dong|row|#)$")


def _is_key(s, name):
    """Cột dùng làm khóa: không trống, mỗi giá trị một lần, có ít nhất 2 giá trị, và là mã (chữ hoặc tên kiểu mã/id), không phải số thứ tự."""
    t = s.dropna()
    if len(t) < 2 or not t.is_unique or NOT_KEY.match(lb.fold(name)):
        return False
    return bool(is_text(s) or lb.is_id(name))


def relations(clean, min_match=MIN_MATCH):
    """[{many, one, key, match, n_one}]: `many` có thể nối tới `one` theo cột `key`. Xếp khớp cao trước."""
    out, names = [], list(clean)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            for c in [c for c in clean[a].columns if c in clean[b].columns]:
                ka, kb = _is_key(clean[a][c], c), _is_key(clean[b][c], c)
                if not (ka or kb):
                    continue
                if ka and kb:                             # một-một: bảng ít dòng hơn là «bảng một»
                    one, many = (a, b) if len(clean[a]) <= len(clean[b]) else (b, a)
                elif ka:
                    one, many = a, b
                else:
                    one, many = b, a
                vals = clean[many][c].dropna()
                if not len(vals):
                    continue
                m = float(vals.isin(set(clean[one][c].dropna())).mean() * 100)
                if m >= min_match:
                    out.append({"many": many, "one": one, "key": str(c), "match": round(m, 2), "n_one": int(clean[one][c].nunique())})
    return sorted(out, key=lambda r: (-r["match"], -r["n_one"]))


def dim_tables(rels):
    """Bảng «một» (danh mục: khách hàng, sản phẩm, đơn hàng...) của các quan hệ."""
    return {r["one"] for r in rels}


def _bfs(edges, base, target):
    """Đường nối từ base tới target chỉ theo chiều nhiều -> một: [(cha, con, khóa)] hoặc None."""
    seen, queue = {base}, [(base, [])]
    while queue:
        cur, path = queue.pop(0)
        if cur == target:
            return path
        for one, key in edges.get(cur, []):
            if one not in seen:
                seen.add(one)
                queue.append((one, path + [(cur, one, key)]))
    return None


def _linked(rels, a, b):
    """Hai bảng có nối được với nhau không, kể cả ngược chiều hoặc gián tiếp qua bảng khác?"""
    adj = {}
    for r in rels:
        adj.setdefault(r["many"], set()).add(r["one"])
        adj.setdefault(r["one"], set()).add(r["many"])
    seen, stack = {a}, [a]
    while stack:
        cur = stack.pop()
        if cur == b:
            return True
        for nx in adj.get(cur, ()):
            if nx not in seen:
                seen.add(nx)
                stack.append(nx)
    return False


def plan(clean, base, wanted, rels=None):
    """Lập kế hoạch nối để khung dữ liệu của `base` có đủ các cột `wanted` = [(bảng, cột)].
    Trả (joins, names): joins = [{file, left_on, right_on, cols:{cột gốc: tên trong khung}}] theo thứ tự nối;
    names = {(bảng, cột): tên cột trong khung đã nối}. Nâng ValueError (tiếng Việt) nếu không nối được an toàn."""
    rels = relations(clean) if rels is None else rels
    edges = {}
    for r in rels:
        edges.setdefault(r["many"], []).append((r["one"], r["key"]))
    parent, order, carry = {}, [], {}
    for f, c in wanted:
        carry.setdefault(f, [])
        if c not in carry[f]:
            carry[f].append(c)
        if f == base or f in parent:
            continue
        path = _bfs(edges, base, f)
        if path is None:
            back = _bfs(edges, f, base) or _linked(rels, base, f)
            why = (f"«{short(base)}» là bảng danh mục (mỗi dòng một đối tượng) còn «{short(f)}» có nhiều dòng cho mỗi đối tượng đó. "
                   f"Chỉ số lấy từ «{short(base)}» mà chia theo cột của «{short(f)}» sẽ bị tính lặp và làm sai tổng. "
                   f"Hãy lấy chỉ số từ «{short(f)}» (ví dụ doanh thu ở bảng chi tiết) rồi chia theo cột của «{short(base)}».") if back else \
                  f"Hai bảng «{short(base)}» và «{short(f)}» chưa có cột khóa chung (cùng tên, mỗi giá trị một dòng) để nối nên không ghép được biến của hai bảng này."
            raise ValueError(why)
        for p, ch, key in path:
            if ch not in parent:
                parent[ch] = (p, key)
                order.append(ch)
                carry.setdefault(ch, [])
            carry.setdefault(p, [])
            if p != base and key not in carry[p]:
                carry[p].append(key)                      # bảng trung gian phải mang theo cột khóa để nối tiếp
    names = {(base, c): str(c) for c in clean[base].columns}
    taken = set(names.values())
    joins = []
    for ch in order:
        p, key = parent[ch]
        left = names.get((p, key))
        if left is None:
            raise ValueError(f"Không tìm thấy cột khóa «{key}» của bảng «{short(p)}» để nối sang «{short(ch)}».")
        names[(ch, key)] = left
        cols = {}
        for c in carry.get(ch, []):
            if c == key:
                continue
            nm = str(c)
            if nm in taken:
                nm = f"{c} ({short(ch)})"
                k = 2
                while nm in taken:
                    nm, k = f"{c} ({short(ch)} {k})", k + 1
            taken.add(nm)
            names[(ch, c)] = nm
            cols[str(c)] = nm
        joins.append({"file": ch, "left_on": left, "right_on": str(key), "cols": cols})
    return joins, names


def frame(clean, base, joins):
    """Khung dữ liệu đã nối. Cùng logic với code do `join_code` sinh ra (cần giống nhau để số liệu trong kiểm tra và trong sandbox khớp)."""
    df = clean[base]
    for j in joins or []:
        r = clean[j["file"]][[j["right_on"], *j["cols"]]].drop_duplicates(j["right_on"]).rename(columns={j["right_on"]: j["left_on"], **j["cols"]})
        df = df.merge(r, on=j["left_on"], how="left")
    return df


def join_code(joins):
    """Các dòng code pandas thực hiện phép nối (sandbox cho phép merge / rename / drop_duplicates)."""
    q = lambda s: repr(str(s))                          # noqa: E731
    L = []
    if joins:
        L.append("# nối thêm cột từ bảng khác: mỗi dòng bảng chính khớp tối đa một dòng bên kia nên số dòng không đổi")
    for j in joins or []:
        cols = [j["right_on"], *j["cols"]]
        ren = {j["right_on"]: j["left_on"], **j["cols"]}
        ren = {k: v for k, v in ren.items() if k != v}
        r = f"dfs[{q(j['file'])}][{cols!r}].drop_duplicates({q(j['right_on'])})" + (f".rename(columns={ren!r})" if ren else "")
        L.append(f"df = df.merge({r}, on={q(j['left_on'])}, how='left')")
    return L


def join_text(base, joins):
    """Câu tiếng Việt mô tả phép nối, hiện cho người dùng."""
    if not joins:
        return ""
    parts = [f"«{short(j['file'])}» (theo {j['right_on']})" for j in joins]
    return f"Hệ thống tự nối bảng «{short(base)}» với " + ", ".join(parts) + "."
