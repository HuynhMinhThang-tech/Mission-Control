# -*- coding: utf-8 -*-
"""Kiểm thử nhanh luồng tài khoản + cách ly dữ liệu. Chạy: python tests/smoke_test.py"""
import os
import sys
import tempfile
import threading
import time

tmp = tempfile.mkdtemp()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PG = os.getenv("TEST_DATABASE_URL", "")          # đặt biến này để chạy trên PostgreSQL thật (đã áp dụng sql/schema.sql trước khi khởi động app)
os.environ.update(DATABASE_URL=PG or f"sqlite:///{tmp}/t.db", ADMIN_EMAIL="Admin@Example.com", ADMIN_PASSWORD="admin-pass-123", ADMIN_NAME="Quản trị",
                  MASTER_KEY="khoa-chu-cho-kiem-thu", SECRET_KEY="khoa-cookie-cho-kiem-thu")
sys.path.insert(0, ROOT)
if PG:
    import psycopg2
    with psycopg2.connect(PG) as _c, _c.cursor() as _cur:
        _cur.execute(open(os.path.join(ROOT, "sql", "schema.sql"), encoding="utf-8").read())

from app import auth, create_app, crypto, db, llm, state  # noqa: E402
from app.errors import UserError  # noqa: E402

app = create_app()
ok_count = 0


def check(cond, label):
    global ok_count
    if not cond:
        print("FAIL:", label)
        sys.exit(1)
    ok_count += 1
    print("ok  ", label)


def client():
    return app.test_client()


def reg(c, name, email, pw="matkhau-123", confirm=None):
    return c.post("/api/auth/register", json={"name": name, "email": email, "password": pw, "confirm": pw if confirm is None else confirm})


def login(c, email, pw="matkhau-123"):
    return c.post("/api/auth/login", json={"email": email, "password": pw})


anon = client()
r = anon.get("/")
check(r.status_code == 302 and "/login" in r.headers["Location"], "chưa đăng nhập: trang chủ chuyển sang /login")
check(anon.get("/api/state").status_code == 401, "chưa đăng nhập: /api/state trả 401")
check(anon.get("/login").status_code == 200, "trang /login mở được")
check(anon.get("/static/css/auth.css").status_code == 200, "tệp tĩnh mở được khi chưa đăng nhập")

# --- đăng ký: kiểm tra đầu vào ---
c = client()
check(reg(c, "An", "an@gmail.com", confirm="khac-mat-khau").status_code == 400, "đăng ký: xác nhận mật khẩu không khớp bị từ chối")
check(reg(c, "An", "khong-phai-email").status_code == 400, "đăng ký: email sai định dạng bị từ chối")
check(reg(c, "An", "an@gmail.com", pw="123").status_code == 400, "đăng ký: mật khẩu ngắn bị từ chối")
check(reg(c, "A", "an@gmail.com").status_code == 400, "đăng ký: tên quá ngắn bị từ chối")
check(reg(c, "An", "An@Gmail.com").status_code == 200, "đăng ký hợp lệ")
check(reg(c, "An 2", "an@gmail.com").status_code == 409, "đăng ký trùng email (không phân biệt hoa/thường) bị chặn")

# --- chưa duyệt thì không vào được ---
check(login(c, "an@gmail.com").status_code == 403, "tài khoản chờ duyệt: đúng mật khẩu vẫn bị chặn (403)")
check("duyệt" in login(c, "an@gmail.com").get_json()["error"], "thông báo nói rõ đang chờ duyệt")
check(login(c, "an@gmail.com", "sai-mat-khau").status_code == 401, "sai mật khẩu: 401 chung chung")
check("duyệt" not in login(c, "an@gmail.com", "sai-mat-khau").get_json()["error"], "sai mật khẩu: không tiết lộ trạng thái tài khoản")
check(c.get("/api/state").status_code == 401, "chờ duyệt: vẫn không vào được API")

