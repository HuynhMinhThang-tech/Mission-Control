# -*- coding: utf-8 -*-
"""Kiểm thử BẢN TỔNG HỢP sau mỗi bước (cổng duyệt giữa hai Agent) với LLM giả, không cần key.
Chạy: python tests/memo_test.py"""
import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _flow as F  # noqa: E402

fails = 0


def check(name, cond, extra=""):
    global fails
    print(("OK   " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    fails += 0 if cond else 1


F.AUTO["memo"] = False                                   # test CHÍNH cổng duyệt: không tự duyệt hộ
app, c = F.setup()
state = lambda: c.get("/api/state").get_json()           # noqa: E731
last_prompt = lambda role: [u for r, u in F.PROMPTS if role in r][-1]   # noqa: E731

F.post(c, "/api/sample")
F.post(c, "/api/start", {"question": "Khu vực nào bán tốt nhất?", "ctx": "Công ty bán lẻ", "decision": "Tăng ngân sách ở đâu?"})
s = F.wait(c)
m0 = s["memo"]["0"]
check("bước 0: bản 'Đề bài' tự ghép (đã duyệt, không chặn) gồm câu hỏi, bối cảnh, quyết định, dữ liệu",
      m0["status"] == "approved" and "Khu vực nào bán tốt nhất?" in m0["md"] and "Công ty bán lẻ" in m0["md"] and "Tăng ngân sách ở đâu?" in m0["md"] and "## Dữ liệu" in m0["md"])

# ---------------------------------------------------------------- chấp nhận bước 1 -> viết bản tổng hợp, CHƯA chạy bước 2
F.post(c, "/api/accept/1")
s = F.wait(c)
m1 = s["memo"]["1"]
check("chấp nhận bước 1: có bản tổng hợp chờ duyệt, bước 1 xong nhưng bước 2 CHƯA chạy", s["st"][1] == "done" and s["st"][2] == "pending" and m1["status"] == "draft" and "2" not in s["d"])
check("bản tổng hợp: phần ghi nhận do code ghép (quy mô, nhận định, vấn đề)", m1["md"].startswith("# Bản tổng hợp · Bước 1") and "## Quy mô dữ liệu" in m1["md"] and "## Nhận định về dữ liệu" in m1["md"])
check("AI chỉ viết 'Lưu ý cho bước sau'; câu có số bịa (999.999) bị bỏ, câu không số được giữ",
      "## Lưu ý cho bước sau" in m1["md"] and "cần thận trọng khi tính trung bình" in m1["md"] and "999.999" not in m1["md"])
check("chưa duyệt thì không chạy được bước 2 bằng đường khác", F.post(c, "/api/run/2", {}, ok=False).status_code in (200, 400, 409) and state()["memo"]["1"]["status"] == "draft")
F.wait(c)

# ---------------------------------------------------------------- sửa tay + cảnh báo số lạ
mine = m1["md"].replace("## Lưu ý cho bước sau", "## Lưu ý cho bước sau\n- Bộ phận Y tế dự phòng là nguồn dữ liệu chính, đừng gộp với Ngoại khoa; số mẫu 123.456.789.")
r = F.post(c, "/api/memo/1/save", {"md": mine})
m1 = state()["memo"]["1"]
check("sửa tay: lưu được, đánh dấu đã sửa, cảnh báo số lạ không có trong ghi nhận (123.456.789)", m1["edited"] and "123.456.789" in m1["warn"] and "Y tế dự phòng" in m1["md"], str(m1.get("warn")))
check("sửa tay: bản trống bị từ chối", F.post(c, "/api/memo/1/save", {"md": "  "}, ok=False).status_code == 400)

# ---------------------------------------------------------------- nhờ AI viết lại theo góp ý
check("nhờ AI viết lại: bắt buộc nêu góp ý", F.post(c, "/api/memo/1/rewrite", {"feedback": ""}, ok=False).status_code == 400)
F.post(c, "/api/memo/1/rewrite", {"feedback": "nhấn mạnh cột doanh thu"})
s = F.wait(c)
m1 = s["memo"]["1"]
check("nhờ AI viết lại: có bản mới theo góp ý, GIỮ phần bạn đã sửa, lưu bản trước để quay lại", "Theo góp ý" in m1["md"] and "nhấn mạnh cột doanh thu" in m1["md"] and "Y tế dự phòng" in m1["md"] and "Y tế dự phòng" in m1["prev"] and m1["status"] == "draft")

# ---------------------------------------------------------------- duyệt -> Agent bước 2 chạy và NHẬN bản tổng hợp làm ngữ cảnh
F.post(c, "/api/memo/1/approve")
s = F.wait(c)
check("duyệt bản tổng hợp: bước 2 mới chạy xong và chờ bạn", s["memo"]["1"]["status"] == "approved" and s["st"][2] == "await")
p2 = last_prompt("Agent Làm sạch")
check("Agent bước 2 nhận bản tổng hợp đã duyệt (kể cả phần bạn sửa) trong ngữ cảnh", "BẢN TỔNG HỢP CÁC BƯỚC TRƯỚC" in p2 and "Y tế dự phòng" in p2 and "Bước 1: Kiểm tra và mô tả dữ liệu" in p2)
check("prompt vẫn đủ nhãn mới 'Câu hỏi:' / 'Bối cảnh:' và dòng góp ý ở cuối", "Câu hỏi: Khu vực nào bán tốt nhất?" in p2 and "Bối cảnh: Công ty bán lẻ" in p2 and "Góp ý của người dùng: không" in p2)
check("đã duyệt thì khóa: không sửa, không duyệt lại", F.post(c, "/api/memo/1/save", {"md": "x" * 50}, ok=False).status_code == 409 and F.post(c, "/api/memo/1/approve", ok=False).status_code == 409)

# ---------------------------------------------------------------- bước 2: bản tổng hợp ghi lựa chọn làm sạch
F.post(c, "/api/accept/2")
s = F.wait(c)
m2 = s["memo"]["2"]
check("bước 2: bản tổng hợp ghi thao tác đã áp dụng và dữ liệu sau làm sạch", m2["status"] == "draft" and "## Thao tác làm sạch đã áp dụng" in m2["md"] and "## Dữ liệu sau làm sạch" in m2["md"] and "dòng ×" in m2["md"])
F.post(c, "/api/memo/2/approve")
s = F.wait(c)
check("bước 3 nhận cả hai bản đã duyệt (bước 1 và 2)", "Bước 2: Làm sạch dữ liệu" in last_prompt("Agent Hoạch định") and "Y tế dự phòng" in last_prompt("Agent Hoạch định"))

# ---------------------------------------------------------------- làm lại từ bước 1 -> bản tổng hợp từ bước 1 trở đi bị xóa
F.post(c, "/api/redo/2")
s = state()
check("làm lại từ bước 2: bản của bước 2 trở đi bị xóa, bản bước 1 còn", "2" not in s["memo"] and s["memo"]["1"]["status"] == "approved" and s["st"][2] == "await")

# ---------------------------------------------------------------- đi trọn tới hết, kiểm tra xuất file và lịch sử
F.AUTO["memo"] = True
F.post(c, "/api/accept/2")
s = F.wait(c)
F.post(c, "/api/a3/code", {"ids": [m["id"] for m in s["d"]["3"]["menu"]], "custom": "", "specs": []})     # bước 3 gồm 3 chặng: chọn mục -> sinh code -> chạy
F.wait(c)
F.post(c, "/api/a3/exec", {"codes": []})
F.wait(c, 120)
F.post(c, "/api/accept/3")
s = F.wait(c)
F.post(c, "/api/accept/4")
s = F.wait(c)
d5 = s["d"]["5"]
F.post(c, "/api/accept/5", {"title": "Báo cáo", "charts": d5["charts"], "kpis": [0], "dash": d5["dash"]["ai"]})
s = F.wait(c)
check("bước 6 (rà soát) có dòng kiểm 'bản tổng hợp đã duyệt 5/5'", any("5/5" in x and "tổng hợp" in x for x in s["d"]["6"]["checks"]), str(s["d"]["6"]["checks"]))
F.post(c, "/api/accept/6")
s = F.wait(c)
check("duyệt xong", s["approved"])
z = zipfile.ZipFile(io.BytesIO(c.get(f"/api/download/{s['id']}/share.zip").get_data()))
names = [n for n in z.namelist() if n.startswith("tong_hop/")]
check("share.zip có thư mục tong_hop/ cho đề bài và 5 bước", names == [f"tong_hop/{k}" for k in ("00_de_bai.md", "01_buoc_1.md", "02_buoc_2.md", "03_buoc_3.md", "04_buoc_4.md", "05_buoc_5.md")], str(names))
check("tệp ZIP của bước 1 chứa đúng bản đã sửa", "Y tế dự phòng" in z.read("tong_hop/01_buoc_1.md").decode("utf-8"))
snap = c.get(f"/api/history/{s['id']}").get_json()
check("lịch sử (chỉ đọc) lưu đủ các bản tổng hợp", set(snap["memo"]) == {"0", "1", "2", "3", "4", "5"} and all(m["status"] == "approved" for m in snap["memo"].values()))

print(f"\n{'TẤT CẢ ĐẠT' if not fails else str(fails) + ' KIỂM TRA THẤT BẠI'}")
sys.exit(1 if fails else 0)
