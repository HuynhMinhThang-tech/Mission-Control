# -*- coding: utf-8 -*-
"""Kiểm thử: cột NGÀY (hoặc SỐ) lưu dạng chữ không bị đối xử như biến phân loại ở bước làm sạch.
Trước đây cột ngày đi qua đường 'đếm giá trị và gộp' (Giữ nguyên / Gộp vào…) giống biến phân loại, và to_dt đọc 05/01/2026 thành 1 tháng 5.
Chạy: python tests/date_clean_test.py"""
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
from app.data.quality import day_order, to_dt  # noqa: E402

n_ok = 0


def check(cond, label):
    global n_ok
    if not cond:
        print("FAIL:", label)
        sys.exit(1)
    n_ok += 1
    print("ok  ", label)


def iso(x):
    return to_dt(pd.Series(x)).dt.strftime("%Y-%m-%d").tolist()


# ---- đọc ngày kiểu Việt Nam
check(iso(["05/01/2026", "06/01/2026", "07/01/2026"]) == ["2026-01-05", "2026-01-06", "2026-01-07"], "05/01/2026 là NGÀY 5 THÁNG 1 (không phải 1 tháng 5 kiểu Mỹ)")
check(iso(["2026-01-03", "2026/02/04", "2026-01-03 10:30:00"]) == ["2026-01-03", "2026-02-04", "2026-01-03"], "dạng năm-trước (ISO) giữ nguyên, không bị đảo ngày/tháng")
mix = to_dt(pd.Series(["2026-01-03", "05/01/2026", "05-01-2026", None, "ngày 8 tháng 1"]))
check(mix.iloc[0] == pd.Timestamp("2026-01-03") and mix.iloc[1] == pd.Timestamp("2026-01-05") and mix.iloc[2] == pd.Timestamp("2026-01-05") and mix.iloc[3:].isna().all(), "cột trộn ISO + d/m/y + d-m-y: đọc đúng từng dạng, ô lạ thành trống")
check(iso(["01/13/2026", "02/20/2026"]) == ["2026-01-13", "2026-02-20"] and day_order(pd.Series(["01/13/2026"])) == (False, True), "dữ liệu CHỨNG MINH tháng/ngày (có số 'tháng' > 12) thì đọc đúng kiểu đó")
check(day_order(pd.Series(["05/01/2026"])) == (True, False) and day_order(pd.Series(["25/01/2026"])) == (True, True), "không đủ chứng cứ: mặc định ngày/tháng nhưng báo rõ là chưa chắc chắn")
dup = to_dt(pd.Series(["05/01/2026", "x"], index=[7, 7]))
check(dup.index.tolist() == [7, 7] and dup.iloc[0] == pd.Timestamp("2026-01-05"), "chỉ số trùng không làm hỏng kết quả")

# ---- dữ liệu: ngày dạng chữ + danh mục thật + số dạng chữ
dates = pd.date_range("2026-01-01", periods=9).strftime("%d/%m/%Y").tolist() * 3
dates[5], dates[7], dates[11], dates[13] = "05-01-2026", "ngày 8 tháng 1", "2026-01-03", None
DM = ["Ăn uống", "an uong", "Di chuyển", "Giải trí", "Ăn uống", "Sinh hoạt", "Sinh hoạt", "Sinh hoạt", "Sinh hoạt"] * 3
NUM = [f"{1000 + i * 7:,}" for i in range(27)]
NUM[3] = "n/a"
df = pd.DataFrame({"Ngày": dates, "Danh mục": DM, "Tiền chữ": NUM, "Số tiền": range(27)})
RAW = {"chi.csv": df}

rep = vc.report(RAW)
by = {c["col"]: c for c in rep}
check(set(by) == {"Ngày", "Danh mục", "Tiền chữ"}, "vẫn quét đúng các cột chữ")
d = by["Ngày"]
check(d["kind"] == "date" and d["variants"] == [] and d["weak"] == [] and d["top"] == [], "cột ngày: KHÔNG có nhóm gộp, KHÔNG có bảng đếm để gộp")
i = d["info"]
check(i["ok"] == 25 and i["n"] == 26 and i["bad_n"] == 1 and i["bad"][0][0] == "ngày 8 tháng 1" and i["min"] == "01/01/2026" and i["max"] == "09/01/2026",
      "cột ngày: đọc được 25/26 ô, chỉ ra đúng ô không đọc được và khoảng thời gian")
check(i["nfmt"] == 3 and i["order"] == "dm" and i["sure"] is False and d["cmd"].startswith("pd.to_datetime"), "cột ngày: 3 cách viết, thứ tự ngày/tháng (chưa chắc chắn), lệnh đã chạy ghi đúng")
n = by["Tiền chữ"]
check(n["kind"] == "num" and n["variants"] == [] and n["info"]["ok"] == 26 and n["info"]["bad"][0][0] == "n/a", "cột số lưu dạng chữ: không gộp, báo ô không đọc được")
check(by["Danh mục"]["kind"] == "cat" and len(by["Danh mục"]["variants"]) == 1, "biến phân loại thật VẪN được gộp như cũ (Ăn uống / an uong)")

