# -*- coding: utf-8 -*-
"""Đăng ký (chờ admin duyệt) / đăng nhập / quản trị tài khoản."""
import re
import threading
import time
from urllib.parse import urlparse

from flask import Blueprint, g, jsonify, redirect, request, send_from_directory, session

from . import config, db, state

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
PUBLIC = {"/login", "/api/auth/login", "/api/auth/register", "/api/auth/reset-request", "/healthz"}
STATUS_MSG = {
    "pending": "Tài khoản đang chờ admin duyệt. Bạn sẽ đăng nhập được sau khi được chấp nhận.",
    "rejected": "Yêu cầu đăng ký của bạn đã bị từ chối. Hãy liên hệ admin nếu cần.",
    "disabled": "Tài khoản đã bị khóa. Hãy liên hệ admin.",
}


def bad(m, c=400):
    return jsonify({"error": m}), c


# ------------------------------------------------------------ Giới hạn số lần thử --
_HITS, _HLOCK = {}, threading.Lock()


def over_limit(bucket, key, limit, window, record=True):
    """True nếu `key` đã vượt `limit` lần trong `window` giây. (Trong bộ nhớ: đủ cho một tiến trình, nhóm nhỏ.)"""
    now, k = time.time(), (bucket, key)
    with _HLOCK:
        hits = [t for t in _HITS.get(k, []) if now - t < window]
        blocked = len(hits) >= limit
        if record and not blocked:
            hits.append(now)
        _HITS[k] = hits
        if len(_HITS) > 5000:                                   # dọn rác định kỳ
            for kk in [kk for kk, v in _HITS.items() if not v or now - v[-1] > 3600]:
                del _HITS[kk]
        return blocked


def clear_hits(bucket, key):
    with _HLOCK:
        _HITS.pop((bucket, key), None)


# ------------------------------------------------------------ Người dùng hiện tại --
def current_user():
    """Đọc trạng thái từ database MỖI request nên khóa/xóa tài khoản và đổi mật khẩu có hiệu lực ngay."""
    uid = session.get("uid")
    if not uid:
        return None
    u = db.get_user(uid)
    if not u or u["status"] != "approved" or session.get("ver") != u["auth_ver"]:      # lệch phiên bản = mật khẩu đã đổi -> đăng nhập lại
        return None
    return u


def guard():
    """Chạy trước MỌI request: kiểm tra nguồn gốc, bắt buộc đăng nhập, gắn phiên làm việc đúng người."""
    p = request.path
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        o = request.headers.get("Origin")
        if o and urlparse(o).netloc != request.host:            # chặn form/POST từ trang web khác (CSRF)
            return bad("Yêu cầu bị từ chối (nguồn không hợp lệ).", 403)
    if p.startswith("/static/") or p in PUBLIC:
        return None
    u = current_user()
    if not u:
        if p.startswith("/api/"):
            return jsonify({"error": "Phiên đăng nhập đã hết hạn, hãy đăng nhập lại.", "login": True}), 401
        return redirect("/login")
    g.user = u
    if (p == "/admin" or p.startswith("/api/admin/")) and u["role"] != "admin":
        return bad("Bạn không có quyền thực hiện thao tác này.", 403) if p.startswith("/api/") else redirect("/")
    state.bind(u["id"])
    return None


# ------------------------------------------------------------ Trang ----------
@bp.get("/login")
def login_page():
    if current_user():
        return redirect("/")
    return send_from_directory(config.TEMPLATE_DIR, "login.html")


@bp.get("/admin")
def admin_page():
    return send_from_directory(config.TEMPLATE_DIR, "admin.html")


@bp.get("/healthz")
def healthz():
    return "ok"


# ------------------------------------------------------------ API xác thực ----
def _norm_email(v):
    return (v or "").strip().lower()


def _check_creds(email, pw, pw2):
    """Kiểm tra email + mật khẩu mới + xác nhận (dùng cho cả đăng ký và đặt lại mật khẩu). Trả về thông báo lỗi hoặc None."""
    if not EMAIL_RE.match(email) or len(email) > 254:
        return "Email/Gmail không hợp lệ."
    if len(pw) < 8:
        return "Mật khẩu cần ít nhất 8 ký tự."
    if len(pw) > 128:
        return "Mật khẩu quá dài (tối đa 128 ký tự)."
    if pw.lower() == email or pw.lower() == email.split("@")[0]:
        return "Mật khẩu không được trùng với email."
    if pw != pw2:
        return "Mật khẩu xác nhận không khớp."
    return None


