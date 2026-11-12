# -*- coding: utf-8 -*-
"""Mỗi cột ngày có MỘT Ý NGHĨA riêng, và chỉ có một số cột nói về KỲ CỦA DỮ LIỆU.

Trước đây hệ thống lấy cột ngày đầu tiên tìm được làm «Khoảng ngày» của cả bộ dữ liệu, nên ngày sinh khách hàng (1955 → 2004) bị ghi thành
khoảng thời gian dữ liệu, rồi đi tiếp vào bản tổng hợp, báo cáo và PowerPoint. Nay:
  * `event`  ngày PHÁT SINH sự việc (ngày đặt hàng, giao dịch, thanh toán, giao hàng...): đây mới là kỳ của dữ liệu.
  * `birth`  ngày sinh: thuộc tính của một người, không phải thời gian diễn ra dữ liệu.
  * `signup` ngày đăng ký / tham gia / mở tài khoản: thuộc tính của khách hàng, không phải kỳ dữ liệu.
  * `other`  ngày không rõ ý nghĩa (tên cột không gợi ý): vẫn liệt kê, nhưng chỉ làm kỳ dữ liệu khi không còn cột nào rõ hơn.
Nhận diện theo TÊN CỘT trước; với cột tên chung chung ở bảng danh mục (bảng được nơi khác tham chiếu) thì xét thêm giá trị."""
import re

import pandas as pd

from .. import labels as lb
from .quality import date_like, is_text, to_dt

ROLE_LABEL = {"event": "Ngày phát sinh", "birth": "Ngày sinh", "signup": "Ngày đăng ký / tham gia", "other": "Ngày khác"}
BIRTH = re.compile(r"ngay\s*_?sinh|ngaysinh|nam\s*_?sinh|namsinh|sinh\s*_?nhat|sinhnhat|(?<![a-z])dob(?![a-z])|birth|date_of_birth|dateofbirth|(?<![a-z])ns(?![a-z])")
SIGNUP = re.compile(r"dang\s*_?ky|dangky|(?<![a-z])dk(?![a-z])|ngaydk|regist|sign\s*_?up|signup|tham\s*_?gia|thamgia|(?<![a-z])join|mo\s*_?tai\s*_?khoan|motk|kich\s*_?hoat|kichhoat|activat|member\s*_?since|customer\s*_?since")
CREATED = re.compile(r"ngay\s*_?tao|ngaytao|created|create_?date|tao\s*_?luc|ghi\s*_?nhan|cap\s*_?nhat|capnhat|updated|modified")
# từ gợi ý ngày PHÁT SINH sự việc: ưu tiên làm kỳ dữ liệu
EVENT = re.compile(r"(?<![a-z])dat(?![a-z])|dat\s*_?hang|ngaydat|(?<![a-z])order|mua|ban\s*_?hang|banhang|giao\s*_?dich|giaodich|thanh\s*_?toan|thanhtoan|invoice|hoa\s*_?don|hoadon|transaction|payment|"
                   r"giao\s*_?hang|giaohang|(?<![a-z])giao(?![a-z])|ngaygiao|ngayban|(?<![a-z])ban(?![a-z])|ngaylap|lap\s*_?(hd|phieu|don)|ship|deliver|xuat\s*_?kho|nhap\s*_?kho|(?<![a-z])phat\s*_?sinh|ky\s*_?bao\s*_?cao|(?<![a-z])period|(?<![a-z])time|thang\b")


def short(name):
    """Tên bảng dễ đọc: «tệp.xlsx::Sheet» -> «Sheet»; tệp CSV -> tên tệp bỏ đuôi."""
    s = str(name)
    if "::" in s:
        return s.split("::", 1)[1]
    return re.sub(r"\.[A-Za-z0-9]{1,5}$", "", s)


def group(name):
    """Tên tệp chứa bảng: «tệp.xlsx::Sheet» -> «tệp.xlsx»."""
    return str(name).split("::", 1)[0]


def _as_dt(s):
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    if is_text(s) and date_like(s):
        return to_dt(s)
    return None


def role_of(col, t=None, dim_table=False):
    """(vai_trò, đoán). `t` là Series ngày đã đọc (để xét giá trị), `dim_table` = bảng này là bảng danh mục (được bảng khác tham chiếu)."""
    f = lb.fold(col)
    if BIRTH.search(f):
        return "birth", False
    if SIGNUP.search(f):
        return "signup", False
    if EVENT.search(f):
        return "event", False
    if CREATED.search(f) and dim_table:
        return "signup", True                       # «ngày tạo» ở bảng khách hàng / sản phẩm là lúc tạo hồ sơ, không phải lúc phát sinh giao dịch
    if t is not None and dim_table and t.notna().any():
        lo, hi = t.min(), t.max()
        if (hi - lo).days >= 25 * 365 and hi < pd.Timestamp.now() - pd.Timedelta(days=10 * 365):
            return "birth", True                    # trải hơn 25 năm và toàn bộ cách đây hơn 10 năm ở bảng danh mục: gần như chắc là ngày sinh
    return "other", False


def date_cols(dfs, dim_tables=()):
    """Mọi cột ngày của mọi bảng: [{file, table, col, label, n, min, max, role, role_label, guess}]."""
    out = []
    for fname, d in dfs.items():
        for c in d.columns:
            t = _as_dt(d[c])
            if t is None or not t.notna().any():
                continue
            role, guess = role_of(c, t, fname in dim_tables)
            out.append({"file": fname, "table": short(fname), "col": str(c), "label": lb.label(c), "n": int(t.notna().sum()), "rows": int(len(d)),
                        "min": f"{t.min():%d/%m/%Y}", "max": f"{t.max():%d/%m/%Y}", "role": role, "role_label": ROLE_LABEL[role], "guess": bool(guess)})
    return out


def pick_period(cols):
    """Cột ngày làm KỲ CỦA DỮ LIỆU: ưu tiên ngày phát sinh có tên rõ nghĩa, rồi nhiều dòng nhất. Không có ngày phát sinh thì lấy ngày không rõ nghĩa;
    chỉ có ngày sinh / đăng ký thì KHÔNG có kỳ dữ liệu (trả None)."""
    def score(c):
        named = bool(EVENT.search(lb.fold(c["col"])))
        return (named, c["n"])
    ev = [c for c in cols if c["role"] == "event"]
    if ev:
        return max(ev, key=score)
    oth = [c for c in cols if c["role"] == "other"]
    return max(oth, key=lambda c: c["n"]) if oth else None
