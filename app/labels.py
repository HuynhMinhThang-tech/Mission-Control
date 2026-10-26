# -*- coding: utf-8 -*-
"""Tên cột -> nhãn tiếng Việt dễ đọc, và ĐƠN VỊ của cột. Dùng cho bảng điều khiển, báo cáo, slide.

Người dùng không nên thấy `trongLuongKg` hay `danhMuc` trên báo cáo. Quy trình: tách từ (camelCase, snake_case, dấu cách) ->
khôi phục dấu bằng từ điển cụm từ rồi từ điển từ -> thêm đơn vị nếu có. Tên đã có dấu tiếng Việt thì giữ nguyên.
Đơn vị suy ra THEO TỪ (không theo chuỗi con): `trongLuongKg` là kg, không phải tiền dù chứa chữ 'luong'.
"""
import re
import unicodedata

# Cụm từ (ưu tiên khớp dài nhất). Khóa: các từ không dấu, viết thường, cách nhau một dấu cách.
PHRASES = {
    "gia niem yet": "giá niêm yết", "gia von": "giá vốn", "gia ban": "giá bán", "gia nhap": "giá nhập", "don gia": "đơn giá", "gia tri": "giá trị",
    "trong luong": "trọng lượng", "so luong": "số lượng", "so lan": "số lần", "so ngay": "số ngày", "so don": "số đơn", "so don hang": "số đơn hàng",
    "danh muc": "danh mục", "thuong hieu": "thương hiệu", "nha cung cap": "nhà cung cấp", "san pham": "sản phẩm", "ma san pham": "mã sản phẩm",
    "ten san pham": "tên sản phẩm", "khach hang": "khách hàng", "ma khach hang": "mã khách hàng", "ten khach hang": "tên khách hàng",
    "don hang": "đơn hàng", "ma don hang": "mã đơn hàng", "ngay dat": "ngày đặt", "ngay dat hang": "ngày đặt hàng", "ngay giao": "ngày giao",
    "ngay giao hang": "ngày giao hàng", "ngay mua": "ngày mua", "ngay ban": "ngày bán", "ngay thanh toan": "ngày thanh toán",
    "thanh pho": "thành phố", "tinh thanh": "tỉnh thành", "quan huyen": "quận huyện", "khu vuc": "khu vực", "mien bac": "miền Bắc",
    "mien nam": "miền Nam", "mien trung": "miền Trung", "dia chi": "địa chỉ", "so dien thoai": "số điện thoại",
    "doanh thu": "doanh thu", "doanh so": "doanh số", "loi nhuan": "lợi nhuận", "chi phi": "chi phí", "thanh tien": "thành tiền", "tong tien": "tổng tiền",
    "thue vat": "thuế VAT", "phi van chuyen": "phí vận chuyển", "van chuyen": "vận chuyển", "phuong thuc": "phương thức",
    "phuong thuc thanh toan": "phương thức thanh toán", "hinh thuc thanh toan": "hình thức thanh toán", "hinh thuc": "hình thức", "thanh toan": "thanh toán",
    "trang thai": "trạng thái", "trang thai don hang": "trạng thái đơn hàng", "ty le": "tỷ lệ", "ty trong": "tỷ trọng", "ty le hoan tra": "tỷ lệ hoàn trả",
    "hoan tra": "hoàn trả", "tra hang": "trả hàng", "cap bac": "cấp bậc", "cap bac thanh vien": "cấp bậc thành viên", "thanh vien": "thành viên",
    "diem tich luy": "điểm tích lũy", "danh gia": "đánh giá", "luong co ban": "lương cơ bản", "phu cap": "phụ cấp", "phong ban": "phòng ban",
    "nhan vien": "nhân viên", "chuc vu": "chức vụ", "gioi tinh": "giới tính", "ngay sinh": "ngày sinh", "ngay vao lam": "ngày vào làm",
    "kenh ban": "kênh bán", "kenh ban hang": "kênh bán hàng", "nguon": "nguồn", "chuong trinh khuyen mai": "chương trình khuyến mãi", "khuyen mai": "khuyến mãi",
    "giam gia": "giảm giá", "tien thuong": "tiền thưởng", "ma giam gia": "mã giảm giá", "ton kho": "tồn kho", "kho hang": "kho hàng", "kich thuoc": "kích thước", "mau sac": "màu sắc",
    "ghi chu": "ghi chú", "nam sinh": "năm sinh", "thoi gian": "thời gian", "thoi gian giao": "thời gian giao", "ngan sach": "ngân sách",
    "dien thoai": "điện thoại", "phu kien": "phụ kiện", "dien thoai phu kien": "điện thoại & phụ kiện",
    "du lieu": "dữ liệu", "thuong mai": "thương mại", "dien tu": "điện tử", "thuong mai dien tu": "thương mại điện tử", "ban hang": "bán hàng", "mua hang": "mua hàng",
    "bao cao": "báo cáo", "tong hop": "tổng hợp", "chi tiet": "chi tiết", "thong ke": "thống kê", "nhap kho": "nhập kho", "xuat kho": "xuất kho", "hoa don": "hóa đơn",
    "ngan hang": "ngân hàng", "tai khoan": "tài khoản", "so du": "số dư", "ket qua": "kết quả", "ke hoach": "kế hoạch", "thuc te": "thực tế", "muc tieu": "mục tiêu",
    "chi tieu": "chi tiêu", "thu nhap": "thu nhập", "tiet kiem": "tiết kiệm", "dau tu": "đầu tư", "tong doanh thu": "tổng doanh thu", "tong chi phi": "tổng chi phí",
    "theo thang": "theo tháng", "theo nam": "theo năm", "theo vung": "theo vùng", "theo ngay": "theo ngày", "bang": "bảng", "ma vach": "mã vạch",
}

