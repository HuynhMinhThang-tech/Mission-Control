# -*- coding: utf-8 -*-
"""Tiến trình con chạy code pandas do AI/người dùng viết.  Chạy bằng:  python -S -E -B sandbox_worker.py job.json

KHÔNG import gói `app` và KHÔNG nhận biến môi trường bí mật của server. Thứ tự dưới đây là bắt buộc:
  1) tự đặt giới hạn tài nguyên (không nâng lên lại được)   2) nạp dữ liệu + thư viện
  3) cài audit hook (không gỡ được)                          4) mới chạy code người dùng
Kết quả ghi ra out.json dưới dạng dữ liệu thuần (JSON), không bao giờ là pickle."""
import io
import json
import os
import sys

SAFE_NAMES = ("len range sum min max abs round sorted enumerate zip list dict set float int str bool tuple isinstance any all map filter "
              "reversed print pow divmod slice Exception ValueError KeyError").split()

BAD_IMPORT = {"subprocess", "_posixsubprocess", "socket", "_socket", "ssl", "_ssl", "ctypes", "_ctypes", "multiprocessing", "_multiprocessing", "pty",
              "telnetlib", "ftplib", "smtplib", "imaplib", "poplib", "nntplib", "webbrowser", "code", "codeop", "pdb", "bdb", "cffi", "xmlrpc", "socketserver"}
BAD_PREFIX = ("socket.", "urllib.", "http.client.", "ftplib.", "smtplib.", "telnetlib.", "imaplib.", "poplib.", "nntplib.", "webbrowser.",   # mạng
              "subprocess.", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty", "os.kill", "os.killpg", "os.startfile",
              "pty.", "multiprocessing.",                                                                                              # sinh tiến trình
              "os.remove", "os.rename", "os.replace", "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.lchown", "os.symlink", "os.link", "os.truncate",
              "os.utime", "os.mkfifo", "os.mknod", "os.chdir", "os.chroot", "os.setxattr", "os.removexattr", "shutil.",                 # sửa hệ thống tệp
              "ctypes.", "gc.", "sys._getframe", "sys._current_frames", "sys._current_exceptions", "code.__new__", "function.__new__",  # mã gốc / lục đối tượng
              "pickle.find_class")
EXTRA_READ = ("/usr/share/zoneinfo", "/etc/localtime", "/dev/null", "/dev/urandom", "/dev/zero")


def _limits(job):
    try:
        with open("/proc/self/oom_score_adj", "w") as f:       # nếu máy hết RAM, hệ điều hành giết tiến trình này TRƯỚC máy chủ web
            f.write("1000")
    except OSError:
        pass
    try:
        import resource
    except ImportError:                                         # Windows: không có rlimit, vẫn còn timeout/RAM-watchdog của tiến trình cha
        return

    def lim(which, soft, hard=None):
        try:
            resource.setrlimit(which, (soft, soft if hard is None else hard))
        except (ValueError, OSError):
            pass
    lim(resource.RLIMIT_AS, job["as_mb"] * 2 ** 20)
    lim(resource.RLIMIT_CPU, job["cpu_s"], job["cpu_s"] + 2)    # soft: SIGXCPU, hard: SIGKILL
    lim(resource.RLIMIT_FSIZE, job["fsize_mb"] * 2 ** 20)
    lim(resource.RLIMIT_CORE, 0)
    lim(resource.RLIMIT_NOFILE, 256)


def _install_hook(sys_path, work):
    norm = lambda p: os.path.normcase(os.path.normpath(os.path.abspath(p)))          # noqa: E731
    read_ok = {norm(p) for p in sys_path if p} | {norm(work)}          # chỉ đúng các thư mục thư viện Python + thư mục tạm riêng (KHÔNG cả cây /usr)
    read_ok |= {norm(p) for p in EXTRA_READ}
    read_ok = tuple(read_ok)
    work = norm(work)
    under = lambda p, roots: any(p == r or p.startswith(r + os.sep) for r in roots)  # noqa: E731
    WRITE = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC

    def deny(what):
        raise PermissionError(f"Sandbox: thao tác bị chặn ({what})")

    def path_of(x):
        try:
            return norm(os.fsdecode(os.fspath(x)))
        except (TypeError, ValueError):
            return None

    def hook(event, args):
        if event == "open":
            p = path_of(args[0]) if not isinstance(args[0], int) else None
            if p is None:                                        # mở theo số mô tả tệp đã có: cho qua
                return
            flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
            mode = args[1] if len(args) > 1 and isinstance(args[1], str) else ""
            if flags & WRITE or any(c in mode for c in "wax+"):
                if not under(p, (work,)):
                    deny("ghi tệp ngoài thư mục tạm")
            elif not under(p, read_ok):
                deny("đọc tệp ngoài thư viện Python")
        elif event in ("os.listdir", "os.scandir"):
            p = path_of(args[0]) if args and args[0] is not None and not isinstance(args[0], int) else None
            if p is not None and not under(p, read_ok):
                deny("liệt kê thư mục")
        elif event == "import":
            if args[0].split(".")[0] in BAD_IMPORT:
                deny("import " + args[0])
        elif event.startswith(BAD_PREFIX):
            deny(event)
    sys.addaudithook(hook)


