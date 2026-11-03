# -*- coding: utf-8 -*-
"""Bộ đánh giá Mission Control (khung HM-02): chạy TRỌN LUỒNG 7 bước trên các bộ dữ liệu mô phỏng rồi kiểm các bất biến.

  python tests/eval/run_eval.py --mock                      # LLM giả: kiểm HẠ TẦNG (luồng, tệp xuất, bất biến). Không cần mạng/khóa. Dùng khi sửa code.
  python tests/eval/run_eval.py --mock --only nhan_su       # một bộ dữ liệu
  EVAL_API_KEY=... python tests/eval/run_eval.py --model gpt-4o --base-url https://api.openai.com/v1 [--strict]
                                                            # LLM THẬT: đo chất lượng AI (chạy tay, tốn tiền). Chưa được thử với mô hình thật trong bản này.

Thoát mã 1 nếu (chế độ --mock) có bất biến bị vi phạm, ca đối chứng nào trượt, hoặc luồng lỗi; chế độ --model chỉ thoát mã 1 khi có --strict
(AI thật có thể vi phạm; mục tiêu là đo, không chặn). Bộ dữ liệu riêng (thật, đã ẩn danh) để ở tests/eval/private/ (đã được .gitignore), cùng định dạng với datasets/."""
import argparse
import io
import json
import os
import sys
import time
import traceback
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))      # tests/ (để dùng _flow)
sys.path.insert(0, HERE)
import _flow as F  # noqa: E402
import invariants as I  # noqa: E402
import mock_llm  # noqa: E402
from datasets import ALL  # noqa: E402
from pptx import Presentation  # noqa: E402

from app import numfmt as nf  # noqa: E402


PLANTED = 1          # số phép tính sai mà LLM giả (mock_llm.py) cố ý cài vào mỗi bộ dữ liệu


def _csv(df, nfd):
    b = df.to_csv(index=False)
    return (unicodedata.normalize("NFD", b) if nfd else b).encode("utf-8")


def _pptx_text(b):
    out = []
    for sl in Presentation(io.BytesIO(b)).slides:
        for sh in sl.shapes:
            if sh.has_text_frame:
                out.append(sh.text_frame.text)
            if getattr(sh, "has_table", False) and sh.has_table:
                out += [cell.text for r in sh.table.rows for cell in r.cells]
    return "\n".join(out)


def run_one(c, ds, question):
    """Chạy trọn luồng cho một bộ dữ liệu + một câu hỏi, trả về I.Run. Lỗi ở bước nào thì ném ngoại lệ kèm tên bước."""
    F.post(c, "/api/new")
    files = [(io.BytesIO(_csv(df, ds.get("nfd"))), n) for n, df in ds["tables"].items()]
    r = c.post("/api/upload", data={"files": files}, content_type="multipart/form-data")
    assert r.status_code == 200, f"tải tệp: {r.get_data(as_text=True)[:200]}"
    F.post(c, "/api/start", {"question": question})

    def step(name, timeout=300):
        s = F.wait(c, timeout)
        if s.get("error"):
            raise RuntimeError(f"{name}: {s['error']}")
        return s

    s = step("bước 1")
    F.post(c, "/api/accept/1"); s = step("bước 2")
    F.post(c, "/api/accept/2"); s = step("bước 3 (menu)")
    F.post(c, "/api/a3/code", {"ids": [m["id"] for m in s["d"]["3"]["menu"]], "custom": "", "specs": []}); s = step("bước 3 (code)")
    F.post(c, "/api/a3/exec", {"codes": []}); s = step("bước 3 (chạy)", 600)
    tables = s["d"]["3"]["result"]["tables"]
    if any(t.get("err") for t in tables) and not any(t.get("rows") for t in tables):
        raise RuntimeError("bước 3: mọi phân tích đều lỗi: " + "; ".join(str(t.get("err"))[:80] for t in tables))
    F.post(c, "/api/accept/3"); s = step("bước 4 (phát hiện)")
    F.post(c, "/api/accept/4"); s = step("bước 5 (thiết kế)")
    d5 = s["d"]["5"]
    F.post(c, "/api/accept/5", {"title": d5.get("title") or "Báo cáo", "charts": d5["charts"], "kpis": [], "dash": d5["dash"]["ai"]}); s = step("bước 6 (rà soát)")
    F.post(c, "/api/accept/6"); s = step("bước 7 (xuất)")
    aid = s["id"]
    get = lambda n: c.get(f"/api/download/{aid}/{n}").data       # noqa: E731
    html = c.get(f"/api/view/{aid}/dashboard.html").get_data(as_text=True)
    dash = json.loads(html.split('<script id="data" type="application/json">')[1].split("</script>")[0])
    d4 = s["d"]["4"]
    return I.Run(truth=ds["truth"], question=question, summary=d4.get("summary", ""), insights=d4.get("insights", []), actions=d4.get("actions", []),
                 risks=d4.get("risks", []), tables=s["d"]["3"]["result"]["tables"], pptx=_pptx_text(get("bao_cao.pptx")), md=get("bao_cao.md").decode("utf-8"),
                 html=c.get(f"/api/view/{aid}/bao_cao.html").get_data(as_text=True), dash=dash,
                 chart_titles=[x.get("title", "") for x in d5["charts"]] + [p["title"] for p in dash.get("plan") or [] if p.get("title")])


