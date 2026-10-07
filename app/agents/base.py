# -*- coding: utf-8 -*-
"""Phần dùng chung cho mọi AI Agent."""
from ..state import A


def SYS(role):
    return (f"Bạn là {role} trong nhóm phân tích dữ liệu. Luôn trả lời bằng tiếng Việt, ngắn gọn, "
            "dựa trên số liệu được cung cấp, không bịa số.")


def ctx_txt(fb=""):
    return (f"Câu hỏi kinh doanh: {A['question']}\nBối cảnh doanh nghiệp: {A['ctx'] or 'không có'}\n"
            f"Góp ý của người dùng: {fb or 'không'}\n")


def prev(i, fb, n=4500):
    """Khi người dùng góp ý, đưa kết quả LẦN TRƯỚC vào prompt để AI sửa đúng chỗ thay vì làm lại từ đầu."""
    if not fb or i not in A["d"]:
        return ""
    import json
    d = {k: v for k, v in A["d"][i].items() if k not in ("gen", "pv", "profile", "issues")}
    return f"BẢN LẦN TRƯỚC (hãy GIỮ phần không bị góp ý, chỉ sửa theo góp ý):\n{json.dumps(d, ensure_ascii=False, default=str)[:n]}\n"
