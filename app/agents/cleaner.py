# -*- coding: utf-8 -*-
"""AGENT 2 · Làm sạch dữ liệu (bước 3). AI chỉ ĐỀ XUẤT, người dùng quyết định."""
import pandas as pd

from ..data.cleaning import OPL, apply_plan
from ..data.quality import issue_counts, quality, schema
from ..llm import llm_json
from ..state import A, put, tick
from ..utils import J
from .base import SYS, ctx_txt, prev

ROLE = "Agent Làm sạch dữ liệu"

# Mô tả từng cách xử lý thiếu (hiển thị ngay trong thẻ thao tác)
METH = {"median": ("Điền trung vị", "Ít bị ngoại lai kéo lệch; chỉ dùng cho cột số."),
        "mean": ("Điền trung bình", "Dễ bị ngoại lai kéo lệch; chỉ dùng cho cột số."),
        "mode": ("Điền giá trị phổ biến nhất", "Phù hợp cột phân loại; có thể làm nhóm phổ biến phình to."),
        "drop_rows": ("Xóa dòng thiếu", "Mất cả dòng, kể cả thông tin ở các cột khác."),
        "value": ("Điền giá trị cố định", "Giữ nguyên số dòng và đánh dấu được dòng thiếu; giá trị điền có thể không phản ánh đúng thực tế.")}

PROMPT = (
    "Hãy ĐỀ XUẤT danh sách thao tác làm sạch để NGƯỜI DÙNG TỰ CHỌN (không quyết định thay họ). Trả về DUY NHẤT JSON: "
    '{"operations":[{"file":"tên file đúng như schema","op":"...","column":"...","method":"...","value":"...",'
    '"reason":"vấn đề gì, vì sao nên xử lý, ảnh hưởng tới phân tích","risk":"rủi ro nếu áp dụng","recommended":true}]}\n'
    "op hợp lệ: drop_duplicates, drop_column, strip_text, lowercase, to_numeric, to_datetime, clip_outliers, "
    "flag_nonpositive (gắn cờ giá trị âm, không sửa), fill_missing.\n"
    "fill_missing có method: median|mean|mode|drop_rows|value (kèm value). Thao tác rủi ro (xóa dữ liệu, cắt ngoại lai) "
    "đặt recommended=false. Không bỏ sót vấn đề quan trọng.")


def run(fb=""):
    tick(0)
    iss = quality(A["raw"])
    res = llm_json(SYS(ROLE),
                   ctx_txt(fb) + prev(2, fb) + f"Schema:\n{J(schema(A['raw'], 3), 5000)}\nVấn đề:\n{iss.to_csv(index=False)[:5000]}\n\n" + PROMPT)
    ops = []
    for k, o in enumerate(res.get("operations", [])):
        f, c = o.get("file"), o.get("column")
        if f not in A["raw"] or o.get("op") not in OPL:
            continue
        if o["op"] != "drop_duplicates" and c not in A["raw"][f].columns:
            continue
        if o["op"] == "fill_missing" and o.get("method") not in ("median", "mean", "mode", "drop_rows", "value"):
            o["method"] = "median"
        hit = iss[(iss["file"] == f) & (iss["col"] == (c or "(toàn bảng)"))]
        o["found"] = "; ".join(f"{r['issue']}: {r['n']}" for r in hit.to_dict("records"))
        o["id"] = f"o{k}"
        o["title"] = f"{OPL[o['op']]} · {f} · {c or '(toàn bảng)'}"
        o["recommended"] = bool(o.get("recommended", True))
        ops.append(o)
    ops = merge_fill(ops)
    tick(1)
    d = {"ops": ops, "meth": METH}
    A["d"][2] = d
    d["pv"] = preview({"sel": {}, "meth": {}, "val": {}})
    put(2, d)


def merge_fill(ops):
    """Nhiều đề xuất 'xử lý thiếu' cho CÙNG một cột là các CÁCH khác nhau của một việc -> gộp thành 1 thao tác có chọn cách."""
    out, first = [], {}
    for o in ops:
        o["numeric"] = bool(pd.api.types.is_numeric_dtype(A["raw"][o["file"]][o["column"]])) if o.get("column") in A["raw"][o["file"]].columns else False
        o["label"] = OPL[o["op"]]
        if o["op"] != "fill_missing":
            out.append(o)
            continue
        k = (o["file"], o["column"])
        alt = {x: o.get(x) for x in ("method", "value", "reason", "risk", "recommended")}
        if k not in first:
            o["alts"] = [alt]
            first[k] = o
            out.append(o)
        else:
            first[k]["alts"].append(alt)
    for o in first.values():
        rec = next((a for a in o["alts"] if a.get("recommended")), o["alts"][0])
        o["recommended"] = any(a.get("recommended") for a in o["alts"])
        for x in ("method", "value", "reason", "risk"):
            o[x] = rec.get(x)
        if not o["numeric"] and o["method"] in ("median", "mean"):
            o["method"] = "mode"
        o["title"] = f"{OPL['fill_missing']} · {o['file']} · {o['column']}"
    for o in out:
        o["id"] = f"o{out.index(o)}"
    return out


