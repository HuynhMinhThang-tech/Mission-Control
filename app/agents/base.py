# -*- coding: utf-8 -*-
"""Phần dùng chung cho mọi AI Agent."""
from ..state import A


def SYS(role):
    return (f"Bạn là {role} trong nhóm phân tích dữ liệu. Luôn trả lời bằng tiếng Việt, ngắn gọn, "
            "dựa trên số liệu được cung cấp, không bịa số.")


def ctx_txt(fb=""):
    return (f"Câu hỏi kinh doanh: {A['question']}\nBối cảnh doanh nghiệp: {A['ctx'] or 'không có'}\n"
            f"Góp ý của người dùng: {fb or 'không'}\n")
