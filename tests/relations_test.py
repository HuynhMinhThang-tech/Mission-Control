# -*- coding: utf-8 -*-
"""Kiểm thử: quan hệ giữa các bảng (sheet) và GHÉP BIẾN TỪ NHIỀU SHEET.
Trước đây bộ ghép biến chỉ làm việc trên MỘT bảng, nên không thể chọn «doanh thu» (bảng chi tiết đơn hàng) chia theo «danh mục» (bảng sản phẩm)
và «thành phố» (bảng khách hàng). Nay hệ thống tự nối bảng theo cột khóa chung, chỉ theo chiều NHIỀU -> MỘT (không nhân dòng), sinh code nối rõ ràng,
và số liệu chạy trong sandbox khớp với pandas tính tay. Chạy: python tests/relations_test.py"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.update(SECRET_KEY="k-test", MASTER_KEY="k-test", DATABASE_URL=f"sqlite:///{tempfile.mkdtemp()}/x.db")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.data import analysis_spec as S  # noqa: E402
from app.data import relations as R  # noqa: E402
from app.data import sandbox  # noqa: E402

n_ok = 0


def check(cond, label):
    global n_ok
    if not cond:
        print("FAIL:", label)
        sys.exit(1)
    n_ok += 1
    print("ok  ", label)


rng = np.random.default_rng(11)
sp = pd.DataFrame({"MaSP": [f"SP{i:03d}" for i in range(30)], "DanhMuc": rng.choice(["Điện thoại", "Laptop", "Phụ kiện"], 30), "GiaVon": rng.integers(10, 99, 30) * 1000.0,
                   "ConBan": rng.choice(["Có", "Không"], 30)})
kh = pd.DataFrame({"MaKH": [f"KH{i:04d}" for i in range(80)], "ThanhPho": rng.choice(["HN", "HCM", "ĐN"], 80), "GhiChu": rng.choice(["a", "b"], 80)})
dh = pd.DataFrame({"MaDH": [f"DH{i:05d}" for i in range(400)], "MaKH": rng.choice(kh.MaKH, 400), "PhuongThuc": rng.choice(["COD", "Thẻ"], 400), "GhiChu": rng.choice(["x", "y", "z"], 400),
                   "NgayDat": pd.Timestamp("2024-01-01") + pd.to_timedelta(rng.integers(0, 300, 400), unit="D")})
ct = pd.DataFrame({"STT": range(1200), "MaDH": rng.choice(dh.MaDH, 1200), "MaSP": rng.choice(sp.MaSP, 1200), "SoLuong": rng.integers(1, 6, 1200)})
ct["ThanhTien"] = ct.SoLuong * rng.integers(100, 900, 1200) * 1000.0
CT, DH, KH, SP = "t.xlsx::ChiTietDonHang", "t.xlsx::DonHang", "t.xlsx::KhachHang", "t.xlsx::SanPham"
F = {CT: ct, DH: dh, KH: kh, SP: sp}

# ---- quan hệ
rel = R.relations(F)
check(sorted((r["many"].split("::")[1], r["one"].split("::")[1], r["key"]) for r in rel) == [("ChiTietDonHang", "DonHang", "MaDH"), ("ChiTietDonHang", "SanPham", "MaSP"), ("DonHang", "KhachHang", "MaKH")],
      "phát hiện đúng 3 quan hệ nhiều -> một (MaDH, MaSP, MaKH), đúng chiều")
check(all(r["match"] == 100 for r in rel) and not any(r["key"] in ("STT", "GhiChu") for r in rel), "không nhầm số thứ tự (STT) hay cột trùng tên không phải khóa (GhiChu) là khóa")
check(R.dim_tables(rel) == {DH, KH, SP}, "bảng danh mục (được tham chiếu) = DonHang, KhachHang, SanPham")
check(R.relations({"a": pd.DataFrame({"MaX": ["1", "2"], "v": [1, 2]}), "b": pd.DataFrame({"MaX": ["9", "8"], "w": [1, 2]})}) == [], "hai bảng cùng tên cột nhưng giá trị không khớp: không coi là liên kết")

# ---- lập kế hoạch nối
joins, names = R.plan(F, CT, [(CT, "ThanhTien"), (SP, "DanhMuc"), (KH, "ThanhPho"), (DH, "PhuongThuc")])
check([j["file"].split("::")[1] for j in joins] == ["DonHang", "SanPham", "KhachHang"] or [j["file"].split("::")[1] for j in joins] == ["SanPham", "DonHang", "KhachHang"], "nối nhiều bước: chi tiết -> đơn hàng -> khách hàng, và chi tiết -> sản phẩm")
fr = R.frame(F, CT, joins)
check(len(fr) == len(ct) and fr["ThanhTien"].sum() == ct["ThanhTien"].sum(), "nối KHÔNG làm đổi số dòng, tổng tiền giữ nguyên (không bị nhân đôi)")
check(names[(SP, "DanhMuc")] == "DanhMuc" and names[(KH, "ThanhPho")] == "ThanhPho", "tên cột giữ nguyên khi không trùng")
j2, n2 = R.plan(F, CT, [(DH, "GhiChu"), (KH, "GhiChu")])
check(len({n2[(DH, "GhiChu")], n2[(KH, "GhiChu")]}) == 2 and "GhiChu (KhachHang)" in n2.values(), "hai cột cùng tên ở hai bảng: cột thứ hai tự đổi tên có ghi nguồn, không đè lên nhau")
try:
    R.plan(F, SP, [(SP, "DanhMuc"), (CT, "SoLuong")])
    check(False, "nối ngược chiều phải bị từ chối")
except ValueError as e:
    check("tính lặp" in str(e) and "SanPham" in str(e) and "ChiTietDonHang" in str(e), "nối ngược chiều (một -> nhiều) bị TỪ CHỐI kèm lý do và cách sửa, không lặng lẽ tính sai")
try:
    R.plan({CT: ct, "t.xlsx::Rieng": pd.DataFrame({"X": [1, 2]})}, CT, [("t.xlsx::Rieng", "X")])
    check(False, "bảng không liên quan phải bị từ chối")
except ValueError as e:
    check("chưa có cột khóa chung" in str(e), "hai bảng không có khóa chung: nói rõ không nối được")

# ---- spec ghép biến nhiều bảng: chuẩn hóa -> code -> chạy sandbox -> so với pandas
ref = lambda f, c: {"file": f, "col": c}  # noqa: E731
spec = {"type": "compare", "measures": [{"col": ref(CT, "ThanhTien"), "agg": "sum"}], "by": [ref(SP, "DanhMuc"), ref(KH, "ThanhPho")]}
n, err = S.normalize(spec, F)
check(err is None and n["file"] == CT and len(n["joins"]) == 3, f"chuẩn hóa spec lấy biến từ 3 sheet; bảng chính là bảng chứa chỉ số ({err})")
check("Hệ thống tự nối bảng «ChiTietDonHang» với" in n["goal"] and "(theo MaSP)" in n["goal"] and "(theo MaKH)" in n["goal"], "mô tả nói rõ bảng nào nối với bảng nào theo khóa nào")
check(set(n["src"].values()) == {CT, SP, KH}, "mỗi biến ghi rõ đến từ sheet nào")
code = S.build_code(n, F)
check(code.count(".merge(") == 3 and "drop_duplicates" in code and "how='left'" in code, "code có 3 phép nối (merge), mỗi bảng phụ khử trùng khóa, nối trái")
got = sandbox.run_code(code, F)                         # DataFrame với cột đã đặt tên tiếng Việt
m = ct.merge(sp[["MaSP", "DanhMuc"]], on="MaSP").merge(dh[["MaDH", "MaKH"]], on="MaDH").merge(kh[["MaKH", "ThanhPho"]], on="MaKH")
exp = m.groupby(["DanhMuc", "ThanhPho"])["ThanhTien"].sum()
gd = got.set_index(["Danh mục", "Thành phố"])["Tổng thành tiền"]
check(len(gd) == len(exp) == 9 and np.allclose(gd.sort_index().to_numpy(), exp.sort_index().to_numpy()) and abs(gd.sum() - ct["ThanhTien"].sum()) < 1,
      "SỐ LIỆU chạy trong sandbox khớp pandas tính tay (9 nhóm danh mục × thành phố), tổng bảo toàn")
check(int(got["Số bản ghi"].sum()) == len(ct), "số bản ghi cộng lại = số dòng của bảng chi tiết (không nhân đôi, không mất dòng)")
n2_, e2 = S.normalize(n, F)
check(e2 is None and n2_["joins"] == n["joins"] and n2_["vars"] == n["vars"], "chuẩn hóa lại spec đã chuẩn hóa cho đúng kết quả cũ (lưu rồi nạp lại vẫn đúng)")

# ---- các kiểu ghép khác với biến ở nhiều sheet
tr, e = S.normalize({"type": "trend", "measures": [{"col": ref(CT, "ThanhTien"), "agg": "sum"}], "time": {"col": ref(DH, "NgayDat"), "grain": "month"}, "by": [ref(SP, "DanhMuc")]}, F)
check(e is None and tr["time"]["col"] == "NgayDat", f"xu hướng theo NGÀY ĐẶT (bảng DonHang) của doanh thu (bảng ChiTiet) chia theo danh mục ({e})")
rg = sandbox.run_code(S.build_code(tr, F), F)
check(abs(float(rg["Tổng"].sum()) - ct["ThanhTien"].sum()) < 5 and set(rg.columns) >= {"Kỳ (tháng)", "Laptop", "Phụ kiện", "Điện thoại"},
      "xu hướng theo tháng (NgayDat ở bảng DonHang) × danh mục (bảng SanPham): tổng các tháng = tổng doanh thu, đủ 3 danh mục")
co, e = S.normalize({"type": "correlate", "x": ref(CT, "SoLuong"), "y": ref(SP, "GiaVon")}, F)
check(e is None and co["file"] == CT, f"tương quan giữa biến của hai sheet ({e})")
pa, e = S.normalize({"type": "pareto", "measures": [{"col": ref(CT, "ThanhTien"), "agg": "sum"}], "by": [ref(KH, "ThanhPho")]}, F)
check(e is None and pa["by"] == ["ThanhPho"], f"80/20: doanh thu theo thành phố khách hàng ({e})")
ra, e = S.normalize({"type": "rate", "cols": [ref(SP, "ConBan")], "by": [ref(DH, "PhuongThuc")]}, F)
check(e is None or "Đạt" in str(e) or "hai giá trị" in str(e) or e is None, f"tỷ lệ đạt với cột ở sheet khác không gây lỗi nối ({e})")
di, e = S.normalize({"type": "distribution", "col": ref(SP, "GiaVon")}, F)
check(e is None and "joins" not in di and di["file"] == SP, f"phân bố một biến ở một sheet: không cần nối ({e})")

# ---- chọn bảng chính khi chỉ đếm / chia nhóm
c1, e = S.normalize({"type": "compare", "measures": [], "by": [ref(KH, "ThanhPho")]}, F)
check(e is None and c1["file"] == KH and "joins" not in c1, "đếm theo thành phố, chỉ có bảng KhachHang: đếm KHÁCH HÀNG (không nối sang bảng khác)")
c2, e = S.normalize({"type": "compare", "measures": [], "by": [ref(KH, "ThanhPho"), ref(DH, "PhuongThuc")]}, F)
check(e is None and c2["file"] == DH, f"đếm theo thành phố × phương thức thanh toán: bảng chính là DonHang (đếm ĐƠN HÀNG) ({e})")
c3, e = S.normalize({"type": "compare", "measures": [], "by": [ref(SP, "DanhMuc"), ref(DH, "PhuongThuc")]}, F)
check(e is None and c3["file"] == CT, f"đếm theo danh mục × phương thức: không bảng nào trong hai bảng nối được nên dùng bảng chi tiết làm cầu nối ({e})")
bad, e = S.normalize({"type": "compare", "measures": [{"col": ref(SP, "GiaVon"), "agg": "sum"}], "by": [ref(DH, "PhuongThuc")]}, F)
check(bad is None and "tính lặp" in e, "chỉ số ở bảng danh mục chia theo cột bảng chi tiết: từ chối, nói rõ vì sao")
nf, e = S.normalize({"type": "compare", "measures": [{"col": ref(CT, "KhongCo"), "agg": "sum"}], "by": [ref(SP, "DanhMuc")]}, F)
check(nf is None and "Không thấy cột" in e, "cột không tồn tại: báo lỗi tiếng Việt")

# ---- tương thích ngược: spec một bảng viết kiểu cũ (tên cột trần) vẫn chạy y như trước
old, e = S.normalize({"type": "compare", "file": SP, "measures": [{"col": "GiaVon", "agg": "mean"}], "by": ["DanhMuc"]}, F)
check(e is None and old["file"] == SP and "joins" not in old and old["by"] == ["DanhMuc"], "spec một bảng kiểu cũ (tên cột trần) vẫn chạy như trước")
print(f"\nTẤT CẢ {n_ok} KIỂM TRA ĐỀU ĐẠT")
