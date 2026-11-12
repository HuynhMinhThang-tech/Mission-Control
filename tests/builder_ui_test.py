# -*- coding: utf-8 -*-
"""Kiểm thử GIAO DIỆN (trình duyệt thật, LLM giả) với tệp Excel 4 sheet:
  1. Bước Kiểm tra: KPI, danh sách bảng, cột ngày có vai trò, xem nhanh từng sheet, tab phân bố mang TÊN SHEET (không phải tên tệp).
  2. Bước Làm sạch: bảng đếm giá trị dài (mã sản phẩm) cao tối đa ~12 dòng và cuộn trong bảng.
  3. Bước Phân tích: thẻ đề xuất cao bằng nhau, thẻ dài cuộn trong thẻ.
  4. Bộ ghép biến mới: hai khung biến, chọn biến từ NHIỀU sheet, gợi ý cách xem, hệ thống tự nối bảng, chạy tới kết quả và khớp pandas.
Cần: pip install playwright openpyxl && playwright install chromium. Không có thì bỏ qua (thoát mã 0).  Chạy: python tests/builder_ui_test.py"""
import io
import json
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("BỎ QUA  builder_ui_test: chưa cài playwright"); sys.exit(0)
import _flow as F  # noqa: E402
from _sheets import NAME, SHEETS, make_xlsx  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

fails = 0


