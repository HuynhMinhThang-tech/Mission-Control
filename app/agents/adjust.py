# -*- coding: utf-8 -*-
"""ĐIỀU CHỈNH (góp ý) ở mọi bước: chạy lại theo góp ý, KIỂM TRA đã áp dụng thật chưa, tự chạy lại nếu chưa, và ghi rõ AI đã đổi gì.

Vấn đề trước đây: bấm "Điều chỉnh" xong, người dùng không biết AI có thật sự đổi gì không (bản mới có thể y hệt bản cũ), code họ đã sửa tay bị bỏ qua,
và lựa chọn đang chọn dở bị xóa. Luồng mới cho mỗi lần điều chỉnh:
  1. chụp 'dấu vân tay' nội dung bước TRƯỚC khi chạy lại;
  2. chạy lại với góp ý (góp ý trước đó vẫn được giữ trong prompt);
  3. so dấu vân tay -> danh sách MỤC THÊM / BỎ / ĐỔI (do code tính, không nhờ AI);
  4. nhờ AI đối chiếu góp ý với thay đổi: đã thực hiện chưa, còn thiếu gì;
  5. chưa thực hiện đủ (hoặc không đổi gì) -> TỰ chạy lại đúng 1 lần với chỉ dẫn mạnh hơn;
  6. lưu `adj` vào dữ liệu bước để giao diện hiện banner "Đã cập nhật theo góp ý" kèm danh sách thay đổi."""
import hashlib
import json

from ..export import dash_plan
from ..llm import llm_json
from ..state import A, LOCK, bump, tick
from ..utils import J
from .base import SYS

ROLE_CHECK = "Agent Kiểm tra việc áp dụng góp ý"
CHECK_LABEL = "Kiểm tra góp ý đã được áp dụng"
REDO_LABEL = "Áp dụng lại cho đủ góp ý"
STEP_NAME = {1: "Kiểm tra và mô tả dữ liệu", 2: "Làm sạch dữ liệu", 3: "Phân tích", 4: "Phát hiện và đề xuất", 5: "Báo cáo và bảng điều khiển"}


