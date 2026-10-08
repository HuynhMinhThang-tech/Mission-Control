# -*- coding: utf-8 -*-
"""Tab "API & Model": mỗi người dùng tự nhập API key (lưu MÃ HÓA), Base URL và model của riêng mình."""
import re

from flask import Blueprint, g, jsonify, request

from . import config, db, llm, state
from .auth import bad, over_limit
from .errors import UserError

bp = Blueprint("settings", __name__)
KEY_RE = re.compile(r"^[\x21-\x7e]{8,512}$")        # ký tự in được, KHÔNG có khoảng trắng/xuống dòng (lỗi dán key hay gặp)


@bp.errorhandler(UserError)
def _user_error(e):
    return bad(str(e))


def _read(require_model):
    """Đọc + kiểm tra form. Trả về (key_mới_hoặc_None, cfg_hiệu_lực)."""
    p = request.get_json(silent=True) or {}
    new_key = (p.get("api_key") or "").strip() or None
    if new_key and not KEY_RE.match(new_key):
        raise UserError("API key chứa khoảng trắng hoặc ký tự không hợp lệ (hoặc quá ngắn). Hãy sao chép lại đúng nguyên key, không kèm dấu cách/xuống dòng.")
    base = llm.check_base_url(p.get("base_url"))
    model = (p.get("model") or "").strip()
    if require_model and not model:
        raise UserError("Hãy nhập hoặc chọn tên model.")
    if len(model) > 200 or re.search(r"\s", model):
        raise UserError("Tên model không hợp lệ (không được chứa khoảng trắng, tối đa 200 ký tự).")
    key = new_key or db.load_llm_cfg(g.user["id"])["api_key"]
    if not key:
        raise UserError("Hãy nhập API key.")
    return new_key, {"api_key": key, "base_url": base, "model": model}


def _limited():
    return over_limit("llm_net", g.user["id"], 20, 600)        # mỗi lần kiểm tra/lấy model là một cuộc gọi ra ngoài


@bp.get("/api/settings/llm")
def get_llm():
    return jsonify({**db.llm_public(g.user["id"]), "default_model": config.DEFAULT_MODEL})


@bp.post("/api/settings/llm")
def save_llm():
    """Lưu rồi kiểm tra kết nối. Lưu trước để người dùng không mất thông tin vừa nhập; kết quả kiểm tra trả về riêng để hiện panel."""
    new_key, cfg = _read(require_model=True)
    uid = g.user["id"]
    db.save_llm(uid, new_key, cfg["base_url"], cfg["model"])
    state.invalidate_llm(uid)
    out = {"ok": True, "saved": True, "settings": db.llm_public(uid)}
    if _limited():
        out["test"] = {"ok": False, "message": "Đã lưu. Bạn kiểm tra kết nối quá nhiều lần, hãy thử lại sau vài phút."}
        return jsonify(out)
    try:
        llm.test_connection(cfg)
        out["test"] = {"ok": True, "message": f"Kết nối thành công với model {cfg['model']}."}
    except UserError as e:
        out["test"] = {"ok": False, "message": str(e)}
    return jsonify(out)


@bp.post("/api/settings/llm/models")
def models():
    _, cfg = _read(require_model=False)
    if _limited():
        return bad("Bạn thao tác quá nhiều lần. Hãy thử lại sau vài phút.", 429)
    return jsonify(models=llm.list_models(cfg))


@bp.post("/api/settings/llm/clear")
def clear():
    uid = g.user["id"]
    db.clear_llm_key(uid)
    state.invalidate_llm(uid)
    return jsonify(ok=True, settings=db.llm_public(uid))
