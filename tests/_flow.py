# -*- coding: utf-8 -*-
"""Bộ dựng kiểm thử dùng chung: chạy TOÀN BỘ luồng 7 bước qua Flask test client với một LLM giả (không cần API key, không cần mạng).

LLM giả đọc 'Góp ý của người dùng' trong prompt rồi phản ánh lại vào kết quả, nhờ đó kiểm tra được:
bấm \"Điều chỉnh\" xong thì dữ liệu hiển thị có thật sự đổi theo góp ý hay không."""
import json
import os
import re
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tmp = tempfile.mkdtemp()
os.environ.update(DATABASE_URL=f"sqlite:///{_tmp}/flow.db", ADMIN_EMAIL="admin@example.com", ADMIN_PASSWORD="admin-pass-123",
                  MASTER_KEY="khoa-chu-kiem-thu-flow", SECRET_KEY="khoa-cookie-kiem-thu-flow", SANDBOX_PARALLEL="2")
sys.path.insert(0, ROOT)

from app import create_app, db, llm  # noqa: E402
import app.routes as routes  # noqa: E402

PROMPTS = []        # (vai trò, nội dung prompt) của mọi lần gọi LLM giả
CALLS = []          # (vai trò, góp ý) của mọi lần gọi LLM giả: để test kiểm tra được LLM có nhận đúng góp ý không


IGNORE = {"on": False}   # True: LLM giả PHỚT LỜ góp ý ở lần chạy đầu (chỉ nghe khi có chỉ dẫn "HỆ THỐNG: lần chạy trước CHƯA áp dụng")


def _fb(user):
    m = re.search(r"không được trả lại bản cũ\): (.*)", user) or re.search(r"Góp ý của người dùng: (.*)", user)
    t = (m.group(1).strip() if m else "")
    t = "" if t in ("", "không") else t
    if t and IGNORE["on"] and "HỆ THỐNG: lần chạy trước CHƯA" not in user:
        return ""
    return t


