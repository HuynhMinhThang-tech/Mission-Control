# -*- coding: utf-8 -*-
"""Kiểm thử TRỌN LUỒNG với LLM giả: KPI mà AI trả là '936.000' (kiểu Việt Nam, 936 nghìn) phải hiện 936.000 đ ở bước Phân tích VÀ ở mọi tệp xuất ra.
Trước đây hệ thống đọc '936.000' thành 936,000 nên thẻ KPI hiện '936 đ', báo cáo/PPTX cũng sai theo.
Chạy: python tests/kpi_flow_test.py"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _flow as F  # noqa: E402

fails = 0


def check(name, cond, extra=""):
    global fails
    print(("OK   " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    fails += 0 if cond else 1


_orig = F.fake_llm


def _llm(*a, **k):
    out = _orig(*a, **k)
    try:
        j = json.loads(out)
    except (TypeError, ValueError):
        return out
    if isinstance(j, dict) and j.get("kpis"):
        j["kpis"] = [{"label": "Tổng chi tiêu trong 9 ngày", "value": "936.000", "delta": ""}]       # đúng ca của người dùng
        return json.dumps(j, ensure_ascii=False)
    return out


F.fake_llm = _llm
app, c = F.setup()
F.post(c, "/api/sample"); F.post(c, "/api/start", {"question": "Tôi tiêu tiền vào đâu nhiều nhất?"}); F.wait(c)
for i in (1, 2):
    F.post(c, f"/api/accept/{i}"); F.wait(c)
F.post(c, "/api/a3/code", {"ids": ["m0"], "custom": "", "specs": []}); F.wait(c)
s = F.post(c, "/api/a3/exec", {"codes": []}) and F.wait(c, 120)
kp = s["d"]["3"]["result"]["kpis"]
check("bước Phân tích: thẻ KPI hiện đủ '936.000 đ' (không còn '936 đ')", kp and kp[0]["value"] == "936.000 đ", str(kp))
for i in (3, 4):
    F.post(c, f"/api/accept/{i}"); F.wait(c)
s = F.wait(c)
F.post(c, "/api/accept/5", {"title": "Chi tiêu 9 ngày", "charts": s["d"]["5"]["charts"], "kpis": [0], "dash": s["d"]["5"]["dash"]["ai"]}); F.wait(c)
F.post(c, "/api/accept/6"); s = F.wait(c)
check("duyệt xong, có đủ tệp xuất", s["approved"] and "bao_cao.pptx" in s["outputs"], str(s.get("outputs")))
get = lambda name: c.get(f"/api/download/{s['id']}/{name}").data  # noqa: E731
html, md = get("bao_cao.html").decode("utf8"), get("bao_cao.md").decode("utf8")
check("báo cáo HTML: KPI 936.000 đ, không có thẻ '936 đ'", "936.000 đ" in html and "936 đ" not in html.replace("936.000 đ", ""), "")
check("báo cáo Markdown: KPI 936.000 đ", "936.000 đ" in md and "936 đ" not in md.replace("936.000 đ", ""))
from pptx import Presentation  # noqa: E402
prs = Presentation(io.BytesIO(get("bao_cao.pptx")))
ppt = "\n".join(r.text for sl in prs.slides for sh in sl.shapes if sh.has_text_frame for p in sh.text_frame.paragraphs for r in p.runs)
check("PowerPoint: KPI 936.000 đ", "936.000 đ" in ppt and "936 đ" not in ppt.replace("936.000 đ", ""))
fonts = {r.font.name for sl in prs.slides for sh in sl.shapes if sh.has_text_frame for p in sh.text_frame.paragraphs for r in p.runs}
check("PowerPoint: dùng Georgia + Segoe UI, không còn Arial", fonts == {"Georgia", "Segoe UI"}, str(fonts))
snap = json.dumps(c.get(f"/api/history/{s['id']}").get_json(), ensure_ascii=False)
check("lịch sử lưu đúng KPI 936.000 đ", "936.000 đ" in snap)
print(f"\n{'TẤT CẢ ĐẠT' if not fails else str(fails) + ' KIỂM TRA THẤT BẠI'}")
sys.exit(1 if fails else 0)
