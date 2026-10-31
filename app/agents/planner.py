# -*- coding: utf-8 -*-
"""AGENT 3 · Hoạch định phân tích → viết code pandas → tổng hợp kết quả (bước 4)."""
from ..data import analysis_spec as S
from ..data.quality import schema
from ..data.sandbox import describe_error, df_table, prepare, run_code
from ..errors import UserError
from .. import numfmt
from ..data.scope import scope_block
from ..data.tablefacts import table_facts
from .playbook import CODE_RULES, SUM_RULES
from ..lang import COLNAME_RULE, localize
from ..llm import llm, llm_json, strip_code
from ..state import A, LOCK, bump, next_gen, put, tick
from ..utils import J
from .base import SYS, ctx_txt, prev
from .charts import is_num, valid_charts

ROLE_PLAN = "Agent Hoạch định phân tích"
ROLE_CODE = "Agent Phân tích dữ liệu (pandas)"
ROLE_FIX = "lập trình viên pandas"
ROLE_SUM = "Agent Tổng hợp kết quả phân tích"
ROLE_LOC = "Biên tập viên tiếng Việt"
ROLE_PARSE = "Agent Nhận diện yêu cầu phân tích"

PROMPT_MENU = (
    "Hãy ĐỀ XUẤT 6-10 phân tích / chỉ số ứng viên để NGƯỜI DÙNG TỰ CHỌN (chưa viết code). Gồm mô tả (điều gì đã xảy ra), "
    "chẩn đoán (vì sao, phân rã theo khu vực/sản phẩm...), và nếu có cột thời gian thì thêm 1 mục dự báo kỳ kế tiếp "
    "(hồi quy tuyến tính/trung bình trượt, có khoảng tin cậy). "
    'Trả về DUY NHẤT JSON: {"menu":[{"title":"...","type":"Mô tả|Chẩn đoán|Dự báo","goal":"trả lời điều gì","metrics":["tên chỉ số = công thức cụ thể"],'
    '"columns":["tên cột THẬT trong dữ liệu mà phân tích này dùng"],"why":"vì sao liên quan tới câu hỏi","recommended":true}]}')

PROMPT_PARSE = (
    'Người dùng mô tả bằng lời điều họ muốn phân tích. Hãy nhận diện thành các yêu cầu có cấu trúc, dùng ĐÚNG tên cột (trường "name") trong danh sách cột. '
    'Trả về DUY NHẤT JSON: {"specs":[{"type":"compare|trend|cross|correlate|distribution","file":"tên file","measures":[{"col":"cột số, hoặc null nếu chỉ đếm số bản ghi","agg":"sum|mean|median|count|nunique|min|max"}],'
    '"by":["cột phân loại"],"time":{"col":"cột thời gian","grain":"day|week|month|quarter|year"},"x":"cột số","y":"cột số","col":"cột"}],"unclear":"phần yêu cầu CHƯA nhận diện được, để chuỗi rỗng nếu hiểu hết"}\n'
    'Quy tắc: compare = chỉ số chia theo 1-2 biến phân loại (by); trend = chỉ số theo thời gian (time), có thể thêm 1 biến by để tách đường; cross = đúng 2 biến phân loại trong by; '
    'correlate = x và y là 2 biến số; distribution = col. Chỉ cột kind=num mới làm chỉ số/x/y; chỉ cột kind=cat mới làm by; chỉ cột kind=date mới làm time. '
    'Ví dụ "doanh thu theo khu vực" = compare, measures [{col: cột doanh thu, agg: sum}], by [cột khu vực]. "xu hướng doanh thu theo tháng" = trend, grain month. '
    'Không có cột phù hợp thì KHÔNG bịa: ghi phần đó vào "unclear". Tối đa 6 yêu cầu, không trùng nhau.')

