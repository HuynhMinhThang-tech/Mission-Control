# -*- coding: utf-8 -*-
"""Gói xuất file: dashboard.html, bao_cao.pptx, bao_cao.md, share.zip + bản lưu để xem lại trong Lịch sử."""
import json
import re
import zipfile
from datetime import datetime

from ..config import WORK
from ..state import A, now_iso, save_history
from ..utils import clean_json
from .dashboard import build_html
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


def snapshot():
    """Toàn bộ các bước đã thực hiện, để xem lại ở chế độ chỉ đọc."""
    keys = ("id", "question", "ctx", "files", "d", "ag", "log", "outputs", "started", "finished", "applied")
    s = {k: A[k] for k in keys}
    s["st"] = ["done"] * 7
    s["approved"] = True
    return clean_json(s)


def publish():
    F = make_final()
    out = WORK / A["id"]
    out.mkdir(exist_ok=True)
    (out / "dashboard.html").write_text(build_html(F), "utf-8")
    (out / "bao_cao.pptx").write_bytes(build_pptx(F))
    (out / "bao_cao.md").write_text(build_md(F), "utf-8")
    with zipfile.ZipFile(out / "share.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for n in ("dashboard.html", "bao_cao.pptx", "bao_cao.md"):
            z.write(out / n, n)
        for n, d in A["clean"].items():
            z.writestr("du_lieu_sach/" + re.sub(r"[^\w.\-]", "_", n) + ("" if n.endswith(".csv") else ".csv"), d.to_csv(index=False))
    A["outputs"] = ["dashboard.html", "bao_cao.pptx", "share.zip"]
    A["approved"] = True
    A["finished"] = now_iso()
    (out / "snapshot.json").write_text(json.dumps(snapshot(), ensure_ascii=False), "utf-8")
    save_history({"id": A["id"], "question": A["question"], "title": A["question"], "ctx": A["ctx"], "started": A["started"],
                  "finished": A["finished"], "files": A["outputs"], "report_title": F["title"],
                  "sources": [f["name"] for f in A["files"]]})