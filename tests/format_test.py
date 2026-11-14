# -*- coding: utf-8 -*-
"""Kiểm thử hồi quy cho: số/đơn vị tiếng Việt, nhãn cột, tiêu đề biểu đồ khớp dữ liệu, nhiều sheet, nhà cung cấp LLM.
Dựng lại ĐÚNG các lỗi người dùng đã thấy (2.24 trillion VNĐ, 11773398767.5, 'điểm', trongLuongKg, tiêu đề 'giảm 15,7%' trên biểu đồ tăng...).
Chạy: python tests/format_test.py"""
import io
import os
import re
import sys
import tempfile
import zipfile

tmp = tempfile.mkdtemp()
os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/f.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app import create_app, db, labels, numfmt, providers, state  # noqa: E402
from app.data.loader import list_sheets, load_files  # noqa: E402
from app.export import publish  # noqa: E402

n_ok = 0


def check(cond, label):
    global n_ok
    if not cond:
        print("FAIL:", label)
        sys.exit(1)
    n_ok += 1
    print("ok  ", label)


# ------------------------------------------------------------------ 1. số và đơn vị --
known = numfmt.Known.from_dfs([pd.DataFrame({"Tháng": ["9", "8"], "Doanh thu": [2240813537.5, 1935760431.25]})])
t = numfmt.fix_text("Doanh thu tháng 9 đạt 2.24 trillion VNĐ, cao nhất trong năm.", known)
check("trillion" not in t and "VNĐ" not in t and "2.240.813.538 đ" in t, f"'2.24 trillion VNĐ' -> số ĐỦ như bảng, tiền nguyên đồng '2.240.813.538 đ' (bảng 2.240.813.537,5; {t})")
t = numfmt.fix_text("Doanh thu tháng 9 lên tới 2 241 813 537 điểm, vượt 12 % so với tháng 8.", known)
check("2.241.813.537 đ" in t and "12,00%" in t and "điểm" not in t, f"số ngăn bằng dấu cách + 'điểm' -> chuẩn Việt, tiền ký hiệu đ, % 2 chữ số ({t})")
t = numfmt.fix_text("Tháng 9 = 2240813537.5, tỷ lệ tăng 2240813537.5/1935760431.25-1≈0.157", known)
check("2.240.813.537,50" in t and "0,16" in t and "." not in t.replace("2.240.813.537", "").replace("1.935.760.431", ""), f"số thô có dấu ngăn nghìn + dấu phẩy thập phân ({t})")
t = numfmt.fix_text("Tỷ lệ hoàn trả cao nhất tháng 3 (6.97%), vượt mức 4.9%. Ngày 24.10.2026, bản 1.2.3, giá 2.240 đồng.")
check("6,97%" in t and "4,90%" in t and "24.10.2026" in t and "1.2.3" in t and "2.240 đ" in t, f"đổi dấu thập phân (% luôn 2 chữ số) nhưng không đụng ngày/phiên bản/số nghìn ({t})")
check(numfmt.fix_text(numfmt.fix_text("Tổng 2.24 trillion VNĐ, 6.97%", known), known) == numfmt.fix_text("Tổng 2.24 trillion VNĐ, 6.97%", known), "chuẩn hóa là idempotent (chạy hai lần không đổi)")
kp = numfmt.fix_kpi({"label": "Doanh thu tổng năm 2026", "value": "11773398767.5"})
check(kp["value"] == "11.773.398.768 đ", f"KPI tiền ghi ĐỦ số, có dấu ngăn nghìn, đơn vị đ, nguyên đồng: {kp['value']}")
check(numfmt.fix_kpi({"label": "Số đơn", "value": "14500"})["value"] == "14.500", "KPI số đếm có dấu ngăn nghìn")
check(numfmt.fix_kpi({"label": "Tỷ lệ hoàn trả", "value": "0.0697"})["value"] == "6,97%", "KPI tỷ lệ 0-1 -> phần trăm")
check(not numfmt.has_value(numfmt.fix_kpi({"label": "Tỷ trọng bán hàng theo vùng", "value": ""})), "KPI rỗng bị nhận diện để loại")
bad = numfmt.audit("Điện thoại & phụ kiện chiếm 1.557.676.062 đồng, tháng 9 đạt 2,24 tỷ đồng", numfmt.Known([2557676062.5, 2240813537.5]))
check(bad == ["1.557.676.062"], f"bắt số lớn không khớp bảng ({bad}), không bắt số đúng")