def real_llm(model, base_url, key):
    from app import llm as L
    cfg = {"api_key": key, "base_url": base_url, "model": model}
    client = L.make_client(cfg)
    return lambda system, user, max_tokens=8000, json_mode=False: L.chat(client, cfg, system, user, max_tokens, json_mode)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--mock", action="store_true", help="LLM giả (kiểm hạ tầng)")
    g.add_argument("--model", help="tên mô hình thật (cần EVAL_API_KEY)")
    ap.add_argument("--base-url", default=os.environ.get("EVAL_BASE_URL", "https://api.openai.com/v1"))
    ap.add_argument("--only", help="chỉ chạy các bộ dữ liệu này, cách nhau bằng dấu phẩy")
    ap.add_argument("--strict", action="store_true", help="chế độ --model: thoát mã 1 nếu có vi phạm")
    a = ap.parse_args()

    questions = json.load(open(os.path.join(HERE, "questions.json"), encoding="utf-8"))
    only = set(a.only.split(",")) if a.only else None
    if a.model and not os.environ.get("EVAL_API_KEY"):
        sys.exit("Thiếu khóa API: đặt biến môi trường EVAL_API_KEY.")

    bad = False
    # ---- 1) ca đối chứng: bất biến có bắt được lỗi không (không cần LLM)
    first = next(iter(ALL.values()))()
    ok, n, miss = I.run_controls(I.clean_run(first["truth"]))
    print(f"Ca đối chứng: {ok}/{n} lỗi cố ý đều bị bất biến bắt" + ("" if ok == n else "   <<< BẤT BIẾN KHÔNG ĐÁNG TIN"))
    for m in miss:
        print("   ✘", m)
    bad |= ok != n

    # ---- 2) chạy trọn luồng từng bộ dữ liệu
    app, c = F.setup()
    import app.agents.planner as planner
    rows, t_all = [], time.time()
    for q in questions:
        if only and q["dataset"] not in only:
            continue
        ds = ALL[q["dataset"]]()
        fake = mock_llm.make(ds) if a.mock else real_llm(a.model, a.base_url, os.environ["EVAL_API_KEY"])
        F.llm.llm = fake
        planner.llm = fake                      # planner đã import sẵn tên `llm`
        t0 = time.time()
        print(f"\n▶ {ds['title']}: «{q['question']}»", flush=True)
        try:
            run = run_one(c, ds, q["question"])
        except Exception as e:                  # noqa: BLE001
            print(f"   ✘ luồng lỗi: {e}")
            if os.environ.get("EVAL_TRACE"):
                traceback.print_exc()
            rows.append((ds["id"], None, None, None, None, None, None, [f"luồng lỗi: {str(e)[:80]}"]))
            bad = True
            continue
        viol = I.check_all(run)
        v = [x.get("verify") for x in run.insights]
        if a.mock and v.count("mismatch") != PLANTED:          # AI giả cài sẵn PLANTED lỗi: hệ thống phải bắt đúng bấy nhiêu, không hơn không kém
            viol["P01"] = [f"AI giả cài sẵn {PLANTED} lỗi số học nhưng hệ thống gắn cờ {v.count('mismatch')} phát hiện"]
        flagged = [x for x in run.insights if x.get("verify") == "mismatch"]
        if a.mock and any(x.get("confidence") == "Cao" for x in flagged):
            viol.setdefault("I01", []).append("phát hiện cài sẵn lỗi vẫn 'Cao'")
        rows.append((ds["id"], len(run.insights), v.count("ok"), v.count("mismatch"), v.count("unverified"), len(run.actions), round(time.time() - t0), viol))
        for code, items in viol.items():
            for it in items[:3]:
                print(f"   ✘ {code}: {it}")
        bad |= bool(viol)

    # ---- 3) bảng điểm
    print("\n" + "=" * 92)
    print(f"{'bộ dữ liệu':<12}{'phát hiện':>10}{'đã kiểm':>9}{'sai':>6}{'chưa kiểm':>11}{'hành động':>11}{'giây':>6}  bất biến vi phạm")
    for ds_id, n_i, ok_i, mm, un, n_a, sec, viol in rows:
        if n_i is None:
            print(f"{ds_id:<12}{'-':>10}{'-':>9}{'-':>6}{'-':>11}{'-':>11}{'-':>6}  {viol[0]}")
        else:
            print(f"{ds_id:<12}{n_i:>10}{ok_i:>9}{mm:>6}{un:>11}{n_a:>11}{sec:>6}  " + (", ".join(f"{k}×{len(x)}" for k, x in viol.items()) or "không"))
    print("=" * 92)
    print(f"Tổng thời gian {round(time.time() - t_all)} giây · chế độ {'mock (LLM giả: chỉ kiểm hạ tầng, KHÔNG phản ánh chất lượng AI)' if a.mock else 'mô hình ' + a.model}")
    print("KẾT LUẬN:", "CÓ VI PHẠM" if bad else "TẤT CẢ ĐẠT")
    sys.exit(1 if bad and (a.mock or a.strict) else 0)


if __name__ == "__main__":
    main()
