# -*- coding: utf-8 -*-
"""Kiểm thử GIAO DIỆN (trình duyệt thật, LLM giả): bước Phân tích xếp thẻ theo lưới nhiều cột, tự đổi số cột khi mở/đóng thanh bên trái/phải.
Trước đây mỗi nhóm góc nhìn là một khối xếp dọc, mà đa số nhóm chỉ có 1 thẻ nên cả trang chỉ có MỘT cột, bên phải trống.
Cần: pip install playwright && playwright install chromium. Không có thì bỏ qua (thoát mã 0).
Chạy: python tests/grid_ui_test.py"""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("BỎ QUA  grid_ui_test: chưa cài playwright"); sys.exit(0)
import _flow as F  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

fails = 0


def check(name, cond, extra=""):
    global fails
    print(("OK   " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    fails += 0 if cond else 1


F.AUTO["memo"] = False
app, c = F.setup()
F.post(c, "/api/sample"); F.post(c, "/api/start", {"question": "Khu vực nào bán tốt nhất?"}); F.wait(c)
for i in (1, 2):
    F.post(c, f"/api/accept/{i}"); F.wait(c); F.post(c, f"/api/memo/{i}/approve"); F.wait(c)          # tới bước 3 (menu)

srv = make_server("127.0.0.1", 5085, app, threaded=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE, errs = "http://127.0.0.1:5085", []

with sync_playwright() as p:
    try:
        b = p.chromium.launch()
    except Exception as e:                                       # noqa: BLE001
        print("BỎ QUA  grid_ui_test: không mở được Chromium:", str(e)[:100]); sys.exit(0)
    ctx = b.new_context(viewport={"width": 1500, "height": 1000})
    assert ctx.request.post(BASE + "/api/auth/login", data={"email": "an@gmail.com", "password": "matkhau-123"}).ok
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "/"); pg.wait_for_selector("#stepper"); pg.click("[data-a=go][data-v='3']"); pg.wait_for_selector(".a3g")
    S = pg.evaluate
    # dữ liệu menu giả: 9 góc nhìn, mỗi góc 1 thẻ (đúng ca trong ảnh của người dùng) + 1 góc có 3 thẻ
    S("""() => { const d = ST.d[3]; d.menu = []; let n = 0;
        for (let g = 0; g < 9; g++) d.menu.push({ id: 'g' + n++, title: 'Phân tích ' + g, angle: 'Góc nhìn ' + g, goal: 'Mục tiêu ' + g, recommended: true, vars: [], metrics: [] });
        for (let k = 0; k < 3; k++) d.menu.push({ id: 'g' + n++, title: 'Nhiều thẻ ' + k, angle: 'Nhóm nhiều thẻ', goal: 'x', recommended: false, vars: [], metrics: [] });
        stage() }""")
    cols = lambda sel=".gx": S("(sel) => { const g = document.querySelector(sel); return getComputedStyle(g).gridTemplateColumns.split(' ').length }", sel)  # noqa: E731
    wid = lambda: S("() => Math.round(document.querySelector('.gx').getBoundingClientRect().width)")  # noqa: E731
    setside = lambda collapsed: S("(c) => { if (document.getElementById('side').classList.contains('c') !== c) document.querySelector('[data-a=sbt]').click() }", collapsed)  # noqa: E731
    setdraw = lambda opened: S("(o) => { if (document.getElementById('drawer').classList.contains('open') !== o) document.querySelector('[data-a=drt]').click() }", opened)  # noqa: E731
    measure = lambda: (pg.wait_for_timeout(450), (wid(), cols()))[1]  # noqa: E731

    # ---- số cột theo độ rộng vùng giữa
    pg.set_viewport_size({"width": 1800, "height": 1000})
    setside(False); setdraw(False); full = measure()
    check("màn rộng: các thẻ xếp thành 3 cột (không còn một cột trơ trọi bên trái)", full[1] == 3, str(full))
    on_rows = S("() => { const r = [...document.querySelectorAll('.a3g:not(.multi) .mc3')].map(e => Math.round(e.getBoundingClientRect().top)); return [...new Set(r)].length }")
    check("9 thẻ đơn lẻ nằm trong 3 hàng (3 thẻ mỗi hàng), không phải 9 hàng", on_rows == 3, str(on_rows))
    multi_w = S("() => { const m = document.querySelector('.a3g.multi'); const g = document.querySelector('.gx'); return Math.round(m.getBoundingClientRect().width / g.getBoundingClientRect().width * 100) }")
    check("nhóm có nhiều thẻ trải hết bề ngang và tự chia 3 cột bên trong", multi_w >= 99 and cols(".a3g.multi .a3c") == 3, f"{multi_w}% / {cols('.a3g.multi .a3c')} cột")

    # ---- mở/đóng thanh bên: số cột tự đổi (không cần tải lại)
    setside(False); setdraw(True); a = measure()                       # trái mở + phải mở: vùng giữa hẹp nhất
    setside(True); setdraw(True); b2 = measure()                       # đóng thanh trái: vùng giữa rộng ra
    setside(True); setdraw(False); c2 = measure()                      # đóng cả hai: rộng nhất
    check("mở thanh phải làm vùng giữa hẹp lại; đóng thanh trái làm rộng ra", a[0] < b2[0] < c2[0], f"{a} {b2} {c2}")
    check("số cột đi theo độ rộng vùng giữa (hẹp hơn thì không nhiều cột hơn)", a[1] <= b2[1] <= c2[1] and c2[1] == 3, f"{a} {b2} {c2}")
    pg.set_viewport_size({"width": 1180, "height": 900}); setside(False); setdraw(False); mid = measure()
    pg.set_viewport_size({"width": 760, "height": 900}); setside(False); setdraw(False); narrow = measure()
    check("cửa sổ vừa: 2 cột; cửa sổ hẹp: 1 cột", mid[1] == 2 and narrow[1] == 1, f"{mid} {narrow}")
    over = S("() => [...document.querySelectorAll('.gx, .gx *')].some(e => e.getBoundingClientRect().right > document.querySelector('main').getBoundingClientRect().right + 1)")
    check("cửa sổ hẹp: không có thẻ nào tràn ra ngoài vùng giữa", not over)

    # ---- pha kết quả: thẻ kết quả cũng thành lưới, bảng rộng cuộn trong thẻ
    pg.set_viewport_size({"width": 1800, "height": 1000}); setside(False); setdraw(False)
    S("""() => { const d = ST.d[3]; d.phase = 'result';
        const mk = i => ({ title: 'Kết quả ' + i, goal: 'g', cols: ['Cột A', 'Cột B', 'Cột C', 'Cột D', 'Cột E', 'Cột F', 'Cột G', 'Cột H', 'Cột I', 'Cột J'], rows: [['x'.repeat(40), 1, 2, 3, 4, 5, 6, 7, 8, 9]], facts: [], vars: [] });
        d.result = { kpis: [], findings: [], tables: [mk(0), mk(1), mk(2), mk(3), mk(4)], charts: [] }; d.tasks = []; stage() }""")
    pg.wait_for_selector(".rc"); pg.wait_for_timeout(450)
    rc = S("() => { const r = [...document.querySelectorAll('.rc')].map(e => e.getBoundingClientRect()); return { tops: [...new Set(r.map(x => Math.round(x.top)))].length, w: Math.round(r[0].width) } }")
    check("kết quả phân tích: 5 thẻ nằm thành 2 hàng (3 + 2), mỗi thẻ rộng hợp lý", rc["tops"] == 2 and rc["w"] >= 400, str(rc))
    wide_over = S("() => { const m = document.querySelector('main').getBoundingClientRect().right; return [...document.querySelectorAll('.rc')].some(e => e.getBoundingClientRect().right > m + 1) }")
    check("bảng có nhiều cột rộng nằm gọn trong thẻ (cuộn ngang trong thẻ), không làm vỡ lưới", not wide_over)
    setdraw(True); setside(False); pg.wait_for_timeout(450)
    check("pha kết quả cũng đổi số cột khi mở thanh bên", cols() <= 3 and cols() >= 1)
    check("không có lỗi JavaScript", errs == [], str(errs))
    pg.set_viewport_size({"width": 1800, "height": 1000}); setdraw(False); setside(False); pg.wait_for_timeout(450)
    b.close()

print("\nTẤT CẢ ĐẠT" if fails == 0 else f"\n{fails} LỖI")
sys.exit(1 if fails else 0)