check(numfmt.audit("Doanh thu tháng 9 lên tới 2.241.813.537 đồng", numfmt.Known([2240813537.5, 1935760431.25])) == ["2.241.813.537"],
      "bắt số AI viết lệch 1 triệu so với bảng (2.241.813.537 so với 2.240.813.537,5)")
check(numfmt.audit("Tăng 304.053.106 đồng so với tháng 8", numfmt.Known.from_dfs([pd.DataFrame({"Doanh thu": [2240813537.5, 1936760431.25]})])) == [],
      "số suy ra hợp lệ (chênh lệch hai ô cùng cột) không bị báo oan")

# ------------------------------------------------------------------ 1a. QUY TẮC SỐ DUY NHẤT --
from app.utils import col_fmt, fmt_dec, fmt_pct, fmt_val, vn  # noqa: E402
check(vn(1234567) == "1.234.567" and vn(12.0) == "12" and vn(1234.5) == "1.234,50" and vn(0.004) == "0,00" and vn(23333.3333) == "23.333,33", "số nguyên không phần thập phân, số lẻ luôn 2 chữ số")
check(fmt_pct(54.2) == "54,20%" and fmt_pct(100) == "100,00%" and fmt_val(155000, "đ") == "155.000 đ" and fmt_val(71.95, "%") == "71,95%" and fmt_val(12.5, "kg") == "12,50 kg", "tỷ lệ 2 chữ số; tiền ghi đủ kèm đơn vị của dữ liệu")
check(col_fmt([1, 2, 3])(1000) == "1.000" and col_fmt([1, 2.5, 3])(1000) == "1.000,00", "cột có số lẻ thì mọi ô 2 chữ số; cột nguyên thì không có phần thập phân")
t = numfmt.fix_text("Chi tiêu trung bình 24,6 nghìn đ, tối đa 155.000đ, sinh hoạt chiếm 71,9%; 5 đồng nghiệp, 3 đội.")
check("24.600 đ" in t and "155.000 đ" in t and "71,90%" in t and "5 đồng nghiệp" in t and "3 đội" in t, f"'24,6 nghìn đ' -> '24.600 đ', một ký hiệu tiền, % 2 chữ số, không đụng từ khác ({t})")
check(numfmt.fix_text(t) == t, "chuẩn hóa số idempotent")
check(numfmt.fix_kpi({"label": "Chi tiêu trung bình", "value": "24600"})["value"] == "24.600 đ" and numfmt.fix_kpi({"label": "Tỷ trọng sinh hoạt", "value": "71.95"})["value"] == "71,95%", "KPI: tiền đủ số, tỷ lệ 2 chữ số")

