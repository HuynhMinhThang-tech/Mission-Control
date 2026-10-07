# -*- coding: utf-8 -*-
"""Toàn bộ API của Flask."""
import json
import re
import traceback
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file, send_from_directory

from . import config
from .agents import NEXT, RUN
from .agents.charts import valid_charts
from .agents.cleaner import apply_choice, preview
from .agents.planner import execute, labels_for as planner_labels, menu as planner_menu, write_code
from .agents.profiler import run as s1_profile
from .constants import STEP_T
from .data.loader import load_files, make_sample
from .export import live_meta, publish
from .export.interactive import build_dashboard
from .state import A, HIST, LOCK, bump, delete_history, log, now_iso, reset, snapshot_path, start_job
from .utils import clean_json

bp = Blueprint("api", __name__)


def bad(m, c=400):
    return jsonify({"error": m}), c


@bp.get("/")
def index():
    return send_from_directory(config.TEMPLATE_DIR, "index.html")


@bp.get("/api/state")
def api_state():
    with LOCK:
        o = {k: A[k] for k in ("id", "question", "ctx", "files", "struct", "dirty", "st", "d", "ag", "approved", "job", "err", "log", "ver", "outputs", "started", "finished", "fbh")}
        o["hist"] = [dict(h, snap=snapshot_path(h["id"]).exists()) for h in HIST]
        return jsonify(clean_json(o))


@bp.post("/api/upload")
def upload():
    fs = request.files.getlist("files")
    if not fs:
        return bad("Chưa chọn tệp")
    try:
        raw, reps, alts = load_files(fs)
    except Exception as e:
        return bad(f"Không đọc được tệp: {e}")
    with LOCK:
        if A["st"][0] == "done":
            return bad("Đã bắt đầu phân tích; hãy bấm 'Làm lại từ bước này' hoặc 'Phân tích mới'.")
        if any(f.get("demo") for f in A["files"]):   # tải dữ liệu thật thì bỏ bộ mẫu
            A["raw"], A["struct"], A["alt"] = {}, {}, {}
        A["raw"].update(raw)                           # CỘNG DỒN; trùng tên thì thay tệp cũ
        A["struct"].update(reps)
        A["alt"].update(alts)
        A["files"] = [{"name": n, "rows": len(d)} for n, d in A["raw"].items()]
        bump()
    return jsonify(ok=True, notices=notices(reps, raw))


def notices(reps, dfs):
    """Thông báo hiện bằng panel ngay sau khi tải: tệp nào đã được chuẩn hóa / có vấn đề cấu trúc."""
    out = []
    for n, m in reps.items():
        top = "; ".join(m["issues"][:3])
        if m["verdict"] == "detected":
            if m["rank"] == 1:     # mỗi sheet báo một lần, ở bảng chính
                base = n.rsplit("::", 1)[0] if m["sheet_tables"] > 1 else n
                k, rows = m["sheet_tables"], f"{len(dfs[n]):,}".replace(",", ".")
                msg = (f"Tìm thấy {k} bảng trong sheet; bảng chính ở {m['range']} ({rows} dòng). Các bảng khác nằm trong danh sách tệp, hãy xóa bảng bạn không cần."
                       if k > 1 else f"Bảng nằm ở {m['range']} ({rows} dòng), hệ thống đã tự cắt đúng vùng dữ liệu.")
                out.append({"type": "ok", "title": f"Đã tự nhận diện bảng: {base}", "msg": msg})
        elif m["verdict"] == "fixed":
            out.append({"type": "warn", "title": f"Đã tự chuẩn hóa: {n}",
                        "msg": f"Tệp có cấu trúc kiểu báo cáo ({top}). Hệ thống đã chuyển thành bảng dữ liệu {len(dfs[n]):,} dòng. Hãy xem phần 'Xem trước dữ liệu' trong danh sách tệp để xác nhận.".replace(",", ".")})
        elif m["verdict"] == "warn":
            out.append({"type": "warn", "title": f"Cấu trúc chưa lý tưởng: {n}", "msg": top + ". Kết quả phân tích có thể kém chính xác."})
        elif m["verdict"] == "bad":
            out.append({"type": "error", "title": f"Tệp không phù hợp để phân tích: {n}",
                        "msg": top + ". Hãy chỉnh lại tệp thành bảng có một dòng tiêu đề và mỗi dòng là một bản ghi, hoặc bấm 'Vẫn dùng file này' nếu bạn chắc chắn."})
    return out


