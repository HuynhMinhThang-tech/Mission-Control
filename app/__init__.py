# -*- coding: utf-8 -*-
import warnings

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from . import auth, config, db, settings, state

HTTP_MSG = {404: "Không tìm thấy chức năng hoặc dữ liệu được yêu cầu (404). Hãy kiểm tra đã chép đủ file mới và khởi động lại server.",
            405: "Máy chủ không hỗ trợ thao tác này (405). Có thể bạn chưa cập nhật file routes.py.",
            413: f"Tệp quá lớn, giới hạn hiện tại là {config.MAX_UPLOAD_MB} MB (đổi MAX_UPLOAD_MB trong .env)."}


def create_app():
    warnings.filterwarnings("ignore")
    app = Flask(__name__, static_folder=str(config.STATIC_DIR), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.config.update(SECRET_KEY=config.SECRET_KEY, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      SESSION_COOKIE_SECURE=config.COOKIE_SECURE, PERMANENT_SESSION_LIFETIME=config.SESSION_DAYS * 86400)
    if config.TRUST_PROXY:                      # chạy sau proxy của Railway/Render: lấy đúng IP, host, https
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    db.init_db()
    from .routes import bp
    app.register_blueprint(auth.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(bp)
    app.before_request(auth.guard)
    app.teardown_request(state.unbind)

    @app.after_request
    def headers(r):
        r.headers.setdefault("X-Content-Type-Options", "nosniff")
        r.headers.setdefault("Referrer-Policy", "same-origin")
        if not request.path.startswith("/static/"):
            r.headers["Cache-Control"] = "no-store"          # không để trình duyệt giữ dữ liệu riêng tư sau khi đăng xuất
        return r

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