# ---- tiền ghi nguyên đồng (không có phần thập phân), số lẻ khác giữ nguyên ----
from app.utils import fmt_num, is_money_unit  # noqa: E402
check(fmt_val(3724488031.25, "đ") == "3.724.488.031 đ" and fmt_val(1850743100, "đ") == "1.850.743.100 đ", "tiền có phần lẻ -> nguyên đồng: 3.724.488.031,25 -> 3.724.488.031 đ")
check(fmt_val(651418562.5, "đ") == "651.418.563 đ" and fmt_val(674584587.5, "đ") == "674.584.588 đ" and fmt_val(-2.5, "đ") == "-3 đ", "làm tròn nửa ra xa số 0 (giống trình duyệt), không làm tròn về số chẵn của Python")
check(fmt_val(5.42, "kg") == "5,42 kg" and vn(0.41) == "0,41" and fmt_val(1234.5, "") == "1.234,50" and fmt_val(54.2, "%") == "54,20%", "số thập phân KHÔNG phải tiền giữ nguyên 2 chữ số (kg, số thuần, %)")
check(is_money_unit("đ") and is_money_unit("VNĐ") and is_money_unit("vnd") and not is_money_unit("kg") and not is_money_unit("%") and not is_money_unit(""), "nhận đơn vị tiền")
check(fmt_num(1234.5, "đ") == "1.235" and fmt_num(1234.5, "kg") == "1.234,50" and fmt_num(1234.5) == "1.234,50", "nhãn số trên biểu đồ theo đơn vị (không kèm đơn vị)")
check(col_fmt([1.5, 2, 3], "đ")(1234.5) == "1.235" and col_fmt([1.5, 2, 3], "kg")(1234.5) == "1.234,50", "cột tiền luôn nguyên đồng kể cả khi có ô lẻ; cột lẻ khác vẫn 2 chữ số")
_k = numfmt.fix_kpi({"label": "Tổng tiền hàng tới TP. Hồ Chí Minh", "value": "3.724.488.031,25 đ", "delta": "+26,12%"})
check(_k["value"] == "3.724.488.031 đ" and _k["delta"] == "+26,12%", f"KPI tiền: bỏ phần thập phân, delta giữ nguyên ({_k})")
check(numfmt.fix_kpi({"label": "Doanh thu", "value": 11773398767.5})["value"] == "11.773.398.768 đ" and numfmt.fix_kpi({"label": "Trọng lượng trung bình", "value": 5.4166})["value"] == "5,42", "KPI số thật: tiền nguyên đồng, số lẻ không phải tiền giữ 2 chữ số")
_t = numfmt.fix_text("Tổng tiền hàng 3724488031.25 đồng, trọng lượng 5,42 kg, tỷ trọng 67,36%, điểm 4,35, 674.584.587,5 đ")
check("3.724.488.031 đ" in _t and "674.584.588 đ" in _t and "5,42 kg" in _t and "67,36%" in _t and "4,35" in _t, f"văn bản AI: chỉ số đứng trước ký hiệu đ bị bỏ phần thập phân ({_t})")
check(numfmt.fix_text(_t) == _t, "chuẩn hóa tiền idempotent")
check(labels.unit("Điểm đánh giá") == "" and labels.unit("DanhGia") == "" and labels.unit("Tổng tiền hàng") == "đ" and labels.unit("TrongLuongKg") == "kg", "«Điểm đánh giá» không bị nhận là tiền (tiền bị bỏ phần thập phân, điểm thì không)")
from app.data.sandbox import df_table  # noqa: E402
_tb = df_table(pd.DataFrame({"Tỉnh": ["A", "B"], "Tổng tiền hàng": [1.5, 2.5], "Trọng lượng (kg)": [0.41, 3.63]}), "x")
check(_tb["units"] == ["", "đ", "kg"], f"bảng kết quả mang đơn vị từng cột để giao diện biết cột nào là tiền ({_tb['units']})")
from app.agents.charts import valid_charts  # noqa: E402
_vc = valid_charts([{"task": 0, "x": "Tỉnh", "y": "Tổng tiền hàng", "kind": "bars", "unit": ""}, {"task": 0, "x": "Tỉnh", "y": "Trọng lượng (kg)", "kind": "bars", "unit": "VNĐ"}], [_tb])
check(_vc[0]["unit"] == "đ" and _vc[1]["unit"] == "đ", f"biểu đồ: AI để trống đơn vị thì suy từ cột (tiền -> đ); VNĐ gộp về đ ({[c['unit'] for c in _vc]})")

# bản JavaScript (giao diện) phải ra CHÍNH XÁC cùng kết quả với bản Python (báo cáo, slide, bản tổng hợp)
import json as _json, shutil as _sh, subprocess as _sp  # noqa: E402
if _sh.which("node"):
    _vec = [0, 5, 12.0, 1234567, 1234.5, 0.004, 99.999, -7, -2.5, 23333.3333, 2240813537.5, 100, 54.2, 0.5]
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _js = ("const fs=require('fs'),vm=require('vm');const c=vm.createContext({Intl});vm.runInContext(fs.readFileSync('static/js/fmt.js','utf8')+';this.FMT=FMT',c);"
           "const v=JSON.parse(process.argv[1]);console.log(JSON.stringify({num:v.map(x=>c.FMT.num(x)),dec:v.map(x=>c.FMT.dec(x)),pct:v.map(x=>c.FMT.pct(x)),val:v.map(x=>c.FMT.val(x,'đ')),"
           "ci:c.FMT.colFmt([1,2,3])(1000),cf:c.FMT.colFmt([1,2.5])(1000),nm:v.map(x=>c.FMT.numU(x,'đ')),nk:v.map(x=>c.FMT.numU(x,'kg')),vk:v.map(x=>c.FMT.val(x,'kg')),cm:v.map(x=>c.FMT.colFmt([1.5],'đ')(x))}))")
    _r = _json.loads(_sp.run(["node", "-e", _js, _json.dumps(_vec)], cwd=_root, capture_output=True, text=True, check=True).stdout)
    _py = {"num": [vn(x) for x in _vec], "dec": [fmt_dec(x) for x in _vec], "pct": [fmt_pct(x) for x in _vec], "val": [fmt_val(x, "đ") for x in _vec],
           "ci": col_fmt([1, 2, 3])(1000), "cf": col_fmt([1, 2.5])(1000), "nm": [fmt_num(x, "đ") for x in _vec], "nk": [fmt_num(x, "kg") for x in _vec],
           "vk": [fmt_val(x, "kg") for x in _vec], "cm": [col_fmt([1.5], "đ")(x) for x in _vec]}
    check(_r == _py, f"JS (fmt.js) và Python (utils.py) định dạng số GIỐNG HỆT nhau: {[(k, a, b) for k in _py for a, b in [(_r[k], _py[k])] if a != b][:2]}")
