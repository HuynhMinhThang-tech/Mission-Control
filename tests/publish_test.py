# -*- coding: utf-8 -*-
"""Kiểm thử publish() với trạng thái giả (không cần API key): dựng báo cáo/PPTX/ZIP và lưu vào DB. Chạy: python tests/publish_test.py"""
import io
import os
import sys
import tempfile
import zipfile

tmp = tempfile.mkdtemp()
os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/p.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from app import create_app, db, state  # noqa: E402
from app.export import publish  # noqa: E402

app = create_app()
u = db.create_user("An", "an@gmail.com", "matkhau-123", status="approved")
df = pd.DataFrame({"Khu vực": ["Bắc", "Trung", "Nam", "Tây"], "Doanh thu": [120.5, 80.0, 210.25, 60.0]})
tab = {"title": "Doanh thu theo khu vực", "cols": list(df.columns), "rows": df.values.tolist(), "err": None}

with app.test_request_context():
    state.bind(u["id"])
    A = state.A
    A["question"], A["ctx"], A["started"] = "Khu vực nào bán tốt nhất?", "Cửa hàng bán lẻ", state.now_iso()
    A["files"] = [{"name": "ban_hang.xlsx", "rows": 4}]
    A["clean"] = {"ban_hang.xlsx": df}
    A["x"] = {3: {0: df}}
    A["d"] = {1: {"kpis": [{"label": "Khoảng ngày", "value": "01/2026"}]},
              2: {"pv": None},
              3: {"phase": "result", "tasks": [{"title": "Doanh thu theo khu vực", "goal": "So sánh"}],
                  "result": {"kpis": [{"label": "Tổng doanh thu", "value": "470,75", "note": ""}], "tables": [tab], "findings": []}},
              4: {"summary": "Miền Nam dẫn đầu.", "insights": [{"title": "Miền Nam đạt 210,25, cao nhất", "confidence": "Cao", "evidence": "210,25 / 470,75 = 44,7%", "source": "Doanh thu theo khu vực"}], "actions": [{"text": "Tăng tồn kho miền Nam", "priority": "Cao", "impact": "Giảm thiếu hàng"}], "risks": ["Dữ liệu chỉ có 4 khu vực"]},
              5: {"title": "Báo cáo doanh thu", "narrative": "Tóm tắt.", "final": {"title": "Báo cáo doanh thu", "kpis": [0], "charts": [{"task": 0, "x": "Khu vực", "y": "Doanh thu", "kind": "bars", "title": "Doanh thu", "unit": "", "insight": "", "recommended": True}]}}}
    A["x"] = {3: {0: df}}
    try:
        publish()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("publish() ném lỗi:", type(e).__name__, e)
        sys.exit(1)
    aid = A["id"]
    print("publish() chạy xong, id =", aid, "| outputs =", A["outputs"], "| approved =", A["approved"])
    state.unbind()

h = db.list_history(u["id"])
assert len(h) == 1 and h[0]["id"] == aid and h[0]["snap"] and h[0]["files"] == ["dashboard.html", "bao_cao.html", "bao_cao.pptx", "share.zip"], h
for n, magic in [("dashboard.html", b"<"), ("bao_cao.html", b"<"), ("bao_cao.pptx", b"PK"), ("share.zip", b"PK"), ("bao_cao.md", b"#")]:
    f = db.get_file(u["id"], aid, n)
    assert f and len(f[0]) > 100 and f[0][:1] == magic[:1], (n, f and len(f[0]))
    print(f"  {n:16s} {len(f[0]):>8,} byte  {f[1]}")
names = zipfile.ZipFile(io.BytesIO(db.get_file(u["id"], aid, "share.zip")[0])).namelist()
print("  share.zip chứa:", names)
assert "bao_cao.pptx" in names and any(n.startswith("du_lieu_sach/") for n in names)
snap = db.get_snapshot(u["id"], aid)
assert snap["question"] == "Khu vực nào bán tốt nhất?" and snap["approved"] and snap["outputs"], snap.keys()
print("  snapshot đọc lại được:", sorted(snap)[:6], "...")
print("\nPUBLISH ĐẠT")
