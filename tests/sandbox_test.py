# -*- coding: utf-8 -*-
"""Kiểm thử sandbox chạy code phân tích. Chạy: python tests/sandbox_test.py  (cần Linux để kiểm tra giới hạn RAM/CPU đầy đủ)."""
import glob
import os
import re
import socket
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.update(SECRET_KEY="k-test", MASTER_KEY="k-test", MASTER_KEY_TEST_SECRET="TOPSECRET-123", DATABASE_URL=f"sqlite:///{tempfile.mkdtemp()}/x.db")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app import state  # noqa: E402
from app.agents import planner  # noqa: E402
from app.data import sandbox as sb  # noqa: E402
from app.errors import UserError  # noqa: E402

n_ok = 0


def check(cond, label):
    global n_ok
    if not cond:
        print("FAIL:", label)
        sys.exit(1)
    n_ok += 1
    print("ok  ", label)


def err_of(code, dfs=None, **kw):
    try:
        sb.run_code(code, dfs if dfs is not None else DFS, **kw)
    except sb.CodeError as e:
        return e.user_text
    except SyntaxError as e:
        return "SyntaxError: " + str(e)
    return None


# ---- bản cũ (chạy trong chính tiến trình, chặn bằng regex) để so kết quả ----
SAFE = dict(len=len, range=range, sum=sum, min=min, max=max, abs=abs, round=round, sorted=sorted, enumerate=enumerate, zip=zip, list=list, dict=dict, set=set,
            float=float, int=int, str=str, bool=bool, tuple=tuple, isinstance=isinstance, any=any, all=all, map=map, filter=filter, reversed=reversed, print=print,
            pow=pow, divmod=divmod, slice=slice, Exception=Exception, ValueError=ValueError, KeyError=KeyError)


def legacy(code, dfs):
    env = {"__builtins__": SAFE, "pd": pd, "np": np, "dfs": {k: v.copy() for k, v in dfs.items()}}
    exec(code, env)
    r = env.get("result")
    if isinstance(r, pd.Series):
        r = r.reset_index()
    if isinstance(r.columns, pd.MultiIndex):
        r.columns = ["_".join(map(str, c)) for c in r.columns]
    if not isinstance(r.index, pd.RangeIndex):
        r = r.reset_index()
    r.columns = [str(c) for c in r.columns]
    r = r.head(200).copy()
    for c in r.columns:                                          # sandbox đổi đối tượng date/Interval/Period trong cột object thành chuỗi (bản cũ để nguyên rồi bảng JSON in ra số khó đọc)
        if r[c].dtype.kind == "m":
            r[c] = r[c].astype(str)
        if r[c].dtype == object:
            r[c] = r[c].map(lambda v: v if v is None or isinstance(v, (str, int, float, bool, np.generic)) else str(v))
    return r.replace([np.inf, -np.inf], np.nan)      # JSON không có vô cực: bảng giao diện cũng vốn hiển thị nó là rỗng (df_table -> null)


rng = np.random.default_rng(7)
N = 3000
sales = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=N, freq="6h"), "region": rng.choice(["Bắc", "Trung", "Nam"], N),
                      "product": rng.choice(["A", "B", "C", "D"], N), "qty": rng.integers(1, 20, N), "revenue": rng.normal(100, 30, N).round(2),
                      "vip": rng.random(N) > 0.8, "note": rng.choice(["ok", None, "trễ hạn"], N)})
sales.loc[::53, "revenue"] = np.nan
cust = pd.DataFrame({"region": ["Bắc", "Trung", "Nam"], "manager": ["An", "Bình", "Chi"]})
DFS = {"sales": sales, "cust": cust}