# --- mật khẩu không lưu dạng rõ ---
with db.scope() as s:
    u = s.query(db.User).filter_by(email="an@gmail.com").one()
    check(u.password_hash != "matkhau-123" and "matkhau-123" not in u.password_hash and u.password_hash.count("$") >= 2, "mật khẩu được băm, không lưu dạng rõ")

# --- admin ---
adm = client()
check(login(adm, "admin@example.com", "admin-pass-123").status_code == 200, "admin đăng nhập (email không phân biệt hoa/thường)")
users = adm.get("/api/admin/users").get_json()["users"]
check(len(users) == 1 and users[0]["email"] == "an@gmail.com" and users[0]["status"] == "pending", "admin thấy yêu cầu chờ duyệt")
check(set(users[0]) == {"id", "display_name", "email", "status", "created_at", "reset_pending", "reset_requested_at"}, "admin chỉ thấy tên/email/trạng thái/ngày (không có mật khẩu, bản băm hay vai trò)")
check("password" not in adm.get("/api/admin/users").get_data(as_text=True).lower(), "phản hồi admin không chứa từ 'password'")
check(adm.get("/api/auth/me").get_json()["pending"] == 1, "admin thấy số yêu cầu đang chờ")

uid_an = users[0]["id"]
check(adm.post(f"/api/admin/users/{uid_an}/approve").status_code == 200, "admin duyệt An")
check(login(c, "an@gmail.com").status_code == 200, "An đăng nhập được sau khi duyệt")
check(c.get("/api/auth/me").get_json()["role"] == "user", "An là user thường")
check(c.get("/api/admin/users").status_code == 403, "user thường không gọi được API admin")
check(c.get("/admin").status_code == 302, "user thường mở /admin bị chuyển về /")
check(adm.post(f"/api/admin/users/1/disable").status_code in (404, 409), "admin không khóa/xóa được admin (tránh tự khóa)")

# --- người dùng thứ hai + cách ly dữ liệu ---
reg(client(), "Bình", "binh@gmail.com")
bid = [u for u in adm.get("/api/admin/users").get_json()["users"] if u["email"] == "binh@gmail.com"][0]["id"]
adm.post(f"/api/admin/users/{bid}/approve")
cb = client()
check(login(cb, "binh@gmail.com").status_code == 200, "Bình đăng nhập")
check(c.post("/api/sample").status_code == 200, "An nạp dữ liệu mẫu")
sa, sb = c.get("/api/state").get_json(), cb.get("/api/state").get_json()
check(len(sa["files"]) > 0 and sb["files"] == [], "Bình KHÔNG thấy dữ liệu của An (cách ly phiên)")
check(sa["id"] != sb["id"], "mỗi người một mã phân tích riêng")
cb.post("/api/new")
check(len(c.get("/api/state").get_json()["files"]) > 0, "Bình bấm 'Phân tích mới' không xóa phiên của An")
check(cb.post("/api/upload").status_code == 400 and len(c.get("/api/state").get_json()["files"]) > 0, "upload lỗi của Bình không ảnh hưởng An")

# --- tác vụ nền chạy đúng phiên của người bấm ---
seen = {}


def job():
    time.sleep(0.2)
    seen["who"] = state.current_user_id()
    state.A["log"].append("job-xong")


with app.test_request_context():
    state.bind(uid_an)
    state.start_job(1, ["x"], job)
    state.unbind()
time.sleep(0.6)
check(seen.get("who") == uid_an, "luồng nền làm việc trên đúng phiên người khởi chạy")
check("job-xong" in state.session_for(uid_an)["log"] and "job-xong" not in state.session_for(bid)["log"], "log của job chỉ vào phiên của An")

