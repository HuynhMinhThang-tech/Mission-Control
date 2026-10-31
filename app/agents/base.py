# -*- coding: utf-8 -*-
"""Phần dùng chung cho mọi AI Agent."""
from ..lang import RULE
from ..state import A


def SYS(role):
    return (f"Bạn là {role} trong nhóm phân tích dữ liệu. Luôn trả lời bằng tiếng Việt, ngắn gọn, "
            "dựa trên số liệu được cung cấp, không bịa số. " + RULE)


def ctx_txt(fb=""):
    fbl = (f"Góp ý của người dùng (ƯU TIÊN SỐ 1: PHẢI thực hiện đúng và thể hiện RÕ trong kết quả mới, không được trả lại bản cũ): {fb}\n"
           if fb else "Góp ý của người dùng: không\n")
    return f"Câu hỏi kinh doanh: {A['question']}\nBối cảnh doanh nghiệp: {A['ctx'] or 'không có'}\n" + fbl


def prev(i, fb, n=4500):
    """Khi người dùng góp ý, đưa kết quả LẦN TRƯỚC vào prompt để AI sửa đúng chỗ thay vì làm lại từ đầu.
    Kèm các góp ý đã gửi trước đó ở bước này: góp ý sau KHÔNG được làm mất kết quả của góp ý trước."""
    if not fb or i not in A["d"]:
        return ""
    import json
    d = {k: v for k, v in A["d"][i].items() if k not in ("gen", "pv", "profile", "issues", "vc", "dist", "cols", "adj", "dash")}
    older = [h for h in (A["fbh"].get(str(i)) or [])[:-1] if h][-5:]          # phần tử cuối là góp ý hiện tại (đã nằm trong ctx_txt)
    hist = ("CÁC GÓP Ý ĐÃ GỬI TRƯỚC ĐÓ Ở BƯỚC NÀY (đã áp dụng vào bản lần trước, VẪN PHẢI GIỮ): " + " | ".join(older) + "\n") if older else ""
    return f"{hist}BẢN LẦN TRƯỚC (hãy GIỮ phần không bị góp ý, chỉ sửa theo góp ý):\n{json.dumps(d, ensure_ascii=False, default=str)[:n]}\n"
