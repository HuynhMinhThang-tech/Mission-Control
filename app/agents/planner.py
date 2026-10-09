# -*- coding: utf-8 -*-
"""AGENT 3 · Hoạch định phân tích → viết code pandas → tổng hợp kết quả (bước 4)."""
from ..data.quality import schema
from ..data.sandbox import describe_error, df_table, prepare, run_code
from ..errors import UserError
from ..llm import llm, llm_json, strip_code
from ..state import A, LOCK, bump, next_gen, put, tick
from ..utils import J
from .base import SYS, ctx_txt, prev
from .charts import is_num, valid_charts

ROLE_PLAN = "Agent Hoạch định phân tích"
ROLE_CODE = "Agent Phân tích dữ liệu (pandas)"
ROLE_FIX = "lập trình viên pandas"
ROLE_SUM = "Agent Tổng hợp kết quả phân tích"

PROMPT_MENU = (
    "Hãy ĐỀ XUẤT 6-10 phân tích / chỉ số ứng viên để NGƯỜI DÙNG TỰ CHỌN (chưa viết code). Gồm mô tả (điều gì đã xảy ra), "
    "chẩn đoán (vì sao, phân rã theo khu vực/sản phẩm...), và nếu có cột thời gian thì thêm 1 mục dự báo kỳ kế tiếp "
    "(hồi quy tuyến tính/trung bình trượt, có khoảng tin cậy). "
    'Trả về DUY NHẤT JSON: {"menu":[{"title":"...","goal":"trả lời điều gì","metrics":["tên chỉ số = công thức cụ thể"],'
    '"why":"vì sao liên quan tới câu hỏi","recommended":true}]}')

PROMPT_CODE = (
    'Viết code cho TỪNG mục (đúng thứ tự, thêm 1 mục riêng cho yêu cầu bổ sung nếu có). Trả về DUY NHẤT JSON: {"tasks":[{"title":"...","goal":"...","code":"..."}]}\n'
    "Mỗi code: Python pandas/numpy (đã có pd, np, dfs), KHÔNG import, KHÔNG đọc/ghi file, KHÔNG dùng .query()/.eval()/thuộc tính bắt đầu bằng gạch dưới (dùng lọc bool df[df['x']>0]); kết quả gán vào biến `result` là DataFrame đã tổng hợp "
    "(<=50 dòng, tên cột rõ ràng; mục dự báo trả cột kỳ, dự báo, cận dưới, cận trên). Truy cập bằng dfs['tên file'].")

PROMPT_SUM = (
    'Trả về DUY NHẤT JSON: {"kpis":[{"label":"","value":"","delta":""}],"charts":[{"task":<số thứ tự bảng>,"x":"cột nhãn","y":"cột số","kind":"bars|cols|line|donut","title":"","unit":""}],'
    '"findings":[{"tag":"Mô tả|Chẩn đoán|Dự báo|Lưu ý","text":"có số liệu"}]}\n'
    "3-6 KPI: value/delta lấy hoặc tính trực tiếp từ bảng, không bịa. 3-5 biểu đồ, ĐA DẠNG loại và KHÔNG trùng nhau (mỗi biểu đồ một bảng/cột khác). kind: 'line' cho chuỗi thời gian; 'bars' xếp hạng/so sánh nhiều nhóm; 'cols' so sánh ít nhóm; 'donut' cơ cấu tỷ trọng (<=7 phần, giá trị không âm). x,y phải là tên cột có thật.")


def menu(fb=""):
    tick(0)
    r = llm_json(SYS(ROLE_PLAN), ctx_txt(fb) + prev(3, fb, 3500) + f"Dữ liệu đã làm sạch:\n{J(schema(A['clean'], 3), 6000)}\n\n" + PROMPT_MENU
                 + ("\nNgười dùng đã góp ý: hãy ĐIỀU CHỈNH danh sách theo đúng góp ý (thêm/bớt/đổi mục), giữ các mục không liên quan." if fb else ""))
    items = r["menu"]
    for k, m in enumerate(items):
        m["id"] = f"m{k}"
    put(3, {"phase": "menu", "menu": items, "tasks": None, "result": None})


