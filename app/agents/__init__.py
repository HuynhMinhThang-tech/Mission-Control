# -*- coding: utf-8 -*-
"""Danh mục AI Agent. Mỗi agent nằm trong 1 file riêng (vai trò + prompt + logic)."""
from . import cleaner, insight, planner, profiler, reporter, reviewer

# Bước chạy bằng nút "Điều chỉnh" / "Thử lại"
RUN = {1: profiler.run, 2: cleaner.run, 3: planner.revise, 4: insight.run, 5: reporter.run, 6: reviewer.run}
# Sau khi chấp nhận bước i thì tự chạy bước kế tiếp
NEXT = {1: (2, cleaner.run), 2: (3, planner.menu), 3: (4, insight.run), 4: (5, reporter.run), 5: (6, reviewer.run)}