# ============ 1) kết quả giống bản cũ ============
CASES = {
    "groupby + sort": "d = dfs['sales']\nresult = d.groupby('region', as_index=False)['revenue'].sum().sort_values('revenue', ascending=False)",
    "resample theo tháng (Series)": "d = dfs['sales']\nresult = d.set_index('date').resample('MS')['revenue'].sum()",
    "pivot_table": "result = dfs['sales'].pivot_table(index='region', columns='product', values='qty', aggfunc='sum')",
    "merge": "result = dfs['sales'].merge(dfs['cust'], on='region').groupby('manager', as_index=False)['qty'].sum()",
    "rolling + pct_change (có NaN)": "d = dfs['sales'].groupby('date')['revenue'].sum().reset_index()\nd['ma'] = d['revenue'].rolling(7).mean()\nd['g'] = d['revenue'].pct_change()\nresult = d.head(60)",
    "value_counts": "result = dfs['sales']['region'].value_counts()",
    "agg nhiều hàm (MultiIndex cột)": "result = dfs['sales'].groupby('region')[['qty','revenue']].agg(['sum','mean'])",
    "describe": "result = dfs['sales'][['qty','revenue']].describe()",
    "nlargest + str + apply": "d = dfs['sales'].nlargest(10, 'revenue').copy()\nd['label'] = d['region'].str.upper() + '-' + d['product']\nd['x'] = d['qty'].apply(lambda v: v * 2)\nresult = d[['label','x','vip','date']]",
    "melt": "result = dfs['sales'].head(20).melt(id_vars=['region'], value_vars=['qty','revenue'])",
    "np.where / log": "d = dfs['sales'].head(30).copy()\nd['flag'] = np.where(d['qty'] > 10, 'cao', 'thấp')\nd['l'] = np.log1p(d['qty'])\nresult = d[['flag','l']]",
    "rỗng": "d = dfs['sales']\nresult = d[d['qty'] > 10**9]",
    "quá 200 dòng": "result = dfs['sales'][['date','qty','revenue']]",
    "múi giờ + strftime": "d = dfs['sales'].head(5).copy()\nd['t'] = d['date'].dt.tz_localize('Asia/Ho_Chi_Minh').dt.strftime('%Y-%m-%d %H:%M')\nresult = d[['t']]",
    "corr": "result = dfs['sales'][['qty','revenue']].corr()",
    "get_dummies": "result = pd.get_dummies(dfs['sales'][['region']]).sum().reset_index()",
    "ewm theo ngày": "d = dfs['sales'].groupby(dfs['sales']['date'].dt.date)['revenue'].sum()\nresult = d.ewm(span=5).mean().reset_index().head(40)",
    "transform + rank": "d = dfs['sales'].copy()\nd['share'] = d['revenue'] / d.groupby('region')['revenue'].transform('sum')\nd['rk'] = d['revenue'].rank(ascending=False)\nresult = d.nlargest(5, 'share')[['region','share','rk']]",
    "regex str": "d = dfs['sales'].head(10).copy()\nd['n'] = d['note'].fillna('').str.replace(r'[aeiou]', '*', regex=True)\nresult = d[['n']]",
    "hồi quy dự báo (polyfit)": "d = dfs['sales']\ns = d.groupby(d['date'].dt.to_period('M').astype(str))['revenue'].sum().reset_index()\nx = np.arange(len(s))\nc = np.polyfit(x, s['revenue'], 1)\ns['fit'] = np.polyval(c, x)\nresult = s",
    "timedelta": "d = dfs['sales'].head(5).copy()\nd['dt'] = d['date'] - d['date'].min()\nresult = d[['dt']]",
    "crosstab chuẩn hóa": "result = pd.crosstab(dfs['sales']['region'], dfs['sales']['product'], normalize='index').round(3)",
    "thứ trong tuần": "result = dfs['sales']['date'].dt.dayofweek.value_counts().sort_index().reset_index()",
    "cumsum + diff": "d = dfs['sales'].groupby('region')['qty'].sum().sort_values().reset_index()\nd['c'] = d['qty'].cumsum()\nd['d'] = d['qty'].diff()\nresult = d",
    "print + f-string + format hằng": "print('xin chào')\nd = dfs['sales'].head(5).copy()\nd['s'] = d['revenue'].map('{:.1f}'.format)\nd['t'] = [f'{a}-{b}' for a, b in zip(d['region'], d['product'])]\nresult = d[['s','t']]",
}
for name, code in CASES.items():
    t0 = time.time()
    new, old = sb.run_code(code, DFS), legacy(code, DFS)
    try:
        pd.testing.assert_frame_equal(new.reset_index(drop=True).astype({c: object for c in new.columns if new[c].dtype == "string" or str(new[c].dtype) == "str"}),
                                      old.reset_index(drop=True).astype({c: object for c in old.columns if old[c].dtype == "string" or str(old[c].dtype) == "str"}),
                                      check_dtype=False, check_exact=False, rtol=1e-9, check_column_type=False, check_categorical=False)
        same = True
    except AssertionError as e:
        same = False
        print("    khác biệt:", str(e)[:300])
    kinds = {c: (new[c].dtype.kind, old[c].dtype.kind) for c in new.columns if new[c].dtype.kind in "iufbMm" or old[c].dtype.kind in "iufbMm"}
    check(same and all(a == b for a, b in kinds.values()), f"giống bản cũ về giá trị và kiểu số/ngày/bool: {name} ({time.time() - t0:.2f}s)")