def _safe_builtins():
    import builtins
    return {k: getattr(builtins, k) for k in SAFE_NAMES}


def _plain(df, pd, np):
    """Đưa DataFrame về kiểu JSON chịu được: bỏ categorical/Interval/Period, tên cột là chuỗi và không trùng."""
    seen, cols = {}, []
    for c in df.columns:
        c = str(c)
        seen[c] = seen.get(c, 0) + 1
        cols.append(c if seen[c] == 1 else f"{c}_{seen[c]}")
    df.columns = cols
    for c in df.columns:
        s = df[c]
        if isinstance(s.dtype, (pd.CategoricalDtype, pd.PeriodDtype, pd.IntervalDtype)):
            s = s.astype(object)
        if s.dtype.kind == "m":                                  # khoảng thời gian: định dạng bảng JSON không đọc ngược được -> dạng chuỗi dễ đọc
            s = s.astype(str)
        if s.dtype == object:
            s = s.map(lambda v: v if v is None or isinstance(v, (str, int, float, bool, np.generic)) else str(v))
        df[c] = s
    return df


def _encode(r, pd):
    """Ghi JSON rồi tự đọc lại thử; kiểu dữ liệu lạ không đọc ngược được thì đổi cột đó thành chuỗi (còn hơn là làm hỏng cả phân tích)."""
    for attempt in (0, 1):
        out = r.to_json(orient="table", index=False, date_format="iso", double_precision=15)
        try:
            pd.read_json(io.StringIO(out), orient="table")
            return out
        except Exception:                                        # noqa: BLE001
            if attempt:
                raise ValueError("Không biểu diễn được kết quả. Hãy trả về cột số, chữ hoặc ngày.")
            r = r.copy()
            for c in r.columns:
                if r[c].dtype.kind not in "iufbM":
                    r[c] = r[c].astype(str)


def _run(code, dfs, pd, np):
    env = {"__builtins__": _safe_builtins(), "pd": pd, "np": np, "dfs": dfs}
    exec(compile(code, "<phân tích>", "exec"), env)
    r = env.get("result")
    if isinstance(r, pd.Series):
        r = r.reset_index()
    if not isinstance(r, pd.DataFrame):
        raise ValueError("Biến `result` phải là DataFrame")
    if isinstance(r.columns, pd.MultiIndex):
        r.columns = ["_".join(map(str, c)) for c in r.columns]
    if not isinstance(r.index, pd.RangeIndex):
        r = r.reset_index()
    r = _plain(r.head(200).copy(), pd, np)
    out = _encode(r, pd)
    if len(out) > 20 * 2 ** 20:
        raise ValueError("Kết quả quá lớn (>20 MB). Hãy tổng hợp gọn hơn: chọn ít cột, cắt chuỗi dài.")
    return out


def main():
    with open(sys.argv[1], encoding="utf-8") as f:
        job = json.load(f)
    _limits(job)
    work = job["work_dir"]
    os.chdir(work)
    try:
        sys.path[:] = job["sys_path"]
        import pickle

        import numpy as np
        import pandas as pd
        with open(job["pkl"], "rb") as f:                        # dữ liệu do chính máy chủ ghi ra (chiều tin cậy)
            dfs = pickle.load(f)
        _install_hook(job["sys_path"], work)
        payload = {"ok": True, "table": _run(job["code"], dfs, pd, np)}
    except BaseException as e:                                   # noqa: BLE001  (gồm MemoryError, PermissionError của sandbox, lỗi cú pháp...)
        payload = {"ok": False, "etype": type(e).__name__, "msg": str(e)[:800]}
    try:
        with open(os.path.join(work, "out.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError:                                              # vượt giới hạn dung lượng ghi: báo lỗi gọn thay vì để lại tệp cụt
        with open(os.path.join(work, "out.json"), "w", encoding="utf-8") as f:
            json.dump({"ok": False, "etype": "ValueError", "msg": "Kết quả quá lớn, không ghi được."}, f)


if __name__ == "__main__":
    main()
