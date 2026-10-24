# -*- coding: utf-8 -*-
"""Kiểm thử chính sách ngôn ngữ: tên cột kết quả không xen tiếng Anh. Chạy: python tests/lang_test.py"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.update(SECRET_KEY="k-test", MASTER_KEY="k-test", DATABASE_URL=f"sqlite:///{tempfile.mkdtemp()}/x.db")

import pandas as pd  # noqa: E402

from app import lang  # noqa: E402
from app.agents.base import SYS  # noqa: E402

n_ok = 0


def check(cond, label):
    global n_ok
    if not cond:
        print("FAIL:", label)
        sys.exit(1)
    n_ok += 1
    print("ok  ", label)


check("tiếng Việt" in SYS("Agent X") and "snake_case" in SYS("Agent X"), "mọi Agent đều nhận luật ngôn ngữ (tiếng Việt, không snake_case)")
check(lang.foreign("COUNT_PER_LEVEL") and lang.foreign("avg_salary") and lang.foreign("Total revenue"), "nhận ra tên cột tiếng Anh/snake_case")
check(not lang.foreign("Cấp bậc") and not lang.foreign("Lương cơ bản") and not lang.foreign("Q3") and not lang.foreign("2025"), "không đụng tên có dấu, mã ngắn, số")
check(not lang.foreign("revenue", known={"revenue"}), "giữ nguyên tên cột gốc của dữ liệu")
check(lang.humanize("COUNT_PER_LEVEL") == "Số lượng theo cấp bậc", "từ điển dự phòng dịch được: " + lang.humanize("COUNT_PER_LEVEL"))

df = pd.DataFrame({"Cấp bậc": ["CV", "NV"], "COUNT_PER_LEVEL": [1, 2], "AVG_LEVEL_SALARY": [1.5, 2.5], "PERC_PER_LEVEL": [10, 20]})
df2 = pd.DataFrame({"ALLOWANCE_RATIO": [14.9]})
asked = []


def ask(ctx, cand):
    asked.append((ctx, cand))
    return {"map": {"COUNT_PER_LEVEL": "Số lượng theo cấp bậc", "AVG_LEVEL_SALARY": "Lương trung bình theo cấp bậc", "PERC_PER_LEVEL": "Tỷ trọng theo cấp bậc (%)",
                    "ALLOWANCE_RATIO": "Tỷ lệ phụ cấp (%)", "BỊA": "x", "Cấp bậc": "Level"}}


out, n = lang.localize([df, None, df2], ["Phân bố lương", "Hỏng", "Phụ cấp"], {"Mã NV"}, ask)
check(list(out[0].columns) == ["Cấp bậc", "Số lượng theo cấp bậc", "Lương trung bình theo cấp bậc", "Tỷ trọng theo cấp bậc (%)"] and out[1] is None, "AI đổi tên cột sang tiếng Việt; cột đã là tiếng Việt giữ nguyên")
check(list(out[2].columns) == ["Tỷ lệ phụ cấp (%)"] and list(df.columns)[1] == "COUNT_PER_LEVEL", "đổi ở bản sao, không sửa dữ liệu gốc")
check(len(asked) == 1 and set(asked[0][1]) == {"COUNT_PER_LEVEL", "AVG_LEVEL_SALARY", "PERC_PER_LEVEL", "ALLOWANCE_RATIO"}, "chỉ hỏi AI các cột chưa phải tiếng Việt, một lượt")


def boom(ctx, cand):
    raise RuntimeError("hết hạn mức")


out, n = lang.localize([df], ["x"], set(), boom)
check(list(out[0].columns)[1] == "Số lượng theo cấp bậc" and not any(lang.foreign(c) for c in out[0].columns), "AI lỗi -> dùng từ điển dự phòng, vẫn không còn tên tiếng Anh")


def bad(ctx, cand):
    return {"map": {"COUNT_PER_LEVEL": "Count", "AVG_LEVEL_SALARY": ""}}


out, n = lang.localize([df], ["x"], set(), bad)
check(not any(lang.foreign(c) for c in out[0].columns), "AI trả lại tên tiếng Anh/rỗng -> bị loại, dùng từ điển")
dup = pd.DataFrame({"a_count": [1], "A COUNT": [2]})
out, _ = lang.localize([dup], ["x"], set(), lambda c, k: {"map": {"a_count": "Số lượng", "A COUNT": "Số lượng"}})
check(list(out[0].columns) == ["Số lượng", "Số lượng (2)"], "tên trùng sau khi đổi được đánh số, không ghi đè nhau")
print(f"\nTẤT CẢ {n_ok} KIỂM TRA ĐỀU ĐẠT")