@bp.post("/api/struct/<act>")
def struct_act(act):
    """Người dùng quyết định: dùng bản gốc / bản đã chuẩn hóa / xác nhận vẫn dùng tệp có vấn đề."""
    name = (request.get_json(silent=True) or {}).get("name")
    with LOCK:
        m = A["struct"].get(name)
        if not m or A["st"][0] == "done":
            return bad("Không thể thay đổi tệp này lúc này.")
        alt = A["alt"].get(name, {})
        if act == "ack":
            m["ack"] = True
        elif act == "use_original":
            A["raw"][name] = alt["plain"]
            m["mode"] = "original"
        elif act == "use_fixed" and alt.get("fixed") is not None:
            A["raw"][name] = alt["fixed"]
            m["mode"] = "fixed"
        else:
            return bad("Thao tác không hợp lệ.")
        A["files"] = [{"name": n, "rows": len(d), **({"demo": True} if any(f["name"] == n and f.get("demo") for f in A["files"]) else {})} for n, d in A["raw"].items()]
        bump()
    return jsonify(ok=True)


@bp.get("/api/preview")
def preview_file():
    """Xem trước dữ liệu của MỌI tệp (sạch hay xấu): bản đang dùng, bản gốc, bản chuẩn hóa, và bản sau làm sạch nếu đã có."""
    name, src = request.args.get("name", ""), request.args.get("src", "current")
    n = max(5, min(int(request.args.get("n", 30) or 30), 200))
    with LOCK:
        alt = A["alt"].get(name, {})
        variants = {"current": A["raw"].get(name)}
        if alt.get("plain") is not None and alt["plain"] is not variants["current"]:
            variants["original"] = alt["plain"]
        if alt.get("fixed") is not None and alt["fixed"] is not variants["current"]:
            variants["fixed"] = alt["fixed"]
        if A["clean"] and name in A["clean"]:
            variants["clean"] = A["clean"][name]
        df = variants.get(src)
        if df is None:
            return bad("Không có dữ liệu để xem trước.", 404)
        m = A["struct"].get(name) or {}
        head = df.head(n)
        cols = []
        for c in df.columns[:60]:
            s = df[c]
            cols.append({"name": str(c), "dtype": str(s.dtype), "missing": int(s.isna().sum()), "unique": int(s.nunique(dropna=True))})
        out = {"name": name, "src": src, "variants": list(variants), "mode": m.get("mode"), "verdict": m.get("verdict"),
               "shape": [int(df.shape[0]), int(df.shape[1])], "cols": cols, "extra_cols": max(0, df.shape[1] - 60),
               "rows": json.loads(head.iloc[:, :60].to_json(orient="values", date_format="iso", default_handler=str))}
    return jsonify(out)


@bp.post("/api/remove_file")
def remove_file():
    """Xóa 1 tệp (có 'name') hoặc xóa tất cả (không có 'name') trước khi bắt đầu."""
    name = (request.get_json(silent=True) or {}).get("name")
    with LOCK:
        if A["st"][0] == "done":
            return bad("Đã bắt đầu phân tích, không thể xóa tệp. Hãy bấm 'Làm lại từ bước này'.")
        if name is None:
            A["raw"], A["struct"], A["alt"] = {}, {}, {}
        else:
            A["raw"].pop(name, None)
            A["struct"].pop(name, None)
            A["alt"].pop(name, None)
        A["files"] = [f for f in A["files"] if f["name"] in A["raw"]]
        bump()
    return jsonify(ok=True)


@bp.post("/api/sample")
def sample():
    """Người dùng CHỦ ĐỘNG chọn dữ liệu mẫu (không còn tự dùng ngầm)."""
    with LOCK:
        if A["st"][0] == "done":
            return bad("Đã bắt đầu phân tích.")
        A["raw"], A["struct"], A["alt"] = make_sample(), {}, {}
        A["files"] = [{"name": n, "rows": len(d), "demo": True} for n, d in A["raw"].items()]
        bump()
    return jsonify(ok=True)


