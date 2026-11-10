# -*- coding: utf-8 -*-
"""Kiểm thử phông chữ của bản PowerPoint. Trước đây mọi chữ đều cố định Arial. Nay theo bộ phông người dùng chọn ở thư viện (bp.font):
tiêu đề chữ có chân (Georgia), nội dung chữ không chân (Segoe UI): cặp phông CÓ SẴN trên Windows/macOS, gần phong cách Claude, vì PowerPoint
không nhúng được phông web. Chạy: python tests/pptx_font_test.py"""
import io
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.util import Pt  # noqa: E402

from app import numfmt  # noqa: E402
from app.export import deck, fonts  # noqa: E402

n_ok = 0


def check(cond, label):
    global n_ok
    if not cond:
        print("FAIL:", label)
        sys.exit(1)
    n_ok += 1
    print("ok  ", label)


def make_F(font=None, title="Tình hình chi tiêu 9 ngày cuối tháng", insight_title=None, chart_insight="Sinh hoạt chiếm 84,51%"):
    d = pd.DataFrame({"Danh mục": ["Sinh hoạt", "Di chuyển", "Giải trí", "Phát sinh"], "Chi tiêu": [790000, 60000, 50000, 36000]})
    kp = numfmt.fix_kpis([{"label": "Tổng chi tiêu trong 9 ngày", "value": "936.000"}, {"label": "Chi tiêu trung bình mỗi ngày", "value": "104.000"},
                          {"label": "Tỷ trọng chi tiêu sinh hoạt", "value": "84.51%"}])
    long_t = insight_title or "Chi tiêu sinh hoạt chiếm 84,51% tổng chi tiêu trong 9 ngày cuối tháng, cao hơn hẳn Di chuyển, Giải trí và Phát sinh cộng lại"
    return {"title": title, "question": "Tôi tiêu tiền vào đâu nhiều nhất?", "ctx": "", "date": "09/11/2026", "period": "T10/2026",
            "files": [{"name": "chi_tieu.csv", "rows": 9}], "summary": "Chi tiêu sinh hoạt chiếm phần lớn. " + "Cần theo dõi thêm. " * 3,
            "insights": [{"title": long_t, "confidence": "Cao", "evidence": "Sinh hoạt = 790.000 đ trên tổng 936.000 đ", "source": "Chi tiêu theo danh mục"}],
            "actions": [{"text": "Đặt trần chi tiêu sinh hoạt theo tuần", "priority": "Cao", "impact": "Giảm chi tiêu không cần thiết"}],
            "risks": ["Dữ liệu chỉ có 9 ngày"], "kpis": kp, "dfs": {0: d}, "table_titles": ["Chi tiêu theo danh mục"], "tasks": [{"title": "Chi tiêu theo danh mục", "goal": ""}],
            "applied": ["Chuẩn hóa ngày"], "quality": None, "font": font,
            "charts": [{"task": 0, "x": "Danh mục", "y": "Chi tiêu", "kind": "bars", "title": "Chi tiêu theo danh mục", "unit": "đ", "insight": chart_insight},
                       {"task": 0, "x": "Danh mục", "y": "Chi tiêu", "kind": "donut", "title": "Cơ cấu chi tiêu", "unit": "đ", "insight": ""}]}


def fonts_in(blob):
    """Mọi tên phông được ghi trong tệp PPTX (slide + biểu đồ), đếm theo tên."""
    z = zipfile.ZipFile(io.BytesIO(blob))
    out = {}
    for n in z.namelist():
        if n.endswith(".xml") and (n.startswith("ppt/slides/") or n.startswith("ppt/charts/")):
            for m in re.findall(r'<a:latin typeface="([^"]+)"', z.read(n).decode("utf8")):
                out[m] = out.get(m, 0) + 1
    return out


# ---- mặc định 'Giống Claude': tiêu đề chữ có chân, nội dung chữ không chân, KHÔNG còn Arial
blob = deck.build_pptx(make_F())
f = fonts_in(blob)
check("Arial" not in f, f"mặc định: không còn chữ nào dùng Arial ({f})")
check(set(f) == {"Georgia", "Segoe UI"}, "mặc định: đúng hai phông Georgia (tiêu đề) và Segoe UI (nội dung)")
prs = Presentation(io.BytesIO(blob))


def runs(slide):
    return [r for sh in slide.shapes if sh.has_text_frame for p in sh.text_frame.paragraphs for r in p.runs]