else:
    print("BỎ QUA  đối chiếu JS/Python: không có node")

# ------------------------------------------------------------------ 1b'. cột «Phương án đề xuất xử lý», nhãn nhận định, vị trí bản tổng hợp --
from app.data.quality import FIX_GENERIC, quality  # noqa: E402
_q = quality({"f.csv": pd.DataFrame({"Số tiền": ["50.000 ", "95.000", "95.000", "7"], "Ghi chú": [None, "a", "a", "b"]})}, with_fix=True)
check("fix" in _q.columns and all(str(x).strip() for x in _q["fix"]) and set(_q["issue"]) <= set(FIX_GENERIC) | {"Giá trị thiếu"}, f"mọi vấn đề phát hiện đều có phương án đề xuất xử lý ({_q[['issue', 'fix']].values.tolist()})")
check("fix" not in quality({"f.csv": pd.DataFrame({"a": [1, 1]})}).columns, "mặc định bảng vấn đề giữ 4 cột cũ (đưa vào prompt không phình)")
from app.agents.profiler import clean_findings, clean_tag  # noqa: E402
check(clean_tag("Chất lượng|Cấu trúc|Phù hợp|Ghép tệp|Mô tả|Lưu ý", "Chất lượng dữ liệu: 70/100") == "Chất lượng" and clean_tag("Phù hợp", "x") == "Phù hợp" and clean_tag("a|b", "Dữ liệu ổn") == "Lưu ý", "nhãn nhận định chép nguyên khuôn «a|b|c» được làm sạch")
check(len(clean_findings([{"tag": "x|y", "text": "Cấu trúc tệp rõ"}, {"tag": "Lưu ý", "text": ""}])) == 1, "nhận định rỗng bị bỏ")
_css = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static/css/app.css"), encoding="utf-8").read()
check(".memo.draft{" in _css and ".memo.dr{" not in _css and ".st.mp .n{" in _css and ".dmr{" in _css, "khung bản tổng hợp không còn dùng chung tên lớp .dr / .memo với thành phần khác")
_js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static/js/app.js"), encoding="utf-8").read()
check(_js.index("h += VIEW[i]()") < _js.index("h += memoBox(i)") < _js.index("h += actions(i, s)"), "bản tổng hợp nằm SAU nội dung bước (cuối bước), trước nút thao tác")

# ------------------------------------------------------------------ 1b. tín hiệu phạm vi & chất lượng (generic) --
from app.data.scope import scope_hints  # noqa: E402
_r = np.random.default_rng(2)
_n = 200
_df = pd.DataFrame({"NgayDat": pd.date_range("2026-01-01", "2026-09-24", periods=_n), "TrangThaiDon": _r.choice(["Hoàn thành", "Hoàn trả", "Đã hủy"], _n, p=[.82, .07, .11]),
                    "SoTien": np.where(_r.random(_n) < .07, -1, 1) * _r.integers(100000, 900000, _n), "ThuongHieu": _r.choice(list("ABCD"), _n), "ChiTiet": [None] * 160 + ["x"] * 40})
