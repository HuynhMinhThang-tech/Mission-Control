# -*- coding: utf-8 -*-
"""Trạng thái phiên phân tích THEO TỪNG NGƯỜI DÙNG + chạy tác vụ nền.

`A` và `LOCK` vẫn là tên cũ để các agent không phải sửa, nhưng giờ chúng là "cửa sổ" tự trỏ tới phiên của
người dùng hiện tại (gắn bởi `bind()` ở đầu mỗi request, và bởi `start_job()` cho luồng nền).
Lịch sử phân tích đã chuyển sang database (xem db.py)."""
import itertools
import threading
import time
import traceback
import uuid
from collections.abc import MutableMapping
from datetime import datetime

from .constants import AG, STEP_T
from .errors import UserError

# Bộ đếm TOÀN CỤC, không bao giờ reset: tránh việc giao diện nhầm trạng thái cũ với trạng thái mới
_VER = itertools.count(1)
_GEN = itertools.count(1)


def fresh():
    return {"id": uuid.uuid4().hex[:12], "created": datetime.now().isoformat(timespec="seconds"), "started": None, "finished": None,
            "question": "", "ctx": "", "files": [], "dirty": [], "raw": {}, "struct": {}, "alt": {}, "clean": None, "st": ["pending"] * 7, "d": {}, "x": {},
            "ag": dict(AG), "approved": False, "job": {"running": False, "step": None, "k": -1}, "err": None, "log": [],
            "ver": next(_VER), "outputs": [], "applied": [], "fbh": {}}


# ------------------------------------------------------------ Phiên theo người dùng --
class Session(dict):
    """Một phiên phân tích của một người dùng (dict như trước + khóa riêng)."""

    def __init__(self, user_id):
        super().__init__(fresh())
        self.user_id = user_id
        self.lock = threading.RLock()
        self.touched = time.time()
        self.llm_cfg = None          # cấu hình LLM của người này (nạp lười từ database, xóa khi họ đổi cấu hình)
        self.llm_client = None


_SESSIONS = {}
_SLOCK = threading.Lock()
_tls = threading.local()
_last_evict = [time.time()]
IDLE_SECONDS = 6 * 3600


def session_for(user_id):
    with _SLOCK:
        s = _SESSIONS.get(user_id)
        if s is None:
            s = _SESSIONS[user_id] = Session(user_id)
        return s


def evict_idle():
    """Giải phóng RAM của phiên bỏ quên quá lâu (không đụng tới phiên đang có tác vụ chạy)."""
    now = time.time()
    if now - _last_evict[0] < 600:
        return
    _last_evict[0] = now
    with _SLOCK:
        for uid in [u for u, s in _SESSIONS.items() if now - s.touched > IDLE_SECONDS and not s["job"]["running"]]:
            del _SESSIONS[uid]


def invalidate_llm(user_id):
    """Người dùng vừa đổi/xóa API key hay model: lần gọi kế tiếp phải nạp lại cấu hình mới."""
    with _SLOCK:
        s = _SESSIONS.get(user_id)
    if s:
        s.llm_cfg = s.llm_client = None


def drop_session(user_id):
    """Dùng khi khóa/xóa tài khoản. Trả về False nếu đang có tác vụ chạy (giữ lại, request kế tiếp sẽ bị chặn do tài khoản đã khóa)."""
    with _SLOCK:
        s = _SESSIONS.get(user_id)
        if s and not s["job"]["running"]:
            del _SESSIONS[user_id]
            return True
        return s is None


def bind(user_id):
    evict_idle()
    _tls.s = session_for(user_id)


def unbind(_exc=None):
    _tls.s = None


def current():
    s = getattr(_tls, "s", None)
    if s is None:
        raise RuntimeError("Chưa có phiên làm việc (chưa đăng nhập).")
    s.touched = time.time()
    return s


def current_user_id():
    return current().user_id


class _SessionView(MutableMapping):
    """`A`: hành xử như dict của phiên hiện tại."""

    def __getitem__(self, k):
        return current()[k]

    def __setitem__(self, k, v):
        current()[k] = v

    def __delitem__(self, k):
        del current()[k]

    def __iter__(self):
        return iter(current())

    def __len__(self):
        return len(current())

    def clear(self):
        current().clear()

    def update(self, *a, **k):
        current().update(*a, **k)


class _LockView:
    """`LOCK`: khóa RLock của phiên hiện tại; nhớ đúng khóa đã lấy để nhả đúng dù ràng buộc phiên có đổi."""

    def __enter__(self):
        lk = current().lock
        lk.acquire()
        st = getattr(_tls, "stack", None)
        if st is None:
            st = _tls.stack = []
        st.append(lk)
        return self

    def __exit__(self, *exc):
        _tls.stack.pop().release()
        return False


A = _SessionView()
LOCK = _LockView()


def reset():
    """Làm mới IN-PLACE để mọi module giữ nguyên tham chiếu tới A."""
    with LOCK:
        A.clear()
        A.update(fresh())


def next_gen():
    return next(_GEN)


def bump():
    A["ver"] = next(_VER)


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def log(msg):
    with LOCK:
        A["log"].append(f"[{datetime.now():%H:%M}] {msg}")


def tick(k):
    with LOCK:
        A["job"]["k"] = k


def put(i, payload):
    with LOCK:
        payload["gen"] = next_gen()
        A["d"][i] = payload
        bump()


def start_job(step, labels, fn, *a):
    owner = current()          # luồng nền phải làm việc trên ĐÚNG phiên của người đã bấm
    with LOCK:
        if A["job"]["running"]:
            raise RuntimeError("Đang có tác vụ chạy, hãy chờ xong.")
        A["st"][step] = "running"
        A["err"] = None
        A["job"] = {"running": True, "step": step, "k": 0}
        A["ag"][step] = labels
        bump()
    log("Bắt đầu: " + STEP_T[step])

    def work():
        _tls.s = owner
        try:
            try:
                fn(*a)
                with LOCK:
                    A["st"][step] = "await"
                    A["job"] = {"running": False, "step": step, "k": 99}
                    bump()
                log("Chờ bạn xác nhận: " + STEP_T[step])
            except Exception as e:
                traceback.print_exc()
                with LOCK:
                    A["st"][step] = "error"
                    A["err"] = {"step": step, "msg": str(e) if isinstance(e, UserError) else f"{type(e).__name__}: {e}"}
                    A["job"] = {"running": False, "step": step, "k": A["job"]["k"]}
                    bump()
                log(f"Lỗi: {e}")
        finally:
            _tls.s = None

    threading.Thread(target=work, daemon=True).start()
