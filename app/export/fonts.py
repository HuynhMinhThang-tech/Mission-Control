# -*- coding: utf-8 -*-
"""Phông chữ của BÁO CÁO HTML và BẢNG ĐIỀU KHIỂN.

Phông của Claude (Anthropic Sans / Anthropic Serif) là phông riêng của Anthropic, không có bản miễn phí để nhúng.
Bộ mặc định «Giống Claude» dùng cặp gần nhất đều hỗ trợ tiếng Việt đầy đủ: tiêu đề chữ có chân (Source Serif 4, gần Anthropic Serif),
nội dung chữ không chân (Inter, gần Anthropic Sans). Người dùng đổi được ở thư viện biểu đồ (bước Báo cáo); lựa chọn nằm trong bản thiết kế `bp.font`.

Phông tải từ Google Fonts khi mở trực tuyến; ngoại tuyến thì dùng phông hệ thống trong chuỗi dự phòng (trang vẫn đọc tốt).
Bản trình chiếu PPTX không dùng được phông web (PowerPoint không nhúng được, máy không cài thì bị thay bằng phông mặc định) nên dùng cặp phông
CÓ SẴN trên Windows/macOS gần với bộ phông đã chọn: tiêu đề chữ có chân -> Georgia, nội dung chữ không chân -> Segoe UI (xem _PPT, pptx())."""
from urllib.parse import quote_plus

DEFAULT = "claude"
SANS_FB = '"Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif'
SERIF_FB = '"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif'

# key -> (nhãn hiển thị, (họ chữ tiêu đề, kiểu), (họ chữ nội dung, kiểu), trọng số cần tải)
_SPEC = {
    "claude": ("Giống Claude (mặc định)", ("Source Serif 4", "serif"), ("Inter", "sans"), {"Source Serif 4": "500;600;700", "Inter": "400;500;600;700"}),
    "app": ("Giống giao diện ứng dụng", ("Source Serif 4", "serif"), ("DM Sans", "sans"), {"Source Serif 4": "500;600;700", "DM Sans": "400;500;600;700"}),
    "inter": ("Hiện đại (Inter)", ("Inter", "sans"), ("Inter", "sans"), {"Inter": "400;500;600;700"}),
    "bevn": ("Tối ưu tiếng Việt (Be Vietnam Pro)", ("Be Vietnam Pro", "sans"), ("Be Vietnam Pro", "sans"), {"Be Vietnam Pro": "400;500;600;700"}),
    "serif": ("Báo chí, chữ có chân (Source Serif 4)", ("Source Serif 4", "serif"), ("Source Serif 4", "serif"), {"Source Serif 4": "400;500;600;700"}),
    "system": ("Phông hệ thống (nhẹ nhất, dùng được ngoại tuyến)", ("", "sans"), ("", "sans"), {}),
}


# key -> (phông tiêu đề, phông nội dung) CHO POWERPOINT. Phải là phông có sẵn trên máy người mở; JS (static/js/analysis.js, PPT_FONTS) hiển thị đúng bảng này
# (tests/pptx_font_test.py so khớp hai bên). "system" giữ Arial như trước cho ai muốn phông trung tính nhất.
_PPT = {"claude": ("Georgia", "Segoe UI"), "app": ("Georgia", "Segoe UI"), "inter": ("Segoe UI", "Segoe UI"), "bevn": ("Segoe UI", "Segoe UI"),
        "serif": ("Georgia", "Georgia"), "system": ("Arial", "Arial")}


def norm(key):
    return key if key in _SPEC else DEFAULT


def pptx(key):
    """(phông tiêu đề, phông nội dung) của bản PowerPoint theo bộ phông đã chọn."""
    return _PPT[norm(key)]


def _stack(name, kind):
    fb = SERIF_FB if kind == "serif" else SANS_FB
    return f'"{name}",{fb}' if name else fb


def url(key):
    fam = _SPEC[norm(key)][3]
    if not fam:
        return ""
    return "https://fonts.googleapis.com/css2?" + "&".join(f"family={quote_plus(n)}:wght@{w}" for n, w in fam.items()) + "&display=swap"


def public():
    """Bảng đầy đủ cho trang (bản xem thử đổi phông tức thì không cần dựng lại)."""
    return {k: {"label": v[0], "head": _stack(*v[1]), "body": _stack(*v[2]), "url": url(k), "ppt": list(_PPT[k])} for k, v in _SPEC.items()}


def head_html(key):
    """Thẻ <link> tải phông (nếu có) và biến CSS --font / --fh. Đặt SAU khối CSS chính để ghi đè giá trị mặc định."""
    k = norm(key)
    p = public()[k]
    link = f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link id="fontlink" rel="stylesheet" href="{p["url"]}">' if p["url"] else ""
    return f'{link}<style id="fontvars">:root{{--font:{p["body"]};--fh:{p["head"]}}}</style>'
