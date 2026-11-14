# -*- coding: utf-8 -*-
"""Đa dạng biểu đồ: 9 dạng (cột ngang, cột dọc, kẹo mút, Pareto, đường, vùng, vành khuyên, tròn đặc, treemap) ở cả bốn nơi:
bước Phân tích/Báo cáo (giao diện), báo cáo HTML (SVG), slide PPTX, bảng điều khiển xuất ra. Cùng quy tắc: tiền nguyên đồng.
Chạy: python tests/charts_test.py"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pptx import Presentation  # noqa: E402

from app.agents.charts import KINDS, valid_charts  # noqa: E402
from app.export import deck  # noqa: E402
from app.export.common import facts  # noqa: E402
from app.export.dash_plan import STATIC_KINDS, _static  # noqa: E402
from app.export.svg import chart_svg, pareto_rows, tm_layout  # noqa: E402

bad = []


def check(ok, msg):
    print(("OK   " if ok else "FAIL ") + msg)
    if not ok:
        bad.append(msg)


rows = [("TP. Hồ Chí Minh", 3724488031.25), ("Bình Dương", 674584587.5), ("Cần Thơ", 651418562.5), ("Đồng Nai", 478596350.0), ("Hà Nội", 120000000.0), ("Huế", 90000000.0)]
series = [("2026-01", 120.0), ("2026-02", 150.0), ("2026-03", 135.0), ("2026-04", 190.0)]
NEW = ("area", "pie", "lollipop", "pareto", "treemap")

check(set(KINDS) == {"bars", "cols", "line", "area", "donut", "pie", "lollipop", "pareto", "treemap"} and set(STATIC_KINDS) == set(KINDS), "9 dạng biểu đồ, bảng điều khiển nhận đủ")

# --- báo cáo HTML (SVG) ---
for k in KINDS:
    s = chart_svg(k, rows if k not in ("line", "area") else series, "đ" if k not in ("line", "area") else "")
    check(s.startswith("<svg") and s.endswith("</svg>"), f"SVG {k}: hợp lệ")
s = {k: chart_svg(k, rows, "đ") for k in KINDS if k not in ("line", "area")}
check(all("3.724.488.031" in v for v in s.values() if True) and not any(",25" in v or ",5<" in v for v in s.values()), "SVG: số tiền nguyên đồng (3.724.488.031), không có phần lẻ")
check("class=\"stem" in s["lollipop"] and "class=\"pop" in s["lollipop"], "kẹo mút: thanh mảnh + chấm")
check("class=\"ref\"" in s["pareto"] and "class=\"ln\"" in s["pareto"] and "88,00%" in s["pareto"], "Pareto: vạch 80%, đường cộng dồn, nêu 88,00% ở điểm vượt 80%")
check("class=\"tm\"" in s["treemap"] and s["treemap"].count("<rect") == 6, "treemap: mỗi nhóm một ô")
check("Tổng" not in s["pie"] and "Tổng" in s["donut"], "tròn đặc không có lỗ giữa, vành khuyên có tổng ở giữa")
check("area s" in chart_svg("area", series, "") and "area s" not in chart_svg("line", series, ""), "vùng tô đậm hơn đường")
# dữ liệu không hợp: tự rơi về dạng gần nhất, không vỡ
neg = [("A", 5.0), ("B", -2.0), ("C", 3.0)]
check(all(chart_svg(k, neg, "").startswith("<svg") for k in KINDS), "có giá trị âm: Pareto/treemap/tròn tự rơi về cột, không lỗi")
check(chart_svg("pareto", rows[:2], "đ").startswith("<svg") and chart_svg("treemap", [("A", 0.0), ("B", 0.0)], "").startswith("<svg"), "quá ít nhóm hoặc tổng bằng 0 vẫn vẽ được")

# --- Pareto / treemap tính đúng ---
pr = pareto_rows(rows)
check([round(c, 2) for _, _, c in pr][:3] == [64.90, 76.65, 88.00] and pr[-1][2] > 99.99, f"cộng dồn Pareto đúng ({[round(c, 2) for _, _, c in pr]})")
cells = []
tm_layout(sorted(rows, key=lambda r: -r[1]), 0, 0, 520, 290, cells)
area_sum = sum(w * h for _, _, _, w, h in cells)
check(abs(area_sum - 520 * 290) < 1 and len(cells) == 6, f"treemap phủ kín hình chữ nhật ({area_sum:.0f} = {520 * 290})")
tot = sum(v for _, v in rows)
check(all(abs(w * h / (520 * 290) - v / tot) < 1e-9 for (_, v), _, _, w, h in cells), "diện tích mỗi ô tỷ lệ đúng giá trị")
check("3/6 nhóm đầu chiếm 88,00% tổng" in facts(rows, "pareto", "đ"), "facts nêu số nhóm đầu tạo 80%")
check(any("→" in f for f in facts(series, "area", "")), "vùng dùng cùng thống kê xu hướng với đường")

# --- slide PPTX ---
prs = Presentation()
for k in KINDS:
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    deck._chart(sl, 0.5, 0.5, 8, 4.5, sorted(rows, key=lambda r: -r[1]) if k in ("lollipop", "pareto", "treemap") else (series if k in ("line", "area") else rows), k, "đ")
buf = io.BytesIO()
prs.save(buf)
buf.seek(0)
types = [str(sh.chart.chart_type).split(" ")[0] for sl in Presentation(buf).slides for sh in sl.shapes if sh.has_chart]
check(len(types) == 9 and "AREA" in types and "PIE" in types and "DOUGHNUT" in types, f"PPTX: 9 biểu đồ hợp lệ, vùng/tròn/vành khuyên dùng kiểu gốc ({types})")

# --- kiểm tra kind AI trả về ---
ycols = ["Tổng tiền hàng", "Doanh thu", "Lợi nhuận", "Chi phí", "Giá vốn", "Số lượng"]
t = {"title": "x", "cols": ["Tỉnh"] + ycols, "rows": [[a] + [b] * 6 for a, b in rows], "units": [""] + ["đ"] * 5 + [""]}
vc = valid_charts([{"task": 0, "x": "Tỉnh", "y": y, "kind": k, "title": k, "unit": ""} for y, k in zip(ycols, ("treemap", "pareto", "lollipop", "area", "pie", "radar"))], [t])
check([c["kind"] for c in vc] == ["treemap", "pareto", "lollipop", "area", "pie", "bars"], f"AI chọn dạng mới được chấp nhận, dạng lạ ('radar') chuyển về cột ngang ({[c['kind'] for c in vc]})")
check([c["unit"] for c in vc] == ["đ", "đ", "đ", "đ", "đ", ""], f"đơn vị biểu đồ suy từ cột: tiền -> đ, số lượng để trống ({[c['unit'] for c in vc]})")

# --- bảng điều khiển: thẻ tĩnh giữ dạng ---
for k in KINDS:
    n = _static({"type": "static", "sid": "a", "kind": k, "title": "t", "labels": ["a", "b", "c"], "values": [3, 2, 1], "unit": "đ"})
    if not n or n["kind"] != k:
        check(False, f"thẻ tĩnh giữ dạng {k}")
        break
else:
    check(True, "thẻ tĩnh của bảng điều khiển giữ nguyên cả 9 dạng")
check(_static({"type": "static", "sid": "a", "kind": "radar", "labels": ["a", "b"], "values": [1, 2]})["kind"] == "bars", "dạng lạ trong bảng điều khiển rơi về cột ngang")

print()
if bad:
    print(f"CÓ {len(bad)} LỖI")
    sys.exit(1)
print("TẤT CẢ ĐẠT")
