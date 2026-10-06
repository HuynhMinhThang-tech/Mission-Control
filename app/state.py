# -*- coding: utf-8 -*-
"""Trạng thái phiên phân tích hiện tại (A) + lịch sử (HIST) + chạy tác vụ nền."""
import itertools
import json
import threading
import traceback
import uuid
from datetime import datetime

from .config import WORK
from .constants import AG, STEP_T

LOCK = threading.RLock()
# Bộ đếm TOÀN CỤC, không bao giờ reset: tránh việc giao diện nhầm trạng thái cũ với trạng thái mới
_VER = itertools.count(1)
_GEN = itertools.count(1)


def fresh():
    return {"id": uuid.uuid4().hex[:8], "created": datetime.now().isoformat(timespec="seconds"), "started": None, "finished": None,
            "question": "", "ctx": "", "files": [], "dirty": [], "raw": {}, "struct": {}, "alt": {}, "clean": None, "st": ["pending"] * 7, "d": {}, "x": {},
            "ag": dict(AG), "approved": False, "job": {"running": False, "step": None, "k": -1}, "err": None, "log": [],
            "ver": next(_VER), "outputs": [], "applied": []}


A = fresh()


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
                A["err"] = {"step": step, "msg": f"{type(e).__name__}: {e}"}
                A["job"] = {"running": False, "step": step, "k": A["job"]["k"]}
                bump()
            log(f"Lỗi: {e}")

    threading.Thread(target=work, daemon=True).start()


# ------------------------------------------------------------------ Lịch sử --
HF = WORK / "history.json"
HIST = json.loads(HF.read_text("utf-8")) if HF.exists() else []


def save_history(entry):
    HIST.insert(0, entry)
    HF.write_text(json.dumps(HIST, ensure_ascii=False), "utf-8")


def snapshot_path(aid):
    return WORK / aid / "snapshot.json"