PROMPT_CODE = (
    'Viết code cho TỪNG mục (đúng thứ tự, thêm 1 mục riêng cho yêu cầu bổ sung nếu có). Trả về DUY NHẤT JSON: {"tasks":[{"title":"...","goal":"...","code":"..."}]}\n'
    "Mỗi code: Python pandas/numpy (đã có pd, np, dfs), KHÔNG import, KHÔNG đọc/ghi file, KHÔNG dùng .query()/.eval()/thuộc tính bắt đầu bằng gạch dưới (dùng lọc bool df[df['x']>0]); kết quả gán vào biến `result` là DataFrame đã tổng hợp "
    "(<=50 dòng; mục dự báo trả cột kỳ, dự báo, cận dưới, cận trên). Truy cập bằng dfs['tên file']. " + COLNAME_RULE + CODE_RULES)

PROMPT_SUM = (
    'Trả về DUY NHẤT JSON: {"kpis":[{"label":"","value":"","delta":""}],"charts":[{"task":<số thứ tự bảng>,"x":"cột nhãn","y":"cột số","kind":"bars|cols|line|donut","title":"","unit":""}],'
    '"findings":[{"tag":"Mô tả|Chẩn đoán|Dự báo|Lưu ý","text":"có số liệu"}]}\n'
    "3-6 KPI: value/delta lấy hoặc tính trực tiếp từ bảng, không bịa. 3-5 biểu đồ, ĐA DẠNG loại và KHÔNG trùng nhau (mỗi biểu đồ một bảng/cột khác). kind: 'line' cho chuỗi thời gian; 'bars' xếp hạng/so sánh nhiều nhóm; 'cols' so sánh ít nhóm; 'donut' cơ cấu tỷ trọng (<=7 phần, giá trị không âm). x,y phải là tên cột có thật." + SUM_RULES)


def _menu_vars(items):
    """Cột mà mỗi đề xuất dùng: ưu tiên AI khai báo (chỉ giữ tên có thật); thiếu thì dò trong chữ mô tả. Giao diện hiện thành 'Biến dùng'."""
    real = {str(c) for d in A["clean"].values() for c in d.columns}
    for m in items:
        v = [c for c in (m.get("columns") or []) if isinstance(c, str) and c in real]
        if not v:
            v = S.vars_in_text(" ".join([str(m.get("title", "")), str(m.get("goal", "")), " ".join(map(str, m.get("metrics") or []))]), A["clean"])
        m["vars"] = v[:8]
        m["type"] = m.get("type") if m.get("type") in ("Mô tả", "Chẩn đoán", "Dự báo") else "Phân tích"
        m["metrics"] = [str(x) for x in (m.get("metrics") or [])][:5]


def menu(fb=""):
    tick(0)
    r = llm_json(SYS(ROLE_PLAN), ctx_txt(fb) + prev(3, fb, 3500) + f"Dữ liệu đã làm sạch:\n{J(schema(A['clean'], 3), 6000)}\n\n" + scope_block(A["clean"]) + PROMPT_MENU
                 + ("\nNgười dùng đã góp ý: hãy ĐIỀU CHỈNH danh sách theo đúng góp ý (thêm/bớt/đổi mục), giữ các mục không liên quan." if fb else ""))
    items = [m for m in r["menu"] if isinstance(m, dict) and m.get("title")]
    if not items:
        raise RuntimeError("AI không đề xuất được phân tích nào. Hãy bấm Thử lại hoặc nêu rõ hơn bạn muốn phân tích gì.")
    for k, m in enumerate(items):
        m["id"] = f"m{k}"
    _menu_vars(items)
    # `cols`: danh sách biến thật (kèm kiểu) cho bộ ghép biến ở giao diện
    put(3, {"phase": "menu", "menu": items, "cols": S.columns_meta(A["clean"]), "tasks": None, "result": None})