def _h(x):
    return hashlib.md5(json.dumps(x, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:10]


def _put(out, key, val):
    key = str(key or "(không tên)")[:120]
    n, k = 1, key
    while k in out:
        n += 1
        k = f"{key} ({n})"
    out[k] = _h(val)


def items(i):
    """{nhãn hiển thị: dấu vân tay} của các mục nội dung ở bước i (đúng pha đang hiển thị với bước 3)."""
    d = A["d"].get(i) or {}
    out = {}
    if i == 1:
        for f in d.get("findings") or []:
            _put(out, f"{f.get('tag', '')}: {str(f.get('text', ''))[:100]}", f)
    elif i == 2:
        for o in d.get("ops") or []:
            _put(out, o.get("title") or o.get("id"), {k: v for k, v in o.items() if k != "id"})
    elif i == 3:
        ph = d.get("phase", "menu")
        if ph == "menu":
            for m in d.get("menu") or []:
                _put(out, m.get("title"), [m.get("goal"), m.get("metrics"), m.get("type")])
        elif ph == "code":
            for t in d.get("tasks") or []:
                _put(out, t.get("title"), [t.get("goal"), t.get("code")])
        else:
            r = d.get("result") or {}
            for t in r.get("tables") or []:
                _put(out, t.get("title"), [t.get("cols"), t.get("rows")])
            for k in r.get("kpis") or []:
                _put(out, "KPI · " + str(k.get("label")), k.get("value"))
            for f in r.get("findings") or []:
                _put(out, f"{f.get('tag', '')}: {str(f.get('text', ''))[:80]}", f)
    elif i == 4:
        if d.get("summary"):
            _put(out, "Tóm tắt", d["summary"])
        for x in d.get("insights") or []:
            _put(out, "Phát hiện · " + str(x.get("title")), x)
        for x in d.get("actions") or []:
            _put(out, "Việc nên làm · " + str(x.get("text"))[:80], x)
        for x in d.get("risks") or []:
            _put(out, "Rủi ro · " + str(x)[:80], x)
    elif i == 5:
        if d.get("title"):
            _put(out, "Tiêu đề báo cáo", d["title"])
        if d.get("narrative"):
            _put(out, "Lời dẫn", d["narrative"])
        for c in d.get("charts") or []:
            _put(out, "Biểu đồ · " + str(c.get("title")), {k: c.get(k) for k in ("task", "x", "y", "kind", "unit")})
        dash = d.get("dash") or {}
        for c in dash.get("ai") or []:
            _put(out, "Bảng điều khiển · " + dash_plan.title(c, dash.get("catalog") or []), {k: c.get(k) for k in ("ds", "by", "m", "kind", "agg")})
    return out


def diff(old, new):
    return {"added": [k for k in new if k not in old][:12], "removed": [k for k in old if k not in new][:12],
            "changed": [k for k in new if k in old and new[k] != old[k]][:12]}


def _any(ch):
    return bool(ch["added"] or ch["removed"] or ch["changed"])


def _brief(i):
    """Nội dung hiện tại rút gọn để AI đối chiếu với góp ý (bước 3: kèm code / vài dòng bảng vì tiêu đề không đủ thấy thay đổi)."""
    d = A["d"].get(i) or {}
    if i == 3 and d.get("phase") == "code":
        return J([{"title": t["title"], "goal": t.get("goal"), "code": t["code"]} for t in d.get("tasks") or []], 3500)
    if i == 3 and d.get("phase") == "result":
        r = d.get("result") or {}
        return J([{"title": t["title"], "cols": t.get("cols"), "rows": (t.get("rows") or [])[:5]} for t in r.get("tables") or []], 3500)
    return "; ".join(items(i).keys())[:3500]


def check(i, fb, ch):
    """{ok, done, missing}. Không có thay đổi nào -> chắc chắn chưa áp dụng (không tốn lượt gọi AI). Lỗi khi kiểm tra -> coi như ổn, không chặn người dùng."""
    if not _any(ch):
        return {"ok": False, "done": "", "missing": "Bản mới không có thay đổi nào so với bản trước."}
    try:
        r = llm_json(SYS(ROLE_CHECK),
                     f"Góp ý của người dùng ở bước «{STEP_NAME.get(i, i)}»: {fb}\n"
                     f"Thay đổi so với bản trước: THÊM {ch['added']}; BỎ {ch['removed']}; ĐỔI {ch['changed']}\n"
                     f"Nội dung hiện tại:\n{_brief(i)}\n\n"
                     'Đánh giá bản MỚI đã THỰC HIỆN góp ý chưa. Trả về DUY NHẤT JSON: {"ok":true|false,"done":"một câu cho biết đã làm gì (bắt đầu bằng động từ)",'
                     '"missing":"phần góp ý còn CHƯA thực hiện, để rỗng nếu đã đủ"}', 600)
        return {"ok": bool(r.get("ok")), "done": str(r.get("done") or "")[:300], "missing": str(r.get("missing") or "")[:300]}
    except Exception:                                      # noqa: BLE001
        return {"ok": True, "done": "", "missing": ""}


def apply_edits(i, p):
    """Chỉnh sửa TAY của người dùng (code đã sửa ở pha 'viết code') phải vào dữ liệu bước TRƯỚC khi AI sửa theo góp ý, nếu không AI viết lại từ bản cũ và mất phần họ sửa."""
    d = A["d"].get(i) or {}
    codes = p.get("codes")
    if i == 3 and isinstance(codes, list) and d.get("tasks"):
        with LOCK:
            for k, t in enumerate(d["tasks"]):
                if k < len(codes) and isinstance(codes[k], str) and codes[k].strip():
                    t["code"] = codes[k]


def run(i, fn, fb):
    """Chạy `fn(fb)` rồi kiểm tra / chạy lại nếu cần. Chạy trong luồng nền của start_job."""
    old = items(i)
    fn(fb)
    ch = diff(old, items(i))
    tick(len(A["ag"][i]) - 1)                              # nhãn cuối của bảng AI Agent: "Kiểm tra góp ý đã được áp dụng"
    v = check(i, fb, ch)
    retried = False
    if not v["ok"]:
        retried = True
        with LOCK:
            A["ag"][i] = list(A["ag"][i]) + [REDO_LABEL]
            bump()
        tick(len(A["ag"][i]) - 1)
        why = v["missing"] or "Kết quả chưa phản ánh góp ý."
        fn(f"{fb}\n[HỆ THỐNG: lần chạy trước CHƯA áp dụng đủ góp ý. Còn thiếu: {why} "
           "Lần này BẮT BUỘC thực hiện đúng góp ý và thể hiện rõ trong kết quả, không trả lại bản cũ.]")
        ch = diff(old, items(i))
        v = check(i, fb, ch)
    d = A["d"].get(i)
    if d is not None:
        with LOCK:
            d["adj"] = {"fb": fb[:300], **ch, "ok": bool(v["ok"]) and _any(ch), "done": v["done"], "missing": v["missing"], "retried": retried, "gen": d.get("gen")}
            bump()