def fake_llm(system, user, max_tokens=8000, json_mode=False):
    fb = _fb(user)
    CALLS.append((system[:80], fb))
    PROMPTS.append((system[:80], user))
    if "Agent Thống kê" in system:
        return json.dumps({"findings": [{"tag": "Chất lượng", "text": "Chất lượng 82/100." + (f" Theo góp ý: {fb}" if fb else "")}]})
    if "Agent Làm sạch" in system:
        ops = [{"file": "sales_q3.csv", "op": "drop_duplicates", "reason": "Có dòng trùng", "risk": "", "recommended": True}]
        if fb:
            ops.append({"file": "sales_q3.csv", "op": "fill_missing", "column": "doanh_thu", "method": "median", "reason": f"Theo góp ý: {fb}", "risk": "", "recommended": True})
        return json.dumps({"operations": ops, "value_counts": {"overview": "ok", "columns": []}})
    if "Agent Hoạch định" in system:
        menu = [{"title": "Doanh thu theo khu vực", "goal": "so sánh", "metrics": ["Tổng doanh thu = sum(doanh_thu)"], "why": "x", "recommended": True},
                {"title": "Doanh thu theo sản phẩm", "goal": "so sánh", "metrics": ["Tổng doanh thu"], "why": "x", "recommended": True}]
        if fb:
            menu.append({"title": f"Mục theo góp ý: {fb}", "goal": "g", "metrics": ["m"], "why": "w", "recommended": True})
        return json.dumps({"menu": menu})
    if "Agent Phân tích dữ liệu" in system:
        # như AI thật: MỖI mục người dùng chọn (và yêu cầu bổ sung nếu có) ra một tác vụ; góp ý đổi cột nhóm
        seg = user.split("Các phân tích người dùng đã chọn:\n")[-1].split("\nYêu cầu bổ sung")[0]
        try:
            items = json.loads(seg)
        except ValueError:
            items = [{"title": "Phân tích 1"}]
        extra = user.split("Yêu cầu bổ sung của người dùng: ")[-1].split("\n")[0].strip()
        titles = [str(i.get("title") or f"Phân tích {k + 1}") for k, i in enumerate(items)] + ([f"Yêu cầu riêng: {extra[:40]}"] if extra and extra != "không" else [])
        by = "khu_vuc"
        if fb:
            by = "san_pham" if ("san pham" in fb.lower() or "sản phẩm" in fb.lower()) else "kenh"
        tasks = [{"title": t, "goal": f"nhóm theo {by}", "code": f"result = dfs['sales_q3.csv'].groupby('{by}', as_index=False)['doanh_thu'].sum()\nresult.columns=['Nhóm','Tổng doanh thu']"} for t in titles]
        return json.dumps({"tasks": tasks})
    if "Biên tập viên" in system:
        return json.dumps({"map": {}})
    if "Agent Tổng hợp kết quả" in system:
        return json.dumps({"kpis": [{"label": "Tổng doanh thu", "value": "100", "delta": ""}],
                           "charts": [{"task": 0, "x": "Nhóm", "y": "Tổng doanh thu", "kind": "bars", "title": "Doanh thu", "unit": ""}],
                           "findings": [{"tag": "Mô tả", "text": "Kết quả."}]})
    if "Agent Phát hiện" in system:
        return json.dumps({"summary": "Tóm tắt." + (f" ({fb})" if fb else ""), "insights": [{"title": "Phát hiện 1", "confidence": "Cao", "evidence": "a", "source": "Phân tích 1"}],
                           "actions": [{"text": "Làm A", "priority": "Cao", "impact": "x"}], "risks": ["r"]})
    if "Agent Nhận diện" in system:
        t = user.split("Yêu cầu của người dùng:")[-1].split("\n\n")[0].lower()      # chỉ phần người dùng viết, không lẫn phần hướng dẫn của prompt
        specs = []
        if "doanh thu" in t and "khu vực" in t:
            specs.append({"type": "compare", "file": "sales_q3.csv", "measures": [{"col": "doanh_thu", "agg": "sum"}], "by": ["khu_vuc"]})
        if "xu hướng" in t or "theo tháng" in t:
            specs.append({"type": "trend", "file": "sales_q3.csv", "measures": [{"col": "Doanh thu", "agg": "sum"}], "time": {"col": "ngay", "grain": "month"}})
        if "bịa" in t:
            specs.append({"type": "compare", "file": "sales_q3.csv", "measures": [{"col": "khong_co", "agg": "sum"}], "by": ["khu_vuc"]})
        return json.dumps({"specs": specs, "unclear": "phần về nhân sự" if "nhân sự" in t else ""})
    if "Agent Kiểm tra" in system:
        return json.dumps({"ok": True, "done": "Đã cập nhật theo góp ý.", "missing": ""})
    if "Agent Thiết kế" in system:
        return json.dumps({"title": "Báo cáo" + (f" · {fb}" if fb else ""), "narrative": "n",
                           "charts": [{"task": 0, "x": "Nhóm", "y": "Tổng doanh thu", "kind": "bars", "title": "Doanh thu", "unit": "", "insight": "i", "recommended": True}],
                           "dash": [{"ds": "sales_q3.csv", "by": "Thời gian", "measure": "Doanh thu", "agg": "sum", "kind": "trend", "title": "Xu hướng", "why": "Xem diễn biến theo tháng"},
                                    {"ds": "sales_q3.csv", "by": "Khu vực", "measure": "Doanh thu", "agg": "sum", "kind": "donut", "title": "Cơ cấu", "why": "Khu vực nào chiếm nhiều"},
                                    {"ds": "sales_q3.csv", "by": "Khu vực", "measure": "Đơn giá", "agg": "avg", "kind": "donut", "title": "Đơn giá TB", "why": "so sánh"},
                                    {"ds": "sales_q3.csv", "by": "Cột bịa", "measure": "Doanh thu", "kind": "bars", "title": "Bịa", "why": "x"}]})
    raise AssertionError("LLM giả chưa biết vai trò: " + system[:80])


def setup():
    llm.llm = fake_llm
    routes.ensure_ready = lambda: None
    app = create_app()
    db.create_user("An", "an@gmail.com", "matkhau-123", status="approved")
    c = app.test_client()
    r = c.post("/api/auth/login", json={"email": "an@gmail.com", "password": "matkhau-123"})
    assert r.status_code == 200, r.get_data(as_text=True)
    return app, c


def wait(c, timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = c.get("/api/state").get_json()
        if not s["job"]["running"]:
            return s
        time.sleep(0.15)
    raise TimeoutError("tác vụ nền chạy quá lâu")


def post(c, url, body=None, ok=True):
    r = c.post(url, json=body or {})
    if ok:
        assert r.status_code == 200, (url, r.status_code, r.get_data(as_text=True)[:300])
    return r
