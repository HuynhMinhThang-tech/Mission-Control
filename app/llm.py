# -*- coding: utf-8 -*-
"""Lớp gọi LLM (Gemini qua endpoint tương thích OpenAI) + đọc JSON chịu lỗi."""
import json
import re

from . import config

_client = None


class Truncated(RuntimeError):
    """Câu trả lời bị cắt giữa chừng vì hết max_tokens."""


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=config.API_KEY, base_url=config.GEMINI_URL)
    return _client


def llm(system, user, max_tokens=8000, json_mode=False):
    if not config.API_KEY or not config.MODEL:
        raise RuntimeError("Chưa cấu hình GEMINI_API_KEY / GEMINI_MODEL trong file .env")
    base = dict(model=config.MODEL, max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    # thử lần lượt: ép JSON + giảm "suy nghĩ" (đỡ tốn token) -> chỉ ép JSON -> không tham số phụ (model/endpoint không hỗ trợ thì bỏ)
    variants = ([dict(response_format={"type": "json_object"}, reasoning_effort="low"), dict(response_format={"type": "json_object"})] if json_mode else []) + [{}]
    last = None
    for extra in variants:
        try:
            r = _get_client().chat.completions.create(**base, **extra)
        except Exception as e:                       # noqa: BLE001
            last = e
            if extra and "400" in str(e):            # tham số phụ bị từ chối -> thử cấu hình đơn giản hơn
                continue
            raise
        ch = r.choices[0]
        if ch.finish_reason == "length":
            raise Truncated(ch.message.content or "")
        return ch.message.content or ""
    raise last


def _balance(s):
    """JSON bị cắt cụt: đóng chuỗi/ngoặc còn thiếu để cứu phần đã có."""
    stack, in_str, esc = [], False, False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    return s + ('"' if in_str else "") + "".join(reversed(stack))


def parse_json(t):
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S) or re.search(r"```(?:json)?\s*(.*)$", t, re.S)
    t = (m.group(1) if m else t).strip()
    a = t.find("{")
    if a < 0:
        raise ValueError("Không thấy JSON trong câu trả lời")
    b = t.rfind("}")
    body = t[a: b + 1] if b > a else t[a:]
    body = body.replace("\u201c", '"').replace("\u201d", '"')
    cands = [body, re.sub(r",\s*([}\]])", r"\1", body), _balance(re.sub(r",\s*([}\]])", r"\1", t[a:]))]
    err = None
    for c in cands:
        try:
            return json.loads(c, strict=False)         # strict=False: cho phép xuống dòng thật bên trong chuỗi (code Python)
        except Exception as e:                         # noqa: BLE001
            err = e
    # bị cắt cụt giữa phần tử: lùi về dấu phẩy gần nhất (phần tử hoàn chỉnh cuối cùng) rồi đóng ngoặc
    tail = re.sub(r",\s*([}\]])", r"\1", t[a:])
    for pos in [m.start() for m in re.finditer(",", tail)][::-1][:60]:
        try:
            return json.loads(_balance(tail[:pos]), strict=False)
        except Exception:                              # noqa: BLE001
            continue
    raise ValueError(f"JSON không hợp lệ: {err}")


def llm_json(system, user, max_tokens=8000):
    """Tối đa 3 lần: (1) bình thường; (2) báo rõ lỗi để model sửa; (3) tăng giới hạn token nếu bị cắt."""
    note, tokens, err = "", max_tokens, None
    for attempt in range(3):
        try:
            return parse_json(llm(system, user + note, tokens, json_mode=True))
        except Truncated:
            tokens = min(tokens * 2, 32000)
            note = "\n\nCÂU TRẢ LỜI TRƯỚC BỊ CẮT DO QUÁ DÀI. Hãy viết NGẮN GỌN hơn, bỏ giải thích thừa, vẫn đủ các trường bắt buộc."
            err = "câu trả lời bị cắt do quá dài"
        except ValueError as e:
            err = str(e)
            note = f"\n\nLẦN TRƯỚC JSON KHÔNG HỢP LỆ ({err[:120]}). Chỉ trả về đúng 1 đối tượng JSON hợp lệ: đóng đủ ngoặc, dấu ngoặc kép trong chuỗi phải thoát bằng \\\", xuống dòng trong code dùng \\n. Không giải thích."
    raise RuntimeError(f"AI trả về dữ liệu không đọc được sau 3 lần thử ({err}). Hãy bấm Thử lại, hoặc rút gọn góp ý.")


def strip_code(t):
    m = re.search(r"```(?:python)?\s*(.*?)```", t, re.S)
    return (m.group(1) if m else t).strip()