llm_text = vc.for_llm(rep)
check("Cột ngày đang lưu dạng chữ" in llm_text and "Ngày: " in llm_text and "Đếm: 01/01/2026" not in llm_text and "Đếm: 05/01/2026" not in llm_text, "AI nhận mô tả đọc ngày, không phải bảng đếm giá trị của ngày")
v = vc.view(rep, {"columns": [{"file": "chi.csv", "column": "Ngày", "finding": "nhận định kiểu phân loại của AI"}]})
fd = {f["col"]: f for f in v["findings"]}
check(fd["Ngày"]["kind"] == "date" and "không gộp giá trị" in fd["Ngày"]["text"] and "phân loại của AI" not in fd["Ngày"]["text"], "nhận định cột ngày do code viết (không để AI viết như biến phân loại)")

# ---- đề xuất: AI lỡ đề xuất gộp cho cột ngày -> bị chặn; luôn có thao tác chuẩn hóa ngày thật
state.bind(1)
state.A["raw"] = RAW
ai = [{"file": "chi.csv", "op": "standardize_text", "column": "Ngày", "mapping": {"05-01-2026": "05/01/2026"}, "recommended": True, "reason": "gộp"},
      {"file": "chi.csv", "op": "standardize_text", "column": "Tiền chữ", "mapping": {"n/a": "0"}, "recommended": True, "reason": "gộp"}]
out = cleaner.fold_standardize(ai, rep)
check(not [o for o in out if o["op"] == "standardize_text" and o["column"] in ("Ngày", "Tiền chữ")], "AI đề xuất gộp giá trị cho cột ngày/số: bị loại")
check([o["op"] for o in out if o.get("column") == "Ngày"] == ["to_datetime"], "cột ngày luôn có đúng MỘT thao tác riêng: chuẩn hóa sang kiểu ngày thật")
td = [o for o in out if o.get("column") == "Ngày"][0]
check(td["recommended"] is True and "NGÀY/THÁNG" in td["reason"] and "THÁNG/NGÀY" in td["risk"], "thao tác ghi rõ thứ tự ngày-tháng đã dùng và rủi ro nếu dữ liệu ghi ngược")
out2 = cleaner.fold_standardize([{"file": "chi.csv", "op": "to_datetime", "column": "Ngày", "recommended": True, "reason": "AI"}], rep)
check(len([o for o in out2 if o.get("op") == "to_datetime" and o.get("column") == "Ngày"]) == 1, "AI đã đề xuất to_datetime thì không thêm bản trùng")
check(any(o["op"] == "standardize_text" and o["column"] == "Danh mục" for o in out), "cột phân loại vẫn được đề xuất gộp")

# ---- chạy cả Agent (AI giả cố tình gộp cột ngày) rồi áp dụng
state.A["question"], state.A["ctx"], state.A["d"] = "q", "", {}
seen = {}
cleaner.llm_json = lambda system, user, *a, **k: (seen.update(u=user), {"operations": ai, "value_counts": {"overview": "Tóm tắt AI", "columns": []}})[1]
state.A["job"] = {"running": True, "step": 2, "k": 0}
cleaner.run()
dd = state.A["d"][2]
check("tuyệt đối không dùng standardize_text cho cột đó" in seen["u"] and "Cột ngày đang lưu dạng chữ" in seen["u"], "prompt báo AI: cột ngày/số không gộp giá trị")
std = [o for o in dd["ops"] if o["op"] == "standardize_text"]
check([o["column"] for o in std] == ["Danh mục"], "kết quả cuối: chỉ còn gộp cho cột phân loại")
dop = [o for o in dd["ops"] if o["op"] == "to_datetime"][0]
check(dop["label"] == "Chuẩn hóa ngày" and dop["found"] and dd["pv"]["fx"][dop["id"]] == "25/27 giá trị đọc được · 1 giá trị không đọc được sẽ thành thiếu",
      "thao tác ngày có kết quả thật: 25/27 dòng đọc được (1 ô thiếu sẵn + 1 ô lạ), 1 ô lạ sẽ thành trống")
check(any(f["col"] == "Ngày" and f["kind"] == "date" for f in dd["vc"]["findings"]), "giao diện nhận được nhận định kiểu 'date' cho cột ngày")
cleaner.apply_choice({"sel": {}, "meth": {}, "val": {}})
col = state.A["clean"]["chi.csv"]["Ngày"]
check(pd.api.types.is_datetime64_any_dtype(col) and col.iloc[4] == pd.Timestamp("2026-01-05") and col.iloc[7] != col.iloc[7] and col.iloc[11] == pd.Timestamp("2026-01-03"),
      "áp dụng: cột thành kiểu ngày THẬT, 05/01/2026 = 5 tháng 1, ISO đúng, ô lạ thành trống")
check(state.A["clean"]["chi.csv"]["Danh mục"].nunique() == 4, "cột phân loại vẫn được gộp (5 → 4 giá trị)")
state.unbind()
print(f"\nTẤT CẢ {n_ok} KIỂM TRA ĐỀU ĐẠT")
