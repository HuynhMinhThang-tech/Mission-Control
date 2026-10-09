# -*- coding: utf-8 -*-
"""Chạy code pandas do AI/người dùng viết trong SANDBOX NHIỀU LỚP + chuyển DataFrame thành bảng JSON.

Lớp 1 (check_code): kiểm tra cú pháp bằng ast: chặn import, thuộc tính riêng `_x`, module nguy hiểm, hàm đọc/ghi tệp.
Lớp 2 (tiến trình con): môi trường rỗng (không có bí mật của server), thư mục tạm riêng, giới hạn CPU/RAM/dung lượng ghi,
        quá giờ hoặc quá RAM thì bị giết, tối đa N sandbox chạy cùng lúc.
Lớp 3 (sandbox_worker): audit hook trong tiến trình con chặn mạng, sinh tiến trình, đọc/ghi tệp ngoài danh sách cho phép.
Kết quả trả về là JSON thuần (không bao giờ unpickle dữ liệu do tiến trình con tạo ra).
Đây là sandbox TỐI GIẢN dùng quyền của cùng người dùng hệ điều hành, KHÔNG phải cô lập ở mức container: xem README."""
import ast
import io
import json
import os
import pickle
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager

import pandas as pd

from .. import config
from ..errors import UserError

WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sandbox_worker.py")
MAX_CODE = 60_000
MAX_OUT = 60 * 2 ** 20
MAX_WORK_MB = 256                                       # tổng dung lượng tối đa code được ghi vào thư mục tạm của nó
SLOT_WAIT = 120                                         # giây chờ tới lượt khi đã đủ số sandbox chạy cùng lúc


class CodeError(Exception):
    """Code chạy lỗi / bị chặn / vượt giới hạn. `user_text` là câu hiển thị cho người dùng và đưa cho AI để tự sửa."""

    def __init__(self, text):
        super().__init__(text)
        self.user_text = text


def describe_error(e):
    return e.user_text if isinstance(e, CodeError) else f"{type(e).__name__}: {e}"


# ------------------------------------------------------------ Lớp 1: kiểm tra cú pháp --
DENY_NAMES = {"eval", "exec", "compile", "open", "input", "globals", "locals", "vars", "getattr", "setattr", "delattr", "breakpoint", "__import__"}
DENY_ATTRS = {
    # module hệ thống / mạng / đối tượng nội bộ có thể là đường tới hệ điều hành
    "os", "sys", "io", "subprocess", "socket", "urllib", "http", "ctypes", "shutil", "pickle", "builtins", "importlib", "tempfile", "pathlib", "glob", "posix",
    "nt", "mmap", "signal", "threading", "multiprocessing", "asyncio", "gc", "inspect", "types", "codecs", "marshal", "ast", "code", "runpy", "core", "compat",
    "util", "testing", "plotting", "lib", "ctypeslib", "distutils", "f2py", "DataSource",
    # đọc/ghi tệp và đánh giá chuỗi thành mã
    "eval", "query", "load", "loads", "save", "savez", "savez_compressed", "savetxt", "fromfile", "tofile", "memmap", "genfromtxt", "loadtxt", "fromregex",
    "ExcelWriter", "ExcelFile", "HDFStore", "show_config", "plot", "hist", "boxplot", "style",
    "to_csv", "to_excel", "to_pickle", "to_sql", "to_json", "to_parquet", "to_html", "to_clipboard", "to_feather", "to_hdf", "to_stata", "to_latex",
    "to_markdown", "to_xml", "to_orc", "to_gbq", "to_xarray"}
BRACE_ATTR = re.compile(r"\{[^{}:!]*[.\[]")                # "{0.__class__}".format(x): TÊN TRƯỜNG đi sâu vào thuộc tính (dấu chấm trong phần định dạng như {:.1f} thì không sao)