# --- lịch sử & tệp: chủ sở hữu ---
snap = {"id": "abc123", "question": "Doanh thu?", "d": {}}
files = {"dashboard.html": (b"<html>an</html>", "text/html; charset=utf-8"), "share.zip": (b"PK-zip", "application/zip")}
db.save_analysis(uid_an, {"id": "abc123", "question": "Doanh thu?", "title": "Doanh thu?", "files": ["dashboard.html", "share.zip"], "sources": ["a.xlsx"], "started": "t", "finished": "t2", "report_title": "BC"}, snap, files)
h = c.get("/api/state").get_json()["hist"]
check(len(h) == 1 and h[0]["id"] == "abc123" and h[0]["snap"] is True, "An thấy luồng đã lưu trong Lịch sử")
check(cb.get("/api/state").get_json()["hist"] == [], "Bình không thấy lịch sử của An")
check(c.get("/api/history/abc123").get_json()["question"] == "Doanh thu?", "An xem lại được bản lưu")
check(cb.get("/api/history/abc123").status_code == 404, "Bình KHÔNG xem được bản lưu của An (đoán ID)")
r = c.get("/api/download/abc123/share.zip")
check(r.status_code == 200 and r.data == b"PK-zip" and "attachment" in r.headers["Content-Disposition"], "An tải được ZIP")
check(cb.get("/api/download/abc123/share.zip").status_code == 404, "Bình KHÔNG tải được tệp của An")
check(c.get("/api/view/abc123/dashboard.html").data == b"<html>an</html>", "An xem được dashboard")
check(cb.get("/api/view/abc123/dashboard.html").status_code == 404, "Bình KHÔNG xem được dashboard của An")
check(adm.get("/api/download/abc123/share.zip").status_code == 404, "ngay cả admin cũng không tải được dữ liệu phân tích của user")
check(cb.post("/api/history/abc123/delete").status_code == 404, "Bình KHÔNG xóa được luồng của An")
check(len(c.get("/api/state").get_json()["hist"]) == 1, "luồng của An vẫn còn sau nỗ lực xóa của Bình")
check(c.post("/api/history/abc123/delete").status_code == 200 and c.get("/api/state").get_json()["hist"] == [], "An xóa được luồng của mình")
check(c.get("/api/download/abc123/share.zip").status_code == 404, "xóa luồng là xóa luôn tệp")

# --- khóa tài khoản có hiệu lực ---
check(adm.post(f"/api/admin/users/{uid_an}/disable").status_code == 200, "admin khóa An")
check(c.get("/api/state").status_code == 401, "An đang đăng nhập bị chặn NGAY LẬP TỨC sau khi bị khóa (không còn độ trễ)")
check(login(c, "an@gmail.com").status_code == 403, "An bị khóa không đăng nhập lại được")
check(adm.post(f"/api/admin/users/{uid_an}/enable").status_code == 200 and login(c, "an@gmail.com").status_code == 200, "mở khóa: An vào lại được")
db.save_analysis(uid_an, {"id": "zzz999", "question": "q"}, None, {"x.txt": (b"1", "text/plain")})
check(adm.post(f"/api/admin/users/{uid_an}/delete").status_code == 200, "admin xóa tài khoản An")
with db.scope() as s:
    check(s.query(db.Analysis).count() == 0 and s.query(db.AnalysisFile).count() == 0, "xóa tài khoản kéo theo xóa toàn bộ dữ liệu của người đó")


# =================== ĐẶT LẠI MẬT KHẨU (chờ admin duyệt) ===================
def rr(email, pw="mk-moi-12345", confirm=None, c=None):
    return (c or client()).post("/api/auth/reset-request", json={"email": email, "password": pw, "confirm": pw if confirm is None else confirm})