@bp.post("/api/start")
def start():
    p = request.get_json(silent=True) or {}
    q = (p.get("question") or "").strip()
    if not q:
        return bad("Hãy nhập câu hỏi kinh doanh")
    with LOCK:
        if not A["raw"]:
            return bad("Hãy tải tệp dữ liệu lên (hoặc bấm 'Dùng bộ dữ liệu mẫu') trước khi bắt đầu.")
        # CỔNG CẤU TRÚC: chặn tệp không phù hợp (hoặc đang dùng bản gốc chưa chuẩn hóa) cho tới khi người dùng xác nhận
        blocked = [(n, m) for n, m in A["struct"].items()
                   if not m.get("ack") and (m["verdict"] == "bad" or (m["verdict"] == "fixed" and m["mode"] == "original"))]
        if blocked:
            n, m = blocked[0]
            more = f" (và {len(blocked) - 1} tệp khác)" if len(blocked) > 1 else ""
            return bad(f"Tệp '{n}'{more} chưa phù hợp để phân tích: " + "; ".join(m["issues"][:2]) +
                       ". Hãy dùng bản đã chuẩn hóa, sửa/xóa tệp, hoặc bấm 'Vẫn dùng file này' nếu bạn chắc chắn.")
        A["question"] = q
        A["ctx"] = (p.get("ctx") or "").strip()
        A["st"][0] = "done"
        A["started"] = A["started"] or now_iso()
        bump()
    log("Đã nạp dữ liệu và câu hỏi")
    try:
        start_job(1, A["ag"][1], s1_profile, "")
    except RuntimeError as e:
        return bad(str(e), 409)
    return jsonify(ok=True)


@bp.post("/api/run/<int:i>")
def run(i):
    fb = ((request.get_json(silent=True) or {}).get("feedback") or "").strip()
    if i not in RUN:
        return bad("Bước không hợp lệ")
    labels = A["ag"][i]
    fn = RUN[i]
    if i == 3:
        ph = (A["d"].get(3) or {}).get("phase", "menu")
        if not fb and A["st"][3] == "error":          # "Thử lại" sau lỗi: chạy lại đúng việc đang dở, không bắt chọn lại từ đầu
            if ph == "code":
                fn, labels = (lambda _fb: execute([])), ["Chạy code phân tích", "Tự sửa lỗi nếu có", "Tổng hợp KPI và phát hiện"]
            else:
                fn, labels = planner_menu, ["Đề xuất phân tích và chỉ số"]
        else:
            labels = planner_labels(fb)
    if fb:
        with LOCK:
            A["fbh"].setdefault(str(i), []).append(fb)
            bump()
        log("Phản hồi: " + fb)
    try:
        start_job(i, labels, fn, fb)
    except RuntimeError as e:
        return bad(str(e), 409)
    return jsonify(ok=True)


@bp.post("/api/preview_clean")
def pv():
    if 2 not in A["d"]:
        return bad("Chưa có đề xuất")
    return jsonify(clean_json(preview(request.get_json(silent=True) or {})))


@bp.post("/api/a3/<act>")
def a3(act):
    p = request.get_json(silent=True) or {}
    d = A["d"].get(3)
    if not d or A["st"][3] != "await":
        return bad("Bước chưa sẵn sàng")
    if act == "reselect":
        with LOCK:
            d["phase"] = "menu"
            d["tasks"] = None
            d["result"] = None
            bump()
        return jsonify(ok=True)
    try:
        if act == "code":
            if not p.get("ids") and not (p.get("custom") or "").strip():
                return bad("Hãy chọn ít nhất 1 mục")
            start_job(3, ["Viết code cho các mục đã chọn"], write_code, p.get("ids", []), p.get("custom", ""))
        elif act == "exec":
            start_job(3, ["Chạy code phân tích", "Tự sửa lỗi nếu có", "Tổng hợp KPI và phát hiện"], execute, p.get("codes", []))
        else:
            return bad("Không hợp lệ")
    except RuntimeError as e:
        return bad(str(e), 409)
    return jsonify(ok=True)


