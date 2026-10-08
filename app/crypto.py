# -*- coding: utf-8 -*-
"""Mã hóa hai chiều cho API key của người dùng (Fernet = AES-128-CBC + HMAC), khóa chủ là MASTER_KEY trong biến môi trường.
Khác mật khẩu (băm một chiều): app phải đọc lại được key để gọi API thay người dùng, nên dùng mã hóa chứ không băm."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from . import config

_f = Fernet(base64.urlsafe_b64encode(hashlib.sha256(config.MASTER_KEY.encode("utf-8")).digest()))


def encrypt(uid, plain):
    """Gắn id người dùng vào bản rõ để dòng mã hóa của người này không thể bị chép sang tài khoản khác."""
    return _f.encrypt(f"{uid}:{plain}".encode("utf-8")).decode("ascii")


def decrypt(uid, token):
    """Trả về None nếu sai khóa chủ / dữ liệu bị sửa / không thuộc người dùng này."""
    try:
        s = _f.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
    pre = f"{uid}:"
    return s[len(pre):] if s.startswith(pre) else None
