# -*- coding: utf-8 -*-
"""Kiểm thử các module mới (không cần LLM, không cần mạng):
  describe.py       phân bố từng biến (histogram / giá trị duy nhất / theo thời gian)
  analysis_spec.py  ghép biến -> kiểm tra spec -> sinh code -> CHẠY THẬT trong sandbox (cần Linux, như tests/sandbox_test.py)
  tablefacts.py     điểm nổi bật của bảng kết quả
  dash_plan.py      kế hoạch biểu đồ của bảng điều khiển
Chạy: python tests/analysis_test.py"""
import os
import sys
import tempfile

os.environ.update(DATABASE_URL=f"sqlite:///{tempfile.mkdtemp()}/a.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.data import analysis_spec as S  # noqa: E402
from app.data.describe import brief, distributions  # noqa: E402
from app.data.loader import make_sample  # noqa: E402
from app.data.tablefacts import table_facts  # noqa: E402
from app.export import dash_plan  # noqa: E402

fails = 0


def check(name, cond, extra=""):
    global fails
    print(("OK   " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    fails += 0 if cond else 1


dfs = make_sample()
sales = dfs["sales_q3.csv"]

# ---------------------------------------------------------------- describe
D = {c["col"]: c for c in distributions(dfs)[0]["cols"]}
check("describe: cột số -> định lượng có histogram và 6 thống kê", D["doanh_thu"]["kind"] == "num" and len(D["doanh_thu"]["hist"]["counts"]) >= 6 and D["doanh_thu"]["stats"]["median"] is not None)
check("describe: histogram đếm đủ số giá trị có thật", sum(D["don_gia"]["hist"]["counts"]) + sum((D["don_gia"]["hist"].get("trim") or {}).values()) == int(sales["don_gia"].notna().sum()))
check("describe: số nguyên ít giá trị -> mỗi giá trị một cột", D["so_luong"]["hist"]["discrete"] and D["so_luong"]["hist"]["labels"] == list(range(1, 8)))
check("describe: cột chữ ít giá trị -> phân loại, kèm giá trị duy nhất và số lần", D["khu_vuc"]["kind"] == "cat" and D["khu_vuc"]["unique"] == len(D["khu_vuc"]["top"]) and sum(c for _, c in D["khu_vuc"]["top"]) == D["khu_vuc"]["total"])
check("describe: ngày lưu dạng chữ -> thời gian, đếm theo tháng", D["ngay"]["kind"] == "date" and D["ngay"]["unit"] == "tháng" and sum(D["ngay"]["counts"]) > 0)
check("describe: mã đơn / mã khách -> mã định danh, không vẽ phân bố", D["ma_don"]["kind"] == "id" and "hist" not in D["ma_don"])
check("describe: nêu số ô thiếu, giá trị âm", D["doanh_thu"]["missing"] > 0 and D["doanh_thu"]["negative"] > 0)
t = pd.DataFrame({"gia": list(np.random.RandomState(1).lognormal(10, .3, 500)) + [1e9], "txt": [f"{i * 100:,}" for i in range(1, 8)] * 71 + ["900"] * 4, "hang": ["A"] * 501})
Dt = {c["col"]: c for c in distributions({"t": t})[0]["cols"]}
check("describe: đuôi cực dài bị cắt ở p1-p99 và nói rõ số giá trị bị ẩn", Dt["gia"]["hist"]["trim"]["high"] >= 1)
check("describe: số lưu dạng chữ vẫn thống kê như số", Dt["txt"]["kind"] == "num" and "chữ" in Dt["txt"]["note"])
check("describe: cột chỉ có 1 giá trị được đánh dấu", Dt["hang"]["kind"] == "cat" and Dt["hang"]["single"])
check("describe: tóm tắt cho AI không rỗng và có tên cột", "doanh_thu" in brief(distributions(dfs)))

# ---------------------------------------------------------------- analysis_spec: kiểm tra
meta = S.columns_meta(dfs)
M = {c["name"]: c for c in meta[0]["cols"]}
check("columns_meta: có kiểu từng biến", M["doanh_thu"]["kind"] == "num" and M["khu_vuc"]["kind"] == "cat" and M["ngay"]["kind"] == "date" and M["doanh_thu"]["unit"])
good = {
    "compare": {"type": "compare", "file": "sales_q3.csv", "measures": [{"col": "doanh_thu", "agg": "sum"}, {"col": "don_gia", "agg": "mean"}], "by": ["khu_vuc"]},
    "compare2": {"type": "compare", "file": "sales_q3.csv", "measures": [], "by": ["khu_vuc", "kenh"]},
    "compare3": {"type": "compare", "file": "sales_q3.csv", "measures": [{"col": None}, {"col": "doanh_thu", "agg": "sum"}], "by": ["san_pham"]},
    "trend_m": {"type": "trend", "file": "sales_q3.csv", "measures": [{"col": "doanh_thu", "agg": "sum"}], "time": {"col": "ngay", "grain": "month"}},
    "trend_q": {"type": "trend", "file": "sales_q3.csv", "measures": [{"col": "doanh_thu", "agg": "sum"}], "time": {"col": "ngay", "grain": "quarter"}, "by": ["khu_vuc"]},
    "trend_w": {"type": "trend", "file": "sales_q3.csv", "measures": [], "time": {"col": "ngay", "grain": "week"}, "by": ["kenh"]},
    "trend_d": {"type": "trend", "file": "sales_q3.csv", "measures": [{"col": "doanh_thu", "agg": "mean"}], "time": {"col": "ngay", "grain": "day"}},
    "trend_y": {"type": "trend", "file": "sales_q3.csv", "measures": [{"col": "doanh_thu", "agg": "sum"}], "time": {"col": "ngay", "grain": "year"}},
    "cross": {"type": "cross", "file": "sales_q3.csv", "measures": [{"col": "doanh_thu", "agg": "sum"}], "by": ["khu_vuc", "san_pham"]},
    "cross_n": {"type": "cross", "file": "sales_q3.csv", "measures": [], "by": ["kenh", "san_pham"]},
    "corr": {"type": "correlate", "file": "sales_q3.csv", "x": "don_gia", "y": "doanh_thu"},
    "dist_num": {"type": "distribution", "file": "sales_q3.csv", "col": "don_gia"},
    "dist_cat": {"type": "distribution", "file": "sales_q3.csv", "col": "kenh"},
    "dist_int": {"type": "distribution", "file": "sales_q3.csv", "col": "so_luong"},
}
norm = {}
for k, sp in good.items():
    n, err = S.normalize(sp, dfs)
    norm[k] = n
    check(f"normalize hợp lệ: {k}", n is not None and err is None and n["title"] and n["goal"] and n["vars"], err)
check("tiêu đề tiếng Việt đúng", norm["compare"]["title"] == "Tổng doanh thu, Trung bình đơn giá theo khu vực" and norm["trend_q"]["title"] == "Tổng doanh thu theo quý và khu vực", f"{norm['compare']['title']} | {norm['trend_q']['title']}")
bads = {
    "đo bằng cột phân loại": {"type": "compare", "file": "sales_q3.csv", "measures": [{"col": "khu_vuc", "agg": "sum"}], "by": ["kenh"]},
    "chia nhóm bằng mã": {"type": "compare", "file": "sales_q3.csv", "measures": [{"col": "doanh_thu"}], "by": ["ma_don"]},
    "xu hướng không phải cột ngày": {"type": "trend", "file": "sales_q3.csv", "measures": [], "time": {"col": "khu_vuc"}},
    "chéo thiếu một biến": {"type": "cross", "file": "sales_q3.csv", "by": ["khu_vuc"]},
    "chéo cùng một biến": {"type": "cross", "file": "sales_q3.csv", "by": ["khu_vuc", "khu_vuc"]},
    "tương quan X = Y": {"type": "correlate", "file": "sales_q3.csv", "x": "don_gia", "y": "don_gia"},
    "cột không tồn tại": {"type": "compare", "file": "sales_q3.csv", "measures": [{"col": "khong_co"}], "by": ["kenh"]},
    "kiểu lạ": {"type": "hack", "file": "sales_q3.csv"},
}
for k, sp in bads.items():
    n, err = S.normalize(sp, dfs)
    check(f"normalize từ chối: {k}", n is None and err, str(n))
one = {"sales_q3.csv": sales}
n, _ = S.normalize({"type": "compare", "measures": [{"col": "Doanh thu", "agg": "sum"}], "by": ["Khu vực"]}, one)
check("nhận tên cột theo nhãn tiếng Việt và tự chọn bảng khi chỉ có một", n is not None and n["measures"][0]["col"] == "doanh_thu" and n["by"] == ["khu_vuc"])
n, _ = S.normalize({"type": "free", "text": "tính tỷ lệ khách quay lại"}, dfs)
check("yêu cầu tự do được giữ nguyên chữ để AI viết code", n["type"] == "free" and "quay lại" in n["text"])
dw = S.data_words(dfs)
check("data_words: giá trị dữ liệu (HCM, Online, SP-A) được bảo vệ khỏi bước dịch tên cột", {"HCM", "Online", "SP-A"} <= dw and "doanh_thu" not in dw, str(sorted(dw)[:8]))
check("vars_in_text nhận ra cột theo nhãn", set(S.vars_in_text("so sánh doanh thu giữa các khu vực", dfs)) >= {"doanh_thu"})

# ---------------------------------------------------------------- analysis_spec: sinh code và CHẠY THẬT
if sys.platform.startswith("linux"):
    from app.data.sandbox import check_code, prepare, run_code
    with prepare(dfs):
        for k, n in norm.items():
            code = S.build_code(n, dfs)
            try:
                check_code(code)
                df = run_code(code, dfs)
                ok = len(df) > 0 and "index" not in df.columns and len(set(df.columns)) == len(df.columns)
                check(f"chạy trong sandbox: {k} -> {df.shape}", ok, str(list(df.columns)))
            except Exception as e:                    # noqa: BLE001
                check(f"chạy trong sandbox: {k}", False, f"{type(e).__name__}: {getattr(e, 'user_text', e)}")
        # kết quả ĐÚNG số (đối chiếu pandas)
        res = run_code(S.build_code(norm["compare"], dfs), dfs).set_index("Khu vực")
        exp = sales.groupby("khu_vuc")["doanh_thu"].sum()
        check("compare: tổng đúng từng nhóm", all(abs(res.loc[g, "Tổng doanh thu"] - round(v, 2)) < .01 for g, v in exp.items()))
        check("compare: tỷ trọng cộng lại ~100%", abs(run_code(S.build_code(norm["compare"], dfs), dfs)["Tỷ trọng (%)"].sum() - 100) < .5)
        tr = run_code(S.build_code(norm["trend_m"], dfs), dfs)
        check("trend: nhãn kỳ YYYY-MM tăng dần, có % thay đổi", list(tr.iloc[:, 0]) == sorted(tr.iloc[:, 0]) and "% thay đổi so với kỳ trước" in tr.columns)
        cr = run_code(S.build_code(norm["cross"], dfs), dfs)
        check("cross: tổng bảng chéo = tổng doanh thu", abs(cr.drop(columns=cr.columns[0]).to_numpy().sum() - sales["doanh_thu"].sum()) < 5)
        ds = run_code(S.build_code(norm["dist_cat"], dfs), dfs)
        check("distribution phân loại: số bản ghi cộng đúng", int(ds["Số bản ghi"].sum()) == int(sales["kenh"].notna().sum()))
        # tên cột có ký tự lạ không thoát khỏi comment / chuỗi
        evil = sales.rename(columns={"kenh": "k\nimport os"})
        n2, _ = S.normalize({"type": "compare", "file": "e.csv", "measures": [{"col": "doanh_thu"}], "by": ["k\nimport os"]}, {"e.csv": evil})
        code2 = S.build_code(n2, {"e.csv": evil})
        check("tên cột chứa xuống dòng không phá được code", all(not ln.lstrip().startswith("import") for ln in code2.splitlines()))
    check("hệ số tương quan được tính riêng", "Pearson" in S.spec_facts(norm["corr"], dfs)[0])
else:
    print("BỎ QUA  sandbox: cần Linux (như tests/sandbox_test.py)")

# ---------------------------------------------------------------- tablefacts
f = table_facts(pd.DataFrame({"Khu vực": ["HCM", "HN", "ĐN"], "Tổng doanh thu": [12.9e9, 8.9e9, 5.4e9], "Tỷ trọng (%)": [47, 33, 20]}))
check("điểm nổi bật: cao nhất / thấp nhất / tỷ trọng", len(f) >= 3 and "HCM" in f[0] and "Thấp nhất" in f[1], str(f))
f = table_facts(pd.DataFrame({"Kỳ": ["2026-01", "2026-02", "2026-03", "2026-04"], "Doanh thu": [100., 90, 120, 130]}))
check("điểm nổi bật theo thời gian: đầu → cuối", any("→" in x for x in f), str(f))
check("điểm nổi bật: bảng 1 dòng không bịa gì", table_facts(pd.DataFrame({"a": ["x"], "b": [1]})) == [] and table_facts(None) == [])

# ---------------------------------------------------------------- dash_plan
cat = dash_plan.catalog(dfs)
c0 = cat[0]
check("catalog: bảng, chiều, thời gian, chỉ số", c0["name"] == "sales_q3.csv" and c0["time"] and len(c0["dims"]) >= 3 and any(m["label"] == "Doanh thu" for m in c0["meas"]))
dk = {d["label"]: d["k"] for d in c0["dims"]}
mk = {m["label"]: m["k"] for m in c0["meas"]}
ai = dash_plan.from_ai([
    {"ds": "sales_q3.csv", "by": "Thời gian", "measure": "Doanh thu", "kind": "trend"},
    {"ds": "sales_q3.csv", "by": "Khu vực", "measure": "Doanh thu", "agg": "sum", "kind": "donut"},
    {"ds": "sales_q3.csv", "by": "Khu vực", "measure": "Đơn giá", "agg": "avg", "kind": "donut"},
    {"ds": "sales_q3.csv", "by": "Cột bịa", "measure": "Doanh thu", "kind": "bars"},
    {"ds": "sales_q3.csv", "by": "Kênh", "measure": "Chỉ số bịa", "kind": "bars"},
    {"ds": "sales_q3.csv", "by": "Khu vực", "measure": "Doanh thu", "agg": "sum", "kind": "donut"},
    "rác"], cat)
check("from_ai: giữ đúng, bỏ cột/chỉ số bịa, bỏ trùng, đổi tròn+trung bình thành cột", len(ai) == 3 and ai[2]["kind"] == "bars" and ai[0]["by"] == "t" and ai[1]["by"] == dk["Khu vực"], str([(a["by"], a["m"], a["kind"]) for a in ai]))
check("validate: sửa tổ hợp vô nghĩa (đường cho biến không phải thời gian)", dash_plan.validate([{"ds": c0["name"], "by": dk["Kênh"], "m": "*", "kind": "trend"}], cat)[0]["kind"] == "bars")
check("validate: thời gian + tròn -> cột dọc; khóa lạ bị bỏ", dash_plan.validate([{"ds": c0["name"], "by": "t", "m": "", "kind": "donut"}, {"ds": c0["name"], "by": "zz"}, {"ds": "x", "by": "t"}, {"ds": c0["name"], "by": "t", "m": "m99"}], cat)[0]["kind"] == "cols" and len(dash_plan.validate([{"ds": c0["name"], "by": "t", "m": "", "kind": "donut"}, {"ds": c0["name"], "by": "zz"}, {"ds": "x", "by": "t"}, {"ds": c0["name"], "by": "t", "m": "m99"}], cat)) == 1)
check("validate: tối đa 12 biểu đồ", len(dash_plan.validate([{"ds": c0["name"], "by": d["k"], "m": m["k"], "agg": a, "kind": "bars"} for d in c0["dims"] for m in c0["meas"] for a in ("sum", "avg")] * 2, cat)) == 12)
auto = dash_plan.auto_plan(cat)
check("auto_plan: có xu hướng + cơ cấu + xếp hạng, đều hợp lệ", any(a["kind"] == "trend" for a in auto) and any(a["kind"] == "donut" for a in auto) and len(dash_plan.validate(auto, cat)) == len(auto))
check("suggest: AI gợi ý quá ít thì bổ sung bằng luật", len(dash_plan.suggest([], cat)) >= 4)
check("title: tên biểu đồ tiếng Việt", dash_plan.title({"ds": c0["name"], "by": dk["Khu vực"], "m": mk["Doanh thu"], "agg": "sum"}, cat) == "Tổng doanh thu theo khu vực" and dash_plan.title({"ds": c0["name"], "by": "t", "m": "", "agg": "count"}, cat) == "Số bản ghi theo tháng")

print(f"\n{'TẤT CẢ ĐẠT' if not fails else str(fails) + ' KIỂM TRA THẤT BẠI'}")
sys.exit(1 if fails else 0)