reg(client(), "Chi", "chi@gmail.com")
cid = db.find_by_email("chi@gmail.com").id
adm.post(f"/api/admin/users/{cid}/approve")
cc = client()
check(login(cc, "chi@gmail.com").status_code == 200 and cc.get("/api/state").status_code == 200, "Chi đăng nhập bằng mật khẩu cũ")
check(rr("chi@gmail.com", confirm="khac-hoan-toan").status_code == 400, "đặt lại: xác nhận không khớp bị từ chối")
check(rr("khong-hop-le").status_code == 400, "đặt lại: email sai định dạng bị từ chối")
check(rr("chi@gmail.com", pw="123").status_code == 400, "đặt lại: mật khẩu mới quá ngắn bị từ chối")
a1, a2 = rr("chi@gmail.com"), rr("khong-ton-tai@gmail.com")
check(a1.status_code == 200 and a1.get_json() == a2.get_json(), "đặt lại: trả lời GIỐNG HỆT cho email có/không có tài khoản (không lộ email)")
check(login(client(), "chi@gmail.com").status_code == 200, "chờ duyệt: mật khẩu CŨ vẫn đăng nhập được")
check(login(client(), "chi@gmail.com", "mk-moi-12345").status_code == 401, "chờ duyệt: mật khẩu MỚI chưa có hiệu lực")
lst = {u["email"]: u for u in adm.get("/api/admin/users").get_json()["users"]}
check(lst["chi@gmail.com"]["reset_pending"] is True and lst["binh@gmail.com"]["reset_pending"] is False, "admin thấy đúng ai đang xin đặt lại mật khẩu")
txt = adm.get("/api/admin/users").get_data(as_text=True).lower()
check("hash" not in txt and "mk-moi" not in txt and "password" not in txt, "admin KHÔNG thấy mật khẩu mới (cũng không thấy bản băm)")
check(adm.get("/api/auth/me").get_json()["pending"] >= 1, "huy hiệu admin tính cả yêu cầu đặt lại mật khẩu")
check(cb.post(f"/api/admin/users/{cid}/approve-reset").status_code == 403, "user thường không duyệt được yêu cầu đặt lại")
check(adm.post(f"/api/admin/users/{cid}/approve-reset").status_code == 200, "admin duyệt đặt lại mật khẩu")
check(login(client(), "chi@gmail.com").status_code == 401, "sau duyệt: mật khẩu cũ hết hiệu lực")
check(login(client(), "chi@gmail.com", "mk-moi-12345").status_code == 200, "sau duyệt: mật khẩu mới dùng được")
check(cc.get("/api/state").status_code == 401, "sau duyệt: phiên đăng nhập CŨ của Chi bị đăng xuất")
check(adm.post(f"/api/admin/users/{cid}/approve-reset").status_code == 409, "duyệt khi không còn yêu cầu bị từ chối")
rr("chi@gmail.com", pw="mk-khac-12345")
check(adm.post(f"/api/admin/users/{cid}/reject-reset").status_code == 200, "admin từ chối yêu cầu đặt lại")
check(login(client(), "chi@gmail.com", "mk-moi-12345").status_code == 200 and login(client(), "chi@gmail.com", "mk-khac-12345").status_code == 401, "từ chối: mật khẩu hiện tại giữ nguyên")
check(rr("admin@example.com", pw="chiem-quyen-123").status_code == 200 and login(client(), "admin@example.com", "admin-pass-123").status_code == 200
      and not db.find_by_email("admin@example.com").reset_hash, "tài khoản admin không đặt lại qua web (tránh bị chiếm)")
check(rr("x1@gmail.com").status_code == 200 and rr("x2@gmail.com").status_code == 429, "giới hạn số yêu cầu đặt lại theo IP")

# =================== API KEY THEO TỪNG NGƯỜI DÙNG ===================
from types import SimpleNamespace as NS  # noqa: E402
import httpx, openai  # noqa: E402,E401

mode, calls = {"fn": None}, []


def ok_resp(**kw):
    return NS(choices=[NS(finish_reason="stop", message=NS(content="OK"))])


def _create(**kw):
    calls.append(kw)
    return mode["fn"](**kw)


