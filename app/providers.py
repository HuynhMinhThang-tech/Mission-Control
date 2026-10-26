# -*- coding: utf-8 -*-
"""Nhà cung cấp LLM: Base URL KHÔNG phải ô nhập độc lập, mà là hệ quả của nhà cung cấp được chọn.

Ứng dụng gọi mọi nhà cung cấp qua giao diện tương thích OpenAI. Mỗi nhà cung cấp có Base URL riêng và họ model riêng
(gemini-*, gpt-*, claude-*...). Nếu model thuộc họ này mà Base URL trỏ tới nhà cung cấp khác thì chắc chắn lỗi, nên ta báo sớm bằng
tiếng Việt kèm cách sửa thay vì để API trả về 404/400 khó hiểu. Gateway (OpenRouter, Groq, Ollama, tuỳ chỉnh) chạy nhiều họ model nên không bị ép khớp.
Gemini, Anthropic đã đối chiếu tài liệu chính thức; các địa chỉ còn lại là địa chỉ công khai phổ biến, nút "Lưu và kiểm tra kết nối" sẽ bắt sai lệch.
"""
import re
from urllib.parse import urlparse

PROVIDERS = [
    {"id": "gemini", "label": "Google Gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "host": r"generativelanguage\.googleapis\.com",
     "model_re": r"^(models/)?gemini", "hint": "gemini-2.5-flash"},
    {"id": "openai", "label": "OpenAI", "base_url": "https://api.openai.com/v1", "host": r"api\.openai\.com",
     "model_re": r"^(gpt-|o\d|chatgpt-)", "hint": "gpt-4o-mini"},
    {"id": "anthropic", "label": "Anthropic (Claude)", "base_url": "https://api.anthropic.com/v1/", "host": r"api\.anthropic\.com",
     "model_re": r"^claude", "hint": "claude-sonnet-4-5",
     "note": "Lớp tương thích OpenAI của Anthropic được hãng mô tả là dùng để thử và so sánh, không khuyến nghị cho sản xuất lâu dài."},
    {"id": "deepseek", "label": "DeepSeek", "base_url": "https://api.deepseek.com", "host": r"api\.deepseek\.com",
     "model_re": r"^deepseek", "hint": "deepseek-chat"},
    {"id": "openrouter", "label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "host": r"openrouter\.ai",
     "model_re": None, "hint": "google/gemini-2.5-flash", "gateway": True},
    {"id": "groq", "label": "Groq", "base_url": "https://api.groq.com/openai/v1", "host": r"api\.groq\.com",
     "model_re": None, "hint": "llama-3.3-70b-versatile", "gateway": True},
    {"id": "ollama", "label": "Ollama (máy cục bộ)", "base_url": "http://localhost:11434/v1", "host": r"^(localhost|127\.0\.0\.1)$",
     "model_re": None, "hint": "llama3.1", "gateway": True, "note": "Chỉ dùng được khi chạy máy cá nhân (máy chủ công khai chặn địa chỉ nội bộ)."},
    {"id": "custom", "label": "Tuỳ chỉnh (tương thích OpenAI)", "base_url": "", "host": None,
     "model_re": None, "hint": "tên-model", "gateway": True, "custom": True},
]
BY_ID = {p["id"]: p for p in PROVIDERS}
FAMILIES = [p for p in PROVIDERS if p.get("model_re")]


def host_of(url):
    try:
        return (urlparse((url or "").strip()).hostname or "").lower()
    except ValueError:
        return ""


def provider_of_url(url):
    """Nhà cung cấp mà Base URL trỏ tới (id) hoặc None nếu là địa chỉ lạ."""
    h = host_of(url)
    for p in PROVIDERS:
        if p.get("host") and h and re.search(p["host"], h):
            return p["id"]
    return None


def family_of_model(model):
    """Họ model (id nhà cung cấp gốc) theo tên: 'gpt-4o' -> 'openai'. None nếu không nhận ra."""
    m = (model or "").strip().lower()
    for p in FAMILIES:
        if re.search(p["model_re"], m):
            return p["id"]
    return None


def check_pair(base_url, model):
    """Trả về thông báo lỗi tiếng Việt nếu Base URL và model chắc chắn không đi với nhau; None nếu ổn hoặc không đủ cơ sở kết luận."""
    pid, fam = provider_of_url(base_url), family_of_model(model)
    if not pid or not fam or fam == pid or BY_ID[pid].get("gateway"):
        return None
    return (f"Model '{model}' là của {BY_ID[fam]['label']} nhưng Base URL đang trỏ tới {BY_ID[pid]['label']}. "
            f"Hãy chọn nhà cung cấp \"{BY_ID[fam]['label']}\" (Base URL sẽ tự điền đúng), hoặc đổi tên model cho khớp {BY_ID[pid]['label']}.")


def public():
    """Danh sách gửi cho giao diện (không chứa bí mật)."""
    return [{k: p.get(k) for k in ("id", "label", "base_url", "model_re", "hint", "note", "gateway", "custom")} for p in PROVIDERS]