_h = scope_hints({"don_hang": _df})
check("«TrangThaiDon»" in _h and "QUYẾT ĐỊNH" in _h, "phát hiện cột phân loại bản ghi cần quyết định phạm vi")
check("«SoTien»" in _h and "âm" in _h, "phát hiện cột số vừa âm vừa dương")
check("24/30" in _h and "tạm tính" in _h, "phát hiện kỳ cuối chưa đủ ngày")
check("«ChiTiet» thiếu 80%" in _h, "phát hiện cột thiếu nhiều không dùng để chia cơ cấu")
check("«ThuongHieu»" not in _h, "cột phân loại thường (thương hiệu) không bị coi là loại bản ghi")

# ------------------------------------------------------------------ 2. nhãn và đơn vị cột --
for raw, want in [("DanhMuc", "Danh mục"), ("ThuongHieu", "Thương hiệu"), ("TrongLuongKg", "Trọng lượng"), ("GiaNiemYet", "Giá niêm yết"),
                  ("GiaVon", "Giá vốn"), ("order_id", "Mã đơn hàng"), ("Doanh thu (đ)", "Doanh thu (đ)"), ("PhuongThucThanhToan", "Phương thức thanh toán"), ("Customer_Name", "Tên khách hàng"),
                  ("du_lieu_thuong_mai_dien_tu", "Dữ liệu thương mại điện tử")]:
    check(labels.label(raw) == want, f"nhãn: {raw} -> {labels.label(raw)}")
check(labels.unit("TrongLuongKg") == "kg" and labels.unit("ThuongHieu") == "" and labels.unit("SoLuong") == "" and labels.unit("GiaNiemYet") == "đ"
      and labels.unit("DoanhThu") == "đ" and labels.unit("TyLeHoanTra") == "%", "đơn vị suy theo TỪ: kg không phải tiền, thương hiệu không phải thưởng")
check(labels.is_rate("GiaNiemYet") and labels.is_rate("TrongLuongKg") and not labels.is_rate("SoLuong") and labels.is_id("MaSanPham") and not labels.is_id("DanhMuc"), "nhận diện đơn giá/tỷ lệ (dùng trung bình) và cột mã")

# ------------------------------------------------------------------ 3. tiêu đề biểu đồ khớp dữ liệu --
rows = [("2026-01-01", 1.2e9), ("2026-02-01", 1.0e9), ("2026-09-01", 2.2e9)]
check(not numfmt.consistent("Doanh thu giảm 15,7% từ tháng 1 đến 3", rows, True), "tiêu đề 'giảm' trên biểu đồ tăng bị phát hiện")
check(numfmt.consistent("Doanh thu tăng 83,3% từ đầu kỳ", rows, True), "tiêu đề đúng hướng, đúng % được giữ")
check(numfmt.headline(rows, "line", "Doanh thu (đ)", True) == "Doanh thu tăng 83,33% từ T1/2026 đến T9/2026", f"câu tính từ dữ liệu: {numfmt.headline(rows, 'line', 'Doanh thu (đ)', True)}")

# ------------------------------------------------------------------ 4. toàn bộ báo cáo: dashboard, HTML, MD, PPTX --
app = create_app()
u = db.create_user("An", "an@gmail.com", "matkhau-123", status="approved")
rng = np.random.default_rng(7)
n = 69
prod = pd.DataFrame({"MaSanPham": [f"SP{i:03d}" for i in range(n)], "DanhMuc": rng.choice(["Điện thoại & Phụ kiện", "Thời trang", "Gia dụng"], n),
                     "ThuongHieu": rng.choice(["Alpha", "Beta", "Gamma", "Delta"], n), "TrongLuongKg": rng.uniform(.5, 5, n).round(1),
                     "GiaNiemYet": rng.choice([1_200_000, 2_500_000, 3_900_000], n), "GiaVon": rng.choice([700_000, 1_500_000, 2_800_000], n)})
days = pd.date_range("2026-01-01", "2026-09-24", freq="D")
sales = pd.DataFrame({"NgayDat": days, "DoanhThu": (rng.uniform(3e7, 9e7, len(days)) * np.linspace(1, 2.2, len(days))).round(0)})
month = pd.DataFrame({"Tháng": [f"2026-{m:02d}-01" for m in range(1, 10)], "Doanh thu": [1.2e9, 1.0e9, 1.1e9, 1.05e9, 1.15e9, 1.25e9, 1.5e9, 1.9357604e9, 2.2408135e9]})
region = pd.DataFrame({"Vùng": ["Miền Nam", "Miền Bắc", "Miền Trung"], "Doanh thu": [5759948862.0, 4689363481.25, 2211528975.0]})