class FakeClient:
    chat = NS(completions=NS(create=_create))
    models = NS(list=lambda: [NS(id="models/gemini-2.5-flash"), NS(id="gpt-x")])


llm.make_client = lambda cfg: FakeClient()
mode["fn"] = ok_resp
KEY = "AIzaFAKE-KEY-1234567890"


def hresp(code, body="x"):
    return httpx.Response(code, request=httpx.Request("POST", "https://api.test/v1/chat"), text=body)


g0 = cb.get("/api/settings/llm").get_json()
check(g0["has_key"] is False and "api_key" not in g0 and g0["base_url"].startswith("https://generativelanguage"), "tab API: ban đầu chưa có key, form gợi ý Base URL mặc định")
cb.post("/api/sample")
r = cb.post("/api/start", json={"question": "doanh thu?"})
check(r.status_code == 400 and "API key" in r.get_json()["error"], "chưa có key: bấm phân tích bị chặn NGAY với thông báo hướng dẫn")
check(cb.post("/api/settings/llm", json={"api_key": "abc def ghi jkl", "model": "m"}).status_code == 400, "key chứa khoảng trắng bị từ chối (lỗi dán key)")
check("API key" in cb.post("/api/settings/llm", json={"model": "m"}).get_json()["error"], "chưa nhập key và chưa có key cũ: báo cần nhập")
check(cb.post("/api/settings/llm", json={"api_key": KEY, "model": ""}).status_code == 400, "thiếu model bị từ chối")
for bad_url, why in [("https://169.254.169.254/latest", "dịch vụ metadata đám mây"), ("http://10.0.0.5/v1", "mạng riêng"), ("https://192.168.1.1/v1", "mạng riêng"),
                     ("ftp://api.example.com", "sai giao thức"), ("https://user:pw@8.8.8.8/v1", "chứa tài khoản/mật khẩu"), ("http://8.8.8.8/v1", "http công khai")]:
    check(cb.post("/api/settings/llm", json={"api_key": KEY, "base_url": bad_url, "model": "m"}).status_code == 400, f"Base URL bị chặn: {why}")
check(cb.get("/api/settings/llm").get_json()["has_key"] is False, "các lần lưu bị từ chối không để lại gì")

r = cb.post("/api/settings/llm", json={"api_key": KEY, "base_url": "", "model": "gemini-2.5-flash"})
j = r.get_json()
check(r.status_code == 200 and j["saved"] and j["test"]["ok"] and "gemini-2.5-flash" in j["test"]["message"], "lưu key + kiểm tra kết nối thành công")
check(j["settings"]["has_key"] and j["settings"]["key_hint"] == "7890" and KEY not in r.get_data(as_text=True) and KEY not in cb.get("/api/settings/llm").get_data(as_text=True), "API không bao giờ trả lại key (chỉ 4 ký tự cuối)")
bid_ = db.find_by_email("binh@gmail.com").id
with db.scope() as s_:
    tok = s_.get(db.UserSettings, bid_).api_key_enc
check(KEY not in tok and "AIza" not in tok and "FAKE" not in tok, "trong database key được MÃ HÓA (không có bản rõ)")
check(crypto.decrypt(bid_, tok) == KEY, "giải mã đúng bằng khóa chủ")
check(crypto.decrypt(cid, tok) is None, "dòng mã hóa của Bình không dùng được cho tài khoản khác (chép sang user khác)")
check(crypto.decrypt(bid_, tok[:-4] + "AAAA") is None, "dữ liệu mã hóa bị sửa thì bị từ chối")
check(client().get("/api/settings/llm").status_code == 401, "chưa đăng nhập không đọc được cấu hình")
cc2 = client(); login(cc2, "chi@gmail.com", "mk-moi-12345")
check(cc2.get("/api/settings/llm").get_json()["has_key"] is False, "Chi không thấy key của Bình")
check(adm.get("/api/settings/llm").get_json()["has_key"] is False and "key" not in adm.get("/api/admin/users").get_data(as_text=True).lower().replace("hint", ""), "admin không thấy key của user")
r = cb.post("/api/settings/llm", json={"api_key": "", "base_url": "", "model": "gemini-2.5-pro"})
check(r.get_json()["settings"]["model"] == "gemini-2.5-pro" and r.get_json()["settings"]["key_hint"] == "7890" and db.load_llm_cfg(bid_)["api_key"] == KEY, "đổi model, để trống key = giữ key cũ")
check(cb.post("/api/settings/llm/models", json={"base_url": ""}).get_json()["models"] == ["gemini-2.5-flash", "gpt-x"], "tải danh sách model từ chính key đã lưu")

