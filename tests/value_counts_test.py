# -*- coding: utf-8 -*-
"""Kiểm thử bước làm sạch: chạy value_counts từng cột, gom giá trị viết khác nhau, AI tổng hợp, áp dụng gộp.
Chạy: python tests/value_counts_test.py"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.update(SECRET_KEY="k-test", MASTER_KEY="k-test", DATABASE_URL=f"sqlite:///{tempfile.mkdtemp()}/x.db")

import pandas as pd  # noqa: E402

from app import state  # noqa: E402
from app.agents import cleaner  # noqa: E402
from app.data import valuecounts as vc  # noqa: E402
from app.data.cleaning import apply_plan  # noqa: E402
from app.data.quality import norm_key, quality  # noqa: E402

n_ok = 0


def check(cond, label):
    global n_ok
    if not cond:
        print("FAIL:", label)
        sys.exit(1)
    n_ok += 1
    print("ok  ", label)


# ---- dữ liệu: cùng một phòng ban viết nhiều kiểu
PB = ["Ban Giám đốc"] * 120 + ["ban giam doc"] * 7 + ["Ban giám đốc "] * 3 + ["BAN GIÁM ĐỐC"] * 2 \
    + ["Phòng Kinh doanh"] * 80 + ["Phong kinh doanh"] * 5 + ["Kế toán"] * 60 + [None] * 4 + ["N/A"] * 3
df = pd.DataFrame({"phong_ban": PB, "ma_nv": [f"NV{i:04d}" for i in range(len(PB))], "luong": range(len(PB))})
df2 = pd.DataFrame({"tinh": ["HCM", "Hà Nội", "ha noi", "HCM"], "so": [1, 2, 3, 4]})
RAW = {"nv.csv": df, "kh.csv": df2}

check(norm_key("Ban Giám đốc") == norm_key("ban giam doc") == norm_key("  BAN GIÁM ĐỐC ") == "ban giam doc", "khóa so sánh: bỏ hoa/thường, dấu, khoảng trắng")
check(norm_key("Phòng KD") != norm_key("Phòng KT"), "khóa so sánh: hai giá trị khác nhau vẫn khác")

rep = vc.report(RAW)
by = {(c["file"], c["col"]): c for c in rep}
check(set(by) == {("nv.csv", "phong_ban"), ("nv.csv", "ma_nv"), ("kh.csv", "tinh")}, "chỉ đếm cột văn bản (bỏ cột số)")
pb = by[("nv.csv", "phong_ban")]
check(pb["cmd"] == "df['phong_ban'].value_counts(dropna=False)", "ghi lại đúng lệnh đã chạy: " + pb["cmd"])
check(pb["top"][0] == ["Ban Giám đốc", 120], "đếm đúng giá trị phổ biến nhất")
check(["(thiếu)", 4] in pb["top"], "đếm cả giá trị thiếu (dropna=False)")
g = {x["canon"]: dict((k, n) for k, n in x["items"]) for x in pb["variants"]}
check(g.get("Ban Giám đốc") == {"Ban Giám đốc": 120, "ban giam doc": 7, "Ban giám đốc ": 3, "BAN GIÁM ĐỐC": 2}, "gom đúng 4 cách viết của 'Ban Giám đốc'")
check("Phòng Kinh doanh" in g and "Kế toán" not in g, "gom 'Phong kinh doanh'; giá trị duy nhất không bị gom")
check(by[("kh.csv", "tinh")]["variants"][0]["canon"] == "Hà Nội", "ưu tiên cách viết có dấu khi số lượng ngang nhau")
check(by[("nv.csv", "ma_nv")]["variants"] == [], "cột mã: mọi giá trị khác nhau nên không có nhóm trùng nghĩa")
big = vc.report({"b": pd.DataFrame({"ma": [f"M{i}" for i in range(400)]})})[0]
check(big["distinct"] == 400 and big["skipped"] and big["variants"] == [] and len(big["top"]) == vc.TOP, "cột có quá nhiều giá trị: vẫn đếm nhưng không gom nhóm, chỉ giữ top")
txt = vc.for_llm(rep)
check("Ban Giám đốc (120)" in txt and "«ban giam doc» ×7" in txt, "văn bản đưa AI chứa cả bảng đếm lẫn nhóm nghi trùng")

# ---- chất lượng: vấn đề mới được phát hiện
iss = quality(RAW)
row = iss[(iss.file == "nv.csv") & (iss.col == "phong_ban") & (iss.issue == "Giá trị viết khác nhau")]
check(len(row) == 1 and int(row.n.iloc[0]) >= 1, "quality() phát hiện 'Giá trị viết khác nhau'")

# ---- chặn AI bịa + bổ sung phần AI bỏ sót
state.bind(1)
state.A["raw"] = RAW
ai_ops = [{"file": "nv.csv", "op": "standardize_text", "column": "phong_ban",
           "mapping": {"ban giam doc": "Ban Giám đốc", "BGĐ": "Ban Giám đốc", "N/A": "Không rõ", "Kế toán": ""}, "reason": "x", "recommended": True},
          {"file": "nv.csv", "op": "standardize_text", "column": "khong_co", "mapping": {"a": "b"}},
          {"file": "nv.csv", "op": "strip_text", "column": "phong_ban"}]
out = cleaner.fold_standardize(ai_ops, rep)
so = [o for o in out if o["op"] == "standardize_text"]
mp = {o["column"]: o["mapping"] for o in so}
check("BGĐ" not in mp["phong_ban"], "mapping bị loại giá trị AI bịa (không có trong cột)")
check(mp["phong_ban"].get("N/A") == "Không rõ" and "Kế toán" not in mp["phong_ban"], "giữ gộp hợp lệ của AI; bỏ cặp có giá trị chuẩn rỗng")
check(mp["phong_ban"].get("BAN GIÁM ĐỐC") == "Ban Giám đốc" and mp["phong_ban"].get("Phong kinh doanh") == "Phòng Kinh doanh", "tự bổ sung nhóm phép đếm tìm thấy mà AI bỏ sót")
check("tinh" in mp and len(so) == 2 and any(o["op"] == "strip_text" for o in out), "cột khác có biến thể được thêm đề xuất; thao tác khác giữ nguyên; cột không tồn tại bị loại")
check(vc.resolve({"a": "b", "b": "c"}) == {"a": "c", "b": "c"}, "xử lý chuỗi A→B→C về thẳng C")

# ---- áp dụng
clean, log = apply_plan(RAW, [{"file": "nv.csv", "op": "standardize_text", "column": "phong_ban", "mapping": mp["phong_ban"]}])
vcn = clean["nv.csv"]["phong_ban"].value_counts(dropna=False)
check(vcn["Ban Giám đốc"] == 132 and vcn["Phòng Kinh doanh"] == 85 and vcn["Không rõ"] == 3 and vcn[pd.NA] == 4, "sau khi gộp: 132 'Ban Giám đốc', 85 'Phòng Kinh doanh', thiếu giữ nguyên")
check(not (quality(clean).query("issue == 'Giá trị viết khác nhau' and col == 'phong_ban'").shape[0]), "sau khi gộp: không còn bị báo 'Giá trị viết khác nhau'")
check(len(clean["nv.csv"]) == len(df), "gộp giá trị không làm mất dòng")

# ---- tổng hợp hiển thị
v = vc.view(rep, {"overview": "Cột phong_ban có nhiều cách viết.", "columns": [{"file": "nv.csv", "column": "phong_ban", "finding": "Có 'N/A' là giá trị lạ."}, {"file": "x", "column": "y", "finding": "bịa"}]})
f = {(x["file"], x["col"]): x for x in v["findings"]}
check(f[("nv.csv", "phong_ban")]["text"] == "Có 'N/A' là giá trị lạ." and ("kh.csv", "tinh") in f and ("x", "y") not in f, "AI tổng hợp hiển thị; cột AI bỏ sót có câu dự phòng tự sinh; cột bịa bị loại")
check(v["cmd"] == vc.CMD and v["ncols"] == 3, "giao diện nhận lệnh đã chạy và số cột")

# ---- viết tắt / thêm bớt chữ / gõ sai: nhóm NGHI trùng (không tự gộp)
RH = {"cap.csv": pd.DataFrame({"cap_bac": ["Nhân viên"] * 17 + ["NV"] + ["Chuyên viên"] * 14 + ["CV"] + ["Trưởng phòng"] * 8 + ["Phó phòng"] * 6 + ["Thực tập sinh"] * 7}),
      "phong.csv": pd.DataFrame({"phong": ["P. Kinh doanh"] * 8 + ["Kinh doanh"] * 5 + ["Phòng Kinh doanh"] * 2 + ["Kế toán"] * 20 + ["Marketing"] * 20 + ["Marketting"] * 2 + ["Kho vận"] * 5}),
      "cn.csv": pd.DataFrame({"chi_nhanh": ["Chi nhánh 1"] * 5 + ["Chi nhánh 2"] * 5 + ["Chi nhánh 10"] * 4 + ["Hà Nội"] * 33 + ["Hà Nôi"] * 1 + ["TP"] * 10})}
rh = {c["col"]: c for c in vc.report(RH)}
wk = {g["canon"]: g for g in rh["cap_bac"]["weak"]}
check(wk["Nhân viên"]["map"] == {"NV": "Nhân viên"} and wk["Chuyên viên"]["map"] == {"CV": "Chuyên viên"} and wk["Chuyên viên"]["why"] == ["viết tắt"], "nhận ra viết tắt: NV = Nhân viên, CV = Chuyên viên (đích là tên đầy đủ)")
check(rh["cap_bac"]["variants"] == [], "viết tắt không bị coi là 'chắc chắn trùng' (không tự gộp)")
pw = rh["phong"]["weak"]
kd = [g for g in pw if "Kinh doanh" in g["map"] or g["canon"] == "Kinh doanh"]
check(len(kd) == 1 and set(kd[0]["map"]) | {kd[0]["canon"]} == {"P. Kinh doanh", "Kinh doanh", "Phòng Kinh doanh"}, "nhận ra P. Kinh doanh = Phòng Kinh doanh = Kinh doanh (thêm/bớt chữ đầu)")
check(any("Marketting" in g["map"] for g in pw), "nhận ra gõ sai nhẹ: Marketting -> Marketing")
cn = rh["chi_nhanh"]["weak"]
check(not any("Chi nhánh 1" in g["map"] or "Chi nhánh 2" in g["map"] or "Chi nhánh 10" in g["map"] for g in cn), "Chi nhánh 1/2/10 chỉ khác chữ số: KHÔNG gộp nhầm")
check(not any("TP" in g["map"] for g in cn) and any("Hà Nôi" in [k for k, _ in g["items"]] for g in rh["chi_nhanh"]["variants"]), "viết tắt không rõ nghĩa 'TP' không bị gộp; lỗi dấu 'Hà Nôi' được gom về 'Hà Nội' (chắc chắn trùng)")
state.A["raw"] = RH
rep2 = vc.report(RH)
out2 = cleaner.fold_standardize([], rep2)
wops = [o for o in out2 if o.get("weak")]
check(wops and all(o["recommended"] is False and o["op"] == "standardize_text" for o in wops), "nhóm nghi trùng thành đề xuất riêng, mặc định CHƯA chọn")
ai2 = [{"file": "cap.csv", "op": "standardize_text", "column": "cap_bac", "mapping": {"CV": "Chuyên viên", "NV": "Nhân viên"}, "recommended": True, "reason": "viết tắt"}]
out3 = cleaner.fold_standardize(ai2, rep2)
main = [o for o in out3 if o.get("column") == "cap_bac" and o["op"] == "standardize_text"]
check(len(main) == 1 and main[0].get("recommended") and main[0]["mapping"] == {"CV": "Chuyên viên", "NV": "Nhân viên"}, "AI xác nhận viết tắt -> nằm trong đề xuất chính (được chọn sẵn), không lặp ở nhóm nghi trùng")

# ---- người dùng tự gộp trên bảng đếm
state.A["d"] = {2: {"ops": []}}
mo = cleaner.manual_ops({"manual": [{"file": "cap.csv", "column": "cap_bac", "mapping": {"CV": "Chuyên viên", "KHÔNGCÓ": "x", "NV": ""}}, {"file": "cap.csv", "column": "khong_co", "mapping": {"a": "b"}}]})
check(len(mo) == 1 and mo[0][1]["mapping"] == {"CV": "Chuyên viên"}, "gộp thủ công: bỏ giá trị không có thật, đích rỗng, cột không tồn tại")
pv = cleaner.preview({"manual": [{"file": "cap.csv", "column": "cap_bac", "mapping": {"CV": "Chuyên viên", "NV": "Nhân viên"}}]})
check(set(pv) >= {"before", "after", "n", "fx"} and pv["after"] != pv["before"], "xem trước chạy được với phần gộp thủ công và có đếm lại số liệu sau gộp")
cl, _ = cleaner.apply_plan(state.A["raw"], [o2 for _, o2 in cleaner.pick_ops({"manual": [{"file": "cap.csv", "column": "cap_bac", "mapping": {"CV": "Chuyên viên", "NV": "Nhân viên"}}]})])
check(sorted(cl["cap.csv"]["cap_bac"].unique()) == ["Chuyên viên", "Nhân viên", "Phó phòng", "Thực tập sinh", "Trưởng phòng"] and cl["cap.csv"]["cap_bac"].value_counts()["Chuyên viên"] == 15, "áp dụng gộp thủ công: CV vào Chuyên viên (15), NV vào Nhân viên (18)")

state.A["raw"] = RAW
# ---- chạy cả Agent với AI giả
state.A["question"], state.A["ctx"], state.A["d"] = "q", "", {}
seen = {}
cleaner.llm_json = lambda system, user, *a, **k: (seen.update(u=user), {"operations": [], "value_counts": {"overview": "Tóm tắt AI", "columns": []}})[1]
state.A["job"] = {"running": True, "step": 2, "k": 0}
ticks = []
orig = cleaner.tick
cleaner.tick = lambda k: (ticks.append(k), orig(k))[1]
cleaner.run()
d = state.A["d"][2]
check("Kết quả đếm giá trị từng cột" in seen["u"] and "«ban giam doc» ×7" in seen["u"], "Agent đưa kết quả value_counts cho AI")
check(ticks == [0, 1, 2], "tiến độ: đếm → AI tổng hợp → tính trước/sau")
ops = [o for o in d["ops"] if o["op"] == "standardize_text"]
check(len(ops) == 2 and all(o["map_view"] and o["found"] and o["recommended"] for o in ops), "có đề xuất gộp (kể cả khi AI không đề xuất), kèm danh sách gộp và số phát hiện")
check(d["pv"]["fx"][ops[0]["id"]].startswith("Gộp ") and d["vc"]["overview"] == "Tóm tắt AI", "hiển thị kết quả trước/sau và phần tổng hợp của AI")
check(d["pv"]["before"]["Định dạng"] > d["pv"]["after"]["Định dạng"], "chọn gộp thì số vấn đề 'Định dạng' giảm")
lg = cleaner.apply_choice({"sel": {}, "meth": {}, "val": {}})
check(state.A["clean"]["nv.csv"]["phong_ban"].nunique() == 4 and any("Gộp giá trị" in x for x in state.A["applied"]), "áp dụng lựa chọn: cột còn 4 giá trị chuẩn")
state.unbind()
print(f"\nTẤT CẢ {n_ok} KIỂM TRA ĐỀU ĐẠT")