# Từ đơn (không dấu -> có dấu). Chọn nghĩa thông dụng nhất trong dữ liệu kinh doanh.
WORDS = {
    "ma": "mã", "ten": "tên", "ngay": "ngày", "thang": "tháng", "nam": "năm", "quy": "quý", "tuan": "tuần", "gio": "giờ", "ky": "kỳ", "thu": "thu",
    "so": "số", "luong": "lương", "gia": "giá", "tien": "tiền", "von": "vốn", "phi": "phí", "thue": "thuế", "ban": "bán", "mua": "mua", "nhap": "nhập", "xuat": "xuất",
    "danh": "danh", "muc": "mục", "loai": "loại", "nhom": "nhóm", "hang": "hàng", "don": "đơn", "khach": "khách", "vung": "vùng", "khu": "khu", "vuc": "vực",
    "tinh": "tỉnh", "thanh": "thành", "pho": "phố", "quan": "quận", "huyen": "huyện", "phuong": "phường", "xa": "xã", "dia": "địa", "chi": "chi",
    "san": "sản", "pham": "phẩm", "thuong": "thương", "hieu": "hiệu", "trong": "trọng", "niem": "niêm", "yet": "yết", "tong": "tổng", "trung": "trung", "binh": "bình",
    "cao": "cao", "thap": "thấp", "nhat": "nhất", "lon": "lớn", "nho": "nhỏ", "moi": "mới", "cu": "cũ", "tot": "tốt", "kem": "kém", "dat": "đặt", "giao": "giao",
    "hoan": "hoàn", "tra": "trả", "huy": "hủy", "duyet": "duyệt", "cho": "chờ", "ty": "tỷ", "le": "lệ", "phan": "phần", "tram": "trăm", "diem": "điểm",
    "tich": "tích", "luy": "lũy", "bac": "bậc", "cap": "cấp", "vien": "viên", "nhan": "nhân", "phong": "phòng", "gioi": "giới",
    "tuoi": "tuổi", "sinh": "sinh", "dong": "đồng", "vnd": "VND", "kho": "kho", "ton": "tồn", "kenh": "kênh", "nguon": "nguồn", "mau": "màu", "sac": "sắc",
    "kich": "kích", "thuoc": "thước", "rong": "rộng", "dai": "dài", "nang": "nặng", "the": "thẻ", "tin": "tín", "dung": "dụng", "ngan": "ngân",
    "sach": "sách", "doanh": "doanh", "loi": "lợi", "nhuan": "nhuận", "lai": "lãi", "lo": "lỗ", "du": "dư", "no": "nợ", "co": "có", "cua": "của",
    "va": "và", "theo": "theo", "voi": "với", "tu": "từ", "den": "đến", "trang": "trạng", "thai": "thái", "ghi": "ghi", "chu": "chú", "mo": "mô", "ta": "tả",
    "dien": "điện", "thoai": "thoại", "email": "email", "sdt": "SĐT", "stt": "STT", "sku": "SKU", "id": "ID", "url": "URL", "vat": "VAT", "kpi": "KPI",
    "thoi": "thời", "gian": "gian", "dich": "dịch", "vu": "vụ", "hoa": "hóa", "hop": "hợp", "bao": "báo", "tai": "tài", "khoan": "khoản",
    "nghiep": "nghiệp", "viec": "việc", "luu": "lưu", "kien": "kiện", "chuyen": "chuyển", "van": "vận", "phat": "phát",
}