mode["fn"] = lambda **kw: (_ for _ in ()).throw(openai.AuthenticationError("Incorrect API key provided", response=hresp(401), body=None))
r = cb.post("/api/settings/llm", json={"api_key": "", "model": "gemini-2.5-pro"})
check(r.status_code == 200 and r.get_json()["saved"] and r.get_json()["test"]["ok"] is False and "API key" in r.get_json()["test"]["message"], "key sai: vẫn lưu nhưng báo lỗi rõ bằng panel")

cfg = {"model": "gpt-9", "base_url": "https://api.test/v1"}
cases = [(openai.AuthenticationError("bad", response=hresp(401), body=None), "API key bị từ chối"),
         (openai.BadRequestError("Error code: 400 - API key not valid. Please pass a valid API key.", response=hresp(400), body=None), "API key không đúng"),
         (openai.PermissionDeniedError("no", response=hresp(403), body=None), "không có quyền dùng model 'gpt-9'"),
         (openai.NotFoundError("not found", response=hresp(404), body=None), "Không tìm thấy model 'gpt-9'"),
         (openai.BadRequestError("The model `gpt-9` does not exist", response=hresp(400), body=None), "Không tìm thấy model 'gpt-9'"),
         (openai.RateLimitError("You exceeded your current quota", response=hresp(429), body=None), "hết hạn mức"),
         (openai.RateLimitError("slow down", response=hresp(429), body=None), "quá nhanh"),
         (openai.APIConnectionError(request=httpx.Request("POST", "https://api.test/v1")), "Không kết nối được tới api.test"),
         (openai.APITimeoutError(request=httpx.Request("POST", "https://api.test/v1")), "Hết thời gian chờ"),
         (openai.InternalServerError("boom", response=hresp(503), body=None), "đang gặp sự cố")]
for exc, want in cases:
    ue = llm.explain(exc, cfg)
    check(isinstance(ue, UserError) and want in str(ue), f"dịch lỗi API: {want}")
check(llm.explain(ValueError("x"), cfg) is None, "lỗi lạ chưa phân loại: để nguyên cho luồng xử lý chung")

with app.test_request_context():
    state.bind(bid_)
    state.invalidate_llm(bid_)
    mode["fn"] = lambda **kw: (_ for _ in ()).throw(openai.BadRequestError("Unsupported parameter: reasoning_effort", response=hresp(400), body=None)) if "reasoning_effort" in kw else ok_resp()
    calls.clear()
    check(llm.llm("s", "u", json_mode=True) == "OK" and len(calls) == 2, "model không hỗ trợ tham số phụ: tự lùi sang cấu hình đơn giản hơn")
    mode["fn"] = lambda **kw: (_ for _ in ()).throw(openai.BadRequestError("API key not valid. Please pass a valid API key.", response=hresp(400), body=None))
    calls.clear()
    try:
        llm.llm("s", "u", json_mode=True)
        check(False, "key sai phải ném lỗi")
    except UserError as e:
        check("API key không đúng" in str(e) and len(calls) == 1, "key sai (Gemini trả 400): báo đúng nguyên nhân và KHÔNG thử lại vô ích")
    mode["fn"] = lambda **kw: (_ for _ in ()).throw(openai.NotFoundError("model not found", response=hresp(404), body=None))
    try:
        llm.llm("s", "u")
        check(False, "model sai phải ném lỗi")
    except UserError as e:
        check("Không tìm thấy model 'gemini-2.5-pro'" in str(e), "model sai: báo đúng tên model đã nhập")
    state.unbind()

    state.bind(cid)
    try:
        llm.ensure_ready()
        check(False, "chưa có key phải ném lỗi")
    except UserError as e:
        check("API key" in str(e), "người chưa có key (Chi) gọi LLM: báo hướng dẫn nhập key")
    state.start_job(1, ["x"], lambda: (_ for _ in ()).throw(UserError("Nội dung thông báo thân thiện")))
    time.sleep(0.5)
    check(state.A["err"]["msg"] == "Nội dung thông báo thân thiện", "lỗi người dùng hiện NGUYÊN VĂN trong panel (không kèm tên lớp lỗi)")
    state.unbind()

