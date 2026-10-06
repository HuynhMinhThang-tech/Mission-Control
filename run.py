# -*- coding: utf-8 -*-
"""MISSION CONTROL - điểm khởi chạy.
Cài  : python -m pip install -r requirements.txt
Cấu hình: sao chép .env.example thành .env rồi điền GEMINI_API_KEY
Chạy : python run.py   -> mở http://localhost:8000
"""
import threading
import webbrowser

from app import create_app
from app import config

app = create_app()

if __name__ == "__main__":
    if not config.API_KEY:
        print("⚠️  Chưa có GEMINI_API_KEY: hãy tạo file .env (xem .env.example)")
    if config.OPEN_BROWSER:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{config.PORT}")).start()
    app.run(host=config.HOST, port=config.PORT, threaded=True)
