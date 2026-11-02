# -*- coding: utf-8 -*-
"""Kiểm thử các lỗi người dùng đã gặp với dữ liệu chi tiêu cá nhân tiếng Việt (0.1.6):
  1. nhãn cột bị chèn dấu cách thừa giữa chữ có dấu ('Loại' -> 'Lo ại'), kể cả khi tệp có dấu dạng tổ hợp (NFD)
  2. duyệt bước 5 bị chặn 'Hãy chọn ít nhất 1 biểu đồ' dù đã chọn biểu đồ bảng điều khiển (vì bảng kết quả bước 4 rỗng)
  3. code AI viết dùng `df` chưa gán / `pd.read_csv('x.csv')` làm bảng kết quả lỗi 'name df is not defined', 'Code bị chặn vì chứa .read_csv'
Chạy: python tests/regression_test.py"""
import io
import json
import os
import random
import re
import sys
import unicodedata as u

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _flow as F  # noqa: E402
from app import labels as lb  # noqa: E402

fails = 0


def check(name, cond, extra=""):
    global fails
    print(("OK   " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    fails += 0 if cond else 1


# ============================================================ 1) nhãn cột
GAP = re.compile(r"[a-z] [àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ]")
names = ["Ngày", "Loại", "Danh mục", "Chi tiết", "Số tiền (đ)", "Hình thức", "Chi tiêu sinh hoạt", "Tỷ lệ chi tiêu", "Đơn giá", "Khu vực", "Mã đơn hàng"]
check("nhãn: tên cột tiếng Việt đúng chính tả giữ nguyên, không chèn dấu cách", all(lb.label(n) == n for n in names), str([(n, lb.label(n)) for n in names if lb.label(n) != n]))
check("nhãn: dạng tổ hợp (NFD) cho kết quả y hệt, không mất dấu", all(lb.label(u.normalize("NFD", n)) == n for n in names), str([(n, lb.label(u.normalize("NFD", n))) for n in names if lb.label(u.normalize("NFD", n)) != n]))
check("nhãn: camelCase vẫn tách đúng (ASCII và có dấu)", lb.label("DanhMuc") == "Danh mục" and lb.label("TổngDoanhThu") == "Tổng doanh thu" and lb.label("ngàyĐặt") == "Ngày đặt" and lb.label("HTMLText") == "HTML Text")
check("nhãn: không nhãn nào có khoảng trắng thừa trước chữ có dấu", not any(GAP.search(lb.label(n)) for n in names))

# ============================================================ dữ liệu: chi tiêu cá nhân, dấu dạng tổ hợp (như xuất từ macOS / Excel)
random.seed(7)
rows = ["Ngày,Loại,Danh mục,Chi tiết,Số tiền (đ),Hình thức"]
for i in range(90):
    typ = random.choice(["Chi tiêu", "Chi tiêu", "Chi tiêu", "Thu nhập"])
    cat = "Lương" if typ == "Thu nhập" else random.choice(["Sinh hoạt", "Di chuyển", "Chi phí hành chính", "Giải trí"])
    rows.append(f"2026-{(i % 3) + 8:02d}-{(i % 27) + 1:02d},{typ},{cat},Khoản {i},{random.randint(20, 900) * 1000},{random.choice(['Tiền mặt', 'Chuyển khoản'])}")
CSV = u.normalize("NFD", "\n".join(rows)).encode("utf-8")

# LLM giả đóng vai AI viết code SAI như trong ảnh: dùng `df` chưa gán, đọc tệp bằng read_csv
BUGGY = [
    ("Tổng chi tiêu theo loại", "result = df[df['Loại'] == 'Chi tiêu'].groupby('Loại', as_index=False)['Số tiền (đ)'].sum()"),
    ("Chi tiêu theo danh mục", "df = pd.read_csv('chi_tieu.csv')\nresult = df[df['Loại'] == 'Chi tiêu'].groupby('Danh mục', as_index=False)['Số tiền (đ)'].sum()"),
    ("Chi tiêu theo ngày", "# tổng theo ngày\nd = pd.read_csv('chi_tieu.csv', parse_dates=['Ngày'])\nresult = d[d['Loại'] == 'Chi tiêu'].groupby('Ngày', as_index=False)['Số tiền (đ)'].sum()"),
]
REPAIRS = []
FIXER = {"ok": True}


def llm(system, user, max_tokens=8000, json_mode=False):
    if "Agent Làm sạch" in system:
        return json.dumps({"operations": [], "value_counts": {"overview": "ok", "columns": []}})
    if "Agent Hoạch định" in system:
        return json.dumps({"menu": [{"title": t, "goal": "g", "metrics": ["m"], "why": "w", "recommended": True} for t, _ in BUGGY]})
    if "Agent Phân tích dữ liệu" in system:
        return json.dumps({"tasks": [{"title": t, "goal": "g", "code": c} for t, c in BUGGY]})
    if "lập trình viên pandas" in system:
        REPAIRS.append(user)
        return "result = df.head(1)" if FIXER["ok"] else "result = dfs['chi_tieu.csv']['Cột không có'].to_frame()"
    return F.fake_llm(system, user, max_tokens, json_mode)


app, c = F.setup()
import app.agents.planner as planner  # noqa: E402
F.llm.llm = llm                      # setup() đặt LLM giả mặc định: đặt lại bản đóng vai AI viết code sai (planner đã import sẵn tên `llm` nên vá cả hai)
planner.llm = llm
r = c.post("/api/upload", data={"files": (io.BytesIO(CSV), "chi_tieu.csv")}, content_type="multipart/form-data")
check("tải tệp chi tiêu dạng NFD", r.status_code == 200, r.get_data(as_text=True)[:200])
F.post(c, "/api/start", {"question": "Tôi tiêu tiền vào đâu nhiều nhất?"})
s = F.wait(c)
raw_cols = [x["name"] for f in s["files"] for x in [f]]
F.post(c, "/api/accept/1"); s = F.wait(c)
F.post(c, "/api/accept/2"); s = F.wait(c)
d3 = s["d"]["3"]
cols = {x["name"]: x for x in d3["cols"][0]["cols"]}
check("giao diện nhận tên cột NFC, nhãn không bị vỡ", all(u.is_normalized("NFC", k) for k in cols) and cols["Loại"]["label"] == "Loại" and cols["Số tiền (đ)"]["label"] == "Số tiền (đ)", str({k: v["label"] for k, v in cols.items()}))

# ============================================================ 3) code AI sai được tự sửa
F.post(c, "/api/a3/code", {"ids": [m["id"] for m in d3["menu"]], "custom": "", "specs": []}); s = F.wait(c)
codes = [t["code"] for t in s["d"]["3"]["tasks"]]
check("bước 3: code AI viết `df` chưa gán đã được thêm dòng df = dfs[...] ngay ở pha code", codes[0].startswith("df = dfs['chi_tieu.csv']"), codes[0][:80])
check("bước 3: pd.read_csv('chi_tieu.csv') đã được thay bằng dfs[...] (giữ chú thích)", all("read_csv" not in x for x in codes) and codes[2].startswith("# tổng theo ngày"), str(codes[1:]))
F.post(c, "/api/a3/exec", {"codes": []}); s = F.wait(c, 120)
tabs = s["d"]["3"]["result"]["tables"]
check("bước 4: cả 3 phân tích chạy được, không còn lỗi 'df is not defined' / '.read_csv'", all(not t.get("err") and t["rows"] for t in tabs), str([(t["title"], t.get("err")) for t in tabs]))
check("bước 4: lọc 'Chi tiêu' khớp dữ liệu NFD (không ra 0 dòng)", tabs[0]["rows"] and all(r[0] == "Chi tiêu" for r in tabs[0]["rows"]), str(tabs[0]["rows"][:2]))
check("bước 4: AI không phải sửa lại gì", not REPAIRS, str(len(REPAIRS)))

# người dùng tự sửa code sai thành read_csv: vẫn chạy được
bad_codes = list(codes)
bad_codes[1] = "d = pd.read_csv('chi_tieu.csv')\nresult = d.groupby('Hình thức', as_index=False)['Số tiền (đ)'].sum()"
F.post(c, "/api/a3/reselect"); F.post(c, "/api/a3/code", {"ids": [m["id"] for m in d3["menu"]], "custom": "", "specs": []}); F.wait(c)
F.post(c, "/api/a3/exec", {"codes": bad_codes}); s = F.wait(c, 120)
tabs = s["d"]["3"]["result"]["tables"]
check("bước 4: người dùng sửa tay thành read_csv vẫn chạy được", all(not t.get("err") for t in tabs) and tabs[1]["rows"], str([(t["title"], t.get("err")) for t in tabs]))

# AI sửa lỗi: nhận prompt có môi trường code (dfs, tên bảng, cấm read_csv)
bad_codes[2] = "result = dfs['chi_tieu.csv']['Cột không có'].to_frame()"
F.post(c, "/api/a3/exec", {"codes": bad_codes}); s = F.wait(c, 120)
check("sửa lỗi bằng AI: prompt nêu rõ dfs, tên bảng và cấm đọc tệp", REPAIRS and "dfs" in REPAIRS[0] and "chi_tieu.csv" in REPAIRS[0] and "KHÔNG gọi pd.read_csv" in REPAIRS[0], REPAIRS[0][:200] if REPAIRS else "chưa gọi")
check("sửa lỗi bằng AI: sửa được ngay lần đầu thì dừng (1 lần gọi AI, bảng có dữ liệu)", len(REPAIRS) == 1 and not s["d"]["3"]["result"]["tables"][2].get("err") and s["d"]["3"]["result"]["tables"][2]["rows"], str(len(REPAIRS)))
REPAIRS.clear(); FIXER["ok"] = False
F.post(c, "/api/a3/exec", {"codes": bad_codes}); s = F.wait(c, 120)
e = s["d"]["3"]["result"]["tables"][2]["err"]
check("sửa lỗi bằng AI: sửa hỏng mãi thì thử đúng 2 lần rồi báo lỗi kèm hướng dẫn", len(REPAIRS) == 2 and "KeyError" in e and "kiểm tra đúng tên" in e, f"{len(REPAIRS)} {e}")
FIXER["ok"] = True

# ============================================================ 2) bước 5: biểu đồ báo cáo rỗng nhưng đã chọn biểu đồ bảng điều khiển
F.post(c, "/api/a3/exec", {"codes": codes}); s = F.wait(c, 120)
F.post(c, "/api/accept/3"); s = F.wait(c)
F.post(c, "/api/accept/4"); s = F.wait(c)
d5 = s["d"]["5"]
check("bước 5: có gợi ý biểu đồ bảng điều khiển", d5["dash"]["ai"], str(d5["dash"]))
plan = d5["dash"]["ai"]
r = F.post(c, "/api/accept/5", {"title": "T", "charts": [], "kpis": [], "dash": [dict(p, on=False) for p in plan]}, ok=False)
check("duyệt bước 5: tắt hết mọi biểu đồ thì báo rõ ràng, không im lặng", r.status_code == 400 and "bật ít nhất 1" in r.get_json()["error"], r.get_data(as_text=True)[:200])
r = F.post(c, "/api/accept/5", {"title": "T", "charts": [], "kpis": [], "dash": []}, ok=False)
check("duyệt bước 5: không có biểu đồ nào ở cả hai nơi thì chỉ cách khắc phục", r.status_code == 400 and "bước 4" in r.get_json()["error"], r.get_data(as_text=True)[:200])
r = F.post(c, "/api/accept/5", {"title": "Báo cáo chi tiêu", "charts": [], "kpis": [], "dash": plan}, ok=False)
check("duyệt bước 5: đã chọn biểu đồ bảng điều khiển thì được duyệt dù báo cáo chưa có biểu đồ", r.status_code == 200, r.get_data(as_text=True)[:200])
s = F.wait(c)
F.post(c, "/api/accept/6"); s = F.wait(c)
check("xuất file thành công khi báo cáo không có biểu đồ", s["approved"] and "dashboard.html" in s["outputs"] and "bao_cao.pptx" in s["outputs"], str(s.get("outputs")))
html = c.get(f"/api/view/{s['id']}/dashboard.html").get_data(as_text=True)
data = json.loads(html.split('<script id="data" type="application/json">')[1].split("</script>")[0])
labs = json.dumps(data, ensure_ascii=False)
check("dashboard xuất ra có nhãn cột đúng, không bị chèn dấu cách", "Số tiền (đ)" in labs or "Số tiền" in labs, labs[:300])
check("dashboard xuất ra: không có chữ bị tách kiểu 'Lo ại', 'Danh m ục'", not any(x in labs for x in ("Lo ại", "Danh m ục", "ti ền", "Ng ày", "Hình th ức")))

print(f"\n{'TẤT CẢ ĐẠT' if not fails else str(fails) + ' KIỂM TRA THẤT BẠI'}")
sys.exit(1 if fails else 0)
