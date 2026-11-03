# -*- coding: utf-8 -*-
"""LLM giả cho chế độ --mock: chạy được trên MỌI bộ dữ liệu trong datasets/ (khác tests/_flow.py chỉ biết bộ bán hàng mẫu).

Đóng vai một AI làm ĐÚNG những điều kế hoạch yêu cầu (chỉ chép ô nguồn, ít phát hiện, hành động gắn phát hiện, giả thuyết nằm ở risks),
nhưng cố tình (1) đề xuất MỘT biểu đồ 'tổng' cho chỉ số không cộng được để kiểm tra lớp bảo vệ ở máy chủ (bất biến I03) và
(2) cài sẵn MỘT phép tính sai trong một phát hiện để kiểm tra việc tính lại (Q1b) và để bất biến I08 có việc làm.
Con số trong phát hiện được đọc từ chính bảng kết quả mà Agent Phát hiện nhận trong prompt, không lấy từ nguồn nào khác.
Mục đích: kiểm HẠ TẦNG (luồng, tệp xuất, bất biến), không đo chất lượng AI thật (việc của chế độ --model)."""
import io
import json
import re

import pandas as pd

from app import labels as lb
from app.utils import vn


def _out_col(mock):
    base = mock["measure"].split(" (")[0].lower()
    return ("Tổng " if mock["agg"] == "sum" else "Trung bình ") + base


def make(ds, prompts=None):
    mock, truth = ds["mock"], ds["truth"]
    out = _out_col(mock)
    raw = ds["tables"][mock["table"]]

    def fake(system, user, max_tokens=8000, json_mode=False):
        if prompts is not None:
            prompts.append((system[:80], user))
        if "Agent Thống kê" in system:
            return json.dumps({"findings": [{"tag": "Chất lượng", "text": "Dữ liệu đọc được; xem điểm chất lượng ở bảng bên dưới."}]})
        if "Agent Làm sạch" in system:
            return json.dumps({"operations": [], "value_counts": {"overview": "ok", "columns": []}})
        if "Agent Hoạch định" in system:
            return json.dumps({"menu": [{"title": mock["title"], "goal": "so sánh các nhóm", "metrics": [out], "why": "trả lời câu hỏi", "recommended": True}]})
        if "Agent Phân tích dữ liệu" in system or "lập trình viên pandas" in system:
            code = (f"df = dfs['{mock['table']}']\nresult = df.groupby('{mock['by']}', as_index=False)['{mock['measure']}'].{mock['agg']}()\n"
                    f"result.columns = ['Nhóm', '{out}']")
            if "lập trình viên pandas" in system:
                return code
            return json.dumps({"tasks": [{"title": mock["title"], "goal": f"nhóm theo {mock['by']}", "code": code}]})
        if "Biên tập viên" in system:
            return json.dumps({"map": {}})
        if "Agent Tổng hợp kết quả" in system:
            v = raw[mock["measure"]].sum() if mock["agg"] == "sum" else raw[mock["measure"]].mean()
            return json.dumps({"kpis": [{"label": out.capitalize(), "value": vn(v, 0), "delta": ""}],
                               "charts": [{"task": 0, "x": "Nhóm", "y": out, "kind": "bars", "title": mock["title"], "unit": ""}],
                               "findings": [{"tag": "Mô tả", "text": "Kết quả theo nhóm."}]})
        if "Agent Phát hiện" in system:
            return json.dumps(_insights(user, mock, truth, out))
        if "Agent Nhận diện" in system:
            return json.dumps({"specs": [], "unclear": ""})
        if "Agent Kiểm tra" in system:
            return json.dumps({"ok": True, "done": "Đã cập nhật theo góp ý.", "missing": ""})
        if "Agent Thiết kế" in system:
            non = lb.label(truth["non_additive"][0])
            by, m = lb.label(mock["by"]), lb.label(mock["measure"])
            return json.dumps({"title": "Báo cáo " + ds["title"], "narrative": "n",
                               "charts": [{"task": 0, "x": "Nhóm", "y": out, "kind": "bars", "title": mock["title"], "unit": "", "insight": "i", "recommended": True}],
                               "dash": [{"ds": mock["table"], "by": by, "measure": m, "agg": "avg" if mock["agg"] == "mean" else "sum", "kind": "bars", "title": mock["title"], "why": "so sánh các nhóm"},
                                        {"ds": mock["table"], "by": by, "measure": non, "agg": "sum", "kind": "bars", "title": f"Tổng {non.lower()}", "why": "(cố ý sai) AI cộng chỉ số không cộng được"}]})
        raise AssertionError("LLM giả chưa biết vai trò: " + system[:80])

    return fake


def _insights(user, mock, truth, out):
    """Đọc bảng kết quả đầu tiên trong prompt ('### [0] Tiêu đề' rồi CSV) và viết phát hiện từ ĐÚNG các ô đó."""
    m = re.search(r"### \[0\] (.+?)\n(.*?)(?=\n### \[|\nPhát hiện sơ bộ|\Z)", user, re.S)
    if not m:
        return {"summary": "Chưa đọc được bảng kết quả.", "insights": [], "actions": [], "risks": []}
    title, df = m.group(1).strip(), pd.read_csv(io.StringIO(m.group(2)))
    g, v = df.columns[0], df.columns[-1]
    df = df.dropna().sort_values(v, ascending=False)
    if len(df) < 2:
        return {"summary": "Chỉ có một nhóm, chưa so sánh được.", "insights": [], "actions": [], "risks": []}
    top, bot = df.iloc[0], df.iloc[-1]
    dec = 0 if float(top[v]).is_integer() and float(bot[v]).is_integer() else 2
    ratio = float(top[v]) / float(bot[v])
    cell = lambda row: f"[{title}, {row[g]}, {v}] = {vn(float(row[v]), dec)}"          # noqa: E731
    absent = truth["absent_terms"][0]
    return {"summary": f"Nhóm {top[g]} dẫn đầu, nhóm {bot[g]} thấp nhất.",
            "insights": [{"title": f"{top[g]} dẫn đầu ở chỉ số «{v}»", "confidence": "Cao", "evidence": f"{cell(top)}; {cell(bot)}", "source": title},
                         {"title": f"{top[g]} cao hơn {bot[g]} khoảng {vn(ratio, 1)} lần", "confidence": "Trung bình",
                          "evidence": f"{vn(float(top[v]), dec)} / {vn(float(bot[v]), dec)} = {vn(ratio, 2)}", "source": title},
                         # LỖI CÀI SẴN: cộng hai nhóm rồi ghi nhiều hơn 20% so với tổng thật. Bộ đánh giá PHẢI thấy phát hiện này bị gắn cờ (xem PLANTED trong run_eval.py).
                         {"title": f"{top[g]} và {bot[g]} cộng lại vượt mốc", "confidence": "Cao",
                          "evidence": f"{vn(float(top[v]), dec)} + {vn(float(bot[v]), dec)} = {vn((float(top[v]) + float(bot[v])) * 1.2, dec)}", "source": title}],
            "actions": [{"text": f"Xem lại nhóm {bot[g]}", "priority": "Trung bình", "impact": "chưa ước tính được"}],
            "risks": [f"Giả thuyết cần kiểm chứng: chênh lệch giữa các nhóm có thể liên quan đến {absent}. Dữ liệu cần thu thêm: thông tin về {absent}."]}