cover = runs(prs.slides[0])
check(cover[0].font.name == "Georgia" and cover[0].font.size == Pt(38), "bìa: tiêu đề dùng Georgia, cỡ 38")
ttl = [r for r in runs(prs.slides[1]) if r.font.size == Pt(24)]
check(ttl and all(r.font.name == "Georgia" for r in ttl), "slide thường: tiêu đề (cỡ 24) dùng Georgia")
body = [r for s in prs.slides for r in runs(s) if r.font.size in (Pt(10), Pt(11), Pt(12), Pt(13), Pt(14))]
check(body and all(r.font.name == "Segoe UI" for r in body), "nội dung, chú thích, nhãn: dùng Segoe UI")
kpi = [r for s in prs.slides for r in runs(s) if r.font.size == Pt(28)]
check(kpi and all(r.font.name == "Segoe UI" for r in kpi), "số KPI cỡ lớn dùng phông không chân (số lining, không bị chữ có chân làm số lệch dòng)")
alltext = "\n".join(r.text for s in prs.slides for r in runs(s))
check("936.000 đ" in alltext and "104.000 đ" in alltext and "84,51%" in alltext, "PPTX hiện đủ KPI 936.000 đ / 104.000 đ / 84,51% (không còn 936 đ)")

# ---- tiêu đề dài co cỡ để luôn trong 2 dòng (chữ có chân rộng hơn Arial)
long_prs = Presentation(io.BytesIO(deck.build_pptx(make_F(chart_insight="X" * 140))))
sizes = {r.font.size.pt for s in long_prs.slides for r in runs(s) if r.font.name == "Georgia" and r.font.bold and len(r.text) > 100}
check(sizes and max(sizes) <= 20, f"tiêu đề rất dài co xuống ≤20pt ({sizes})")
mid = Presentation(io.BytesIO(deck.build_pptx(make_F(chart_insight="Y" * 100))))
check(any(r.font.size.pt == 22 for s in mid.slides for r in runs(s) if len(r.text) == 100), "tiêu đề dài vừa: 22pt")

# ---- các bộ phông khác
for key, want in [("system", {"Arial"}), ("serif", {"Georgia"}), ("inter", {"Segoe UI"}), ("bevn", {"Segoe UI"}), ("app", {"Georgia", "Segoe UI"})]:
    got = set(fonts_in(deck.build_pptx(make_F(font=key))))
    check(got == want, f"bộ phông '{key}' -> PPTX dùng {sorted(want)} (thực tế {sorted(got)})")
check(set(fonts_in(deck.build_pptx(make_F(font="khong-co")))) == {"Georgia", "Segoe UI"}, "khóa phông lạ -> mặc định Giống Claude")

# ---- không rò rỉ giữa các lần xuất (ContextVar): sau khi dựng bản 'system' thì lần dựng kế tiếp vẫn đúng, và mặc định ngoài build là Georgia/Segoe
deck.build_pptx(make_F(font="system"))
check(deck.FONT() == "Segoe UI" and deck.FONT(head=True) == "Georgia", "sau khi dựng bản 'system', phông mặc định không bị kẹt lại")
check(set(fonts_in(deck.build_pptx(make_F()))) == {"Georgia", "Segoe UI"}, "lần dựng kế tiếp không bị ảnh hưởng bởi lần trước")

# ---- bảng phông ở Python và ở giao diện (JS) phải khớp
js = open(os.path.join(ROOT, "static", "js", "analysis.js"), encoding="utf-8").read()
m = re.search(r"const PPT_FONTS = \{(.*?)\};", js, re.S)
jsmap = {k: tuple(re.findall(r"'([^']+)'", v)) for k, v in re.findall(r"(\w+):\s*(\[[^\]]*\])", m.group(1))}
check(jsmap == fonts._PPT, f"giao diện (analysis.js) và fonts.py cùng một bảng phông PowerPoint ({jsmap})")
check(all(fonts.public()[k]["ppt"] == list(v) for k, v in fonts._PPT.items()) and set(fonts._PPT) == set(fonts._SPEC), "fonts.public() trả đúng phông PowerPoint cho mọi bộ phông")
check("Arial" not in js.split("PPT_FONTS")[1].split("const FONTS")[0].replace("system: ['Arial', 'Arial']", ""), "giao diện không còn ghi 'PowerPoint luôn dùng Arial'")
check("luôn dùng Arial" not in js, "ghi chú cũ 'luôn dùng Arial' đã bỏ")

print(f"\nTẤT CẢ {n_ok} KIỂM TRA ĐỀU ĐẠT")