q = "d = dfs['sales'].copy()\nd['nhóm'] = pd.qcut(d['revenue'], 4, duplicates='drop')\nresult = d.groupby('nhóm', observed=True)['qty'].sum().reset_index()"
r = sb.run_code(q, DFS)
check(len(r) == 4 and r["nhóm"].map(type).eq(str).all(), "qcut/Interval (cột categorical) được đổi thành chuỗi thay vì làm hỏng bảng")
dup = sb.run_code("result = pd.concat([dfs['sales'][['qty']], dfs['sales'][['qty']]], axis=1).head(3)", DFS)
check(list(dup.columns) == ["qty", "qty_2"], "tên cột trùng được đánh số lại")
check(err_of("result = dfs['sales']['khong_co']") == "KeyError: 'khong_co'", "lỗi code giữ đúng định dạng 'KeyError: ...' để AI tự sửa")
check("`result`" in err_of("x = 1"), "thiếu biến result: báo rõ")
check(err_of("result = (") .startswith("SyntaxError"), "lỗi cú pháp: báo SyntaxError")
check(sb.describe_error(sb.CodeError("abc")) == "abc" and sb.describe_error(KeyError("k")) == "KeyError: 'k'", "describe_error")
big = sb.run_code("result = pd.DataFrame({'a': ['x' * 10**6] * 200})", DFS) if False else None
check("quá lớn" in err_of("result = pd.DataFrame({'a': ['x' * 10**6] * 200})"), "kết quả khổng lồ bị từ chối gọn gàng")

# ============ 2) lớp kiểm tra cú pháp (ast) ============
BLOCK = {"import": "import os\nresult = dfs['sales']", "from-import": "from os import path\nresult = dfs['sales']", "thuộc tính riêng": "result = dfs['sales'].__class__",
         "thuộc tính _x": "result = dfs['sales']._data", "đọc tệp": "result = pd.read_csv('x.csv')", "ghi tệp": "dfs['sales'].to_csv('x.csv')\nresult = dfs['sales']",
         "getattr": "result = getattr(dfs['sales'], 'head')(3)", "eval": "result = eval('1')", "open": "result = open('x')", "pd.io": "result = pd.io.common.os",
         ".query": "result = dfs['sales'].query('qty > 3')", "np.load": "result = np.load('x.npy')", ".format đi sâu thuộc tính": "s = '{0.__class__}'.format(1)\nresult = dfs['sales']",
         ".format trên biến": "f = '{}'\ns = f.format(1)\nresult = dfs['sales']", "f-string vào thuộc tính riêng": "s = f'{dfs.__class__}'\nresult = dfs['sales']",
         "tên dunder": "__builtins__ = 1\nresult = dfs['sales']", ".os": "result = pd.io.common.os.getcwd()", "sys": "result = pd.compat.sys"}
for name, code in BLOCK.items():
    check("bị chặn" in (err_of(code) or ""), f"ast chặn: {name}")
check(err_of("result = dfs['sales'].head(2)") is None, "code hợp lệ không bị chặn nhầm")

# ============ 3) lớp trong: ngay cả khi lớp ast bị vượt qua (_check=False) ============
OS = "pd.io.common.os"
secret_file = os.path.join(tempfile.mkdtemp(), "bi_mat.txt")
open(secret_file, "w").write("NOI-DUNG-BI-MAT")
flag = "/tmp/mc_probe_flag_x"
if os.path.exists(flag):
    os.remove(flag)