def tab(title, df):
    return {"title": title, "cols": list(df.columns), "rows": df.values.tolist(), "err": None}


with app.test_request_context():
    state.bind(u["id"])
    A = state.A
    A["question"], A["ctx"], A["started"] = "Cho tôi tình hình kinh doanh, sản phẩm bán chạy", "Thương mại điện tử", state.now_iso()
    A["files"] = [{"name": "du_lieu_thuong_mai_dien_tu.xlsx::SanPham", "rows": n}, {"name": "du_lieu_thuong_mai_dien_tu.xlsx::DoanhThu", "rows": len(days)}]
    A["clean"] = {"du_lieu_thuong_mai_dien_tu.xlsx::SanPham": prod, "du_lieu_thuong_mai_dien_tu.xlsx::DoanhThu": sales}
    A["x"] = {3: {0: month, 1: region}}
    A["d"] = {1: {"kpis": []}, 2: {"pv": None},
              3: {"phase": "result", "tasks": [{"title": "Doanh thu hàng tháng", "goal": "xu hướng"}, {"title": "Doanh thu theo vùng", "goal": "so sánh"}],
                  "result": {"kpis": [{"label": "Doanh thu tổng năm 2026", "value": "11773398767.5"}, {"label": "Doanh thu bán chạy nhất", "value": "2258413537.5"},
                                      {"label": "Tỷ trọng bán hàng theo vùng", "value": ""}],
                             "tables": [tab("Doanh thu hàng tháng", month), tab("Doanh thu theo vùng", region)], "findings": []}},
              4: {"summary": "Doanh thu tháng 9 đạt 2.24 trillion VNĐ, cao nhất trong năm, với điện thoại & phụ kiện chiếm 57% tổng doanh thu.",
                  "insights": [{"title": "Doanh thu tháng 9 lên tới 2 241 813 537 điểm, vượt 12 % so với tháng 8", "confidence": "Cao", "source": "Doanh thu hàng tháng",
                                "evidence": "Tháng 9 = 2240813537.5, Tháng 8 = 1935760431.25, tỷ lệ tăng 2240813537.5/1935760431.25-1≈0.157"},
                               {"title": "Điện thoại & phụ kiện chiếm 1 557 676 062 điểm, tương đương 57% doanh thu", "confidence": "Cao", "source": "Doanh thu theo vùng",
                                "evidence": "Điện thoại & phụ kiện = 2557676062.5"}],
                  "actions": [{"text": "Tối ưu khuyến mãi", "priority": "Cao", "impact": "Tăng 1.5 triệu VND"}], "risks": ["Tháng 9 mới có 24 ngày"]},
              5: {"title": "Tình hình doanh thu 2026", "narrative": "Doanh thu tháng 9 đạt 2.24 trillion VNĐ.",
                  "final": {"title": "Tình hình doanh thu 2026", "kpis": [0, 1, 2],
                            "charts": [{"task": 0, "x": "Tháng", "y": "Doanh thu", "kind": "line", "title": "Doanh thu tháng 2026", "unit": "đ",
                                        "insight": "Doanh thu giảm 15,7% từ tháng 1 đến 3", "recommended": True},
                                       {"task": 1, "x": "Vùng", "y": "Doanh thu", "kind": "bars", "title": "Doanh thu theo vùng", "unit": "đ", "insight": "", "recommended": True}]}}}
    publish()
    aid = A["id"]
    state.unbind()

get = lambda name: db.get_file(u["id"], aid, name)[0]       # noqa: E731
html, md, dash = get("bao_cao.html").decode("utf8"), get("bao_cao.md").decode("utf8"), get("dashboard.html").decode("utf8")
from pptx import Presentation  # noqa: E402
prs = Presentation(io.BytesIO(get("bao_cao.pptx")))
ppt = "\n".join(sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame)
for name, body in [("báo cáo HTML", html), ("Markdown", md), ("PPTX", ppt), ("dashboard", dash)]:
    check(not re.search(r"trillion|billion|million|VNĐ|VND", body.replace("VND_", "")) , f"{name}: không còn trillion/VND tiếng Anh")
    check("11773398767.5" not in body and "2240813537.5" not in body and "1935760431.25" not in body, f"{name}: không còn số thô thiếu dấu ngăn nghìn")
