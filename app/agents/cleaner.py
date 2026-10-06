# -*- coding: utf-8 -*-
"""AGENT 2 · Làm sạch dữ liệu (bước 3). AI chỉ ĐỀ XUẤT, người dùng quyết định."""
from ..data.cleaning import OPL, apply_plan
from ..data.quality import issue_counts, quality, schema
from ..llm import llm_json
from ..state import A, put, tick
from ..utils import J
from .base import SYS, ctx_txt

ROLE = "Agent Làm sạch dữ liệu"

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
                   ctx_txt(fb) + f"Schema:\n{J(schema(A['raw'], 3), 5000)}\nVấn đề:\n{iss.to_csv(index=False)[:5000]}\n\n" + PROMPT)
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
    tick(1)
    d = {"ops": ops}
    A["d"][2] = d
    d["pv"] = preview({"sel": {}, "meth": {}, "val": {}})
    put(2, d)


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
    return {"before": b, "after": a, "n": int(sum(b.values()) - sum(a.values()))}


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
