# -*- coding: utf-8 -*-
"""Lớp gọi LLM (Gemini qua endpoint tương thích OpenAI)."""
import json
import re

from . import config

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=config.API_KEY, base_url=config.GEMINI_URL)
    return _client


def llm(system, user, max_tokens=6000):
    if not config.API_KEY or not config.MODEL:
        raise RuntimeError("Chưa cấu hình GEMINI_API_KEY / GEMINI_MODEL trong file .env")
    r = _get_client().chat.completions.create(
        model=config.MODEL, max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    return r.choices[0].message.content


def parse_json(t):
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    t = m.group(1) if m else t
    return json.loads(t[t.find("{"): t.rfind("}") + 1])


def llm_json(system, user, max_tokens=6000):
    try:
        return parse_json(llm(system, user, max_tokens))
    except Exception:
        return parse_json(llm(system, user + "\n\nLẦN TRƯỚC JSON KHÔNG HỢP LỆ. Chỉ trả về đúng 1 JSON hợp lệ, không giải thích.", max_tokens))


def strip_code(t):
    m = re.search(r"```(?:python)?\s*(.*?)```", t, re.S)
    return (m.group(1) if m else t).strip()