def parse_request(text):
    """Cách tiếp cận 2 của bộ ghép biến: người dùng mô tả bằng lời -> AI nhận diện thành spec -> CODE kiểm tra với dữ liệu thật.
    Trả {specs (đã kiểm tra, có tiêu đề/biến dùng), rejected (lý do không nhận diện được), unclear}."""
    text = (text or "").strip()
    if not text:
        raise UserError("Hãy mô tả điều bạn muốn phân tích.")
    clean = A["clean"]
    cols = [{"file": f["file"], "cols": [{"name": c["name"], "label": c["label"], "kind": c["kind"], "unit": c["unit"], "top": c.get("top")} for c in f["cols"]]} for f in S.columns_meta(clean)]
    r = llm_json(SYS(ROLE_PARSE), f"Danh sách cột (kind: num=định lượng, cat=phân loại, date=thời gian, id=mã định danh):\n{J(cols, 6000)}\n\nYêu cầu của người dùng:\n{text[:800]}\n\n" + PROMPT_PARSE, 2500)
    specs, rejected, seen = [], [], set()
    for sp in (r.get("specs") or [])[:6]:
        n, err = S.normalize(sp, clean)
        if n is None:
            rejected.append(err)
            continue
        key = J({k: n.get(k) for k in ("type", "file", "measures", "by", "time", "x", "y", "col")})
        if key not in seen:
            seen.add(key)
            specs.append(n)
    return {"specs": specs, "rejected": rejected, "unclear": str(r.get("unclear") or "").strip()[:300]}


def spec_task(sp):
    """Một ô ghép biến -> một tác vụ: code do CODE sinh (không nhờ AI), nên đúng chính xác những biến người dùng đã chọn."""
    return {"title": sp["title"], "goal": sp["goal"], "code": S.build_code(sp, A["clean"]), "spec": sp, "vars": sp["vars"], "src": "spec"}


def write_code(ids, custom, fb="", t0=0, specs=None):
    tick(t0)
    d = A["d"][3]
    clean = A["clean"]
    specs = d.get("specs", []) if specs is None else specs
    norm = [n for n, _ in (S.normalize(sp, clean) for sp in specs) if n]       # kiểm tra lại với dữ liệu thật: không tin dữ liệu từ trình duyệt
    structured = [sp for sp in norm if sp["type"] != "free"]
    free = [sp["text"] for sp in norm if sp["type"] == "free"]
    custom_all = "; ".join(x for x in [(custom or "").strip(), *free] if x)
    items = [m for m in d["menu"] if m["id"] in ids]
    rewrite = bool(fb and d.get("tasks"))
    tasks = []
    ask_items = list(items)
    if rewrite:                              # có góp ý -> AI viết lại TOÀN BỘ (kể cả các ô ghép biến) theo góp ý
        ask_items += [{"title": sp["title"], "goal": sp["goal"], "columns": sp["vars"]} for sp in structured]
    else:
        tasks += [spec_task(sp) for sp in structured]
    old = ""
    if rewrite:
        old = (f"CODE LẦN TRƯỚC (đã gồm các chỉnh sửa tay của người dùng nếu có):\n{J([{'title': t['title'], 'code': t['code']} for t in d['tasks']], 5000)}\n"
               f"NGƯỜI DÙNG GÓP Ý: {fb}\nHãy SỬA code/cách tính theo đúng góp ý (đổi chỉ số, nhóm theo cột khác, lọc, thêm/bớt mục...), giữ phần không bị góp ý.\n")
    if ask_items or custom_all.strip():
        r = llm_json(SYS(ROLE_CODE),
                     ctx_txt(fb) + f"Dữ liệu đã làm sạch (biến `dfs` là dict tên file→DataFrame):\n{J(schema(clean, 3), 6000)}\n"
                     f"Các phân tích người dùng đã chọn:\n{J(ask_items)}\nYêu cầu bổ sung của người dùng: {custom_all or 'không'}\n{old}\n" + scope_block(clean) + PROMPT_CODE, 12000)
        for t in r.get("tasks", []):
            if isinstance(t, dict) and t.get("code"):
                tasks.append({"title": str(t.get("title") or "Phân tích"), "goal": str(t.get("goal") or ""), "code": t["code"], "vars": S.vars_in_code(t["code"], clean), "src": "ai"})
    if not tasks:
        raise RuntimeError("AI không trả về code nào. Hãy bấm Thử lại hoặc mô tả góp ý rõ hơn.")
    with LOCK:
        d["tasks"] = tasks
        d["ids"], d["custom"], d["specs"] = list(ids), custom, norm
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
    write_code(d.get("ids", []), d.get("custom", ""), fb, t0=1, specs=d.get("specs", []))
    if ph == "result":
        execute([], t0=2)


