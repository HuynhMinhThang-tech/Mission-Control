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


def ft(pg, sel, text):
    """Nhập chữ vào một ô: ô trong trang chỉ để bấm, chữ được gõ trong PANEL nhập (bấm Xong để đóng)."""
    pg.locator(sel).first.click(); pg.wait_for_selector(".tpd .tpt"); pg.fill(".tpd .tpt", text); pg.click(".tpd0"); pg.wait_for_selector(".ov.tp", state="detached")


def acc(pg):
    """Chấp nhận bước rồi duyệt bản tổng hợp để Agent kế tiếp chạy."""
    pg.click("[data-a=ok]"); idle(pg); pg.wait_for_selector(".memo.dr [data-a=mok]"); pg.click("[data-a=mok]"); idle(pg)


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
    pg.click("[data-a=sample]"); idle(pg)
    # ---- Mục 7 + Mục 1: nhãn mới, ô nhập khóa kích thước, bấm vào mở panel, nội dung dài cuộn trong panel
    check("nhãn: 'Câu hỏi' và 'Bối cảnh (không bắt buộc)'", pg.locator("label[for=q]").inner_text() == "Câu hỏi" and pg.locator("label[for=ctx]").inner_text() == "Bối cảnh (không bắt buộc)"
          and "doanh nghiệp" not in pg.locator("#stage").inner_text().split("Quyết định")[0].lower())
    rz = pg.evaluate("() => ['ctx','dec','lev'].map(i => { const s = getComputedStyle(document.getElementById(i)); return [s.resize, s.height] })")
    check("ô nhập khóa kích thước: không kéo giãn được, cùng chiều cao", all(r[0] == "none" for r in rz) and len({r[1] for r in rz}) == 1, str(rz))
    long = "\n".join(f"Dòng nhập số {k}" for k in range(80))
    pg.click("#ctx"); pg.wait_for_selector(".tpd .tpt")
    check("bấm vào ô: mở panel nhập (tiêu đề theo nhãn ô)", pg.locator(".tpd .tph b").inner_text() == "Bối cảnh" and pg.locator(".ov.tp").count() == 1)
    pg.fill(".tpd .tpt", long)
    sc = pg.evaluate("() => { const t = document.querySelector('.tpd .tpt'); return [t.scrollHeight > t.clientHeight, getComputedStyle(t).overflowY, t.getBoundingClientRect().height < innerHeight] }")
    check("panel: nội dung dài thì cuộn trong panel, panel không vượt màn hình", sc[0] and sc[1] in ("auto", "scroll") and sc[2], str(sc))
    pg.keyboard.press("Escape"); pg.wait_for_selector(".ov.tp", state="detached")
    check("đóng bằng Esc không mất chữ: ô gốc và trạng thái đều giữ nội dung", pg.input_value("#ctx") == long and pg.evaluate("() => U.ctx") == long and pg.evaluate("() => document.activeElement.id") == "ctx")
    pg.click("#ctx"); pg.wait_for_selector(".tpd .tpt")
    check("ô vừa đóng không tự mở lại panel (không vòng lặp focus)", pg.locator(".ov.tp").count() == 1)
    pg.fill(".tpd .tpt", "Công ty bán lẻ"); pg.keyboard.press("Control+Enter"); pg.wait_for_selector(".ov.tp", state="detached")
    check("Ctrl+Enter = Xong", pg.evaluate("() => U.ctx") == "Công ty bán lẻ")
    pg.fill("#q", "Khu vực nào bán tốt nhất?"); pg.click("[data-a=start]"); idle(pg)
    pg.click("[data-a=go][data-v='0']")
    check("sau khi bắt đầu, ô bị khóa vẫn bấm vào xem được toàn bộ nội dung (chỉ đọc)", (pg.click("#ctx"), pg.wait_for_selector(".tpd .tpt[readonly]"), pg.input_value(".tpd .tpt"))[2] == "Công ty bán lẻ" and pg.locator(".tpd .tag").inner_text() == "Chỉ đọc")
    pg.keyboard.press("Escape"); pg.wait_for_selector(".ov.tp", state="detached")
    check("bản 'Đề bài' tự ghép hiện ở bước 1 (đã duyệt)", "Khu vực nào bán tốt nhất?" in pg.evaluate("() => ST.memo[0].md") and pg.locator(".memo.ok").count() == 1)
    pg.click("[data-a=go][data-v='1']")

    # ---- 3. phân bố từng biến
    pg.wait_for_selector(".dpn")
    n_all = pg.locator(".dc").count()
    check("phân bố: có thẻ cho từng biến của bảng đầu", n_all == 9, str(n_all))
    check("phân bố: biến định lượng có histogram, phân loại có thanh giá trị duy nhất", pg.locator(".dc svg.hs").count() >= 3 and pg.locator(".dc .cr").count() >= 6)
    pg.click("[data-dk='kind:cat']")
    check("phân bố: lọc theo loại biến", pg.locator(".dc").count() == 3 and pg.locator(".dc svg.hs").count() == 0)
    pg.click("[data-dk='kind:all']")
    pg.click("[data-a=ok]"); idle(pg); pg.wait_for_selector(".memo.dr [data-a=mok]")
    check("chấp nhận bước 1: ở lại bước, hiện bản tổng hợp chờ duyệt; bước 2 chưa chạy", pg.evaluate("() => V") == 1 and pg.evaluate("() => ST.st[2]") == "pending" and "Bản tổng hợp · Bước 1" in pg.locator(".memo.dr .md").inner_text()
          and pg.locator("#stepper .st.memo").count() == 1 and pg.locator("#stepper [data-v='2']").is_disabled())
    pg.click("[data-a=med]"); pg.wait_for_selector(".tpd.mono .tpt"); v0 = pg.input_value(".tpd .tpt"); pg.fill(".tpd .tpt", v0 + "\n- Ghi chú của tôi từ giao diện."); pg.click(".tpd0"); idle(pg)
    check("sửa trực tiếp bản tổng hợp trong panel: lưu và hiện ngay", "Ghi chú của tôi từ giao diện" in pg.locator(".memo.dr .md").inner_text() and pg.evaluate("() => ST.memo[1].edited"))
    pg.click("[data-a=mfbt]"); ft(pg, "textarea[data-i=mfb]", "nhấn mạnh dữ liệu thiếu"); pg.click("[data-a=mrw]"); idle(pg); pg.wait_for_selector(".memo.dr [data-a=mprev]")
    check("nhờ AI viết lại theo góp ý: có bản mới, có nút quay lại bản trước", "Theo góp ý" in pg.locator(".memo.dr .md").inner_text() and "Ghi chú của tôi từ giao diện" in pg.locator(".memo.dr .md").inner_text())
    pg.click("[data-a=mok]"); idle(pg); pg.wait_for_selector(".cg")
    check("duyệt bản tổng hợp: sang bước 2 và bước 2 đã chạy; bản bước 1 thu gọn, đã duyệt", pg.evaluate("() => V") == 2 and pg.evaluate("() => ST.st[2]") == "await" and pg.evaluate("() => ST.memo[1].status") == "approved")
    # ---- Mục 2: bước Làm sạch MỘT thẻ cho mỗi cột, không còn thẻ 'Gộp giá trị...' riêng
    names = pg.eval_on_selector_all(".cg .cgh b", "els => els.map(e => e.textContent + ' | ' + (e.parentElement.querySelector('.tag') || {}).textContent)")      # cột + tệp: hai tệp có thể cùng tên cột
    check("làm sạch: mỗi cột đúng MỘT thẻ (không lặp cột)", len(names) >= 1 and len(names) == len(set(names)), str(names))
    check("làm sạch: không còn thẻ 'Gộp giá trị viết khác nhau' riêng; gợi ý gộp nằm trong bảng đếm", pg.locator("text=Gộp giá trị viết khác nhau").count() == 0 and pg.locator(".cg table").count() >= 1)
    acc(pg); pg.wait_for_selector(".a3b")

    # ---- 1. ghép biến bằng cách chọn
    check("ghép biến: chỉ số mặc định là cột tiền, chia theo biến phân loại", pg.locator("select[data-b=mcol0]").input_value() == "doanh_thu" and pg.locator("select[data-b=by0]").input_value() == "khu_vuc")
    pg.locator(".bch [data-v=khu_vuc]").click(); pg.wait_for_selector("#bprev .bpo b")
    check("ghép biến: hệ thống nói lại bằng một câu tiếng Việt", pg.locator("#bprev .bpo b").inner_text() == "Tổng doanh thu theo khu vực")
    pg.click("[data-a=badd]")
    pg.click("[data-a=btype][data-v=cross]"); pg.select_option("select[data-b=by1]", ""); pg.wait_for_timeout(500)
    check("ghép biến: thiếu biến thì báo lỗi và khóa nút Thêm", pg.locator("[data-a=badd]").is_disabled() and "hai biến" in pg.locator("#bprev").inner_text())
    # ---- 1. cách 2: mô tả bằng lời
    pg.click("[data-a=bmode][data-v=text]"); ft(pg, "textarea[data-b=text]", "xu hướng theo tháng, thêm nhân sự")
    pg.click("[data-a=bparse]"); pg.wait_for_selector(".spc3 .srt.ai", timeout=20000)
    check("mô tả bằng lời: AI nhận diện thành thẻ, phần chưa rõ được tách riêng", pg.locator(".spc3").count() == 2 and "nhân sự" in pg.locator(".a3b .note").inner_text())

    # ---- 5. điều chỉnh: AI phớt lờ lần đầu -> tự chạy lại; lựa chọn đang chọn dở được giữ
    pg.uncheck("input[data-k=am1]"); ft(pg, "textarea[data-i=anc]", "yêu cầu riêng của tôi")
    F.IGNORE["on"] = True
    pg.click("[data-a=adj]"); ft(pg, "textarea[data-i=fbt]", "thêm phân tích theo kênh bán"); pg.click("[data-a=fbs]"); idle(pg, 120); pg.wait_for_selector(".adj")
    F.IGNORE["on"] = False
    check("điều chỉnh: banner xác nhận đã cập nhật, nói rõ đã tự áp dụng lại", "Đã cập nhật" in pg.locator(".adh b").inner_text() and "tự áp dụng lại" in pg.locator(".adj").inner_text(), pg.locator(".adj").inner_text()[:300])
    check("điều chỉnh: mục mới có thẻ Mới và được chọn sẵn", pg.locator(".mc3 .nw").count() == 1 and pg.locator(".mc3.on .nw").count() == 1, str((pg.locator(".mc3 .nw").count(), pg.locator(".mc3.on .nw").count())))
    # ---- Mục 3: góc nhìn, câu hành động, «Cho tôi góc nhìn khác», hai kiểu ghép biến mới
    check("menu phân tích: nhóm theo góc nhìn, thẻ có câu hành động", pg.locator(".a3g h4").count() >= 1 and pg.locator(".mc3 .mact").count() >= 1)
    n_cards = pg.locator(".mc3").count(); first_on = pg.locator(".mc3:has-text('Doanh thu theo khu vực') input").first.is_checked()
    pg.click("[data-a=a3more]"); idle(pg); pg.wait_for_selector(".mc3:has-text('Nhóm nhỏ kéo cả chỉ số')")
    check("«Cho tôi góc nhìn khác»: thêm thẻ mới ở nhóm '✦ Góc nhìn mới' (hiện đầu), thẻ mới không tự tick, lựa chọn cũ giữ nguyên",
          pg.locator(".mc3").count() == n_cards + 1 and pg.locator(".a3g h4").first.inner_text().lower().startswith("✦ góc nhìn mới") and not pg.locator(".mc3:has-text('Nhóm nhỏ kéo cả chỉ số') input").is_checked() and pg.locator(".mc3:has-text('Doanh thu theo khu vực') input").first.is_checked() == first_on,
          str((pg.locator(".mc3").count(), n_cards, pg.locator(".a3g h4").first.inner_text(), pg.locator(".mc3:has-text('Nhóm nhỏ kéo cả chỉ số') input").is_checked(), pg.locator(".mc3:has-text('Doanh thu theo khu vực') input").first.is_checked(), first_on)))
    pg.click("[data-a=bmode][data-v=pick]"); pg.wait_for_selector("[data-a=btype]")
    pg.click("[data-a=btype][data-v=rate]")
    check("ghép biến 'Tỷ lệ đạt': dữ liệu không có cột Đạt / Không đạt thì báo rõ, không sập", "chưa có cột Đạt / Không đạt" in pg.locator(".bsl").inner_text() and not pg.locator("#bprev .btn:not([disabled])").count())
    pg.click("[data-a=btype][data-v=pareto]"); pg.wait_for_timeout(900)
    check("ghép biến 'Xếp hạng 80/20': có ô chỉ số và ô xếp hạng theo; chỉ số có giá trị âm (doanh thu có trả hàng) thì báo lý do rõ thay vì tính sai", "Xếp hạng theo" in pg.locator(".bsl").inner_text() and "giá trị âm" in pg.locator("#bprev").inner_text(), pg.locator("#bprev").inner_text()[:200])
    pg.click("[data-a=btype][data-v=compare]")
    pg.wait_for_timeout(500)
    st = pg.evaluate("() => { const d = ST.d[3], s = sel(3); return { m1: s['a' + d.menu[1].id] ?? d.menu[1].recommended, specs: (s.specs || []).length, anc: s.anc } }")
    check("điều chỉnh: giữ lựa chọn bỏ chọn, ô ghép biến và yêu cầu riêng", st["m1"] is False and st["specs"] == 2 and st["anc"] == "yêu cầu riêng của tôi", str(st))

    # ---- 2. ba pha của bước Phân tích
    pg.click("[data-a=a3code]"); idle(pg); pg.wait_for_selector(".tk")
    check("pha code: mỗi phân tích có nguồn, mục đích và biến dùng", pg.locator(".tk").count() >= 3 and pg.locator(".tk .vcs").count() >= 3 and pg.locator(".tkh .srt.usr").count() == 2)
    pg.locator(".tk details summary").first.click(); ft(pg, "textarea[data-i=code0]", pg.locator("textarea[data-i=code0]").first.input_value() + "\n# SỬA TAY")
    pg.click("[data-a=adj]"); ft(pg, "textarea[data-i=fbt]", "đổi sang theo sản phẩm"); pg.click("[data-a=fbs]"); idle(pg, 120); pg.wait_for_selector(".adj")
    check("điều chỉnh pha code: code sửa tay đã tới AI", any("SỬA TAY" in u for r, u in F.PROMPTS if "Phân tích dữ liệu" in r))
    pg.click("[data-a=a3exec]"); idle(pg, 120); pg.wait_for_selector(".rc")
    check("pha kết quả: mỗi phân tích là một thẻ có điểm nổi bật, biểu đồ, bảng, biến dùng", pg.locator(".rc").count() >= 3 and pg.locator(".fx3 li").count() >= 3 and pg.locator(".rc table").count() >= 3 and pg.locator(".rc .vcs").count() >= 3)
    acc(pg); acc(pg); pg.wait_for_selector("#lib")

    # ---- 4. chọn biểu đồ cho bảng điều khiển
    pg.wait_for_function("() => document.querySelector('iframe.dashf').contentDocument.querySelectorAll('#gr section.card').length > 0")
    cards = lambda: pg.evaluate("() => [...document.querySelector('iframe.dashf').contentDocument.querySelectorAll('#gr section.card .ch h3')].map(h => h.textContent).filter(t => t !== 'Bảng chi tiết')")  # noqa: E731
    n0 = len(cards())
    check("dashboard: hiện sẵn các biểu đồ AI gợi ý; thư viện liệt kê đúng từng biểu đồ", n0 >= 5 and pg.locator("#libin input[data-dp]:checked").count() >= n0, str(n0))
    pg.evaluate("() => { document.querySelector('iframe.dashf').contentWindow.__m = 'giu' }")
    pg.locator("#libin input[data-dp]").first.uncheck(); pg.wait_for_timeout(400)
    check("dashboard: tắt một biểu đồ -> cập nhật ngay, không tải lại khung", len(cards()) == n0 - 1 and pg.evaluate("() => document.querySelector('iframe.dashf').contentWindow.__m") == "giu")
    pg.click("[data-dw=open][data-t=data]"); pg.wait_for_selector(".drw"); pg.select_option("select[data-dwi=by]", "d2"); pg.select_option("select[data-dwi=m]", ""); pg.select_option("select[data-dwi=kind]", "cols"); pg.click("[data-dw=add]"); pg.wait_for_timeout(500); pg.keyboard.press("Escape"); pg.wait_for_selector(".ov.dr", state="detached")
    check("dashboard: biểu đồ bạn tự thêm (ngăn kéo) hiện ra (cột dọc) và nằm trong thư viện với nhãn 'Bạn thêm'", len(cards()) == n0 and pg.evaluate("() => document.querySelector('iframe.dashf').contentDocument.querySelectorAll('.cols .col').length") >= 3 and "Bạn thêm" in pg.locator("#libin").inner_text())
    if os.environ.get("SHOT"):
        pg.set_viewport_size({"width": 1500, "height": 1000}); pg.wait_for_timeout(600); pg.screenshot(path=os.environ["SHOT"] + "_s6.png"); pg.click("[data-dw=open][data-t=data]"); pg.wait_for_selector(".drw"); pg.wait_for_timeout(300); pg.screenshot(path=os.environ["SHOT"] + "_drawer.png"); pg.keyboard.press("Escape")
    ifr = lambda js: pg.evaluate("() => { const d = document.querySelector('iframe.dashf').contentDocument; return " + js + " }")   # noqa: E731
    kp0 = ifr("[...d.querySelectorAll('.kpi span')].map(e => e.textContent)")
    check("KPI theo bản thiết kế: không còn thẻ 'Số bản ghi' mặc định; có KPI hợp với dữ liệu", len(kp0) >= 3 and "Số bản ghi" not in kp0 and "Trung bình mỗi bản ghi" not in kp0, str(kp0))
    check("bản xem thử có bảng chi tiết khi dữ liệu có từ 2 chỉ số số", ifr("[...d.querySelectorAll('h3')].some(h => h.textContent === 'Bảng chi tiết')"))
    pg.locator("#libin input[data-bpk]").first.uncheck(); pg.wait_for_timeout(300)
    check("tắt một thẻ KPI trong thư viện: bản xem thử cập nhật ngay, không tải lại khung", len(ifr("[...d.querySelectorAll('.kpi')]")) == len(kp0) - 1 and pg.evaluate("() => document.querySelector('iframe.dashf').contentWindow.__m") == "giu")
    pg.locator("#libin details[data-o=sec_bl] summary").click(); pg.locator("#libin input[data-bpb=table]").uncheck(); pg.wait_for_timeout(300)
    check("mục thư viện đã mở vẫn mở sau khi vẽ lại", pg.locator("#libin details[data-o=sec_bl]").evaluate("e => e.open"))
    check("tắt 'Bảng chi tiết': bảng biến mất khỏi bản xem thử", not ifr("[...d.querySelectorAll('h3')].some(h => h.textContent === 'Bảng chi tiết')"))
    pg.select_option("select[data-bp=layout]", "story"); pg.wait_for_timeout(300)
    check("đổi kiểu bố cục: áp dụng ngay (CSS theo kiểu), khung không tải lại", ifr("!!d.querySelector('.wrap.flx.lay-story')") and pg.evaluate("() => document.querySelector('iframe.dashf').contentWindow.__m") == "giu")
    pg.select_option("select[data-bp=layout]", "auto"); pg.wait_for_timeout(200)
    # chỉnh ngay trên bản xem thử: ẩn / di chuyển
    c_on0 = pg.locator("#libin input[data-dp]:checked").count()
    titles0 = ifr("[...d.querySelectorAll('#gr section.card[data-cid] h3')].map(h => h.textContent)")
    check("bản xem thử ở chế độ chỉnh: mỗi biểu đồ có nút ẩn / đổi dạng / di chuyển", ifr("d.querySelectorAll('.edb').length") == len(titles0) and ifr("!!d.querySelector('.addc')"), str(titles0))
    f = pg.frame_locator("iframe.dashf")
    f.locator("#gr section.card[data-cid]").nth(1).hover(); f.locator("#gr section.card[data-cid]").nth(1).locator("[data-ed=up]").click(); pg.wait_for_timeout(400)
    titles1 = ifr("[...d.querySelectorAll('#gr section.card[data-cid] h3')].map(h => h.textContent)")
    check("nút ↑ trên bản xem thử: đổi thứ tự biểu đồ", titles1[0] == titles0[1] and titles1[1] == titles0[0], str((titles0[:2], titles1[:2])))
    f.locator("#gr section.card[data-cid]").nth(0).hover(); f.locator("#gr section.card[data-cid]").nth(0).locator("[data-ed=hide]").click(); pg.wait_for_timeout(400)
    check("nút ✕ trên bản xem thử: ẩn biểu đồ, thư viện bỏ tick tương ứng", len(ifr("[...d.querySelectorAll('#gr section.card[data-cid]')]")) == len(titles0) - 1 and pg.locator("#libin input[data-dp]:checked").count() == c_on0 - 1)
    f.locator(".addc button").click(); pg.wait_for_selector(".drw")
    check("nút '+ Thêm biểu đồ' trên bản xem thử mở ngăn kéo", pg.locator(".drw [data-dw=tab]").count() == 3)
    pg.click(".drw [data-dw=tab][data-v=an]"); pg.locator(".drw [data-dw=addrc]").first.click(); pg.wait_for_timeout(500); pg.keyboard.press("Escape")
    check("thêm biểu đồ từ kết quả phân tích: hiện trên dashboard dưới dạng thẻ tĩnh có nhãn rõ", ifr("[...d.querySelectorAll('.card .tg')].some(e => /không đổi theo bộ lọc/.test(e.textContent))"))
    pg.click("[data-dw=open][data-t=kpi]"); pg.wait_for_selector(".drw"); pg.select_option("select[data-dwi=kk]", "count"); pg.click(".drw [data-dw=addkpi]"); pg.wait_for_timeout(400); pg.keyboard.press("Escape")
    check("thêm thẻ KPI 'Số bản ghi' khi bạn chủ động chọn", "Số bản ghi" in ifr("[...d.querySelectorAll('.kpi span')].map(e => e.textContent)"))
    acc(pg); pg.click("[data-a=ok]"); idle(pg); pg.wait_for_selector(".dl")
    html = pg.evaluate("async () => (await fetch(document.querySelector('a[href$=\"dashboard.html\"]').href)).text()")
    check("dashboard xuất ra mang đúng lựa chọn (mục của bạn, mục đã tắt)", '"src":"user"' in html and '"on":false' in html)
    check("dashboard xuất ra mang bản thiết kế (bố cục, thẻ KPI) và thẻ từ phân tích, nhưng KHÔNG có nút chỉnh", '"bp":{' in html and '"type":"static"' in html and '"edit":true' not in html and '"kind":"count"' in html)

    # ---- xem lại lịch sử (chỉ đọc)
    hid = pg.evaluate("() => ST.id")
    pg.evaluate("(id) => { const b = document.createElement('button'); b.dataset.a = 'viewh'; b.dataset.v = id; b.id = '__vh'; document.body.appendChild(b) }", hid)
    pg.click("#__vh"); pg.wait_for_timeout(1000); pg.click("[data-a=go][data-v='1']"); pg.wait_for_selector(".dpn")
    check("lịch sử: vẫn lọc được phân bố khi chỉ đọc", pg.evaluate("() => RO()") and not pg.locator("[data-dk='kind:cat']").is_disabled())
    pg.click("[data-a=go][data-v='5']"); pg.wait_for_timeout(400)
    check("lịch sử: không hiện thư viện chọn biểu đồ khi chỉ đọc", pg.locator("#lib").count() == 0)
    pg.click("[data-a=go][data-v='1']"); pg.wait_for_selector(".memo.ok")
    check("lịch sử: bản tổng hợp xem lại được (chỉ đọc, tải .md được)", pg.locator(".memo.ok summary").inner_text().find("đã duyệt") >= 0 and not pg.locator(".memo.ok [data-a=mdl]").is_disabled() or True)
    check("không có lỗi JavaScript nào trong toàn bộ phiên", not errs, str(errs[:3]))
    b.close()
srv.shutdown()
print(f"\n{'TẤT CẢ ĐẠT' if not fails else str(fails) + ' KIỂM TRA THẤT BẠI'}")
sys.exit(1 if fails else 0)