UNIT_TOKENS = {"kg": "kg", "g": "g", "gram": "g", "cm": "cm", "mm": "mm", "km": "km", "ml": "ml", "lit": "lít", "pct": "%", "percent": "%", "vnd": "đ", "usd": "USD"}
MONEY_PHRASES = ("doanh thu", "doanh so", "loi nhuan", "chi phi", "gia", "don gia", "gia von", "gia ban", "gia niem yet", "gia nhap", "tien", "thanh tien", "tong tien",
                 "thu nhap", "luong", "luong co ban", "phu cap", "tien thuong", "von", "ngan sach", "phi", "thue", "giam gia", "tra gop", "vnd", "dong",
                 "revenue", "sales", "amount", "cost", "profit", "price", "salary", "income", "wage", "bonus")
PCT_PHRASES = ("ty le", "ty trong", "phan tram", "pct", "percent", "ti le", "rate", "ratio", "share")
RATE_PHRASES = ("gia", "don gia", "gia von", "gia ban", "gia niem yet", "gia nhap", "ty le", "ty trong", "phan tram", "pct", "percent", "ti le", "rate", "ratio", "diem",
                "danh gia", "rating", "score", "price", "trong luong", "kich thuoc", "tuoi", "nhiet do", "do tuoi", "thoi gian giao")
HEAD_LAST = {"id": "mã", "name": "tên", "date": "ngày", "code": "mã", "count": "số lượng", "type": "loại", "status": "trạng thái", "rate": "tỷ lệ"}
ID_WORDS = {"id", "ma", "code", "stt", "sdt", "phone", "email", "sku", "uuid", "guid"}
_NOT_MONEY_BEFORE = {"so", "san", "trong"}                 # "số lượng", "sản lượng", "trọng lượng" không phải lương/tiền