check("11.773.398.768 đ" in html and "11.773.398.768 đ" in md and "11.773.398.767,50" not in html, "KPI hiện đủ số, nguyên đồng '11.773.398.768 đ' ở HTML và Markdown")
for name, body in [("báo cáo HTML", html), ("Markdown", md), ("PPTX", ppt), ("dashboard", dash)]:
    check(not re.search(r"\d\s*(?:nghìn tỷ|tỷ|triệu)\b(?!\s*lệ|\s*trọng)", re.sub(r"<[^>]+>", " ", body)) or name == "dashboard", f"{name}: không còn số tiền viết tắt tỷ/triệu")
check("Tỷ trọng bán hàng theo vùng" not in html and "Tỷ trọng bán hàng theo vùng" not in ppt, "KPI rỗng không lên báo cáo và PPTX")
check("giảm 15,7" not in html and "giảm 15,7" not in ppt and "tăng" in html and "T1/2026" in html, "tiêu đề biểu đồ sai hướng được thay bằng câu tính từ dữ liệu")
check("điểm" not in html.replace("Điểm", "") .replace("điểm bất", ""), "đơn vị tiền không còn là 'điểm'")
check("Cần kiểm tra số liệu" in html, "phát hiện có số lớn không khớp bảng được gắn cờ 'Cần kiểm tra số liệu'")
check("Danh mục" in dash and "Thương hiệu" in dash and "Trọng lượng" in dash and '"DanhMuc"' not in dash and "trongLuongKg" not in dash, "dashboard dùng nhãn tiếng Việt thay tên biến")
check("class=\"dtabs\"" in dash and "data-ds=" in dash and 'id="dsw"' not in dash, "dashboard đổi bảng bằng tab, không còn ô chọn")

# ------------------------------------------------------------------ phông chữ của báo cáo và bảng điều khiển --
from app.export import fonts as _fonts  # noqa: E402
check(_fonts.norm("không-có") == "claude" and _fonts.norm("inter") == "inter" and "Source Serif 4" in _fonts.public()["claude"]["head"] and "Inter" in _fonts.public()["claude"]["body"], "bộ phông: mặc định 'Giống Claude' (Source Serif 4 + Inter), khóa lạ -> mặc định")
check(_fonts.url("system") == "" and "fonts.googleapis.com/css2?family=Inter" in _fonts.url("inter"), "phông hệ thống không tải gì; phông web tải từ Google Fonts")
for name, body in [("báo cáo HTML", html), ("dashboard", dash)]:
    check('id="fontvars"' in body and "--fh:" in body and "Source Serif 4" in body and "fonts.googleapis.com" in body and "var(--fh)" in body, f"{name}: có phông Giống Claude, tiêu đề dùng --fh")
from app.export import dash_plan as _dp  # noqa: E402
check(_dp.validate_bp({"font": "serif"}, [])["font"] == "serif" and _dp.validate_bp({"font": "lạ"}, [])["font"] == "claude", "bản thiết kế giữ lựa chọn phông, khóa lạ -> mặc định")

# ------------------------------------------------------------------ 5. nhiều sheet = nhiều tab --
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as w:
    pd.DataFrame({"Thang": ["2026-01", "2026-02", "2026-03"], "DoanhThu": [100, 120, 90]}).to_excel(w, sheet_name="DoanhThu", index=False)
    pd.DataFrame({"DanhMuc": list("ABCD"), "SoLuong": [3, 4, 5, 6]}).to_excel(w, sheet_name="SanPham", index=False)


class F:
    filename = "ban_hang.xlsx"

    def read(self):
        return buf.getvalue()


info = list_sheets([F()])[0]
check(info["sheets"] == ["DoanhThu", "SanPham"] and info["info"]["SanPham"]["rows"] == 5, "liệt kê sheet kèm số dòng x cột")
d, *_ = load_files([F()], {"ban_hang.xlsx": ["DoanhThu", "SanPham"]})
check(list(d) == ["ban_hang.xlsx::DoanhThu", "ban_hang.xlsx::SanPham"], "chọn nhiều sheet -> mỗi sheet một bảng 'tệp::sheet'")
d, *_ = load_files([F()], {"ban_hang.xlsx": "SanPham"})
check(list(d) == ["ban_hang.xlsx::SanPham"], "vẫn nhận chọn một sheet dạng chuỗi (tương thích cũ)")