@bp.post("/api/auth/register")
def register():
    p = request.get_json(silent=True) or {}
    name, email = (p.get("name") or "").strip(), _norm_email(p.get("email"))
    pw, pw2 = p.get("password") or "", p.get("confirm") or ""
    if over_limit("reg", request.remote_addr, 5, 3600, record=False):
        return bad("Bạn đã gửi quá nhiều yêu cầu đăng ký. Hãy thử lại sau.", 429)
    if not (2 <= len(name) <= 80):
        return bad("Tên hiển thị cần từ 2 đến 80 ký tự.")
    err = _check_creds(email, pw, pw2)
    if err:
        return bad(err)
    over_limit("reg", request.remote_addr, 5, 3600)        # chỉ tính các yêu cầu hợp lệ (gõ sai form không bị phạt)
    try:
        db.create_user(name, email, pw)
    except ValueError as e:
        return bad(str(e), 409)
    return jsonify(ok=True, message="Đã gửi yêu cầu đăng ký. Bạn sẽ đăng nhập được sau khi admin duyệt tài khoản.")


@bp.post("/api/auth/login")
def login():
    p = request.get_json(silent=True) or {}
    email, pw = _norm_email(p.get("email")), p.get("password") or ""
    ip = request.remote_addr
    if over_limit("login_ip", ip, 40, 900, record=False) or over_limit("login_em", email, 8, 900, record=False):
        return bad("Đăng nhập sai quá nhiều lần. Hãy thử lại sau ít phút.", 429)
    u = db.check_login(email, pw[:128])
    if not u:
        over_limit("login_ip", ip, 40, 900)
        over_limit("login_em", email, 8, 900)
        return bad("Email hoặc mật khẩu không đúng.", 401)
    if u["status"] != "approved":             # chỉ tiết lộ trạng thái khi đã nhập ĐÚNG mật khẩu
        return bad(STATUS_MSG.get(u["status"], "Tài khoản chưa dùng được."), 403)
    clear_hits("login_em", email)
    session.clear()
    session["uid"], session["ver"] = u["id"], u["auth_ver"]
    session.permanent = True
    return jsonify(ok=True)


RESET_MSG = ("Nếu email này có tài khoản đang hoạt động, yêu cầu đặt lại mật khẩu đã được gửi tới admin. "
             "Trong lúc chờ duyệt, mật khẩu cũ vẫn dùng được; sau khi admin duyệt, hãy đăng nhập bằng mật khẩu mới.")


@bp.post("/api/auth/reset-request")
def reset_request():
    """Quên mật khẩu: người dùng nhập email + mật khẩu MỚI + xác nhận. Mật khẩu mới được băm và chờ admin duyệt (giống đăng ký)."""
    p = request.get_json(silent=True) or {}
    email, pw, pw2 = _norm_email(p.get("email")), p.get("password") or "", p.get("confirm") or ""
    ip = request.remote_addr
    if over_limit("rst", ip, 5, 3600, record=False):
        return bad("Bạn đã gửi quá nhiều yêu cầu. Hãy thử lại sau.", 429)
    err = _check_creds(email, pw, pw2)
    if err:
        return bad(err)
    over_limit("rst", ip, 5, 3600)
    if not over_limit("rst_em", email, 3, 3600):          # mỗi email tối đa 3 yêu cầu/giờ để không làm ngập hàng chờ của admin
        db.request_reset(email, pw)
    return jsonify(ok=True, message=RESET_MSG)           # luôn trả lời giống nhau: không tiết lộ email nào có tài khoản


@bp.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.get("/api/auth/me")
def me():
    u = g.user
    out = {"display_name": u["display_name"], "email": u["email"], "role": u["role"]}
    if u["role"] == "admin":
        out["pending"] = db.count_pending()
    return jsonify(out)


# ------------------------------------------------------------ API quản trị ----
@bp.get("/api/admin/users")
def admin_users():
    """Chỉ tên hiển thị, email, trạng thái, ngày đăng ký. Không có mật khẩu (kể cả bản băm) trong bất kỳ phản hồi nào."""
    keys = ("id", "display_name", "email", "status", "created_at", "reset_pending", "reset_requested_at")
    return jsonify(users=[{k: u[k] for k in keys} for u in db.list_users() if u["role"] == "user"])


@bp.post("/api/admin/users/<int:uid>/<action>")
def admin_action(uid, action):
    if action not in ("approve", "reject", "disable", "enable", "delete", "approve-reset", "reject-reset"):
        return bad("Thao tác không hợp lệ.", 404)
    if action.endswith("-reset"):
        ok, msg = db.decide_reset(uid, action == "approve-reset")
    else:
        ok, msg = db.change_status(uid, action)
    if not ok:
        return bad(msg, 409)
    if action in ("reject", "disable", "delete"):
        state.drop_session(uid)
    return jsonify(ok=True, message=msg)
