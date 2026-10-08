# -*- coding: utf-8 -*-
"""Công cụ dòng lệnh chạy trên máy chủ (cần DATABASE_URL trỏ đúng database).
  python manage.py set-password email@gmail.com    # đặt lại mật khẩu của BẤT KỲ tài khoản nào, kể cả admin quên mật khẩu
Quyền admin thì cấp bằng SQL: xem sql/schema.sql (phần 3)."""
import getpass
import sys

from app import db


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "set-password":
        sys.exit(__doc__)
    email = sys.argv[2].strip().lower()
    pw = getpass.getpass("Mật khẩu mới: ")
    if len(pw) < 8 or len(pw) > 128:
        sys.exit("Mật khẩu cần từ 8 đến 128 ký tự.")
    if pw != getpass.getpass("Nhập lại mật khẩu: "):
        sys.exit("Mật khẩu xác nhận không khớp.")
    db.init_db()
    print("Đã đổi mật khẩu (mọi phiên đăng nhập cũ bị đăng xuất)." if db.set_password(email, pw) else f"Không tìm thấy tài khoản {email}.")


if __name__ == "__main__":
    main()
