# -*- coding: utf-8 -*-
"""Kiểm thử TRỌN LUỒNG 7 bước qua API với LLM giả (không cần key, không cần mạng), tập trung vào 5 cải tiến:
  1. ghép biến (spec / parse)         2. bước Phân tích: biến dùng, điểm nổi bật       3. phân bố từng biến ở bước 1
  4. chọn biểu đồ cho bảng điều khiển 5. ĐIỀU CHỈNH: cập nhật thật, tự chạy lại nếu AI phớt lờ, giữ code sửa tay
Chạy: python tests/flow_test.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _flow as F  # noqa: E402

fails = 0


def check(name, cond, extra=""):
    global fails
    print(("OK   " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    fails += 0 if cond else 1


app, c = F.setup()
state = lambda: c.get("/api/state").get_json()          # noqa: E731
run = lambda i, fb, **kw: (F.post(c, f"/api/run/{i}", {"feedback": fb, **kw}), F.wait(c))[1]   # noqa: E731
n_calls = lambda role: sum(1 for r, _ in F.PROMPTS if role in r)            # noqa: E731

F.post(c, "/api/sample")
F.post(c, "/api/start", {"question": "Khu vực nào bán tốt nhất?"})
s = F.wait(c)

# ============================================================ bước 1: phân bố từng biến
d1 = s["d"]["1"]
dist = {f["file"]: {x["col"]: x for x in f["cols"]} for f in d1["dist"]}
check("bước 1: có phân bố cho mọi bảng", set(dist) == {f["name"] for f in s["files"]}, str(list(dist)))
S1 = dist["sales_q3.csv"]
check("bước 1: biến định lượng có histogram, phân loại có giá trị duy nhất, ngày theo tháng",
      S1["doanh_thu"]["kind"] == "num" and S1["doanh_thu"]["hist"]["counts"] and S1["khu_vuc"]["kind"] == "cat" and S1["khu_vuc"]["top"] and S1["ngay"]["kind"] == "date" and S1["ngay"]["labels"])
check("bước 1: AI nhận bản tóm tắt phân bố để nhận định", any("Phân bố từng biến" in u for r, u in F.PROMPTS if "Thống kê" in r))
check("bước 1: dung lượng phân bố hợp lý (<150 KB)", len(json.dumps(d1["dist"])) < 150_000, str(len(json.dumps(d1["dist"]))))

# ---- điều chỉnh bước 1
s = run(1, "nhấn mạnh chất lượng cột doanh thu")
a = s["d"]["1"]["adj"]
check("điều chỉnh bước 1: có kết quả cập nhật gắn đúng phiên bản", a["gen"] == s["d"]["1"]["gen"] and a["fb"].startswith("nhấn mạnh") and (a["added"] or a["changed"]), str(a))
check("điều chỉnh bước 1: dữ liệu phân bố vẫn còn sau khi chạy lại", s["d"]["1"]["dist"] and s["d"]["1"]["kpis"])
check("điều chỉnh: AI được ra lệnh PHẢI thực hiện góp ý", any("PHẢI thực hiện" in u and "nhấn mạnh chất lượng" in u for r, u in F.PROMPTS if "Thống kê" in r))

# ============================================================ bước 2
F.post(c, "/api/accept/1"); s = F.wait(c)
s = run(2, "điền thiếu doanh thu bằng trung vị")
d2 = s["d"]["2"]
check("điều chỉnh bước 2: thao tác mới theo góp ý được đánh dấu là MỚI", any("thiếu" in x and "doanh_thu" in x for x in d2["adj"]["added"]) and d2["adj"]["ok"], str(d2["adj"]))
F.post(c, "/api/accept/2"); s = F.wait(c)

# ============================================================ bước 3: menu
d3 = s["d"]["3"]
check("menu: có danh sách biến thật (kèm kiểu) cho bộ ghép biến", d3["phase"] == "menu" and d3["cols"] and {x["kind"] for x in d3["cols"][0]["cols"]} >= {"num", "cat", "date"})
check("menu: mỗi đề xuất có kiểu và biến dùng", all("type" in m and isinstance(m["vars"], list) for m in d3["menu"]) and any(m["vars"] for m in d3["menu"]))

# ---- AI phớt lờ góp ý lần đầu -> hệ thống tự chạy lại
F.IGNORE["on"] = True
before = n_calls("Hoạch định")
s = run(3, "thêm phân tích theo kênh bán")
F.IGNORE["on"] = False
a = s["d"]["3"]["adj"]
check("AI phớt lờ góp ý: hệ thống phát hiện và TỰ chạy lại, kết quả đã áp dụng", a["retried"] and a["ok"] and any("kênh" in x for x in a["added"]), str(a))
check("AI phớt lờ góp ý: đúng 2 lần gọi Agent hoạch định (1 phớt lờ + 1 áp dụng lại)", n_calls("Hoạch định") - before == 2, str(n_calls("Hoạch định") - before))
check("menu sau điều chỉnh có mục mới", any("kênh" in m["title"] for m in s["d"]["3"]["menu"]))

# ---- góp ý lần 2: góp ý trước KHÔNG bị mất
s = run(3, "thêm so sánh theo khu vực")
users = [u for r, u in F.PROMPTS if "Hoạch định" in r][-1]
check("góp ý lần 2: prompt còn nhắc góp ý lần 1", "CÁC GÓP Ý ĐÃ GỬI TRƯỚC ĐÓ" in users and "thêm phân tích theo kênh bán" in users)

# ---- ghép biến: kiểm tra / mô tả bằng lời
r = F.post(c, "/api/a3/spec", {"spec": {"type": "compare", "file": "sales_q3.csv", "measures": [{"col": "doanh_thu", "agg": "sum"}], "by": ["khu_vuc"]}}).get_json()
check("/a3/spec: hợp lệ -> tiêu đề + mô tả + biến dùng", r["ok"] and r["spec"]["title"] == "Tổng doanh thu theo khu vực" and r["spec"]["vars"] == ["doanh_thu", "khu_vuc"])
r = F.post(c, "/api/a3/spec", {"spec": {"type": "cross", "file": "sales_q3.csv", "by": ["khu_vuc"]}}).get_json()
check("/a3/spec: thiếu biến -> lỗi tiếng Việt, không sập", r["ok"] is False and "hai biến" in r["error"], str(r))
r = F.post(c, "/api/a3/parse", {"text": "doanh thu theo khu vực và xu hướng theo tháng, thêm nhân sự, thêm cả cột bịa"}).get_json()
check("/a3/parse: AI nhận diện 2 yêu cầu, loại cột bịa, tách phần chưa rõ", len(r["specs"]) == 2 and len(r["rejected"]) == 1 and "khong_co" in r["rejected"][0] and "nhân sự" in r["unclear"], str(r))
check("/a3/parse: spec trả về đã kiểm tra với dữ liệu thật (cột đúng tên thật)", r["specs"][1]["measures"][0]["col"] == "doanh_thu" and r["specs"][1]["time"]["col"] == "ngay")
check("/a3/parse: câu rỗng bị từ chối", F.post(c, "/api/a3/parse", {"text": "  "}, ok=False).status_code == 400)
specs = [x for x in r["specs"]]
specs.append({"type": "correlate", "file": "sales_q3.csv", "x": "don_gia", "y": "doanh_thu"})
specs.append({"type": "compare", "file": "sales_q3.csv", "measures": [{"col": "khong_co"}], "by": ["kenh"]})       # giả mạo từ trình duyệt: phải bị loại
specs.append("rác")

# ---- tạo code: ô ghép biến sinh code TRỰC TIẾP (không nhờ AI), AI chỉ lo mục menu
n_code = n_calls("Phân tích dữ liệu")
F.post(c, "/api/a3/code", {"ids": ["m0"], "custom": "", "specs": specs}); s = F.wait(c)
d3 = s["d"]["3"]
check("tạo code: 3 ô ghép biến hợp lệ + 1 mục AI, ô giả mạo bị loại", [t["src"] for t in d3["tasks"]] == ["spec", "spec", "spec", "ai"], str([t["src"] for t in d3["tasks"]]))
check("tạo code: code của ô ghép biến do hệ thống sinh, đúng biến đã chọn", "groupby" in d3["tasks"][0]["code"] and "'doanh_thu'" in d3["tasks"][0]["code"] and d3["tasks"][0]["vars"] == ["doanh_thu", "khu_vuc"])
prompt = [u for r_, u in F.PROMPTS if "Phân tích dữ liệu" in r_][-1]
check("tạo code: AI KHÔNG phải viết lại các ô ghép biến", n_calls("Phân tích dữ liệu") - n_code == 1 and "Tổng doanh thu theo khu vực" not in prompt)
check("tạo code: mỗi tác vụ có biến dùng", all(t["vars"] for t in d3["tasks"]))
only = F.post(c, "/api/a3/reselect"); s = F.wait(c)
F.post(c, "/api/a3/code", {"ids": [], "custom": "", "specs": specs[:1]}); s = F.wait(c)
check("chỉ ghép biến (không chọn gợi ý AI, không nhập chữ): không gọi AI viết code", [t["src"] for t in s["d"]["3"]["tasks"]] == ["spec"] and n_calls("Phân tích dữ liệu") - n_code == 1)
F.post(c, "/api/a3/reselect"); F.post(c, "/api/a3/code", {"ids": ["m0"], "custom": "", "specs": specs}); s = F.wait(c)
check("chọn rỗng bị từ chối", F.post(c, "/api/a3/code", {"ids": [], "custom": "", "specs": []}, ok=False).status_code in (400, 409))

# ---- điều chỉnh ở pha code: code người dùng sửa tay phải tới được AI
tasks = s["d"]["3"]["tasks"]
edited = [t["code"] for t in tasks]
edited[0] = edited[0] + "\n# SỬA TAY CỦA TÔI"
s = run(3, "đổi sang theo sản phẩm", codes=edited)
old_code_prompt = [u for r_, u in F.PROMPTS if "Phân tích dữ liệu" in r_][-1]
check("điều chỉnh pha code: AI nhận ĐÚNG bản code người dùng đã sửa tay", "SỬA TAY CỦA TÔI" in old_code_prompt)
check("điều chỉnh pha code: ô ghép biến cũng được AI viết lại theo góp ý (không bị khóa)", "Tổng doanh thu theo khu vực" in old_code_prompt and s["d"]["3"]["adj"]["ok"], str(s["d"]["3"].get("adj")))
check("điều chỉnh pha code: giữ lại danh sách ô ghép biến để chọn lại", len(s["d"]["3"]["specs"]) == 3)

# ---- chạy: điểm nổi bật + biến dùng + tương quan
F.post(c, "/api/a3/reselect"); F.post(c, "/api/a3/code", {"ids": ["m0"], "custom": "", "specs": specs}); F.wait(c)
F.post(c, "/api/a3/exec", {"codes": []}); s = F.wait(c, 120)
res = s["d"]["3"]["result"]
check("kết quả: mọi bảng chạy được, có biến dùng và nguồn", len(res["tables"]) == 4 and all(not t.get("err") and t["vars"] and t["src"] for t in res["tables"]), str([(t["title"], t.get("err")) for t in res["tables"]]))
check("kết quả: điểm nổi bật do code tính (cao nhất / thấp nhất / tỷ trọng)", any("Cao nhất" in x for x in res["tables"][0]["facts"]) and any("chiếm" in x for x in res["tables"][0]["facts"]), str(res["tables"][0]["facts"]))
corr = next(t for t in res["tables"] if "Đơn giá" in t["title"])
check("kết quả: bảng tương quan kèm hệ số Pearson", any("Pearson" in x for x in corr["facts"]), str(corr["facts"]))
s = run(3, "đổi sang theo kênh nhé")
check("điều chỉnh pha kết quả: chạy lại và báo thay đổi", s["d"]["3"]["phase"] == "result" and s["d"]["3"]["adj"]["gen"] == s["d"]["3"]["gen"] and s["d"]["3"]["adj"]["changed"], str(s["d"]["3"].get("adj")))
F.post(c, "/api/accept/3"); s = F.wait(c)

# ============================================================ bước 4, 5
s = run(4, "thêm khuyến nghị về kênh")
check("điều chỉnh bước 4: cập nhật", s["d"]["4"]["adj"]["ok"] and any("kênh" in x or "góp ý" in x or "Tóm tắt" in x for x in s["d"]["4"]["adj"]["changed"] + s["d"]["4"]["adj"]["added"]), str(s["d"]["4"]["adj"]))
F.post(c, "/api/accept/4"); s = F.wait(c)
d5 = s["d"]["5"]
cat = d5["dash"]["catalog"]
check("bước 5: có danh mục biểu đồ khả dụng của bảng điều khiển", cat and cat[0]["dims"] and cat[0]["meas"] and cat[0]["time"])
ai = d5["dash"]["ai"]
check("bước 5: AI gợi ý biểu đồ dashboard, cột bịa bị loại, đều là ai", ai and all(x["src"] == "ai" for x in ai) and not any("bịa" in (x.get("title") or "") for x in ai), str(ai[:3]))
check("bước 5: gợi ý ghi theo khóa kỹ thuật đã kiểm tra", ai[0]["by"] == "t" and ai[0]["kind"] == "trend" and ai[1]["kind"] == "donut")
s = run(5, "đổi tiêu đề nhấn mạnh khu vực dẫn đầu")
check("điều chỉnh bước 5: tiêu đề đổi và được báo", "Tiêu đề báo cáo" in s["d"]["5"]["adj"]["changed"] and s["d"]["5"]["title"].startswith("Báo cáo"), str(s["d"]["5"]["adj"]))
check("điều chỉnh bước 5: gợi ý biểu đồ dashboard vẫn còn", s["d"]["5"]["dash"]["ai"])

import base64  # noqa: E402
ai = s["d"]["5"]["dash"]["ai"]
plan = [dict(p, on=(i != 0)) for i, p in enumerate(ai)]
b = base64.urlsafe_b64encode(json.dumps(plan).encode()).decode().rstrip("=")
h = c.get("/api/dash_preview?plan=" + b).get_data(as_text=True)
pl = json.loads(h.split('<script id="data" type="application/json">')[1].split("</script>")[0])["plan"]
check("xem trước dashboard: dùng đúng kế hoạch người dùng chọn (kể cả mục tắt)", len(pl) == len(ai) and pl[0]["on"] is False and pl[1]["on"] is True)
h0 = c.get("/api/dash_preview").get_data(as_text=True)
check("xem trước dashboard: chưa chọn gì thì dùng gợi ý của AI", json.loads(h0.split('<script id="data" type="application/json">')[1].split("</script>")[0])["plan"][0]["by"] == "t")
check("xem trước dashboard: plan hỏng không làm sập", c.get("/api/dash_preview?plan=@@@").status_code == 200)
check("xem trước dashboard: plan rỗng là hợp lệ (không chọn biểu đồ nào)", json.loads(c.get("/api/dash_preview?plan=" + base64.urlsafe_b64encode(b"[]").decode().rstrip("=")).get_data(as_text=True).split('<script id="data" type="application/json">')[1].split("</script>")[0])["plan"] == [])

mine = {"ds": "sales_q3.csv", "by": cat[0]["dims"][2]["k"], "m": "", "agg": "count", "kind": "cols", "src": "user", "on": True}
F.post(c, "/api/accept/5", {"title": "Báo cáo của tôi", "charts": s["d"]["5"]["charts"], "kpis": [0], "dash": plan[:2] + [mine, {"ds": "x", "by": "zz"}, {"ds": "sales_q3.csv", "by": "d0", "m": "m99"}]}); s = F.wait(c)
fin = s["d"]["5"]["final"]["dash"]
check("duyệt bước 5: lưu kế hoạch đã làm sạch (bỏ mục sai, giữ mục của bạn và trạng thái bật/tắt)", len(fin) == 3 and fin[0]["on"] is False and fin[2]["src"] == "user" and fin[2]["kind"] == "cols", str(fin))

# ============================================================ bước 6
check("bước 6 không nhận góp ý (chỉ kiểm tra)", F.post(c, "/api/run/6", {"feedback": "sửa gì đó"}, ok=False).status_code == 400)
F.post(c, "/api/accept/6"); s = F.wait(c)
check("duyệt xong", s["approved"] and "dashboard.html" in s["outputs"])
dash_html = c.get(f"/api/view/{s['id']}/dashboard.html").get_data(as_text=True)
pub = json.loads(dash_html.split('<script id="data" type="application/json">')[1].split("</script>")[0])["plan"]
check("dashboard xuất ra chứa đúng kế hoạch biểu đồ đã chọn", len(pub) == 3 and pub[0]["on"] is False and pub[2]["src"] == "user")
snap = c.get(f"/api/history/{s['id']}").get_json()
check("lịch sử (chỉ đọc) lưu cả phân bố, danh mục biểu đồ, thông tin điều chỉnh", snap["d"]["1"]["dist"] and snap["d"]["5"]["dash"]["catalog"] and snap["d"]["3"]["adj"])

print(f"\n{'TẤT CẢ ĐẠT' if not fails else str(fails) + ' KIỂM TRA THẤT BẠI'}")
sys.exit(1 if fails else 0)