def labels_for(fb):
    """Nhãn tác vụ hiển thị ở bảng AI Agent, tùy pha đang góp ý."""
    ph = (A["d"].get(3) or {}).get("phase", "menu")
    if ph == "menu":
        return ["Đọc góp ý và chỉnh danh sách phân tích"]
    base = ["Đọc góp ý của bạn", "Viết lại code theo góp ý"]
    return base + (["Chạy lại code", "Tự sửa lỗi nếu có", "Tổng hợp KPI và phát hiện"] if ph == "result" else [])


def localize_results(dfs, titles):
    """Đổi tên cột kết quả sang tiếng Việt: AI dịch theo ngữ cảnh (có từ điển dự phòng nếu AI lỗi)."""
    known = {str(c) for df in A["clean"].values() for c in df.columns} | S.data_words(A["clean"])      # giá trị dữ liệu (HCM, Online, SP-A...) làm tên cột pivot: giữ nguyên

    def ask(ctx, cand):
        return llm_json(SYS(ROLE_LOC), f"Các bảng kết quả và cột của chúng: {J(ctx, 3000)}\nCác tên cột chưa phải tiếng Việt: {J(cand, 1500)}\n"
                        'Hãy đặt lại từng tên thành tiếng Việt có dấu, tự nhiên, ngắn gọn, đúng nghĩa theo bảng chứa nó (vd COUNT_PER_LEVEL -> "Số lượng theo cấp bậc", '
                        'AVG_LEVEL_SALARY -> "Lương trung bình theo cấp bậc", PERC_PER_LEVEL -> "Tỷ trọng theo cấp bậc (%)"). Trả về DUY NHẤT JSON {"map":{"tên cũ":"tên mới"}}.', 1500)
    out, _ = localize(dfs, titles, known, ask)
    return out


def execute(codes, t0=0):
    d = A["d"][3]
    tick(t0)
    dfs, errs = [], []
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
            errs.append(err)
    tick(t0 + 2)
    dfs = localize_results(dfs, [t["title"] for t in d["tasks"]])       # tên cột kết quả: một thứ tiếng (tiếng Việt), không xen tiếng Anh
    tabs = [df_table(df, t["title"], e) for df, t, e in zip(dfs, d["tasks"], errs)]
    if all(x is None for x in dfs):
        raise RuntimeError("Không có phân tích nào chạy thành công: " + "; ".join(t["err"] or "" for t in tabs)[:300])
    for t, task, df in zip(tabs, d["tasks"], dfs):                       # điểm nổi bật + biến dùng của từng bảng: code tính, không nhờ AI
        task["vars"] = task["spec"]["vars"] if task.get("spec") else S.vars_in_code(task["code"], A["clean"])
        t["facts"] = (S.spec_facts(task["spec"], A["clean"]) if task.get("spec") else []) + (table_facts(df) if df is not None else [])
        t["vars"], t["src"], t["goal"] = task["vars"], task.get("src", "ai"), task.get("goal", "")
    A["x"][3] = dfs
    txt = "\n\n".join(f"### [{i}] {t['title']} (cột: {t['cols']})\n{dfs[i].head(30).to_csv(index=False)}" for i, t in enumerate(tabs) if dfs[i] is not None)
    r = llm_json(SYS(ROLE_SUM), ctx_txt() + f"Các bảng kết quả:\n{txt[:14000]}\n\n" + PROMPT_SUM)
    known = numfmt.Known.from_dfs(dfs)                                   # mọi số có thật trong bảng kết quả: dùng để đoán đúng độ lớn và đối chiếu
    kpis = numfmt.fix_kpis(r.get("kpis"), known)                          # KPI: 11773398767.5 -> "11,77 tỷ đồng"
    r = {**numfmt.fix_payload({k: v for k, v in r.items() if k != "kpis"}, known), "kpis": kpis}
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