mode["fn"] = ok_resp
r = cb.post("/api/settings/llm/clear")
check(r.get_json()["settings"]["has_key"] is False and db.load_llm_cfg(bid_)["api_key"] == "", "xóa API key")
with app.test_request_context():
    state.bind(bid_)
    try:
        llm.ensure_ready()
        check(False, "sau khi xóa key phải ném lỗi")
    except UserError:
        check(True, "sau khi xóa key: phiên đang mở cũng không dùng được key cũ")
    state.unbind()

# --- bảo vệ ---
r = client().post("/api/auth/login", json={"email": "x@y.com", "password": "p"}, headers={"Origin": "https://evil.example"})
check(r.status_code == 403, "POST từ nguồn khác (CSRF) bị chặn")
t = client()
codes = [login(t, "binh@gmail.com", "sai-" + str(i)).status_code for i in range(10)]
check(429 in codes, "đăng nhập sai nhiều lần bị giới hạn (429)")
check(login(t, "binh@gmail.com").status_code == 429, "bị khóa tạm thời kể cả khi nhập đúng")
check(client().get("/healthz").data == b"ok", "healthz hoạt động không cần đăng nhập")
check("no-store" in cb.get("/api/state").headers["Cache-Control"], "API không cho trình duyệt cache")
if PG:
    reg(client(), "Chủ hệ thống", "owner@gmail.com")
    sql = open(os.path.join(ROOT, "sql", "schema.sql"), encoding="utf-8").read()
    check(login(client(), "owner@gmail.com").status_code == 403, "[SQL] trước khi chạy SQL: owner đang chờ duyệt")
    with psycopg2.connect(PG) as _c, _c.cursor() as _cur:
        _cur.execute(sql)                                                        # chạy lại nguyên file (mặc định email you@gmail.com => bỏ qua an toàn)
    check(db.find_by_email("owner@gmail.com").role == "user", "[SQL] chạy file chưa sửa email: không cấp admin cho ai")
    with psycopg2.connect(PG) as _c, _c.cursor() as _cur:
        _cur.execute(sql.replace("'you@gmail.com'", "'Owner@Gmail.com'"))     # sửa email (chữ hoa/thường không quan trọng) rồi chạy
    own = client()
    check(login(own, "owner@gmail.com").status_code == 200 and own.get("/api/admin/users").status_code == 200, "[SQL] sau khi chạy SQL: owner là admin, vào được trang quản trị")
    with psycopg2.connect(PG) as _c, _c.cursor() as _cur:
        _cur.execute(sql.replace("'you@gmail.com'", "'Owner@Gmail.com'"))     # chạy lần nữa: an toàn
    check(db.find_by_email("owner@gmail.com").role == "admin", "[SQL] chạy lại nhiều lần vẫn an toàn")
print(f"\nTẤT CẢ {ok_count} KIỂM TRA ĐỀU ĐẠT")