# ------------------------------------------------------------------ 6. nhà cung cấp và Base URL --
check(providers.check_pair("https://api.openai.com/v1", "gemini-2.5-flash") and "Google Gemini" in providers.check_pair("https://api.openai.com/v1", "gemini-2.5-flash"),
      "model Gemini + Base URL OpenAI: báo lỗi tiếng Việt kèm cách sửa")
check(providers.check_pair("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.5-flash") is None and providers.check_pair("https://openrouter.ai/api/v1", "gpt-4o") is None
      and providers.check_pair("https://api.noi-bo.vn/v1", "gpt-4o") is None, "khớp hoặc là gateway/địa chỉ riêng thì không chặn")
check(providers.BY_ID["gemini"]["base_url"].startswith("https://generativelanguage.googleapis.com/v1beta/openai") and providers.provider_of_url("https://api.anthropic.com/v1/") == "anthropic",
      "mỗi nhà cung cấp có Base URL mặc định riêng; nhận ra nhà cung cấp từ địa chỉ")

# ------------------------------------------------------------------ 7. KPI '936.000' không được thành '936' --
# Ca thật: AI trả KPI "936.000" (kiểu Việt Nam, 936 nghìn) nhưng hệ thống đọc thành 936,000 nên thẻ KPI hiện "936 đ"; báo cáo cũng sai theo.
kv = lambda label, v, k=None: numfmt.fix_kpi({"label": label, "value": v}, k)["value"]          # noqa: E731
check(kv("Tổng chi tiêu trong 9 ngày", "936.000") == "936.000 đ" and kv("Chi tiêu trung bình mỗi ngày", "104.000") == "104.000 đ",
      "KPI tiền '936.000' / '104.000' hiện đủ 936.000 đ / 104.000 đ (không còn 936 đ / 104 đ)")
check(kv("Tổng chi tiêu", "936.000 đ") == "936.000 đ", "KPI '936.000 đ' (đã có đơn vị) giữ nguyên 936.000 đ")
check(kv("Số giao dịch", "1.250") == "1.250" and kv("Số giao dịch", "1.250.000") == "1.250.000", "KPI số đếm '1.250' là một nghìn hai trăm năm mươi, không phải 1,25")
check(kv("Số tiền", 936000.0) == "936.000 đ" and kv("Điểm trung bình", 936.123) == "936,12" and kv("Điểm trung bình", 4.5) == "4,50",
      "giá trị là SỐ THẬT thì dùng đúng giá trị (936.123 là 936,12, không bị đoán là kiểu Việt Nam)")
check(kv("Tỷ trọng chi tiêu sinh hoạt", "84.51%") == "84,51%" and kv("Tổng chi tiêu", "1,234.56") == "1.235 đ" and kv("Tổng chi tiêu", "936,000") == "936.000 đ",
      "các kiểu viết khác vẫn đúng: 84.51% · 1,234.56 (tiền nên nguyên đồng) · 936,000")
check(kv("Điểm trung bình", "12.500", numfmt.Known([12.5, 3.0, 8.2])) == "12,50" and kv("Doanh thu", "12.500", numfmt.Known([12500, 3.0])) == "12.500 đ",
      "chuỗi mơ hồ '12.500': bảng kết quả chỉ có 12,5 thì là số lẻ; có 12500 thì là mười hai nghìn năm trăm")
a = numfmt.fix_kpi({"label": "Tổng chi tiêu", "value": "936.000"})
check(numfmt.fix_kpi(a)["value"] == a["value"] == "936.000 đ", "định dạng KPI hai lần (khi chạy phân tích rồi khi xuất báo cáo) ra cùng một kết quả")
check([k["value"] for k in numfmt.fix_kpis([{"label": "Tổng chi tiêu", "value": "936.000"}, {"label": "Chi tiêu trung bình mỗi ngày", "value": "104.000"}])] == ["936.000 đ", "104.000 đ"],
      "fix_kpis (đường mà bước Phân tích và bước xuất báo cáo cùng dùng) cho đúng 936.000 đ và 104.000 đ")

print(f"\nTẤT CẢ {n_ok} KIỂM TRA ĐỀU ĐẠT")
