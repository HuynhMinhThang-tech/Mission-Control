# -*- coding: utf-8 -*-
import warnings

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from . import config

HTTP_MSG = {404: "Không tìm thấy chức năng hoặc dữ liệu được yêu cầu (404). Hãy kiểm tra đã chép đủ file mới và khởi động lại server.",
            405: "Máy chủ không hỗ trợ thao tác này (405). Có thể bạn chưa cập nhật file routes.py.",
            413: f"Tệp quá lớn, giới hạn hiện tại là {config.MAX_UPLOAD_MB} MB (đổi MAX_UPLOAD_MB trong .env)."}


def create_app():
    warnings.filterwarnings("ignore")
    app = Flask(__name__, static_folder=str(config.STATIC_DIR), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    from .routes import bp
    app.register_blueprint(bp)

    @app.errorhandler(Exception)
    def on_error(e):
        """Lỗi ở /api luôn trả JSON {error: ...} để giao diện hiện bằng panel."""
        if not request.path.startswith("/api"):
            if isinstance(e, HTTPException):
                return e
            raise e
        if isinstance(e, HTTPException):
            return jsonify({"error": HTTP_MSG.get(e.code, e.description or "Có lỗi xảy ra")}), e.code
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Lỗi máy chủ: {type(e).__name__}: {e}"}), 500

    return app