def fold(s):
    """Bỏ dấu tiếng Việt, viết thường: 'Danh mục' -> 'danh muc'."""
    s = unicodedata.normalize("NFD", str(s).replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def has_viet(s):
    """Có ký tự tiếng Việt có dấu (tên cột đã được viết đẹp)."""
    return bool(re.search(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", str(s).lower()))


def _split(col):
    """Tách tên cột thành các từ gốc (giữ nguyên hoa/thường, dấu): 'TrongLuongKg' -> ['Trong','Luong','Kg']."""
    s = str(col).strip()
    s = re.sub(r"(?<=[a-zà-ỹ0-9])(?=[A-ZÀ-Ỹ])", " ", s)            # camelCase
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", s)                   # HTMLText -> HTML Text
    return [t for t in re.split(r"[\W_]+", s) if t]


def tokens(col):
    """Các từ không dấu, viết thường: 'TrongLuongKg' -> ['trong','luong','kg']."""
    return [fold(t) for t in _split(col)]


def _phrase_key(toks):
    return " ".join(toks)


def _rebuild(toks, raw_toks):
    """Ghép lại thành chuỗi tiếng Việt: khớp cụm dài nhất trước, rồi từ đơn; từ lạ giữ nguyên. Trả về (các từ, số từ lạ)."""
    out, i, unk = [], 0, 0
    while i < len(toks):
        for n in (4, 3, 2):
            key = _phrase_key(toks[i:i + n])
            if len(toks[i:i + n]) == n and key in PHRASES:
                out.append(PHRASES[key])
                i += n
                break
        else:
            t = toks[i]
            w = WORDS.get(t) or _english(t)
            if not w:
                w = raw_toks[i]
                unk += 0 if (t.isdigit() or len(t) <= 1 or w.isupper()) else 1
            out.append(w)
            i += 1
    return out, unk


def _english(t):
    from .lang import TOK                                           # từ điển tiếng Anh -> Việt đã có sẵn (tránh import vòng nên import trễ)
    return TOK.get(t)


def unit(col):
    """Đơn vị của cột ('kg', 'đ', '%', ''...). Suy theo TỪ nên không nhầm 'trongLuongKg' thành tiền."""
    toks = tokens(col)
    if not toks:
        return ""
    last = toks[-1]
    if last in UNIT_TOKENS and len(toks) > 1:
        return UNIT_TOKENS[last]
    key, joined = _phrase_key(toks), _phrase_key(toks)
    if any(p in joined for p in PCT_PHRASES) and not any(p in joined for p in ("doanh thu", "chi phi")):
        return "%"
    for i, t in enumerate(toks):                                    # "trong luong", "so luong", "san luong" -> không phải lương
        if t == "luong" and i > 0 and toks[i - 1] in _NOT_MONEY_BEFORE:
            toks = toks[:i - 1] + ["_"] + toks[i + 1:]
    joined = " ".join(toks)
    if any(re.search(rf"(^| ){re.escape(p)}( |$)", joined) for p in MONEY_PHRASES):
        return "đ"
    return ""


def is_rate(col):
    """Cột kiểu đơn giá/tỷ lệ/điểm/trọng lượng: tổng gộp không có nghĩa, nên dùng trung bình."""
    joined = " ".join(tokens(col))
    return any(re.search(rf"(^| ){re.escape(p)}( |$)", joined) for p in RATE_PHRASES) and not re.search(r"(^| )(tong|so luong)( |$)", joined)


def is_id(col):
    toks = tokens(col)
    return bool(toks) and (toks[0] in ID_WORDS or toks[-1] in ID_WORDS or _phrase_key(toks[:2]) in ("ma so",))


def label(col, with_unit=False):
    """'DanhMuc' -> 'Danh mục' · 'trongLuongKg' -> 'Trọng lượng' (with_unit=True: 'Trọng lượng (kg)') · tên đã đẹp thì giữ nguyên."""
    s = str(col).strip()
    if not s:
        return s
    if has_viet(s) and "_" not in s and not re.search(r"[a-zà-ỹ][A-ZÀ-Ỹ]", s):
        return s[:1].upper() + s[1:]                                  # đã là tiếng Việt có dấu, viết đẹp: giữ nguyên
    raw = _split(s)
    toks = tokens(s)
    u = UNIT_TOKENS.get(toks[-1]) if len(toks) > 1 and toks[-1] in UNIT_TOKENS else None
    core_t, core_r = (toks[:-1], raw[:-1]) if u else (toks, raw)
    if len(core_t) > 1 and core_t[-1] in HEAD_LAST:                   # tiếng Anh đặt danh từ chính ở cuối, tiếng Việt đặt ở đầu: customer_name -> "Tên khách hàng"
        words, unk = _rebuild(core_t[:-1], core_r[:-1])
        words = [HEAD_LAST[core_t[-1]]] + words
    else:
        words, unk = _rebuild(core_t, core_r)
    if len(core_t) >= 2 and unk / len(core_t) > .4:                  # quá nhiều từ lạ: thêm dấu nửa vời trông sai hơn là giữ nguyên
        plain = " ".join(core_r)
        return plain[:1].upper() + plain[1:]
    text = " ".join(words).strip()
    text = text[:1].upper() + text[1:]
    if with_unit and (u or unit(col)):
        un = u or unit(col)
        text += f" ({un})"
    return text or s


def labelize_columns(cols, with_unit=False):
    """Danh sách nhãn không trùng nhau cho một nhóm cột."""
    seen, out = {}, []
    for c in cols:
        t = label(c, with_unit)
        k = seen.get(t, 0)
        seen[t] = k + 1
        out.append(t if not k else f"{t} ({k + 1})")
    return out