def effect(o, o2):
    """Nếu áp dụng riêng thao tác này lên dữ liệu hiện tại thì điều gì thay đổi (đếm thật, không phải ước lượng)."""
    f, c = o["file"], o.get("column")
    d = A["raw"][f]
    n = apply_plan({f: d}, [o2])[0][f]
    r0, r1 = len(d), len(n)
    vi = lambda x: f"{int(x):,}".replace(",", ".")        # noqa: E731
    op = o["op"]
    if op == "fill_missing":
        m0 = int(d[c].isna().sum())
        if o2.get("method") == "drop_rows":
            return f"Xóa {vi(r0 - r1)} dòng thiếu · còn {vi(r1)} dòng"
        return f"{vi(m0)} ô thiếu → {vi(int(n[c].isna().sum()))} · giữ nguyên {vi(r1)} dòng"
    if op == "drop_duplicates":
        return f"Xóa {vi(r0 - r1)} dòng trùng · còn {vi(r1)} dòng"
    if op in ("to_datetime", "to_numeric"):
        bad0, bad1 = int(d[c].isna().sum()), int(n[c].isna().sum())
        return f"{vi(len(n) - bad1)}/{vi(len(n))} giá trị đọc được" + (f" · {vi(bad1 - bad0)} giá trị không đọc được sẽ thành thiếu" if bad1 > bad0 else "")
    if op == "clip_outliers":
        ch = int(((d[c] != n[c]) & d[c].notna()).sum())
        return f"Đổi {vi(ch)} giá trị về ngưỡng IQR (tối đa {n[c].max():,.0f})".replace(",", ".")
    if op in ("strip_text", "lowercase"):
        return f"Sửa {vi(int(((d[c].astype(str) != n[c].astype(str)) & d[c].notna()).sum()))} ô"
    if op == "flag_nonpositive":
        return f"Gắn cờ {vi(int(n[c + '_nghi_van'].sum()))} dòng (không sửa giá trị)"
    if op == "drop_column":
        return f"Bỏ cột «{c}» (mất {vi(int(d[c].notna().sum()))} giá trị)"
    return ""


def pick_ops(p):
    out = []
    for o in A["d"][2]["ops"]:
        if (p.get("sel") or {}).get(o["id"], o["recommended"]):
            o2 = {k: o[k] for k in ("file", "op", "column", "method", "value") if k in o}
            if o["op"] == "fill_missing":
                o2["method"] = (p.get("meth") or {}).get(o["id"], o.get("method", "median"))
                if o2["method"] == "value":
                    o2["value"] = (p.get("val") or {}).get(o["id"], o.get("value", "Không rõ"))
            out.append((o, o2))
    return out


def preview(p):
    out, _ = apply_plan(A["raw"], [o2 for _, o2 in pick_ops(p)])
    b, a = issue_counts(A["raw"]), issue_counts(out)
    fx = {}
    for o in A["d"][2]["ops"]:
        o2 = {k: o[k] for k in ("file", "op", "column", "method", "value") if k in o}
        if o["op"] == "fill_missing":
            o2["method"] = (p.get("meth") or {}).get(o["id"], o.get("method", "median"))
            o2["value"] = (p.get("val") or {}).get(o["id"], o.get("value") or "Không rõ")
        try:
            fx[o["id"]] = effect(o, o2)
        except Exception:                         # noqa: BLE001
            fx[o["id"]] = ""
    return {"before": b, "after": a, "n": int(sum(b.values()) - sum(a.values())), "fx": fx}


def apply_choice(p):
    """Áp dụng lựa chọn của người dùng, lưu lại lựa chọn cuối để xem lại trong Lịch sử."""
    picked = pick_ops(p)
    A["clean"], lg = apply_plan(A["raw"], [o2 for _, o2 in picked])
    A["applied"] = [f"{OPL[o2['op']]} ({o2.get('column') or 'toàn bảng'})" for _, o2 in picked]
    chosen = {o["id"]: o2 for o, o2 in picked}
    for o in A["d"][2]["ops"]:
        o["chosen"] = o["id"] in chosen
        if o["op"] == "fill_missing" and o["id"] in chosen:
            o["method"] = chosen[o["id"]]["method"]
            if "value" in chosen[o["id"]]:
                o["value"] = chosen[o["id"]]["value"]
    A["dirty"] = []
    A["d"][2]["pv"] = preview(p)
    return lg