def check_code(code):
    if len(code) > MAX_CODE:
        raise CodeError("Code quá dài.")
    tree = ast.parse(code)                                  # SyntaxError được giữ nguyên để người dùng/AI thấy dòng lỗi

    def block(what):
        raise CodeError(f"Code bị chặn vì chứa '{what}'")
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            block("import")
        elif isinstance(n, ast.Name):
            if n.id in DENY_NAMES or (n.id.startswith("__") and n.id.endswith("__")):
                block(n.id)
        elif isinstance(n, ast.Attribute):
            a = n.attr
            if a.startswith("_") or a in DENY_ATTRS or a.startswith("read_"):
                block("." + a)
            if a in ("format", "format_map") and not (isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
                                                      and a == "format" and not BRACE_ATTR.search(n.value.value)):
                block(".format() (hãy dùng f-string)")
        elif isinstance(n, ast.arg) and n.arg.startswith("__"):
            block(n.arg)


# ------------------------------------------------------------ Lớp 2: tiến trình con --
_tls = threading.local()
_SLOTS = threading.BoundedSemaphore(config.SANDBOX_PARALLEL)
_ENV_PASS = ("PATH", "LD_LIBRARY_PATH", "SYSTEMROOT", "WINDIR", "TZ", "LANG", "LC_ALL")     # chỉ những biến hạ tầng, không có bí mật


def mem_limit_mb():
    if config.SANDBOX_MEM_MB:
        return config.SANDBOX_MEM_MB
    total = None
    for f in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):      # giới hạn của container (Railway/Render...)
        try:
            v = open(f).read().strip()
            if v.isdigit() and int(v) < 2 ** 50:
                total = int(v) / 2 ** 20
                break
        except OSError:
            pass
    if total is None:
        try:
            total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 20
        except (ValueError, OSError, AttributeError):
            total = 2048
    return int(min(3072, max(256, total * 0.5)))


def _child_env():
    env = {k: os.environ[k] for k in _ENV_PASS if k in os.environ}
    env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return env


def _rss_mb(pid):
    try:
        with open(f"/proc/{pid}/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2 ** 20
    except (OSError, ValueError, IndexError):
        return None


def _dir_mb(path):
    try:
        return sum(e.stat().st_size for e in os.scandir(path) if e.is_file(follow_symlinks=False)) / 2 ** 20
    except OSError:
        return 0


def _kill(proc):
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError, OSError):
        pass
    proc.wait()


def _dump(dfs):
    d = tempfile.mkdtemp(prefix="mc-sbx-in-")
    path = os.path.join(d, "dfs.pkl")
    with open(path, "wb") as f:
        pickle.dump(dfs, f, protocol=pickle.HIGHEST_PROTOCOL)
    return d, path


@contextmanager
def prepare(dfs):
    """Ghi dữ liệu ra tệp tạm MỘT lần cho cả loạt lần chạy trong khối `with` (đỡ tốn thời gian khi chạy nhiều tác vụ liên tiếp)."""
    d, path = _dump(dfs)
    prev = getattr(_tls, "prep", None)
    _tls.prep = (dfs, path)
    try:
        yield
    finally:
        _tls.prep = prev
        shutil.rmtree(d, ignore_errors=True)


def run_code(code, dfs, _check=True):
    """Chạy `code` (gán DataFrame vào biến `result`) trên bản sao của `dfs`. Ném CodeError nếu code lỗi/bị chặn/vượt giới hạn."""
    if _check:
        check_code(code)
    prep = getattr(_tls, "prep", None)
    own = None
    if prep and prep[0] is dfs:
        pkl = prep[1]
    else:
        own, pkl = _dump(dfs)
    job = tempfile.mkdtemp(prefix="mc-sbx-job-")
    try:
        work = os.path.join(job, "work")
        os.mkdir(work)
        mem, tmo = mem_limit_mb(), config.SANDBOX_TIMEOUT
        spec = {"code": code, "pkl": pkl, "work_dir": work, "as_mb": mem + 1536, "cpu_s": tmo, "fsize_mb": 64,
                "sys_path": [p for p in sys.path if p and os.path.realpath(p) != os.path.realpath(os.path.join(os.path.dirname(WORKER), "..", ".."))]}
        spec_path = os.path.join(job, "job.json")
        with open(spec_path, "w", encoding="utf-8") as f:
            json.dump(spec, f)
        if not _SLOTS.acquire(timeout=SLOT_WAIT):
            raise UserError("Máy chủ đang bận chạy phân tích của người khác. Hãy thử lại sau ít phút.")
        try:
            rc, why, err = _spawn(spec_path, work, tmo, mem)
        finally:
            _SLOTS.release()
        return _collect(work, rc, why, err, tmo, mem)
    finally:
        shutil.rmtree(job, ignore_errors=True)
        if own:
            shutil.rmtree(own, ignore_errors=True)


