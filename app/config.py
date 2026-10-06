# -*- coding: utf-8 -*-
"""Cấu hình đọc từ file .env (không để khóa API trong mã nguồn)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
GEMINI_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/").strip()

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
OPEN_BROWSER = os.getenv("OPEN_BROWSER", "1") == "1"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))

STATIC_DIR = BASE / "static"
TEMPLATE_DIR = BASE / "templates"
WORK = BASE / "workspace"
WORK.mkdir(exist_ok=True)