e = err_of(f"{OS}.system('echo x > {flag}')\nresult = dfs['sales']", _check=False)
check("bị chặn" in (e or "") and not os.path.exists(flag), "hook chặn chạy lệnh hệ thống (os.system)")
e = err_of(f"{OS}.fork()\nresult = dfs['sales']", _check=False)
check("bị chặn" in (e or ""), "hook chặn tạo tiến trình mới (fork)")
e = err_of(f"fd = {OS}.open('{secret_file}', 0)\nresult = dfs['sales']", _check=False)
check("bị chặn" in (e or ""), "hook chặn đọc tệp ngoài thư viện Python (tệp bí mật)")
e = err_of(f"fd = {OS}.open('/proc/{os.getpid()}/environ', 0)\nresult = dfs['sales']", _check=False)
check("bị chặn" in (e or ""), "hook chặn đọc /proc/<pid máy chủ>/environ")
e = err_of(f"fd = {OS}.open('{flag}', 65)\nresult = dfs['sales']", _check=False)
check("bị chặn" in (e or "") and not os.path.exists(flag), "hook chặn ghi tệp ngoài thư mục tạm")
e = err_of(f"result = pd.DataFrame({{'f': {OS}.listdir('/')}})", _check=False)
check("bị chặn" in (e or ""), "hook chặn liệt kê thư mục gốc")
r = sb.run_code(f"result = pd.DataFrame({{'k': sorted({OS}.environ.keys())}})", DFS, _check=False)
check("MASTER_KEY_TEST_SECRET" not in " ".join(r["k"]) and "SECRET_KEY" not in r["k"].tolist() and "DATABASE_URL" not in r["k"].tolist(), "môi trường tiến trình con không có biến bí mật của server")
srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1); srv.settimeout(1.0); port = srv.getsockname()[1]
e = err_of(f"pd.io.common.urlopen('http://127.0.0.1:{port}/')\nresult = dfs['sales']", _check=False)
try:
    srv.accept()
    got = True
except socket.timeout:
    got = False
check("bị chặn" in (e or "") and not got, "hook chặn kết nối mạng (máy chủ thử không nhận được kết nối nào)")
srv.close()
r = sb.run_code(f"fd = {OS}.open('ghi_trong_thu_muc_tam.txt', 65)\n{OS}.write(fd, b'ok')\n{OS}.close(fd)\nresult = pd.DataFrame({{'ok': [1]}})", DFS, _check=False)
check(len(r) == 1, "ghi trong thư mục tạm riêng của lần chạy vẫn được phép")

# ============ 4) giới hạn tài nguyên ============
sb.config.SANDBOX_TIMEOUT = 3
t0 = time.time()
e = err_of("while True:\n    pass\nresult = dfs['sales']")
dt = time.time() - t0
check("quá 3 giây" in (e or "") and dt < 8, f"vòng lặp vô hạn bị dừng sau {dt:.1f}s")
time.sleep(0.3)
def workers():
    """Tiến trình sandbox thật = argv dạng [python, -S, -E, -B, .../sandbox_worker.py, job.json] (không khớp theo chuỗi để khỏi nhầm lệnh shell khác)."""
    out = []
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            argv = open(f"/proc/{pid}/cmdline", "rb").read().split(b"\0")
        except OSError:
            continue
        if len(argv) >= 6 and argv[1:4] == [b"-S", b"-E", b"-B"] and argv[4].endswith(b"sandbox_worker.py"):
            out.append(pid)
    return out


check(not workers(), "không còn tiến trình con nào sót lại sau khi bị giết")
sb.config.SANDBOX_TIMEOUT = 60
e = err_of("x = np.ones(10**10)\nresult = dfs['sales']")
check("bộ nhớ" in (e or ""), "xin cấp phát 80 GB: bị từ chối gọn gàng")
sb.config.SANDBOX_MEM_MB = 300
t0 = time.time()
e = err_of("l = []\nwhile True:\n    l.append(np.ones(2 * 10**7))\nresult = dfs['sales']")
check("bộ nhớ" in (e or "") and "300" in (e or "") or "bộ nhớ" in (e or ""), f"RAM tăng dần bị giết sau {time.time() - t0:.1f}s ({(e or '')[:60]}...)")
sb.config.SANDBOX_MEM_MB = 0
t0 = time.time()
e = err_of(f"o = {OS}\nfor i in range(100):\n    fd = o.open(f'f{{i}}', 65)\n    o.write(fd, b'x' * 60_000_000)\n    o.close(fd)\nresult = dfs['sales']", _check=False)
check("dữ liệu tạm" in (e or ""), f"ghi liên tục để đầy đĩa bị dừng sau {time.time() - t0:.1f}s")
check(sb.mem_limit_mb() >= 256, f"giới hạn RAM tự tính theo máy: {sb.mem_limit_mb()} MB")

