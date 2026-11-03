# -*- coding: utf-8 -*-
"""Kiểm thử bản 0.1.7 (HM-01 trong kế hoạch nâng cấp): sửa nhanh các lỗi làm mất lòng tin.
  Q1/Q1b  bằng chứng không còn phép tính tự do; phép tính còn sót bị CODE tính lại, sai thì gắn cờ
  Q2      prompt không ép AI bịa (không ép số lượng, không ép hành động, không "mức thay đổi hợp lý")
  Q3      không còn câu tự khẳng định cứng khi có phát hiện chưa kiểm được
  Q4      KPI bảng điều khiển: không chắc thì dùng trung bình, đổi tay được trên thẻ; AI không được chọn "tổng" cho chỉ số không cộng được
  Q5      trạng thái kiểm tra hiện ở bước 5, báo cáo, bảng điều khiển
  Q6      thẻ dữ liệu do code lập, đưa vào prompt
  Q7      hai ô bối cảnh (quyết định, đòn bẩy)
Chạy: python tests/quickfix_test.py"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _flow as F  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from pptx import Presentation  # noqa: E402

from app import labels as lb, numfmt as nf  # noqa: E402
from app.agents import insight as insight_mod, playbook  # noqa: E402
from app.data.scope import data_card  # noqa: E402
from app.export import dash_plan, interactive  # noqa: E402

fails = 0


def check(name, cond, extra=""):
    global fails
    print(("OK   " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    fails += 0 if cond else 1


# ============================================================ Q1b: tính lại phép tính trong bằng chứng
CALC = [
    ("669,19 + 543,6 + 410,5 + 389,12 + 301,77 + 420,1 + 330 = 2.152,25", 1, 1),   # ca trong ảnh: tổng thật là 3.064,28
    ("669,19 + 543,6 + 410,5 + 389,12 + 301,77 + 420,1 + 330 = 3.064,28", 1, 0),
    ("(120,5 + 130 + 99,5) / 3 = 39,46", 1, 1),                                     # trung bình thật 116,67
    ("(120,5 + 130 + 99,5) / 3 = 116,67", 1, 0),
    ("669,19 / 2.152,25 = 31,09%", 1, 0),
    ("669,19 / 2.152,25 = 41,09%", 1, 1),
    ("[Phân tích 1, NM1, Sản lượng] = 669,19; [Phân tích 1, NM2, Sản lượng] = 543,6", 0, 0),   # ô nguồn, không phải phép tính
    ("T3/2026 = 123", 0, 0),
    ("2026-03-01 = 5", 0, 0),
    ("1,2 tỷ + 0,8 tỷ = 2 tỷ", 1, 0),
    ("1,2 tỷ + 0,8 tỷ = 3 tỷ", 1, 1),
    ("5 - 8 = -3", 1, 0),
    ("5 - 8 = 3", 1, 1),
    ("2.240 / 1.000 = 2,24", 1, 0),                                                  # dấu chấm mơ hồ: hiểu kiểu nào khớp cũng không bị bắt oan
    ("10 / 0 = 5", 0, 0),                                                           # chia 0: không kết luận
    ("5,5 / 12 = 45,83%", 1, 0),                                                    # lệch chỉ do toán hạng đã làm tròn: không phải sai
    ("5 / 12 = 42%", 1, 0),
    ("5 / 12 = 52%", 1, 1),
    ("Tổng NM1 = 669,19 + 543,6 = 1.300,79", 1, 1),
    ("36,38 × 12 = 436,56", 1, 0),
]
wrong = [(t, nf.calc_check(t)) for t, ck, bd in CALC if (nf.calc_check(t)["checked"], len(nf.calc_check(t)["bad"])) != (ck, bd)]
check(f"Q1b: tính lại phép tính trong bằng chứng ({len(CALC)} ca, gồm ca sai trong ảnh)", not wrong, str(wrong[:2]))
check("Q1b: giá trị tính lại hiển thị đúng (3.064,28 và 116,67)",
      nf.calc_check(CALC[0][0])["bad"][0]["calc"] == "3.064,28" and nf.calc_check(CALC[2][0])["bad"][0]["calc"] == "116,67")
check("Q1b: numfmt không dùng eval/exec", not re.search(r"\b(eval|exec)\(", open(nf.__file__, encoding="utf-8").read()))

tab = pd.DataFrame({"Nhóm": list("ABC"), "Giá trị": [1500000000.0, 800000000.0, 700000000.0]})
known = nf.Known.from_dfs([tab])
ins = nf.audit_insights([
    {"title": "A chiếm 50% tổng", "confidence": "Cao", "evidence": "1.500.000.000 / 3.000.000.000 = 50%"},
    {"title": "Tổng ba nhóm", "confidence": "Cao", "evidence": "669,19 + 543,6 + 410,5 = 2.152,25"},
    {"title": "Doanh thu 9.999.999.999 đồng", "confidence": "Cao", "evidence": "không rõ"},
    {"title": "Nhận định chung", "confidence": "Trung bình", "evidence": "xu hướng đi lên"},
], known)
check("Q1b: phát hiện có phép tính đúng -> verify=ok, giữ độ tin cậy", ins[0]["verify"] == "ok" and ins[0]["confidence"] == "Cao")
check("Q1b: phép tính sai -> verify=mismatch, calc_mismatch có số tính lại, hạ độ tin cậy xuống Thấp",
      ins[1]["verify"] == "mismatch" and ins[1]["confidence"] == "Thấp" and "1.623,29" in ins[1]["calc_mismatch"][0], str(ins[1]))
check("Q1b: số lớn không có trong bảng -> mismatch (hành vi cũ giữ nguyên)", ins[2]["verify"] == "mismatch" and ins[2]["check"] and ins[2]["confidence"] == "Thấp")
check("Q1b: không có gì để kiểm -> 'unverified' (KHÔNG coi là đúng), giữ nguyên độ tin cậy", ins[3]["verify"] == "unverified" and ins[3]["confidence"] == "Trung bình")
check("Q1b: gọi nhiều lần cho cùng kết quả (idempotent: make_final/live_meta gọi lại)", nf.audit_insights(ins, known) == ins)
check("Q1b: đếm đã kiểm / tổng; all_verified chỉ đúng khi mọi phát hiện đều ok", nf.verify_counts(ins) == (1, 4) and not nf.all_verified(ins) and nf.all_verified(ins[:1]) and not nf.all_verified([]))

# ---- Q1b mở rộng: đối chiếu từng ô được trích [bảng, hàng, cột] = giá trị với bảng kết quả (Q1 cấm viết phép tính nên đây là cách kiểm chính)
cdf = pd.DataFrame({"Nhóm": ["NM1", "NM2", "NM3"], "Tổng sản lượng": [31892.6, 10482.9, 20000.0]})
ck = nf.Known.from_dfs([cdf])
cc_ = lambda t: nf.check_cells(t, ck)                           # noqa: E731
check("Q1b ô trích: giá trị khớp (kể cả làm tròn, viết lệch hoa/dấu tên hàng, cột) -> ok",
      cc_("[Sản lượng, NM1, Tổng sản lượng] = 31.892,6")["ok"] == 1 and cc_("[Sản lượng, NM1, Tổng sản lượng] = 31.893")["ok"] == 1
      and cc_("[Sản lượng, nm1, tong san luong] = 31.892,6")["ok"] == 1 and cc_("[Sản lượng, NM2, Tổng sản lượng] = 10,5 nghìn")["ok"] == 1)
check("Q1b ô trích: ô tìm thấy mà lệch giá trị -> báo sai kèm giá trị bảng ghi", "31.892,6" in cc_("[Sản lượng, NM1, Tổng sản lượng] = 99.999,9")["bad"][0])
check("Q1b ô trích: không tìm thấy hàng/cột -> 'chưa kiểm được', KHÔNG báo sai oan",
      all(cc_(t) == {"ok": 0, "bad": [], "unlocated": 1} for t in ("[Sản lượng, NM9, Tổng sản lượng] = 5", "[Sản lượng, NM1, Cột lạ] = 5", "[x, NM1] = 5")))
ins_c = nf.audit_insights([{"title": "NM1 dẫn đầu", "confidence": "Cao", "evidence": "[Sản lượng, NM1, Tổng sản lượng] = 31.892,6"},
                           {"title": "NM1 dẫn đầu", "confidence": "Cao", "evidence": "[Sản lượng, NM1, Tổng sản lượng] = 39.999,9"},
                           {"title": "NM9 dẫn đầu", "confidence": "Cao", "evidence": "[Sản lượng, NM9, Tổng sản lượng] = 31.892,6"}], ck)
check("Q1b ô trích: số NHỎ (dưới 1 triệu) cũng được kiểm: khớp -> ok; lệch -> mismatch + hạ 'Thấp'; không định vị được -> unverified",
      [x["verify"] for x in ins_c] == ["ok", "mismatch", "unverified"] and ins_c[1]["confidence"] == "Thấp" and "31.892,6" in nf.verify_note(ins_c[1]), str([(x["verify"], x.get("confidence")) for x in ins_c]))

# ============================================================ Q1/Q2: prompt
P = insight_mod.PROMPT
check("Q1: evidence chỉ chép ô nguồn, không viết phép tính", "KHÔNG viết phép tính" in P and "phép tính cụ thể" not in P)
check("Q2: không ép số lượng (tối đa, được phép 0), bỏ '3-5 phát hiện'", "3-5 phát hiện" not in P and "Tối đa 5" in P and "được phép 0" in P)
check("Q2: hành động chỉ đưa khi gắn phát hiện, được phép bỏ trống", "chỉ đưa khi gắn với một phát hiện" in P and "được phép bỏ trống" in P)
check("Q2: không còn 'mức thay đổi hợp lý' như một chỉ dẫn tự đặt (cả INSIGHT_RULES lẫn CODE_RULES)",
      "mức thay đổi hợp lý (nêu giả định)" not in playbook.INSIGHT_RULES and "mức thay đổi hợp lý theo dữ liệu" not in playbook.CODE_RULES and "KHÔNG tự đặt mức thay đổi" in playbook.INSIGHT_RULES)
check("Q2: có câu đóng 'chỉ khẳng định điều suy ra được từ cột và bảng được cung cấp' + yếu tố ngoài dữ liệu chỉ là giả thuyết",
      "Chỉ khẳng định điều suy ra được từ các cột và bảng được cung cấp" in P and "giả thuyết cần kiểm chứng" in P)
check("Q2: có quy tắc không tự đặt mốc so sánh, tác động chỉ bằng số có sẵn trong bảng", "KHÔNG tự đặt mốc" in playbook.INSIGHT_RULES and "chưa ước tính được" in playbook.INSIGHT_RULES)

# ============================================================ Q4: KPI mặc định an toàn
add = {c: lb.is_additive(c) for c in ["Doanh thu", "Số lượng", "Tổng tiền", "Số tiền (đ)", "Sản lượng", "Khối lượng sản xuất", "Thời lượng", "revenue"]}
non = {c: lb.is_additive(c) for c in ["Tuổi", "Age", "Điểm", "Đơn giá", "Rating", "Chiều cao", "Thâm niên", "Satisfaction", "Mã đơn hàng", "Tỷ lệ hoàn trả"]}
check("Q4: cột tiền/số lượng/khối lượng/thời lượng/'Tổng...' cộng được", all(add.values()), str([c for c, v in add.items() if not v]))
check("Q4: tuổi, điểm, đơn giá, cột LẠ (Age, Satisfaction...) KHÔNG cộng được -> mặc định trung bình", not any(non.values()), str([c for c, v in non.items() if v]))
check("Q4: 'Khối lượng', 'Thời lượng' không còn bị gắn đơn vị tiền (đ)", lb.unit("Khối lượng sản xuất") == "" and lb.unit("Thời lượng") == "" and lb.unit("Lương") == "đ")

rng = np.random.default_rng(3)
n = 120
df = pd.DataFrame({"Ngày": pd.date_range("2026-01-01", periods=n).astype(str), "Khu vực": rng.choice(["Bắc", "Trung", "Nam"], n),
                   "Doanh thu": rng.integers(100, 900, n) * 1000, "Số lượng": rng.integers(1, 9, n), "Age": rng.integers(20, 60, n),
                   "Tuổi": rng.integers(20, 60, n), "Điểm": rng.integers(1, 10, n), "Đơn giá": rng.integers(10, 99, n) * 1000})
spec = interactive._spec("x.csv", df)
mm = {m["label"]: m for m in spec["meas"]}
check("Q4: bảng điều khiển: Age, Tuổi, Điểm, Đơn giá mặc định trung bình; Doanh thu, Số lượng cộng",
      all(mm[k]["avg"] for k in ("Age", "Tuổi", "Điểm", "Đơn giá")) and not mm["Doanh thu"]["avg"] and not mm["Số lượng"]["avg"] and mm["Doanh thu"]["add"], str({k: v["avg"] for k, v in mm.items()}))
cat = dash_plan.catalog({"x.csv": df})
age_k = next(m["k"] for m in cat[0]["meas"] if m["label"] == "Age")
rev_k = next(m["k"] for m in cat[0]["meas"] if m["label"] == "Doanh thu")
dim = cat[0]["dims"][0]["k"]
pl = dash_plan.validate([{"ds": "x.csv", "by": dim, "m": age_k, "agg": "sum", "kind": "bars", "src": "ai"},
                         {"ds": "x.csv", "by": dim, "m": rev_k, "agg": "sum", "kind": "bars", "src": "ai"},
                         {"ds": "x.csv", "by": "t", "m": age_k, "agg": "sum", "kind": "trend", "src": "user"}], cat)
check("Q4: AI chọn 'tổng' cho tuổi -> đổi sang trung bình; AI chọn tổng cho doanh thu -> giữ; người dùng tự chọn tổng -> giữ",
      [p["agg"] for p in pl] == ["avg", "sum", "sum"], str([(p["m"], p["agg"], p["src"]) for p in pl]))
check("Q4: tiêu đề biểu đồ AI không còn 'Tổng age'", "Tổng" not in dash_plan.title(pl[0], cat), dash_plan.title(pl[0], cat))
pl2 = dash_plan.validate([{"ds": "x.csv", "by": dim, "m": age_k, "agg": "sum", "kind": "bars", "src": "ai", "title": "Tổng tuổi theo khu vực"},
                          {"ds": "x.csv", "by": dim, "m": rev_k, "agg": "sum", "kind": "bars", "src": "ai", "title": "Tổng doanh thu theo khu vực"}], cat)
check("Q4: AI viết sẵn tiêu đề 'Tổng tuổi...' mà bị đổi sang trung bình -> bỏ tiêu đề đó (không để chữ 'Tổng' trên số trung bình); tiêu đề hợp lệ được giữ",
      "Tổng" not in str(dash_plan.title(pl2[0], cat)) and pl2[1]["title"] == "Tổng doanh thu theo khu vực", str([(p["agg"], p["title"]) for p in pl2]))
js = open(os.path.join(os.path.dirname(interactive.__file__), "assets", "live.js"), encoding="utf-8").read()
check("Q4: live.js có nút đổi cách tổng hợp trên thẻ chỉ số (data-ag) và dùng aggOf thay cho m.avg cứng", "data-ag" in js and "aggOf" in js and js.count("m.avg ? 'avg' : 'sum'") == 1)

# ============================================================ Q6: thẻ dữ liệu
card = data_card({"san_xuat.csv": pd.DataFrame({"Ngày": pd.date_range("2026-01-01", periods=60).astype(str), "Nhà máy": rng.choice(["NM1", "NM2"], 60), "Sản lượng": rng.normal(100, 5, 60).round(1)})})
check("Q6: thẻ dữ liệu liệt kê bảng, cột (kèm kiểu), kỳ thời gian thật", all(x in card for x in ("san_xuat.csv", "Sản lượng (số)", "Nhà máy (phân loại)", "Ngày (thời gian)", "01/01/2026 đến 01/03/2026")), card[:300])
check("Q6: thẻ dữ liệu có câu giới hạn (chỉ dựa vào đây; ngoài dữ liệu là giả thuyết)", "Chỉ được dựa vào những bảng, cột" in card and "giả thuyết cần kiểm chứng" in card)
check("Q6: không có bảng -> thẻ rỗng", data_card({}) == "" and data_card({"a": pd.DataFrame()}) == "")

# ============================================================ luồng đầy đủ với LLM giả: Q1b, Q3, Q5, Q6, Q7
app, c = F.setup()
orig = F.fake_llm
BOX = {"ins": None}


def fake(system, user, max_tokens=8000, json_mode=False):
    if "Agent Phát hiện" in system and BOX["ins"] is not None:
        F.PROMPTS.append((system[:80], user))
        return json.dumps(BOX["ins"](user) if callable(BOX["ins"]) else BOX["ins"])
    return orig(system, user, max_tokens, json_mode)


F.llm.llm = fake


def run_flow(payload, **start):
    BOX["ins"] = payload
    F.post(c, "/api/new")
    F.post(c, "/api/sample")
    F.post(c, "/api/start", {"question": "Khu vực nào bán tốt nhất?", **start})
    s = F.wait(c)
    F.post(c, "/api/accept/1"); F.wait(c)
    F.post(c, "/api/accept/2"); s = F.wait(c)
    F.post(c, "/api/a3/code", {"ids": [m["id"] for m in s["d"]["3"]["menu"]], "custom": "", "specs": []}); F.wait(c)
    F.post(c, "/api/a3/exec", {"codes": []}); F.wait(c, 120)
    F.post(c, "/api/accept/3"); s = F.wait(c)
    F.post(c, "/api/accept/4"); s = F.wait(c)
    d5 = s["d"]["5"]
    F.post(c, "/api/accept/5", {"title": "Báo cáo", "charts": d5["charts"], "kpis": [], "dash": d5["dash"]["ai"]}); s = F.wait(c)
    check("luồng: bước 6 (rà soát) tạo xong", "checks" in s["d"]["6"], str(s["d"].get("6")))
    chk = s["d"]["6"]["checks"]
    F.post(c, "/api/accept/6"); s = F.wait(c)
    aid = s["id"]
    get = lambda n: c.get(f"/api/download/{aid}/{n}").data       # noqa: E731
    pp = Presentation(io.BytesIO(get("bao_cao.pptx")))
    txt = []
    for sl in pp.slides:
        for sh in sl.shapes:
            if sh.has_text_frame:
                txt.append(sh.text_frame.text)
            if getattr(sh, "has_table", False) and sh.has_table:
                txt += [cell.text for r in sh.table.rows for cell in r.cells]
    return s, chk, "\n".join(txt), get("bao_cao.md").decode("utf-8"), c.get(f"/api/view/{aid}/bao_cao.html").get_data(as_text=True), c.get(f"/api/view/{aid}/dashboard.html").get_data(as_text=True)


GOOD = {"summary": "Tóm tắt.", "insights": [
    {"title": "Hai khu vực gộp lại 300", "confidence": "Cao", "evidence": "[Phân tích 1, A, Tổng doanh thu] = 100; [Phân tích 1, B, Tổng doanh thu] = 200; 100 + 200 = 300", "source": "Phân tích 1"},
    {"title": "Trung bình hai khu vực là 15", "confidence": "Trung bình", "evidence": "(10 + 20) / 2 = 15", "source": "Phân tích 1"}],
    "actions": [{"text": "Xem lại nhóm yếu", "priority": "Cao", "impact": "chưa ước tính được"}], "risks": ["Giả thuyết cần kiểm chứng: chiến dịch. Dữ liệu cần thu thêm: chi phí."]}
s, chk, pptx, md, html, dash = run_flow(GOOD, decision="có tăng ngân sách quảng cáo không?", levers="giá bán, ngân sách quảng cáo", ctx="Cửa hàng nhỏ")
ins4 = s["d"]["4"]["insights"]
check("Q1b/Q5 (luồng): cả hai phát hiện verify=ok, giữ nguyên độ tin cậy", [x["verify"] for x in ins4] == ["ok", "ok"] and ins4[0]["confidence"] == "Cao", str([(x["verify"], x["confidence"]) for x in ins4]))
check("Q3 (luồng): mọi phát hiện đã kiểm -> được phép khẳng định ở tiêu đề slide", "mỗi phát hiện đều có số liệu đã đối chiếu" in pptx, pptx[:300])
check("Q3 (luồng): bước 7 nói '2/2 phát hiện đã kiểm được' và không có cảnh báo", any("2/2 phát hiện đã kiểm được số liệu" in x and not x.startswith("⚠") for x in chk), str(chk))
check("Q5 (luồng): báo cáo HTML có nhãn 'Đã kiểm số liệu' và chân trang '2/2 phát hiện đã được đối chiếu'", "Đã kiểm số liệu" in html and "2/2 phát hiện đã được đối chiếu" in html)
check("Q5 (luồng): Markdown ghi '2/2 phát hiện đã được đối chiếu'", "2/2 phát hiện đã được đối chiếu" in md and "⚠" not in md.split("## Phát hiện chính")[1].split("## Khuyến nghị")[0])
check("Q3 (luồng): báo cáo HTML không còn câu 'Mọi con số được tính từ dữ liệu đã làm sạch, bằng chứng truy ngược'", "Mọi con số được tính" not in html)
data = json.loads(dash.split('<script id="data" type="application/json">')[1].split("</script>")[0])
check("Q5 (luồng): dữ liệu bảng điều khiển mang trạng thái kiểm tra của từng phát hiện", [x.get("verify") for x in data["insights"]] == ["ok", "ok"])

# Q6: prompt của Agent Phát hiện và Agent Thiết kế có thẻ dữ liệu
pi = [u for r, u in F.PROMPTS if "Agent Phát hiện" in r][-1]
pr = [u for r, u in F.PROMPTS if "Agent Thiết kế" in r][-1]
check("Q6 (luồng): prompt Agent Phát hiện có thẻ dữ liệu (tên bảng, cột thật)", "THẺ DỮ LIỆU" in pi and "sales_q3.csv" in pi and "doanh_thu" in pi, pi[:100])
check("Q6 (luồng): prompt Agent Thiết kế cũng có thẻ dữ liệu", "THẺ DỮ LIỆU" in pr)

# Q7: bối cảnh
st = c.get("/api/state").get_json()
check("Q7: ctx nối đủ bối cảnh, quyết định, đòn bẩy; brief giữ riêng từng phần",
      st["ctx"] == "Cửa hàng nhỏ | Quyết định cần đưa ra từ kết quả này: có tăng ngân sách quảng cáo không? | Những thứ người dùng có thể thay đổi: giá bán, ngân sách quảng cáo"
      and st["brief"] == {"ctx": "Cửa hàng nhỏ", "decision": "có tăng ngân sách quảng cáo không?", "levers": "giá bán, ngân sách quảng cáo"}, str((st["ctx"], st["brief"])))
check("Q7: AI đọc được quyết định và đòn bẩy trong prompt", "có tăng ngân sách quảng cáo không?" in pi and "Những thứ người dùng có thể thay đổi: giá bán" in pi)
check("Q7: báo cáo xuất ra hiện bối cảnh đầy đủ", "Quyết định cần đưa ra từ kết quả này" in md)

# --- một phát hiện có phép tính sai (ca trong ảnh) -> gắn cờ, không khẳng định cứng ở đâu cả
BAD = {"summary": "Tóm tắt.", "insights": [
    {"title": "Bảy nhà máy cộng lại 2.152,25 nghìn tấn", "confidence": "Cao", "evidence": "669,19 + 543,6 + 410,5 + 389,12 + 301,77 + 420,1 + 330 = 2.152,25", "source": "Phân tích 1"},
    {"title": "Hai nhóm cộng 300", "confidence": "Cao", "evidence": "100 + 200 = 300", "source": "Phân tích 1"}], "actions": [], "risks": []}
s, chk, pptx, md, html, dash = run_flow(BAD)
ins4 = s["d"]["4"]["insights"]
check("Q1b (luồng): phép tính sai trong ảnh bị gắn cờ, độ tin cậy 'Cao' bị hạ xuống 'Thấp'", ins4[0]["verify"] == "mismatch" and ins4[0]["confidence"] == "Thấp" and "3.064,28" in ins4[0]["calc_mismatch"][0], str(ins4[0]))
check("Q3 (luồng): có phát hiện bị gắn cờ -> tiêu đề slide trung tính, không còn câu khẳng định", "Các phát hiện chính" in pptx and "mỗi phát hiện đều có" not in pptx)
check("Q3 (luồng): slide hiện cảnh báo 'Phép tính không khớp'", "Phép tính không khớp" in pptx)
check("Q3 (luồng): bước 7 đổi câu thành '1/2 phát hiện đã kiểm được' và là dòng cảnh báo (⚠)", any(x.startswith("⚠") and "1/2" in x for x in chk) and not any("2/2" in x for x in chk), str(chk))
check("Q3/Q5 (luồng): Markdown ghi cảnh báo và '1/2 phát hiện đã được đối chiếu'", "⚠ Phép tính không khớp" in md and "1/2 phát hiện đã được đối chiếu" in md)
check("Q5 (luồng): báo cáo HTML có nhãn 'Phép tính không khớp' và dòng 'Lưu ý kiểm tra'", "vf-bad" in html and "Lưu ý kiểm tra" in html and "3.064,28" in html)

# --- ô được trích khớp bảng thật -> đã kiểm (dù số nhỏ); ô trích lệch giá trị -> gắn cờ, đúng giá trị bảng ghi hiện ra trong báo cáo
def _cells(user):
    m = re.search(r"### \[0\] (.+?)\n(.*?)(?=\n### \[|\nPhát hiện sơ bộ|\Z)", user, re.S)
    tdf = pd.read_csv(io.StringIO(m.group(2)))
    g, v = tdf.columns[0], tdf.columns[-1]
    r0 = tdf.iloc[0]
    fmt = lambda x: nf.vn(float(x), 2)                          # noqa: E731
    return {"summary": "Tóm tắt.", "actions": [], "risks": [], "insights": [
        {"title": f"{r0[g]} là nhóm đầu bảng", "confidence": "Cao", "evidence": f"[{m.group(1).strip()}, {r0[g]}, {v}] = {fmt(r0[v])}", "source": "p"},
        {"title": f"{r0[g]} gấp rưỡi mức thật", "confidence": "Cao", "evidence": f"[{m.group(1).strip()}, {r0[g]}, {v}] = {fmt(float(r0[v]) * 1.5)}", "source": "p"}]}, float(r0[v])


REAL = {}
BOX_FN = lambda u: (lambda p, real: (REAL.update(v=real), p)[1])(*_cells(u))            # noqa: E731
s, chk, pptx, md, html, dash = run_flow(BOX_FN)
ins4 = s["d"]["4"]["insights"]
check("Q1b ô trích (luồng): ô khớp bảng thật -> verify=ok kể cả khi số nhỏ hơn 1 triệu", ins4[0]["verify"] == "ok" and ins4[0]["confidence"] == "Cao", str(ins4[0]))
check("Q1b ô trích (luồng): ô lệch giá trị -> mismatch, hạ 'Thấp', ghi chú nêu đúng giá trị bảng", ins4[1]["verify"] == "mismatch" and ins4[1]["confidence"] == "Thấp"
      and nf.vn(REAL["v"], 2) in ins4[1]["cell_mismatch"][0], str(ins4[1]))
check("Q5 (luồng): báo cáo HTML nêu 'Số trích không khớp bảng kết quả'; tiêu đề slide trung tính", "Số trích không khớp bảng kết quả" in html and "mỗi phát hiện đều có" not in pptx)

# --- 0 phát hiện, 0 hành động: luồng và mọi tệp xuất vẫn chạy
ZERO = {"summary": "Dữ liệu chưa đủ để kết luận.", "insights": [], "actions": [], "risks": ["Giả thuyết cần kiểm chứng: có thể do mùa vụ. Dữ liệu cần thu thêm: lịch khuyến mãi."]}
s, chk, pptx, md, html, dash = run_flow(ZERO)
check("Q2 (luồng): AI trả 0 phát hiện, 0 hành động -> luồng 7 bước và mọi tệp xuất vẫn chạy", s["approved"] and "bao_cao.pptx" in s["outputs"] and len(pptx) > 100, str(s.get("outputs")))
check("Q2 (luồng): báo cáo nói rõ chưa có phát hiện đủ chắc, bước 7 cũng vậy", "Chưa có phát hiện nào đủ chắc" in md and any("Chưa có phát hiện nào đủ chắc" in x for x in chk), str(chk))
check("Q2 (luồng): không còn bảng khuyến nghị rỗng trong Markdown; giả thuyết (risks) vẫn được giữ", "## Khuyến nghị hành động" not in md and "Giả thuyết cần kiểm chứng" in md)

# ============================================================ Q4 + Q5 trong trình duyệt thật (bỏ qua nếu thiếu Playwright/Chromium)
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        small = pd.DataFrame({"Ngày": pd.date_range("2026-01-01", periods=60).astype(str), "Khu vực": rng.choice(["Bắc", "Nam"], 60), "Age": rng.integers(20, 60, 60)})
        meta = {"title": "T", "question": "q", "ctx": "", "date": "01/01/2026", "summary": "s", "actions": [], "risks": [],
                "insights": nf.audit_insights([{"title": "x", "confidence": "Cao", "evidence": "1 + 2 = 4"}, {"title": "y", "confidence": "Cao", "evidence": "1 + 2 = 3"}, {"title": "z", "confidence": "Cao", "evidence": "xu hướng"}], nf.Known())}
        pg.set_content(interactive.build_dashboard(meta, {"x.csv": small}))
        pg.wait_for_selector(".kpi.hero")
        hero = lambda: pg.inner_text(".kpi.hero span").lower()       # noqa: E731
        check("Q4 (trình duyệt): thẻ chính của cột 'Age' mặc định là TRUNG BÌNH, không phải 'Tổng age'", "trung bình" in hero() and "tổng" not in hero(), hero())
        pg.click(".kpi.hero [data-ag=sum]")
        check("Q4 (trình duyệt): bấm 'Tổng' trên thẻ thì đổi sang tổng, kèm lưu ý chỉ số này thường không cộng được", "tổng" in hero() and "không cộng được" in pg.inner_text(".kpi.hero"), hero())
        pg.click(".kpi.hero [data-ag=avg]")
        check("Q4 (trình duyệt): bấm 'Trung bình' thì quay lại, lưu ý biến mất", "trung bình" in hero() and "không cộng được" not in pg.inner_text(".kpi.hero"))
        tags = pg.locator("#nar .in .tag").all_inner_texts()
        check("Q5 (trình duyệt): bảng điều khiển hiện nhãn kiểm tra: không khớp / đã kiểm / chưa kiểm được",
              any("Phép tính không khớp" in t for t in tags) and any("Đã kiểm số liệu" in t for t in tags) and any("Chưa kiểm được" in t for t in tags), str(tags))
        check("Q5 (trình duyệt): có dòng cảnh báo cụ thể cho phép tính sai (1 + 2 = 4)", "1 + 2 = 4" in pg.inner_text("#nar"))
        check("trình duyệt: không có lỗi JavaScript", not errs, str(errs))
        b.close()
except Exception as e:                                          # noqa: BLE001
    print("BỎ QUA  phần trình duyệt:", str(e)[:120])

print(f"\n{'TẤT CẢ ĐẠT' if not fails else str(fails) + ' KIỂM TRA THẤT BẠI'}")
sys.exit(1 if fails else 0)