def write_code(ids, custom, fb="", t0=0):
    tick(t0)
    d = A["d"][3]
    items = [m for m in d["menu"] if m["id"] in ids]
    old = ""
    if fb and d.get("tasks"):
        old = (f"CODE LẦN TRƯỚC:\n{J([{'title': t['title'], 'code': t['code']} for t in d['tasks']], 5000)}\n"
               f"NGƯỜI DÙNG GÓP Ý: {fb}\nHãy SỬA code/cách tính theo đúng góp ý (đổi chỉ số, nhóm theo cột khác, lọc, thêm/bớt mục...), giữ phần không bị góp ý.\n")
    r = llm_json(SYS(ROLE_CODE),
                 ctx_txt(fb) + f"Dữ liệu đã làm sạch (biến `dfs` là dict tên file→DataFrame):\n{J(schema(A['clean'], 3), 6000)}\n"
                 f"Các phân tích người dùng đã chọn:\n{J(items)}\nYêu cầu bổ sung của người dùng: {custom or 'không'}\n{old}\n" + PROMPT_CODE, 12000)
    tasks = [t for t in r.get("tasks", []) if isinstance(t, dict) and t.get("code")]
    if not tasks:
        raise RuntimeError("AI không trả về code nào. Hãy bấm Thử lại hoặc mô tả góp ý rõ hơn.")
    with LOCK:
        d["tasks"] = tasks
        d["ids"], d["custom"] = list(ids), custom
        d["phase"] = "code"
        d["result"] = None
        d["gen"] = next_gen()
        bump()


def revise(fb):
    """Góp ý ở bước Phân tích: áp vào ĐÚNG pha đang xem. Pha kết quả -> viết lại code rồi chạy lại luôn."""
    d = A["d"].get(3) or {}
    ph = d.get("phase", "menu")
    if ph == "menu" or not d.get("tasks"):
        return menu(fb)
    write_code(d.get("ids", []), d.get("custom", ""), fb, t0=1)
    if ph == "result":
        execute([], t0=2)


def labels_for(fb):
    """Nhãn tác vụ hiển thị ở bảng AI Agent, tùy pha đang góp ý."""
    ph = (A["d"].get(3) or {}).get("phase", "menu")
    if ph == "menu":
        return ["Đọc góp ý và chỉnh danh sách phân tích"]
    base = ["Đọc góp ý của bạn", "Viết lại code theo góp ý"]
    return base + (["Chạy lại code", "Tự sửa lỗi nếu có", "Tổng hợp KPI và phát hiện"] if ph == "result" else [])


def execute(codes, t0=0):
    d = A["d"][3]
    tick(t0)
    dfs, tabs = [], []
    with prepare(A["clean"]):                          # ghi dữ liệu cho sandbox một lần, dùng cho mọi tác vụ bên dưới
        for t, task in enumerate(d["tasks"]):
            code = codes[t] if t < len(codes) and codes[t].strip() else task["code"]
            err = df = None
            for attempt in range(2):
                try:
                    df = run_code(code, A["clean"])
                    err = None
                    break
                except UserError:
                    raise                                    # hệ thống bận / lỗi không phải do code: đừng nhờ AI sửa code
                except Exception as e:
                    err = describe_error(e)
                    if attempt == 0:
                        tick(t0 + 1)
                        code = strip_code(llm(SYS(ROLE_FIX),
                                              f"Sửa code lỗi, chỉ trả code (không import, không .query()/.eval()).\nLỗi: {err}\nSchema: {J(schema(A['clean'], 2), 4000)}\nCode:\n{code}"))
            task["code"] = code
            dfs.append(df)
            tabs.append(df_table(df, task["title"], err))
    if all(x is None for x in dfs):
        raise RuntimeError("Không có phân tích nào chạy thành công: " + "; ".join(t["err"] or "" for t in tabs)[:300])
    tick(t0 + 2)
    A["x"][3] = dfs
    txt = "\n\n".join(f"### [{i}] {t['title']} (cột: {t['cols']})\n{dfs[i].head(30).to_csv(index=False)}" for i, t in enumerate(tabs) if dfs[i] is not None)
    r = llm_json(SYS(ROLE_SUM), ctx_txt() + f"Các bảng kết quả:\n{txt[:14000]}\n\n" + PROMPT_SUM)
    charts = valid_charts(r.get("charts", []), tabs)
    if not charts:
        for i, t in enumerate(tabs):
            num = [c for c in t["cols"] if is_num(t, c)]
            if num and t["cols"][0] != num[0]:
                charts.append({"task": i, "x": t["cols"][0], "y": num[0], "kind": "bars", "title": t["title"], "unit": ""})
    with LOCK:
        d["result"] = {"kpis": r.get("kpis", []), "charts": charts, "findings": r.get("findings", []), "tables": tabs}
        d["phase"] = "result"
        d["gen"] = next_gen()
        bump()