@bp.post("/api/accept/<int:i>")
def accept(i):
    p = request.get_json(silent=True) or {}
    with LOCK:
        if A["st"][i] != "await" or A["job"]["running"]:
            return bad("Bước chưa sẵn sàng")
    try:
        if i == 2:
            for l in apply_choice(p)[:10]:
                log("Đã áp dụng: " + l)
        elif i == 3:
            if A["d"][3]["phase"] != "result":
                return bad("Hãy chạy phân tích trước")
        elif i == 4:
            d = A["d"][4]
            d["insights"] = [x for k, x in enumerate(d["insights"]) if (p.get("ins") or [])[k:k + 1] != [False]]
            d["actions"] = [x for k, x in enumerate(d["actions"]) if (p.get("act") or [])[k:k + 1] != [False]]
        elif i == 5:
            tabs = A["d"][3]["result"]["tables"]
            ch = valid_charts(p.get("charts", []), tabs)
            if not ch:
                return bad("Hãy chọn ít nhất 1 biểu đồ")
            A["d"][5]["final"] = {"title": (p.get("title") or A["d"][5]["title"]).strip(), "charts": ch, "kpis": [int(k) for k in p.get("kpis", [])]}
        elif i == 6:
            publish()
    except Exception as e:
        traceback.print_exc()
        return bad(f"Không thể xác nhận: {e}", 500)
    with LOCK:
        A["st"][i] = "done"
        bump()
    log(("Đã chấp nhận: " + STEP_T[i]) if i < 6 else "Đã duyệt báo cáo")
    if i < 6:
        nxt = NEXT[i]
        try:
            start_job(nxt[0], A["ag"][nxt[0]], nxt[1], "")
        except RuntimeError as e:
            return bad(str(e), 409)
    return jsonify(ok=True)


@bp.post("/api/redo/<int:i>")
def redo(i):
    with LOCK:
        if A["job"]["running"] or A["approved"]:
            return bad("Không thể làm lại lúc này")
        for j in range(i + 1, 7):
            A["st"][j] = "pending"
            A["d"].pop(j, None)
            A["fbh"].pop(str(j), None)
        if i == 0:
            A["st"][0] = "pending"
            A["d"].clear()
            A["clean"] = None
        else:
            A["st"][i] = "await"
        A["err"] = None
        bump()
    log("Quay lại: " + STEP_T[i])
    return jsonify(ok=True)


@bp.post("/api/new")
def new():
    with LOCK:
        if A["job"]["running"]:
            return bad("Đang có tác vụ chạy, hãy chờ xong rồi tạo phân tích mới.", 409)
        reset()
    return jsonify(ok=True)


@bp.get("/api/history/<aid>")
def history_item(aid):
    f = snapshot_path(re.sub(r"[^\w\-]", "", aid))
    if not f.exists():
        return bad("Phân tích này không có bản lưu để xem lại (tạo bởi phiên bản cũ).", 404)
    return jsonify(json.loads(f.read_text("utf-8")))


@bp.post("/api/history/<aid>/delete")
def history_delete(aid):
    with LOCK:
        if A["id"] == aid:
            if A["job"]["running"]:
                return bad("Phân tích này đang chạy, hãy chờ xong rồi xóa.", 409)
            reset()          # đang mở đúng luồng này -> đưa về trạng thái trống
        bump()
    if not delete_history(aid):
        return bad("Không tìm thấy phân tích này.", 404)
    return jsonify(ok=True)


def _file(aid, name):
    return config.WORK / re.sub(r"[^\w\-]", "", aid) / Path(name).name


@bp.get("/api/download/<aid>/<name>")
def download(aid, name):
    f = _file(aid, name)
    return send_file(f, as_attachment=True) if f.exists() else bad("Không tìm thấy tệp", 404)


@bp.get("/api/view/<aid>/<name>")
def view_file(aid, name):
    if name not in ("dashboard.html", "bao_cao.html"):
        return bad("Không hợp lệ", 404)
    f = _file(aid, name)
    return send_file(f, mimetype="text/html") if f.exists() else bad("Không tìm thấy tệp (có thể là bản cũ chưa có tệp này)", 404)


@bp.get("/api/dash_preview")
def dash_preview():
    """Dashboard tương tác dựng từ dữ liệu ĐÃ LÀM SẠCH, dùng để xem thử ở bước Báo cáo (trước khi duyệt)."""
    with LOCK:
        if not A["clean"]:
            return bad("Chưa có dữ liệu đã làm sạch.", 404)
        html = build_dashboard(live_meta(request.args.get("title") or None), A["clean"])
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}
