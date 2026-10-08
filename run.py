# -*- coding: utf-8 -*-
"""MISSION CONTROL - điểm khởi chạy.
Cài  : python -m pip install -r requirements.txt
Cấu hình: sao chép .env.example thành .env (admin đầu tiên); mỗi người dùng tự nhập API key trong tab "API & Model"
Chạy : python run.py   -> mở http://localhost:8000
"""
import threading
import webbrowser

from app import create_app
from app import config

app = create_app()

if __name__ == "__main__":
    if config.OPEN_BROWSER:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{config.PORT}")).start()
    app.run(host=config.HOST, port=config.PORT, threaded=True)