def check(name, cond, extra=""):
    global fails
    print(("OK   " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    fails += 0 if cond else 1


F.AUTO["memo"] = False
app, c = F.setup()
blob, T = make_xlsx()
c.post("/api/upload", data={"files": (io.BytesIO(blob), NAME), "sheets": json.dumps({NAME: SHEETS})}, content_type="multipart/form-data")
F.post(c, "/api/start", {"question": "Doanh thu theo nhóm khách hàng và sản phẩm?"}); F.wait(c)
srv = make_server("127.0.0.1", 5093, app, threaded=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE, errs = "http://127.0.0.1:5093", []


def idle(pg, t=90):
    pg.wait_for_function("() => ST && !ST.job.running && !BUSY", timeout=t * 1000); pg.wait_for_timeout(250)


with sync_playwright() as p:
    try:
        b = p.chromium.launch()
    except Exception as e:                                       # noqa: BLE001
        print("BỎ QUA  builder_ui_test: không mở được Chromium:", str(e)[:100]); sys.exit(0)
    ctx = b.new_context(viewport={"width": 1700, "height": 1000})
    assert ctx.request.post(BASE + "/api/auth/login", data={"email": "an@gmail.com", "password": "matkhau-123"}).ok
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_NAME_NOT_RESOLVED" not in m.text else None)
    pg.goto(BASE + "/"); pg.wait_for_selector("#stepper"); pg.wait_for_function("() => ST && ST.st[1] === 'await'"); pg.click("[data-a=go][data-v='1']"); pg.wait_for_selector(".ovw")
    txt = lambda sel: pg.locator(sel).inner_text()  # noqa: E731

    # ============ 1. bước Kiểm tra và mô tả
    kp = txt("#stage .kpis")
    check("KPI nói đủ 4 bảng, 8.888 dòng, tổng 19 cột (không chỉ bảng lớn nhất)", all(x in kp for x in ("4\nSố bảng", "8.888", "Tổng số dòng", "19", "Tổng số cột")), kp[:200])
    check("KPI 'Kỳ dữ liệu' là NGÀY ĐẶT của bảng DonHang, không phải ngày sinh khách hàng", "Kỳ dữ liệu" in kp and "Ngày đặt · DonHang" in kp and "1955" not in kp and "1956" not in kp, kp)
    tb = pg.locator(".ovw").first
    check("danh sách bảng: 4 dòng, đúng số dòng/số cột từng bảng, nêu liên kết giữa các bảng", tb.locator("tbody tr").count() == 4 and "5.320" in tb.inner_text() and "→ DonHang" in tb.inner_text() and "(MaKH)" in tb.inner_text(), tb.inner_text()[:300])
    dts = pg.locator(".ovw:has(h3:has-text('Các cột ngày'))")
    check("cột ngày: 3 cột, mỗi cột ghi vai trò; ngày sinh / đăng ký ghi 'không dùng làm kỳ'; chỉ ngày đặt là 'Kỳ của dữ liệu'",
          dts.locator("tbody tr").count() == 3 and dts.locator("tr:has-text('Ngày sinh') >> text=Thuộc tính, không dùng làm kỳ").count() >= 1 and dts.locator("tr:has-text('Ngày đăng ký') >> text=Thuộc tính").count() >= 1
          and dts.locator("tr:has-text('Ngày đặt') >> text=Kỳ của dữ liệu").count() == 1, dts.inner_text()[:400])
    seg = pg.locator(".dfl:has-text('Xem nhanh từng bảng') .seg button")
    check("xem nhanh: một nút cho mỗi sheet, mang tên sheet", seg.all_inner_texts() == SHEETS, str(seg.all_inner_texts()))
    pg.click(".dfl:has-text('Xem nhanh từng bảng') .seg button:has-text('KhachHang')"); pg.wait_for_timeout(200)
    smp = pg.locator(".ovw:has(.dfl:has-text('Xem nhanh từng bảng'))")
    check("chọn sheet KhachHang: hiện đúng cột và dữ liệu của sheet đó", "HoTen" in smp.inner_text() and "ThanhPho" in smp.inner_text() and "MaSP" not in smp.locator("thead").inner_text(), smp.locator("thead").inner_text())
    dist_tabs = pg.locator(".dpn .seg").first.locator("button")
    labels = dist_tabs.evaluate_all("els => els.map(e => e.childNodes[0].textContent.trim())")
    check("Phân bố từng biến: 4 tab mang TÊN SHEET (trước đây cả 4 tab cùng là tên tệp)", labels == SHEETS and len(set(labels)) == 4, str(labels))
    pg.click(".dpn .seg >> nth=0 >> button:has-text('KhachHang')"); pg.wait_for_timeout(300)
    check("thẻ biến Thời gian của Ngày sinh / Ngày đăng ký có nhãn 'không phải kỳ dữ liệu'", pg.locator(".dpn .tag.w[title*='không phải thời gian']").count() >= 2, str(pg.locator(".dpn .tag.w").count()))

    # ============ 2. bước Làm sạch: bảng đếm giá trị dài cuộn trong khung
    F.post(c, "/api/accept/1"); F.wait(c); F.post(c, "/api/memo/1/approve"); F.wait(c)
    pg.reload(); pg.wait_for_selector("#stepper"); pg.wait_for_function("() => ST && ST.st[2] === 'await'"); pg.click("[data-a=go][data-v='2']"); pg.wait_for_selector(".cg", state="attached")
    pg.evaluate("() => { document.querySelectorAll('#stage details').forEach(d => d.open = true) }"); pg.wait_for_timeout(300)
    vc = pg.evaluate("""() => [...document.querySelectorAll('.cg')].filter(e => e.querySelector('.vcd .tw')).map(e => { const t = e.querySelector('.vcd .tw'); const h = e.querySelector('.vcs-hint');
        return { col: e.querySelector('b').textContent, rows: t.querySelectorAll('tbody tr').length, h: Math.round(t.getBoundingClientRect().height), scroll: t.scrollHeight > t.clientHeight + 2, hint: h ? h.textContent : '' } })""")
    masp = [x for x in vc if x["col"] == "MaSP"][0]
    check("cột MaSP (40 giá trị hiện): bảng cao tối đa ~12 dòng (≤ 600px) và CUỘN trong bảng, có dòng hướng dẫn", masp["rows"] == 40 and masp["h"] <= 600 and masp["scroll"] and "cuộn trong bảng" in masp["hint"], str(masp))
    small = [x for x in vc if x["col"] == "PhuongThuc"][0]
    check("cột ít giá trị (PhuongThuc: 3 giá trị): bảng giữ nguyên chiều cao, không có thanh cuộn thừa", not small["scroll"] and small["h"] < 300 and not small["hint"], str(small))
    pos = pg.evaluate("() => { const e = [...document.querySelectorAll('.cg')].find(x => x.querySelector('b').textContent === 'MaSP').querySelector('.vcd .tw'); e.scrollTop = 9999; return e.scrollTop > 0 }")
    check("cuộn trong bảng đếm giá trị chạy được (xem hết mọi dòng)", pos)

    # ============ 3. bước Phân tích
    F.post(c, "/api/accept/2"); F.wait(c); F.post(c, "/api/memo/2/approve"); F.wait(c)
    pg.reload(); pg.wait_for_selector("#stepper"); pg.wait_for_function("() => ST && ST.st[3] === 'await'"); pg.click("[data-a=go][data-v='3']"); pg.wait_for_selector(".a3b")
    LONG = " Nếu thấy mục này cao hơn hẳn các mục còn lại, hãy cân nhắc điều chỉnh chiến lược và theo dõi kỹ theo từng tuần để có phản ứng kịp thời." * 4
    pg.evaluate("""(LONG) => { const d = ST.d[3]; d.menu = ['Top sản phẩm', 'Lợi nhuận danh mục', 'Chi tiết danh mục', 'Pareto', 'Số lượng', 'Thương hiệu'].map((t, i) => ({ id: 'g' + i, title: t, angle: 'Góc ' + i, goal: 'Xác định ' + t,
        action: i % 2 ? 'Ngắn.' : LONG, recommended: true, vars: ['MaSP', 'ThanhTien'], metrics: ['Tổng doanh thu = SUM(ThanhTien)'], why: i === 2 ? LONG : '' })); stage() }""", LONG)
    pg.wait_for_timeout(300)
    hs = pg.evaluate("() => [...document.querySelectorAll('.mc3')].map(e => Math.round(e.getBoundingClientRect().height))")
    sc = pg.evaluate("() => [...document.querySelectorAll('.mc3 .mcb')].map(e => e.scrollHeight > e.clientHeight + 2)")
    check("thẻ phân tích đề xuất: MỌI thẻ cao bằng nhau dù nội dung dài ngắn khác nhau", len(hs) == 6 and len(set(hs)) == 1, str(hs))
    check("thẻ có nội dung dài thì cuộn trong thẻ, thẻ ngắn không có thanh cuộn", sc[0] and not sc[1] and sc[2], str(sc))

    # ============ 4. bộ ghép biến: nhiều sheet
    pg.reload(); pg.wait_for_selector("#stepper"); pg.wait_for_function("() => ST && ST.st[3] === 'await'"); pg.click("[data-a=go][data-v='3']"); pg.wait_for_selector(".a3b")
    pick = lambda role, tbl, col: pg.click(f"[data-a=bvar][data-v*='\"{role}\"'][data-v*='{tbl}'][data-v*='\"{col}\"']")  # noqa: E731
    left, right = pg.locator(".bpanel").nth(0), pg.locator(".bpanel").nth(1)
    check("hai khung: trái = phân loại + thời gian, phải = định lượng; biến xếp theo từng sheet", "Biến phân loại và thời gian" in left.inner_text() and "Biến định lượng" in right.inner_text()
          and all(x in left.inner_text() for x in ("DonHang", "KhachHang", "SanPham")) and "Đếm số bản ghi" in right.inner_text() and "Thành tiền" in right.inner_text())
    check("khung trái có các biến thời gian; ngày sinh / đăng ký được ghi chú ngay trên chip", left.locator("button:has-text('Ngày sinh') i").inner_text() == "ngày sinh" and left.locator("button:has-text('Ngày đặt') i").inner_text() == "thời gian")
    check("hiện các liên kết giữa bảng: ChiTietDonHang → DonHang (MaDH)...", "ChiTietDonHang → DonHang" in pg.locator(".brl").inner_text() and "(MaSP)" in pg.locator(".brl").inner_text())
    pg.fill("input[data-b=q]", "thành"); pg.wait_for_timeout(250)
    f1 = (left.locator("button.bv").all_inner_texts(), right.locator("button.bv").all_inner_texts())
    check("ô tìm biến lọc cả hai khung (gõ 'thành' còn Thành phố | Thành tiền)", len(f1[0]) == 1 and "Thành phố" in f1[0][0] and len(f1[1]) == 1 and "Thành tiền" in f1[1][0], str(f1))
    pg.fill("input[data-b=q]", ""); pg.wait_for_timeout(250)

    pick("meas", "ChiTietDonHang", "ThanhTien"); pick("dim", "SanPham", "DanhMuc"); pick("dim", "KhachHang", "ThanhPho"); pg.wait_for_selector("#bprev .bpo b")
    check("chọn biến ở 3 sheet khác nhau: thanh 'Đang chọn' liệt kê đủ, kèm sheet của từng biến", pg.locator(".bsc").count() == 3 and "SanPham" in pg.locator("#bsel").inner_text() and "KhachHang" in pg.locator("#bsel").inner_text())
    check("hệ thống gợi ý 'Chéo hai biến phân loại' (có nhãn Gợi ý)", pg.locator("[data-a=btype].on").get_attribute("data-v") == "cross" and "Gợi ý" in pg.locator("[data-a=btype].on").inner_text())
    prev = pg.locator("#bprev").inner_text()
    check("bản xem trước nói rõ tự nối bảng nào theo khóa nào", "Tổng thành tiền: danh mục × thành phố" in prev and "Hệ thống tự nối bảng «ChiTietDonHang»" in prev and "(theo MaSP)" in prev and "(theo MaKH)" in prev, prev)
    check("kiểu chưa đủ biến bị mờ kèm lý do (Tương quan, Xu hướng, Tỷ lệ đạt)", all(pg.locator(f"[data-a=btype][data-v={k}]").is_disabled() for k in ("correlate", "trend", "rate")) and "2 biến định lượng" in pg.locator("[data-a=btype][data-v=correlate]").inner_text())
    pg.select_option("#bsel select[data-b=agg]", "mean"); pg.wait_for_timeout(700)
    check("đổi cách tính sang Trung bình: bản xem trước cập nhật", "Trung bình thành tiền" in pg.locator("#bprev").inner_text(), pg.locator("#bprev").inner_text()[:160])
    pg.select_option("#bsel select[data-b=agg]", "sum"); pg.wait_for_timeout(600)
    pick("dim", "DonHang", "NgayDat"); pg.wait_for_timeout(700)
    check("thêm biến thời gian (Ngày đặt ở bảng DonHang): gợi ý chuyển sang 'Xu hướng theo thời gian', có chọn đơn vị tháng/quý", pg.locator("[data-a=btype].on").get_attribute("data-v") == "trend" and pg.locator("#bgr .seg button").count() >= 3)
    pick("dim", "DonHang", "NgayDat"); pg.wait_for_timeout(500)                    # bỏ chọn
    pg.click("[data-a=btype][data-v=compare]"); pg.wait_for_timeout(600)
    check("tự chọn kiểu khác gợi ý: kiểu đang chọn không còn nhãn 'Gợi ý'", pg.locator("[data-a=btype].on").get_attribute("data-v") == "compare" and "Gợi ý" not in pg.locator("[data-a=btype].on").inner_text())
    pg.click("[data-a=btype][data-v=cross]"); pg.wait_for_timeout(500)
    pg.click("[data-a=badd]"); pg.wait_for_selector(".spc3")
    check("Thêm vào danh sách: thẻ phân tích tự ghép có câu mô tả phép nối", pg.locator(".spc3").count() == 1 and "Hệ thống tự nối bảng" in pg.locator(".spc3").inner_text(), pg.locator(".spc3").inner_text()[:200])

    # lỗi nối ngược chiều
    pg.click("[data-a=bclear]"); pg.wait_for_timeout(300)
    pick("meas", "SanPham", "GiaVon"); pick("dim", "DonHang", "PhuongThuc"); pg.wait_for_timeout(900)
    check("chỉ số ở bảng danh mục chia theo cột bảng đơn hàng: hệ thống TỪ CHỐI, nói vì sao, khóa nút Thêm", "tính lặp" in pg.locator("#bprev").inner_text() and pg.locator("[data-a=badd]").is_disabled(), pg.locator("#bprev").inner_text()[:200])
    pg.click("[data-a=bclear]"); pg.wait_for_timeout(300)
    check("'Xóa chọn' dọn sạch lựa chọn", pg.locator(".bsc").count() == 0 and pg.locator("[data-a=badd]").is_disabled())

    # chạy tới kết quả, so với pandas
    pg.click("[data-a=a3sel][data-v=none]"); pg.click("[data-a=a3code]"); idle(pg); pg.wait_for_selector(".tk")
    code = pg.evaluate("() => ST.d[3].tasks[0].code")
    check("pha code: phân tích tự ghép có code nối bảng rõ ràng (3 phép merge)", code.count(".merge(") == 3 and "drop_duplicates" in code, code[:300])
    pg.click("[data-a=a3exec]"); idle(pg, 120); pg.wait_for_selector(".rc")
    tb = pg.evaluate("() => { const t = ST.d[3].result.tables[0]; return { title: t.title, cols: t.cols, rows: t.rows } }")
    ct, sp, dh, kh = T["ct"], T["sp"], T["dh"], T["kh"]
    m = ct.merge(sp[["MaSP", "DanhMuc"]], on="MaSP").merge(dh[["MaDH", "MaKH"]], on="MaDH").merge(kh[["MaKH", "ThanhPho"]], on="MaKH")
    exp = m.groupby(["DanhMuc", "ThanhPho"])["ThanhTien"].sum()
    cities = tb["cols"][1:]                                       # kiểu «Chéo»: hàng = danh mục, mỗi cột là một thành phố
    got = {(r[0], city): float(v) for r in tb["rows"] for city, v in zip(cities, r[1:]) if city != "Tổng"}
    check("KẾT QUẢ THẬT của phân tích ghép từ 3 sheet: bảng ma trận Danh mục × từng thành phố", tb["cols"][0] == "Danh mục" and {"DN", "HCM", "HN"} <= set(cities), str(tb["cols"]))
    check(f"từng ô khớp pandas tính tay ({len(exp)} ô danh mục × thành phố) và tổng bảo toàn", len(got) == len(exp) and all(abs(got[k] - exp[k]) < 1 for k in exp.index) and abs(sum(got.values()) - ct["ThanhTien"].sum()) < 5, f"{len(got)}/{len(exp)}")
    check("không có lỗi JavaScript trong toàn bộ phiên", errs == [], str(errs))
    b.close()

print("\nTẤT CẢ ĐẠT" if fails == 0 else f"\n{fails} LỖI")
sys.exit(1 if fails else 0)
