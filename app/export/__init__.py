# -*- coding: utf-8 -*-
"""Gói xuất file: dashboard.html, bao_cao.pptx, bao_cao.md, share.zip + bản lưu để xem lại trong Lịch sử."""
import io
import re
import zipfile
from datetime import datetime

from .. import db
from ..state import A, current_user_id, now_iso
from ..utils import clean_json
from .dashboard import build_html
from .interactive import build_dashboard
from .deck import build_pptx
from .common import dedupe_charts
from .markdown import build_md


def make_final():
    d3, d4, d5 = A["d"][3]["result"], A["d"][4], A["d"][5]
    fin = d5["final"]
    kpi_all = d3["kpis"]
    period = next((k["value"] for k in A["d"][1]["kpis"] if k["label"] == "Khoảng ngày"), None)
    tasks = [{"title": t["title"], "goal": t.get("goal", "")} for t in A["d"][3]["tasks"]]
    method = f"Làm sạch: {', '.join(A.get('applied', [])) or 'không áp dụng'}. Phân tích: {', '.join(t['title'] for t in tasks)}."
    return {"title": fin["title"], "question": A["question"], "ctx": A["ctx"], "date": datetime.now().strftime("%d/%m/%Y"),
            "kpis": [kpi_all[i] for i in fin["kpis"] if i < len(kpi_all)], "charts": dedupe_charts(fin["charts"], A["x"][3]), "dfs": A["x"][3],
            "tables": d3["tables"], "table_titles": [t["title"] for t in d3["tables"]], "tasks": tasks,
            "summary": d4["summary"], "insights": d4["insights"], "actions": d4["actions"], "risks": d4.get("risks", []),
            "narrative": d5["narrative"], "method": method, "applied": A.get("applied", []), "files": A["files"],
            "period": period, "quality": A["d"].get(2, {}).get("pv")}


def live_meta(title=None):
    """Thông tin chữ đi kèm dashboard tương tác. Dùng được cả khi chưa duyệt (xem trước ở bước Báo cáo)."""
    d4, d5 = A["d"].get(4) or {}, A["d"].get(5) or {}
    return {"title": title or (d5.get("final") or {}).get("title") or d5.get("title") or "Dashboard phân tích", "question": A["question"], "ctx": A["ctx"],
            "date": datetime.now().strftime("%d/%m/%Y"), "summary": d4.get("summary", ""), "insights": d4.get("insights", []),
            "actions": d4.get("actions", []), "risks": d4.get("risks", [])}


def snapshot():
    """Toàn bộ các bước đã thực hiện, để xem lại ở chế độ chỉ đọc."""
    keys = ("id", "question", "ctx", "files", "d", "ag", "log", "outputs", "started", "finished", "applied")
    s = {k: A[k] for k in keys}
    s["st"] = ["done"] * 7
    s["approved"] = True
    return clean_json(s)


def publish():
    """Dựng toàn bộ tệp xuất trong bộ nhớ rồi lưu một lượt vào database (không còn ghi ra đĩa)."""
    F = make_final()
    mt_html, mt_md = "text/html; charset=utf-8", "text/markdown; charset=utf-8"
    files = {
        "dashboard.html": (build_dashboard(live_meta(F["title"]), A["clean"]).encode("utf-8"), mt_html),   # dashboard TƯƠNG TÁC (lọc, lọc chéo)
        "bao_cao.html": (build_html(F).encode("utf-8"), mt_html),                                           # báo cáo tĩnh có bằng chứng
        "bao_cao.pptx": (build_pptx(F), "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        "bao_cao.md": (build_md(F).encode("utf-8"), mt_md),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ("dashboard.html", "bao_cao.html", "bao_cao.pptx", "bao_cao.md"):
            z.writestr(n, files[n][0])
        for n, d in A["clean"].items():
            z.writestr("du_lieu_sach/" + re.sub(r"[^\w.\-]", "_", n) + ("" if n.endswith(".csv") else ".csv"), d.to_csv(index=False))
    files["share.zip"] = (buf.getvalue(), "application/zip")
    outputs = ["dashboard.html", "bao_cao.html", "bao_cao.pptx", "share.zip"]

    A["outputs"], A["approved"], A["finished"] = outputs, True, now_iso()
    try:
        db.save_analysis(current_user_id(),
                         {"id": A["id"], "question": A["question"], "title": A["question"], "ctx": A["ctx"], "started": A["started"], "finished": A["finished"],
                          "files": outputs, "report_title": F["title"], "sources": [f["name"] for f in A["files"]]},
                         snapshot(), files)
    except Exception:
        A["outputs"], A["approved"], A["finished"] = [], False, None        # lưu lỗi thì không để phiên kẹt ở trạng thái "đã duyệt"
        raise
