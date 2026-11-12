# -*- coding: utf-8 -*-
"""Kiểm thử TRỌN LUỒNG với LLM giả: tệp Excel NHIỀU SHEET (ChiTietDonHang, DonHang, KhachHang, SanPham).
Trước đây bước Kiểm tra và mô tả chỉ tính KPI trên bảng lớn nhất, lấy cột ngày ĐẦU TIÊN (ngày sinh khách hàng) làm «Khoảng ngày» của cả bộ dữ liệu
(rồi đi tiếp vào bản tổng hợp, báo cáo, PowerPoint), và tab «phân bố từng biến» hiện tên tệp thay vì tên sheet.
Chạy: python tests/multisheet_test.py"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _flow as F  # noqa: E402
import pandas as pd  # noqa: E402

fails = 0


def check(name, cond, extra=""):
    global fails
    print(("OK   " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    fails += 0 if cond else 1


from _sheets import NAME, SHEETS, make_xlsx  # noqa: E402


F.AUTO["memo"] = False
app, c = F.setup()
blob, T = make_xlsx()
r = c.post("/api/upload", data={"files": (io.BytesIO(blob), NAME), "sheets": json.dumps({NAME: SHEETS})}, content_type="multipart/form-data")
check("tải lên tệp 4 sheet", r.status_code == 200 and r.get_json().get("ok"), r.get_data(as_text=True)[:200])
F.post(c, "/api/start", {"question": "Doanh thu theo nhóm khách hàng và sản phẩm?"}); s = F.wait(c)
d = s["d"]["1"]

# ---- việc 1: quy mô theo TẤT CẢ các bảng
K = {k["label"]: k for k in d["kpis"]}
check("KPI nói đúng 4 bảng (không chỉ bảng lớn nhất)", K["Số bảng"]["value"] == "4" and K["Số bảng"]["delta"] == "1 tệp", str(d["kpis"]))
tot = len(T["ct"]) + len(T["dh"]) + len(T["kh"]) + len(T["sp"])
check("tổng số dòng = cộng cả 4 bảng (5.320 + 3.000 + 499 + 69 = 8.888)", K["Tổng số dòng"]["value"] == "8.888" and "5.320" in K["Tổng số dòng"]["delta"] and tot == 8888, str(K["Tổng số dòng"]))
check("tổng số cột = cộng cả 4 bảng", K["Tổng số cột"]["value"] == str(5 + 4 + 5 + 5), str(K["Tổng số cột"]))
check("có đủ 4 bảng, mỗi bảng đúng số dòng và số cột", {t["table"]: (t["rows"], t["cols"]) for t in d["tables"]} == {"ChiTietDonHang": (5320, 5), "DonHang": (3000, 4), "KhachHang": (499, 5), "SanPham": (69, 5)}, str(d["tables"]))
check("xem nhanh có mẫu của CẢ 4 bảng", [x["file"].split("::")[1] for x in d["samples"]] == ["ChiTietDonHang", "DonHang", "KhachHang", "SanPham"] and all(len(x["rows"]) == 5 for x in d["samples"]))
check("phát hiện đủ 3 quan hệ giữa các bảng (MaDH, MaKH, MaSP)", sorted(r["key"] for r in d["relations"]) == ["MaDH", "MaKH", "MaSP"] and all(r["match"] == 100 for r in d["relations"]), str(d["relations"]))

# ---- việc 2: kỳ dữ liệu là NGÀY ĐẶT, không phải ngày sinh / đăng ký
role = {(x["table"], x["col"]): x["role"] for x in d["dates"]}
check("ngày sinh = 'birth', ngày đăng ký = 'signup', ngày đặt = 'event'", role == {("KhachHang", "NgaySinh"): "birth", ("KhachHang", "NgayDangKy"): "signup", ("DonHang", "NgayDat"): "event"}, str(role))
p = d["period"]
dat = T["dh"]["NgayDat"]
check("kỳ dữ liệu = khoảng NGÀY ĐẶT của bảng DonHang", p["table"] == "DonHang" and p["col"] == "NgayDat" and p["min"] == f"{dat.min():%d/%m/%Y}" and p["max"] == f"{dat.max():%d/%m/%Y}", str(p))
check("KPI 'Kỳ dữ liệu' ghi rõ cột nguồn và KHÔNG phải khoảng ngày sinh (1955 → 2004)", K["Kỳ dữ liệu"]["value"] == f"{p['min']} → {p['max']}" and "Ngày đặt" in K["Kỳ dữ liệu"]["delta"] and "1956" not in K["Kỳ dữ liệu"]["value"] and "Khoảng ngày" not in K, str(K.get("Kỳ dữ liệu")))
check("KPI 'Khóa ghép' nói rõ 3 liên kết", K["Khóa ghép"]["delta"].startswith("3 liên kết"), str(K["Khóa ghép"]))

# ---- bản tổng hợp (memo) và tệp xuất
F.post(c, "/api/accept/1"); s = F.wait(c)
md = s["memo"]["1"]["md"]
check("bản tổng hợp liệt kê từng bảng, liên kết và cột ngày (có vai trò)", all(x in md for x in ("## Các bảng dữ liệu (4)", "ChiTietDonHang", "## Liên kết giữa các bảng", "→ DonHang theo cột MaDH", "## Các cột ngày", "thuộc tính, không phải kỳ của dữ liệu", "dùng làm kỳ của dữ liệu")), md[:900])
check("bản tổng hợp KHÔNG coi ngày sinh là kỳ dữ liệu", "Ngày sinh (KhachHang)" in md and not any("ngày sinh" in ln.lower() and "dùng làm kỳ của dữ liệu" in ln for ln in md.split("\n")))
F.post(c, "/api/memo/1/approve"); F.wait(c)
from app.export import period_of  # noqa: E402
check("tệp xuất: kỳ dữ liệu = khoảng NGÀY ĐẶT (cover, dashboard, báo cáo, PowerPoint đều lấy từ đây)", period_of(d) == f"{p['min']} → {p['max']}" and "1956" not in period_of(d), period_of(d))
check("chỉ có ngày sinh / đăng ký: KHÔNG in kỳ dữ liệu sai", period_of({"period": None, "kpis": [{"label": "Kỳ dữ liệu", "value": "Chưa xác định"}]}) is None)
check("bản lưu cũ (chưa có 'period') vẫn xem lại được bằng KPI cũ", period_of({"kpis": [{"label": "Khoảng ngày", "value": "01/01/2024 → 31/01/2024"}]}) == "01/01/2024 → 31/01/2024")
from app.agents.profiler import overview  # noqa: E402
from app.data.datecols import date_cols  # noqa: E402
only = {"x.xlsx::KhachHang": T["kh"]}
kp, per = overview(only, [], date_cols(only))
kk = {k["label"]: k for k in kp}
check("chỉ có bảng khách hàng (ngày sinh + đăng ký): KPI nói 'Chưa xác định', nêu lý do", per is None and kk["Kỳ dữ liệu"]["value"] == "Chưa xác định" and "thuộc tính" in kk["Kỳ dữ liệu"]["delta"], str(kk.get("Kỳ dữ liệu")))
one = {"x.csv": T["dh"]}
kp1, per1 = overview(one, [], date_cols(one))
k1 = {k["label"]: k for k in kp1}
check("một bảng duy nhất: vẫn hiện 'Số dòng' / 'Số cột' như cũ", k1["Số dòng"]["value"] == "3.000" and k1["Số cột"]["value"] == "4" and per1["col"] == "NgayDat" and "Số bảng" not in k1)
# ---- kết quả không phụ thuộc THỨ TỰ sheet (lỗi cũ: lấy cột ngày đầu tiên của sheet đầu tiên có cột ngày)
from app.data.quality import date_range  # noqa: E402
from app.data.relations import relations as _rels, dim_tables as _dim  # noqa: E402
raw = {f"{NAME}::{n}": pd.read_excel(io.BytesIO(blob), sheet_name=n) for n in ("KhachHang", "DonHang", "ChiTietDonHang", "SanPham")}    # khách hàng đứng ĐẦU
check("(ghi lại lỗi cũ) hàm cũ date_range lấy khoảng NGÀY SINH khi sheet khách hàng đứng trước", date_range(raw).split(" → ")[0].endswith(("1955", "1956", "1957")), date_range(raw))
from app.data.datecols import pick_period  # noqa: E402
pp = pick_period(date_cols(raw, _dim(_rels(raw))))
check("hàm mới: dù sheet khách hàng đứng trước, kỳ dữ liệu vẫn là NGÀY ĐẶT", pp["col"] == "NgayDat" and pp["min"] == f"{dat.min():%d/%m/%Y}", str(pp))
print(f"\n{'TẤT CẢ ĐẠT' if not fails else str(fails) + ' KIỂM TRA THẤT BẠI'}")
sys.exit(1 if fails else 0)
