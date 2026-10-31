# -*- coding: utf-8 -*-
"""Kiểm thử GIAO DIỆN bằng trình duyệt thật (Playwright + Chromium) với LLM giả: phân bố biến, ghép biến, ba pha bước Phân tích,
điều chỉnh (tự chạy lại, giữ lựa chọn), chọn biểu đồ dashboard (cập nhật ngay không tải lại), xem lại lịch sử (chỉ đọc).
Cần: pip install playwright && playwright install chromium. Không có thì bỏ qua (thoát mã 0).
Chạy: python tests/ui_test.py"""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("BỎ QUA  ui_test: chưa cài playwright"); sys.exit(0)
import _flow as F  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

fails = 0


def check(name, cond, extra=""):
    global fails
    print(("OK   " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    fails += 0 if cond else 1


app, _ = F.setup()
srv = make_server("127.0.0.1", 5079, app, threaded=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE, errs = "http://127.0.0.1:5079", []


def idle(pg, t=90):
    pg.wait_for_function("() => ST && !ST.job.running && !BUSY", timeout=t * 1000); pg.wait_for_timeout(200)


with sync_playwright() as p:
    try:
        b = p.chromium.launch()
    except Exception as e:                                       # noqa: BLE001
        print("BỎ QUA  ui_test: không mở được Chromium:", str(e)[:100]); sys.exit(0)
    ctx = b.new_context(viewport={"width": 1500, "height": 1000})
    assert ctx.request.post(BASE + "/api/auth/login", data={"email": "an@gmail.com", "password": "matkhau-123"}).ok
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_NAME_NOT_RESOLVED" not in m.text else None)
    pg.goto(BASE + "/"); pg.wait_for_selector("[data-a=sample]")
    pg.click("[data-a=sample]"); idle(pg); pg.fill("#q", "Khu vực nào bán tốt nhất?"); pg.click("[data-a=start]"); idle(pg)

    # ---- 3. phân bố từng biến
    pg.wait_for_selector(".dpn")
    n_all = pg.locator(".dc").count()
    check("phân bố: có thẻ cho từng biến của bảng đầu", n_all == 9, str(n_all))
    check("phân bố: biến định lượng có histogram, phân loại có thanh giá trị duy nhất", pg.locator(".dc svg.hs").count() >= 3 and pg.locator(".dc .cr").count() >= 6)
    pg.click("[data-dk='kind:cat']")
    check("phân bố: lọc theo loại biến", pg.locator(".dc").count() == 3 and pg.locator(".dc svg.hs").count() == 0)
    pg.click("[data-dk='kind:all']")
    pg.click("[data-a=ok]"); idle(pg); pg.click("[data-a=ok]"); idle(pg); pg.wait_for_selector(".a3b")

    # ---- 1. ghép biến bằng cách chọn
    check("ghép biến: chỉ số mặc định là cột tiền, chia theo biến phân loại", pg.locator("select[data-b=mcol0]").input_value() == "doanh_thu" and pg.locator("select[data-b=by0]").input_value() == "khu_vuc")
    pg.locator(".bch [data-v=khu_vuc]").click(); pg.wait_for_selector("#bprev .bpo b")
    check("ghép biến: hệ thống nói lại bằng một câu tiếng Việt", pg.locator("#bprev .bpo b").inner_text() == "Tổng doanh thu theo khu vực")
    pg.click("[data-a=badd]")
    pg.click("[data-a=btype][data-v=cross]"); pg.select_option("select[data-b=by1]", ""); pg.wait_for_timeout(500)
    check("ghép biến: thiếu biến thì báo lỗi và khóa nút Thêm", pg.locator("[data-a=badd]").is_disabled() and "hai biến" in pg.locator("#bprev").inner_text())
    # ---- 1. cách 2: mô tả bằng lời
    pg.click("[data-a=bmode][data-v=text]"); pg.fill("textarea[data-b=text]", "xu hướng theo tháng, thêm nhân sự")
    pg.click("[data-a=bparse]"); pg.wait_for_selector(".spc3 .srt.ai", timeout=20000)
    check("mô tả bằng lời: AI nhận diện thành thẻ, phần chưa rõ được tách riêng", pg.locator(".spc3").count() == 2 and "nhân sự" in pg.locator(".a3b .note").inner_text())

    # ---- 5. điều chỉnh: AI phớt lờ lần đầu -> tự chạy lại; lựa chọn đang chọn dở được giữ
    pg.uncheck("input[data-k=am1]"); pg.fill("textarea[data-i=anc]", "yêu cầu riêng của tôi")
    F.IGNORE["on"] = True
    pg.click("[data-a=adj]"); pg.fill("textarea[data-i=fbt]", "thêm phân tích theo kênh bán"); pg.click("[data-a=fbs]"); idle(pg, 120); pg.wait_for_selector(".adj")
    F.IGNORE["on"] = False
    check("điều chỉnh: banner xác nhận đã cập nhật, nói rõ đã tự áp dụng lại", "Đã cập nhật" in pg.locator(".adh b").inner_text() and "tự áp dụng lại" in pg.locator(".adj").inner_text())
    check("điều chỉnh: mục mới có thẻ Mới và được chọn sẵn", pg.locator(".mc3 .nw").count() == 1 and pg.locator(".mc3.on .nw").count() == 1)
    st = pg.evaluate("() => { const d = ST.d[3], s = sel(3); return { m1: s['a' + d.menu[1].id] ?? d.menu[1].recommended, specs: (s.specs || []).length, anc: s.anc } }")
    check("điều chỉnh: giữ lựa chọn bỏ chọn, ô ghép biến và yêu cầu riêng", st["m1"] is False and st["specs"] == 2 and st["anc"] == "yêu cầu riêng của tôi", str(st))

    # ---- 2. ba pha của bước Phân tích
    pg.click("[data-a=a3code]"); idle(pg); pg.wait_for_selector(".tk")
    check("pha code: mỗi phân tích có nguồn, mục đích và biến dùng", pg.locator(".tk").count() >= 3 and pg.locator(".tk .vcs").count() >= 3 and pg.locator(".tkh .srt.usr").count() == 2)
    pg.locator(".tk details summary").first.click(); ta = pg.locator("textarea[data-i=code0]").first; ta.fill(ta.input_value() + "\n# SỬA TAY")
    pg.click("[data-a=adj]"); pg.fill("textarea[data-i=fbt]", "đổi sang theo sản phẩm"); pg.click("[data-a=fbs]"); idle(pg, 120); pg.wait_for_selector(".adj")
    check("điều chỉnh pha code: code sửa tay đã tới AI", any("SỬA TAY" in u for r, u in F.PROMPTS if "Phân tích dữ liệu" in r))
    pg.click("[data-a=a3exec]"); idle(pg, 120); pg.wait_for_selector(".rc")
    check("pha kết quả: mỗi phân tích là một thẻ có điểm nổi bật, biểu đồ, bảng, biến dùng", pg.locator(".rc").count() >= 3 and pg.locator(".fx3 li").count() >= 3 and pg.locator(".rc table").count() >= 3 and pg.locator(".rc .vcs").count() >= 3)
    pg.click("[data-a=ok]"); idle(pg); pg.click("[data-a=ok]"); idle(pg); pg.wait_for_selector("#dpick")

    # ---- 4. chọn biểu đồ cho bảng điều khiển
    pg.wait_for_function("() => document.querySelector('iframe.dashf').contentDocument.querySelectorAll('#gr section.card').length > 0")
    cards = lambda: pg.evaluate("() => [...document.querySelector('iframe.dashf').contentDocument.querySelectorAll('#gr section.card .ch h3')].map(h => h.textContent).filter(t => t !== 'Bảng chi tiết')")  # noqa: E731
    n0 = len(cards())
    check("dashboard: hiện sẵn các biểu đồ AI gợi ý", n0 >= 5 and pg.locator(".dpc > div:first-child input[data-dp]:checked").count() == n0, str(n0))
    pg.evaluate("() => { document.querySelector('iframe.dashf').contentWindow.__m = 'giu' }")
    pg.locator(".dpc > div:first-child input[data-dp]").first.uncheck(); pg.wait_for_timeout(400)
    check("dashboard: tắt một biểu đồ -> cập nhật ngay, không tải lại khung", len(cards()) == n0 - 1 and pg.evaluate("() => document.querySelector('iframe.dashf').contentWindow.__m") == "giu")
    pg.select_option("select[data-dpb=by]", "d2"); pg.select_option("select[data-dpb=m]", ""); pg.select_option("select[data-dpb=kind]", "cols"); pg.click("[data-dpa=add]"); pg.wait_for_timeout(500)
    check("dashboard: biểu đồ bạn tự thêm hiện ra (cột dọc)", len(cards()) == n0 and pg.evaluate("() => document.querySelector('iframe.dashf').contentDocument.querySelectorAll('.cols .col').length") >= 3 and pg.locator(".dpc > div:nth-child(2) .dpi").count() == 1)
    pg.click("[data-a=ok]"); idle(pg); pg.click("[data-a=ok]"); idle(pg); pg.wait_for_selector(".dl")
    html = pg.evaluate("async () => (await fetch(document.querySelector('a[href$=\"dashboard.html\"]').href)).text()")
    check("dashboard xuất ra mang đúng lựa chọn (mục của bạn, mục đã tắt)", '"src":"user"' in html and '"on":false' in html)

    # ---- xem lại lịch sử (chỉ đọc)
    hid = pg.evaluate("() => ST.id")
    pg.evaluate("(id) => { const b = document.createElement('button'); b.dataset.a = 'viewh'; b.dataset.v = id; b.id = '__vh'; document.body.appendChild(b) }", hid)
    pg.click("#__vh"); pg.wait_for_timeout(1000); pg.click("[data-a=go][data-v='1']"); pg.wait_for_selector(".dpn")
    check("lịch sử: vẫn lọc được phân bố khi chỉ đọc", pg.evaluate("() => RO()") and not pg.locator("[data-dk='kind:cat']").is_disabled())
    pg.click("[data-a=go][data-v='5']"); pg.wait_for_timeout(400)
    check("lịch sử: không hiện bộ chọn biểu đồ khi chỉ đọc", pg.locator("#dpick").count() == 0)
    check("không có lỗi JavaScript nào trong toàn bộ phiên", not errs, str(errs[:3]))
    b.close()
srv.shutdown()
print(f"\n{'TẤT CẢ ĐẠT' if not fails else str(fails) + ' KIỂM TRA THẤT BẠI'}")
sys.exit(1 if fails else 0)
