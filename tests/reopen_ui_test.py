# -*- coding: utf-8 -*-
"""Kiểm thử GIAO DIỆN (trình duyệt thật, LLM giả): chọn sai biểu đồ ở bước Báo cáo thì chọn lại được.
Trước đây: bấm "Chấp nhận" thì trang cuộn thẳng tới bản tổng hợp (có mục KPI), lối quay lại chỉ là nút mờ "Làm lại từ bước này" ở đáy,
bước 6 không có lối quay lại, và sau khi TẢI LẠI TRANG thì lựa chọn đã chốt mất, quay về mặc định của AI.
Cần: pip install playwright && playwright install chromium. Không có thì bỏ qua (thoát mã 0).
Chạy: python tests/reopen_ui_test.py"""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("BỎ QUA  reopen_ui_test: chưa cài playwright"); sys.exit(0)
import _flow as F  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

fails = 0


def check(name, cond, extra=""):
    global fails
    print(("OK   " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    fails += 0 if cond else 1


F.AUTO["memo"] = False                                   # tự bấm duyệt bản tổng hợp trên giao diện
app, c = F.setup()
# đi tới bước 5 bằng API (nhanh); trình duyệt dùng chung trạng thái của người dùng này
F.post(c, "/api/sample"); F.post(c, "/api/start", {"question": "Khu vực nào bán tốt nhất?"}); F.wait(c)
for i in (1, 2):
    F.post(c, f"/api/accept/{i}"); F.wait(c); F.post(c, f"/api/memo/{i}/approve"); F.wait(c)
F.post(c, "/api/a3/code", {"ids": ["m0"], "custom": "", "specs": []}); F.wait(c)
F.post(c, "/api/a3/exec", {"codes": []}); F.wait(c, 120)
for i in (3, 4):
    F.post(c, f"/api/accept/{i}"); F.wait(c); F.post(c, f"/api/memo/{i}/approve"); F.wait(c)

srv = make_server("127.0.0.1", 5083, app, threaded=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE, errs = "http://127.0.0.1:5083", []


def idle(pg, t=90):
    pg.wait_for_function("() => ST && !ST.job.running && !BUSY", timeout=t * 1000); pg.wait_for_timeout(200)


with sync_playwright() as p:
    try:
        b = p.chromium.launch()
    except Exception as e:                                       # noqa: BLE001
        print("BỎ QUA  reopen_ui_test: không mở được Chromium:", str(e)[:100]); sys.exit(0)
    ctx = b.new_context(viewport={"width": 1500, "height": 1000})
    assert ctx.request.post(BASE + "/api/auth/login", data={"email": "an@gmail.com", "password": "matkhau-123"}).ok
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_NAME_NOT_RESOLVED" not in m.text else None)
    pg.goto(BASE + "/"); pg.wait_for_selector("#stepper"); pg.click("[data-a=go][data-v='5']"); pg.wait_for_selector("#libin input[data-dp]")
    S = pg.evaluate
    st = lambda: S("() => ({V, st5: ST.st[5], st6: ST.st[6], memo5: (ST.memo[5] || {}).status, lib: !!document.getElementById('lib'), btns: [...document.querySelectorAll('#stage button[data-a]')].map(b => b.dataset.a + ':' + b.textContent.trim())})")  # noqa: E731
    ticks = lambda: S("() => [...document.querySelectorAll('#libin input[data-dp]')].map(i => i.checked)")  # noqa: E731
    ticks0 = ticks()

    # ---- chọn "sai" một biểu đồ rồi chấp nhận
    pg.locator("#libin input[data-dp]").first.uncheck(); pg.wait_for_timeout(300)
    chosen = ticks()
    check("chọn biểu đồ: có thay đổi so với mặc định của AI", chosen != ticks0)
    pg.click("[data-a=ok]"); idle(pg); pg.wait_for_selector(".memo.draft [data-a=mok]")
    check("sau 'Chấp nhận': bản tổng hợp có nút 'Chọn lại biểu đồ' ngay cạnh nút Duyệt", pg.locator(".memo.draft [data-a=reopen]").inner_text() == "Chọn lại biểu đồ" and "Chọn lại biểu đồ" in pg.locator(".memo.draft .sub").inner_text(), str(st()))

    # ---- tải lại trang (mất bộ nhớ lựa chọn của trình duyệt) rồi chọn lại
    pg.reload(); pg.wait_for_selector("#stepper"); pg.wait_for_function("() => ST"); pg.click("[data-a=go][data-v='5']"); pg.wait_for_selector(".memo.draft [data-a=reopen]")
    pg.click(".memo.draft [data-a=reopen]"); idle(pg); pg.wait_for_selector("#libin input[data-dp]")
    s1 = st()
    check("bấm 'Chọn lại biểu đồ': bước 5 mở lại (chờ bạn), có thư viện biểu đồ; bước 6 chưa chạy; bản tổng hợp bước 5 bỏ", s1["V"] == 5 and s1["st5"] == "await" and s1["lib"] and s1["st6"] == "pending" and s1["memo5"] is None, str(s1))
    check("sau khi TẢI LẠI TRANG: lựa chọn biểu đồ đã chốt được giữ, không quay về mặc định của AI", ticks() == chosen, str((ticks(), chosen)))

    # ---- chọn lại đúng, đi tới bước 6
    pg.locator("#libin input[data-dp]").first.check(); pg.wait_for_timeout(300)
    pg.click("[data-a=ok]"); idle(pg); pg.wait_for_selector(".memo.draft [data-a=mok]"); pg.click("[data-a=mok]"); idle(pg)
    s2 = st()
    check("bước 6: có nút 'Chọn lại biểu đồ' cạnh 'Duyệt báo cáo'", s2["V"] == 6 and "reopen:Chọn lại biểu đồ" in s2["btns"] and "ok:Duyệt báo cáo" in s2["btns"], str(s2))
    pg.click("[data-a=reopen][data-v='5']"); idle(pg); pg.wait_for_selector("#libin input[data-dp]")
    s3 = st()
    check("từ bước 6 bấm 'Chọn lại biểu đồ': về bước Báo cáo đang chọn, lựa chọn vừa chốt còn nguyên", s3["V"] == 5 and s3["st5"] == "await" and ticks() == ticks0, str((s3, ticks(), ticks0)))

    # ---- nhãn nút ở bước đã xong; sau khi duyệt báo cáo thì khóa
    pg.click("[data-a=ok]"); idle(pg); pg.wait_for_selector(".memo.draft [data-a=mok]"); pg.click("[data-a=mok]"); idle(pg)
    pg.click("[data-a=go][data-v='5']"); pg.wait_for_timeout(300)
    check("bước 5 đã xong: nút ở đáy là 'Chọn lại biểu đồ' (không còn 'Làm lại từ bước này' dễ hiểu nhầm là chạy lại AI)", pg.locator("#stage > .card > .act [data-a=reopen]").inner_text() == "Chọn lại biểu đồ" and pg.locator("[data-a=redo]").count() == 0)
    pg.click("[data-a=go][data-v='4']"); pg.wait_for_timeout(300)
    check("các bước khác đã xong: nút 'Mở lại bước này để chỉnh'", pg.locator("#stage > .card > .act [data-a=reopen]").inner_text() == "Mở lại bước này để chỉnh")
    pg.click("[data-a=go][data-v='6']"); pg.wait_for_timeout(200); pg.click("[data-a=ok]"); idle(pg); pg.wait_for_selector(".dl")
    pg.click("[data-a=go][data-v='5']"); pg.wait_for_timeout(300)
    check("sau khi DUYỆT báo cáo (đã xuất): không còn nút mở lại (đã khóa)", pg.locator("[data-a=reopen]").count() == 0 and pg.locator("[data-a=redo]").count() == 0)
    check("không có lỗi JavaScript trong toàn bộ phiên", errs == [], str(errs))
    b.close()

print("\nTẤT CẢ ĐẠT" if fails == 0 else f"\n{fails} LỖI")
sys.exit(1 if fails else 0)