def _spawn(spec_path, work, timeout, mem):
    errf = os.path.join(work, "stderr.txt")
    kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, cwd=work, env=_child_env())
    if os.name == "posix":
        kw["start_new_session"] = True                       # để giết được cả nhóm tiến trình
    with open(errf, "wb") as ef:
        proc = subprocess.Popen([sys.executable, "-S", "-E", "-B", WORKER, spec_path], stderr=ef, **kw)
        end, why = time.monotonic() + timeout, None
        while True:
            try:
                rc = proc.wait(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                pass
            if time.monotonic() > end:
                why = "time"
            else:
                rss = _rss_mb(proc.pid)
                if rss is not None and rss > mem:
                    why = "mem"
                elif _dir_mb(work) > MAX_WORK_MB:
                    why = "disk"
            if why:
                _kill(proc)
                rc = proc.returncode
                break
    try:
        with open(errf, "rb") as f:
            err = f.read()[-600:].decode("utf-8", "replace").strip()
    except OSError:
        err = ""
    return rc, why, err


def _collect(work, rc, why, err, timeout, mem):
    if why == "time":
        raise CodeError(f"Code chạy quá {timeout} giây nên bị dừng. Hãy viết lại cho nhẹ hơn (tránh vòng lặp từng dòng, dùng thao tác theo cột/groupby).")
    if why == "mem":
        raise CodeError(f"Code dùng quá {mem} MB bộ nhớ nên bị dừng. Hãy xử lý gọn hơn (lọc cột/dòng trước, tránh nhân chéo bảng). "
                        f"Dữ liệu rất lớn có thể cần nâng gói máy chủ hoặc tăng SANDBOX_MEM_MB.")
    if why == "disk":
        raise CodeError(f"Code ghi quá {MAX_WORK_MB} MB dữ liệu tạm nên bị dừng.")
    out = os.path.join(work, "out.json")
    if os.path.exists(out) and os.path.getsize(out) < MAX_OUT:
        with open(out, encoding="utf-8") as f:
            j = json.load(f)
        if j.get("ok"):
            return pd.read_json(io.StringIO(j["table"]), orient="table")
        et, msg = j.get("etype", "Error"), j.get("msg", "")
        if et == "MemoryError":
            raise CodeError(f"Code dùng quá nhiều bộ nhớ (giới hạn {mem + 1536} MB bộ nhớ ảo). Hãy xử lý gọn hơn.")
        if et == "PermissionError" and msg.startswith("Sandbox:"):
            raise CodeError("Code bị chặn: " + msg[len("Sandbox: "):])
        raise CodeError(f"{et}: {msg}")
    if rc is not None and rc < 0:
        sig = -rc
        if sig == signal.SIGXCPU or sig == signal.SIGKILL and not err:
            raise CodeError(f"Code dùng quá nhiều thời gian CPU (giới hạn {timeout} giây) hoặc bộ nhớ nên bị dừng.")
        raise CodeError(f"Tiến trình chạy code bị dừng đột ngột (tín hiệu {sig}). {err[-300:]}".strip())
    raise CodeError(f"Không chạy được sandbox (mã thoát {rc}). {err[-400:]}".strip())


def df_table(df, title, err=None):
    if df is None:
        return {"title": title, "cols": [], "rows": [], "err": err}
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[c]):
            d[c] = d[c].dt.strftime("%Y-%m-%d")
    return {"title": title, "cols": list(d.columns), "rows": json.loads(d.head(200).to_json(orient="values")), "err": err}
