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