# ============ 5) đồng thời, dọn dẹp, bận ============
before = set(glob.glob(os.path.join(tempfile.gettempdir(), "mc-sbx-*")))
active, peak, lock = [0], [0], threading.Lock()
orig_spawn = sb._spawn


def counting(*a, **k):
    with lock:
        active[0] += 1
        peak[0] = max(peak[0], active[0])
    try:
        return orig_spawn(*a, **k)
    finally:
        with lock:
            active[0] -= 1


sb._spawn = counting
sb._SLOTS = threading.BoundedSemaphore(2)
res = []
ths = [threading.Thread(target=lambda: res.append(len(sb.run_code("result = dfs['sales'].head(3)", DFS)))) for _ in range(6)]
[t.start() for t in ths]
[t.join() for t in ths]
check(res == [3] * 6 and peak[0] <= 2, f"6 yêu cầu cùng lúc: tất cả thành công, tối đa {peak[0]} sandbox chạy song song (giới hạn 2)")
sb._spawn = orig_spawn
sb._SLOTS = threading.BoundedSemaphore(1)
sb._SLOTS.acquire()
sb.SLOT_WAIT = 0.5
try:
    sb.run_code("result = dfs['sales'].head(1)", DFS)
    check(False, "hết chỗ phải báo bận")
except UserError as e:
    check("đang bận" in str(e), "đủ số sandbox đang chạy: báo bận bằng UserError (không bắt AI sửa code)")
sb._SLOTS = threading.BoundedSemaphore(2)
sb.SLOT_WAIT = 120
after = set(glob.glob(os.path.join(tempfile.gettempdir(), "mc-sbx-*")))
check(after == before, "không để lại thư mục tạm nào sau mọi lần chạy (kể cả lần bị giết)")

# ============ 6) tích hợp planner.execute ============
s = state.session_for(990)
state.bind(990)
state.A["clean"] = DFS
state.A["d"] = {3: {"phase": "menu", "tasks": [
    {"title": "Doanh thu theo vùng", "code": "result = dfs['sales'].groupby('region', as_index=False)['revenue'].sum()"},
    {"title": "Cột sai tên", "code": "result = dfs['sales'].groupby('khu_vuc', as_index=False)['revenue'].sum()"},
    {"title": "Cố import", "code": "import os\nresult = dfs['sales']"},
    {"title": "Hỏng mãi", "code": "result = dfs['sales']['khong_co']"}]}}
state.A["x"] = {}
fixes = []
FIX = "result = dfs['sales'].groupby('region', as_index=False)['qty'].sum()"
planner.llm = lambda system, user, *a, **k: (fixes.append(user), FIX if "khong_co" not in user else "result = dfs['sales']['khong_co']")[1]
planner.llm_json = lambda *a, **k: {"kpis": [], "charts": [], "findings": []}
planner.execute([], t0=0)
tabs = state.A["d"][3]["result"]["tables"]
check([t["err"] is None for t in tabs] == [True, True, True, False], "execute: 2 tác vụ lỗi/bị chặn được AI sửa; tác vụ hỏng mãi báo lỗi")
check(any("Code bị chặn vì chứa 'import'" in u for u in fixes) and any("KeyError: 'khu_vuc'" in u for u in fixes), "execute: AI nhận đúng thông báo lỗi (cả lỗi bị chặn lẫn lỗi pandas)")
check("KeyError: 'khong_co'" in tabs[3]["err"], "execute: lỗi cuối cùng hiện cho người dùng")
orig_run = planner.run_code
planner.run_code = lambda *a, **k: (_ for _ in ()).throw(UserError("Máy chủ đang bận"))
try:
    planner.execute([], t0=0)
    check(False, "UserError phải đi thẳng lên")
except UserError:
    check(True, "execute: lỗi hệ thống (bận) đi thẳng lên, không đốt lượt gọi AI để 'sửa code'")
planner.run_code = orig_run
state.unbind()

print(f"\nTẤT CẢ {n_ok} KIỂM TRA SANDBOX ĐỀU ĐẠT")
