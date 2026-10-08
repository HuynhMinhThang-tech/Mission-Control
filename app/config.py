# -*- coding: utf-8 -*-
"""Cấu hình đọc từ file .env / biến môi trường (không để khóa bí mật trong mã nguồn)."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

STATIC_DIR = BASE / "static"
TEMPLATE_DIR = BASE / "templates"
WORK = BASE / "workspace"          # chỉ dùng cho SQLite khi chạy máy cá nhân (và khóa phiên tạm)
WORK.mkdir(exist_ok=True)

# --- LLM: khóa API / model / Base URL do TỪNG người dùng tự nhập trong tab "API & Model" (lưu mã hóa trong database).
#     Dưới đây chỉ là giá trị gợi ý ban đầu hiển thị trong form. ---
DEFAULT_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/").strip()
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

# --- Máy chủ ---
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
OPEN_BROWSER = os.getenv("OPEN_BROWSER", "1") == "1"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
IS_PROD = os.getenv("APP_ENV", "dev").strip().lower() == "production"
TRUST_PROXY = os.getenv("TRUST_PROXY", "1" if IS_PROD else "0") == "1"      # sau Railway/Render: tin header X-Forwarded-*
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1" if IS_PROD else "0") == "1"

# --- Cơ sở dữ liệu: Postgres khi deploy (DATABASE_URL), SQLite khi chạy máy cá nhân ---
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    DATABASE_URL = f"sqlite:///{(WORK / 'app.db').as_posix()}"
else:
    # Nhà cung cấp cấp URL dạng postgres:// hoặc postgresql://. Chỉ định rõ driver psycopg2 (đã có trong requirements) vì
    # các bản SQLAlchemy mới tự chọn psycopg v3 cho 'postgresql://' -> sẽ lỗi ModuleNotFoundError khi khởi động.
    for _p in ("postgres://", "postgresql://"):
        if DATABASE_URL.startswith(_p):
            DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len(_p):]
            break


def _persisted(env_name, fname, hint):
    """Lấy khóa bí mật từ biến môi trường; khi chạy dev thì tự sinh và nhớ trong workspace/ để không đổi giữa các lần khởi động."""
    k = os.getenv(env_name, "").strip()
    if k:
        return k
    if IS_PROD:
        raise RuntimeError(f"Thiếu {env_name}: bắt buộc khi APP_ENV=production ({hint}). Tạo bằng: python -c \"import secrets;print(secrets.token_hex(32))\"")
    f = WORK / fname
    if f.exists():
        return f.read_text("utf-8").strip()
    k = secrets.token_hex(32)
    f.write_text(k, "utf-8")
    return k


SECRET_KEY = _persisted("SECRET_KEY", ".secret_key", "ký cookie đăng nhập")
# MASTER_KEY mã hóa API key của người dùng trong database. TÁCH RIÊNG với SECRET_KEY và phải sao lưu: mất khóa này thì mọi API key đã lưu không giải mã được.
MASTER_KEY = _persisted("MASTER_KEY", ".master_key", "mã hóa API key người dùng")
SESSION_DAYS = int(os.getenv("SESSION_DAYS", "14"))

# --- Tài khoản admin đầu tiên (chỉ được tạo khi chưa tồn tại email này) ---
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_NAME = os.getenv("ADMIN_NAME", "Admin").strip() or "Admin"
