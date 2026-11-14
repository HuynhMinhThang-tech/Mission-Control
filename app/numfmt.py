# -*- coding: utf-8 -*-
"""Chuẩn hóa SỐ và ĐƠN VỊ trong mọi chữ do AI viết (một thứ tiếng, một kiểu số) và đối chiếu số với bảng kết quả.

Vì sao cần: AI hay viết "2.24 trillion VNĐ", "2 241 813 537 điểm", "2240813537.5" - sai ngôn ngữ, sai đơn vị, không có dấu ngăn nghìn,
và đôi khi sai cả độ lớn. Ở đây mọi văn bản đi qua `fix_text` trước khi hiển thị; số lớn còn được đối chiếu với các bảng kết quả (`audit`).
Quy tắc số (một nơi duy nhất, xem utils.py): số nguyên 1.234.567 · số lẻ và tỷ lệ luôn 2 chữ số sau dấu phẩy (1.234,50 · 57,30%) ·
tiền ghi ĐỦ số kèm đơn vị của dữ liệu (2.240.813.537 đ), không viết tắt nghìn/triệu/tỷ.
"""
import re

import numpy as np
import pandas as pd

from .data import names as _names
from .utils import fmt_dec, fmt_pct, fmt_val, vn

# ------------------------------------------------------------------ định dạng --
MONEY_WORDS = re.compile(r"doanh thu|doanh số|chi phí|lợi nhuận|\bgiá\b|tiền|thu nhập|vốn|ngân sách|lương|đóng góp|chi tiêu|thanh toán|khoản thu", re.I)


def money_vi(v, nd=2):
    """Tiền ghi ĐỦ số, có dấu ngăn nghìn (1250000000 -> '1.250.000.000'); không viết tắt tỷ/triệu/nghìn."""
    return vn(v, nd)


def num_vi(v, nd=2):
    return vn(v, nd)


def pct_vi(ratio, nd=2):
    return fmt_pct(ratio * 100, nd)


# ------------------------------------------------------------------ giá trị đã biết --
class Known:
    """Tập mọi con số có trong các bảng kết quả (từng ô + tổng từng cột), để đối chiếu số trong văn bản."""

    def __init__(self, values=(), direct=None):
        arr = np.asarray([float(v) for v in values if v is not None and np.isfinite(v)], dtype=float)
        self.a = np.unique(np.abs(arr)) if arr.size else arr
        dv = values if direct is None else direct                     # direct: chỉ ô và tổng cột (không gồm số suy ra), dùng để "chốt" số làm tròn của AI về đúng số trong bảng
        da = np.asarray([float(v) for v in dv if v is not None and np.isfinite(v)], dtype=float)
        self.d = np.unique(np.abs(da)) if da.size else da
        self.frames = []                         # các bảng kết quả (DataFrame) để đối chiếu từng ô được trích, xem check_cells
        self.names = None                        # {map: {mã: tên}, cols}: mã còn sót trong văn bản AI viết sẽ được đổi thành tên (data/names.py)

    @classmethod
    def from_dfs(cls, dfs, names=None):
        vals, frames, direct = [], [], []
        for df in (dfs.values() if isinstance(dfs, dict) else dfs or []):
            if df is None or not hasattr(df, "columns"):
                continue
            frames.append(df)
            for c in df.columns:
                s = pd.to_numeric(df[c], errors="coerce").dropna()
                if s.empty or pd.api.types.is_bool_dtype(df[c]):
                    continue
                vals.extend(s.tolist()[:2000])
                vals.append(float(s.sum()))
                direct.extend(s.tolist()[:2000])
                direct.append(float(s.sum()))
                if 2 <= len(s) <= 40:                                       # số suy ra hợp lệ: chênh lệch và tổng hai giá trị cùng cột (vd tháng này so với tháng trước)
                    a = s.to_numpy(dtype=float)
                    vals.extend((a[:, None] - a[None, :]).ravel().tolist())
                    vals.extend((a[:, None] + a[None, :]).ravel().tolist())
        k = cls(vals, direct)
        k.frames = frames
        k.names = names
        return k

    def snap(self, x, tol):
        """Giá trị TRỰC TIẾP trong bảng (một ô hoặc tổng một cột) gần x nhất trong sai số tol; None nếu không có."""
        if not self.d.size:
            return None
        x = abs(float(x))
        i = int(np.searchsorted(self.d, x))
        c = [float(self.d[j]) for j in (i - 1, i) if 0 <= j < self.d.size and abs(self.d[j] - x) <= tol]
        return min(c, key=lambda v: abs(v - x)) if c else None

    def has(self, x, tol=None):
        """Có giá trị nào trong bảng khớp x (sai số tol, tối thiểu nửa đơn vị làm tròn)? Dung sai CHẶT: lệch cả một chữ số là phải bị bắt."""
        if not self.a.size:
            return True                          # chưa có bảng nào để đối chiếu -> không kết luận sai
        x = abs(float(x))
        tol = max(tol or 0.5, 0.5)
        i = int(np.searchsorted(self.a, x))
        return any(0 <= j < self.a.size and abs(self.a[j] - x) <= tol for j in (i - 1, i))

    def __bool__(self):
        return bool(self.a.size)


# ------------------------------------------------------------------ sửa chữ --
_EN_UNIT = {"trillion": 1e12, "billion": 1e9, "million": 1e6, "thousand": 1e3}
_NUM = r"\d{1,3}(?:[.,\u202f\u00a0 ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_RE_EN = re.compile(rf"(?<![\w.,])({_NUM})\s*(trillions?|billions?|millions?|thousands?)\b(?:\s*(VN[DĐ]|đồng|dong|đ)(?!\w))?", re.I)
_RE_GRP = re.compile(r"(?<![\d.,])\d{1,3}(?:[\u202f\u00a0]\d{3})+(?:[.,]\d+)?(?!\d)|(?<![\d.,])\d{1,3}(?: \d{3}){2,}(?:[.,]\d+)?(?!\d)")
_RE_RAW = re.compile(r"(?<![\d.,])(?!0\d)(\d{4,})(?:\.(\d+))?(?![\d.,]*\d)")
_RE_DEC = re.compile(r"(?<![\d.,])(\d{1,3})\.(\d+)(?!\d|\.\d)")
_RE_DIEM = re.compile(r"(\d[\d.,]{5,})(\s+)điểm\b")
_RE_CUR = re.compile(r"\bVN[DĐ]\b", re.I)
_SC = {"nghìn tỷ": 1e12, "tỷ": 1e9, "triệu": 1e6, "nghìn": 1e3}
_RE_SCALED = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+\.\d{1,2}|\d+(?:,\d+)?)\s*(nghìn tỷ|tỷ|triệu|nghìn)(?!\w)(?:\s*(đồng|đ|VN[DĐ])(?!\w))?", re.I)
_RE_PCT = re.compile(r"(?<![\d.,])(?<!\d-)(?<!\d–)(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)\s*%")
_RE_CDEC = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})+|\d+),(\d+)(?!\d)(?!,\d)")
# "5.000 đồng" / "5000đ" / "5000 VNĐ" -> "5.000 đ" (một ký hiệu tiền); không đụng "5 đồng nghiệp", "3 đội"
_NOT_MONEY = r"(?!\s+(?:nghiệp|loạt|thời|ý|bộ|đều|nhất|chí|hành|tình|bào|minh|phục|hạng|nghĩa|tâm|bạn|lòng))"
_RE_DONG = re.compile(r"(?<=\d)\s*(?:đồng|VN[DĐ]|đ)(?!\w)" + _NOT_MONEY, re.I)


def _to_float_en(s):
    s = re.sub(r"[\u202f\u00a0 ]", "", s)
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    return float(s)


def fix_text(text, known=None):
    """Đưa số/đơn vị trong một đoạn chữ về kiểu Việt Nam. `known` (Known) dùng để đoán đúng độ lớn khi AI ghi 'trillion' cho số tỷ."""
    if not isinstance(text, str) or not text or not re.search(r"\d", text):
        return text
    s = text

    def en(m):
        num, word, cur = m.group(1), m.group(2).lower().rstrip("s"), m.group(3)
        try:
            v = _to_float_en(num)
        except ValueError:
            return m.group(0)
        cands = [v * _EN_UNIT[word]] + ([v * 1e9] if word == "trillion" else [])      # AI hay gọi nhầm "tỷ" là trillion
        pick = next((c for c in cands if known and known.has(c, c * 0.003)), cands[0])
        pick = (known.snap(pick, pick * 0.003) if known else None) or pick            # có đúng số trong bảng thì dùng số đó
        return fmt_val(pick, "đ") if cur else vn(pick)

    money_ctx = bool(MONEY_WORDS.search(s))

    def scaled(m):
        """'2,24 tỷ đồng' -> '2.240.813.537 đ': tiền ghi đủ số. Chỉ đổi khi có đơn vị tiền, hoặc câu nói về tiền (trừ 'nghìn' vì hay chỉ số người/lượt)."""
        num, word, cur = m.group(1), m.group(2).lower(), m.group(3)
        if not cur and not (money_ctx and word != "nghìn"):
            return m.group(0)
        try:
            dec = len(num.split(",")[1]) if "," in num else len(num.split(".")[1]) if re.fullmatch(r"\d+\.\d{1,2}", num) else 0
            v = float(num) if re.fullmatch(r"\d+\.\d{1,2}", num) else float(num.replace(".", "").replace(",", "."))
        except (ValueError, IndexError):
            return m.group(0)
        v *= _SC[word]
        tol = min(0.5 * 10 ** -dec * _SC[word], v * 0.005)
        v = (known.snap(v, tol) if known else None) or v
        return fmt_val(v, "đ")

    def pct(m):
        tok = m.group(1)
        try:
            x = float(tok) if re.fullmatch(r"\d+\.\d+", tok) and not re.fullmatch(r"\d{1,3}\.\d{3}", tok) else float(tok.replace(".", "").replace(",", "."))
        except ValueError:
            return m.group(0)
        return fmt_pct(x)

    s = _RE_EN.sub(en, s)
    s = _RE_SCALED.sub(scaled, s)
    s = _RE_GRP.sub(lambda m: _grp(m.group(0)), s)
    s = _RE_RAW.sub(_raw, s)
    s = _RE_PCT.sub(pct, s)                                     # mọi tỷ lệ % luôn đúng 2 chữ số sau dấu phẩy
    s = _RE_DEC.sub(_dec, s)
    s = _RE_CDEC.sub(_cdec, s)                                  # số thập phân đã có dấu phẩy: đủ 2 chữ số
    s = _RE_CUR.sub("đ", s)
    s = _RE_DONG.sub(" đ", s)
    if money_ctx:                                               # "2.241.813.537 điểm" trong câu nói về tiền -> đ
        s = _RE_DIEM.sub(r"\1\2đ", s)
    s = _RE_MONEY_DEC.sub(_money_whole, s)                     # tiền ghi nguyên đồng: "3.724.488.031,25 đ" -> "3.724.488.031 đ"
    return _names.decode_text(s, getattr(known, "names", None))     # mã còn sót (SP003) -> tên (Điện thoại Viet-Tech Pro); làm SAU CÙNG để số trong tên không bị chuẩn hóa nhầm


# Số có phần thập phân đứng ngay trước ký hiệu tiền «đ»: tiền ghi nguyên đồng nên bỏ phần thập phân (làm tròn), số không kèm «đ» giữ nguyên.
_RE_MONEY_DEC = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})*|\d+),(\d+)(\s*đ)(?!\w)")


def _money_whole(m):
    try:
        x = float(m.group(1).replace(".", "") + "." + m.group(2))
    except ValueError:
        return m.group(0)
    return vn(x, 0) + m.group(3)


def _two(x):
    """Số lẻ đúng 2 chữ số sau dấu phẩy; số rất nhỏ (làm tròn ra 0,00) giữ 4 chữ số để không mất thông tin."""
    return fmt_dec(x, 4).rstrip("0").rstrip(",") if x and round(x, 2) == 0 else fmt_dec(x, 2)


def _grp(tok):
    t = re.sub(r"[\u202f\u00a0 ]", "", tok).replace(",", ".")
    try:
        return vn(float(t), 2)
    except ValueError:
        return tok


def _raw(m):
    ip, fp = m.group(1), m.group(2)
    if fp is None and len(ip) == 4 and 1900 <= int(ip) <= 2100:
        return m.group(0)                                       # năm
    try:
        return vn(float(ip + ("." + fp if fp else "")), 2)
    except ValueError:
        return m.group(0)


def _dec(m):
    ip, fp = m.group(1), m.group(2)
    if len(fp) == 3 and ip != "0":
        return m.group(0)                                       # 2.240 có thể là hai nghìn hai trăm bốn mươi: giữ nguyên
    return _two(float(f"{ip}.{fp}"))


def _cdec(m):
    ip, fp = m.group(1), m.group(2)
    if len(fp) == 2 or (len(fp) == 3 and ip != "0"):
        return m.group(0)                                       # đã đủ 2 chữ số / "1,234" có thể là kiểu Mỹ của 1234: giữ nguyên
    try:
        return _two(float(ip.replace(".", "") + "." + fp))
    except ValueError:
        return m.group(0)


_SKIP_KEYS = {"code", "cmd", "name", "file", "col", "column", "id", "src", "kind", "x", "y", "task", "tag", "priority", "confidence"}


def fix_payload(o, known=None):
    """Áp fix_text cho mọi chuỗi trong dict/list (bỏ qua các khóa kỹ thuật như code, tên cột, mã)."""
    if isinstance(o, str):
        return fix_text(o, known)
    if isinstance(o, list):
        return [fix_payload(v, known) for v in o]
    if isinstance(o, dict):
        return {k: (v if k in _SKIP_KEYS else fix_payload(v, known)) for k, v in o.items()}
    return o


# ------------------------------------------------------------------ KPI --
_PURE_NUM = re.compile(r"^\s*([-+−]?)\s*(\d[\d.,\s\u202f\u00a0]*)\s*(%|đ|đồng|VN[DĐ])?\s*$", re.I)
_PCT_LABEL = re.compile(r"tỷ lệ|tỷ trọng|phần trăm|tăng trưởng|\(%\)|%", re.I)


def _near(known, x, rel=0.002):
    """Bảng kết quả có đúng giá trị x không (sai số tương đối chặt, khác Known.has vốn dung sai rộng)?"""
    a = getattr(known, "a", None)
    if a is None or not a.size:
        return False
    x = abs(float(x))
    i = int(np.searchsorted(a, x))
    return any(0 <= j < a.size and abs(a[j] - x) <= max(x * rel, 1e-9) for j in (i - 1, i))


def _parse_vi_or_en(s, known=None):
    """Chuỗi số -> số. '936.000' chỉ có MỘT dấu chấm và đúng 3 chữ số sau nó: theo quy tắc số của ứng dụng (dấu chấm ngăn nghìn) đó là 936 nghìn,
    không phải 936,000. Chỉ đọc là số thập phân khi bảng kết quả có giá trị đó mà không có giá trị nghìn. Trước đây luôn đọc là thập phân nên
    KPI '936.000 đ' hiện thành '936 đ'."""
    s = re.sub(r"[\s\u202f\u00a0]", "", s)
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    elif s.count(",") > 1:
        s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if not re.fullmatch(r"\d{1,3},\d{3}", s) else s.replace(",", "")
    elif re.fullmatch(r"[1-9]\d{0,2}\.\d{3}", s):
        th, dec = float(s.replace(".", "")), float(s)
        return dec if _near(known, dec) and not _near(known, th) else th
    return float(s)


def fix_kpi(k, known=None):
    """Một KPI {label, value, delta}: giá trị toàn số được định dạng theo quy tắc số chung (nguyên 1.234 · lẻ 1.234,50 · % 54,20% · tiền ghi đủ kèm đ)."""
    k = dict(k)
    label, val = str(k.get("label") or ""), k.get("value")
    x, unit, matched = None, "", False
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if np.isfinite(val):
            x, matched = float(val), True                    # số thật: dùng đúng giá trị, không qua chuỗi (936.0 hay 1234.567 không bị đoán là kiểu Việt Nam)
        else:
            val = repr(val)
    if x is None and isinstance(val, str):
        m = _PURE_NUM.match(val)
        if m:
            matched = True
            try:
                x = _parse_vi_or_en(m.group(2), known) * (-1 if m.group(1) else 1)
                unit = (m.group(3) or "").lower()
            except ValueError:
                x = None
    if x is not None:
        pctish = _PCT_LABEL.search(label) and not MONEY_WORDS.search(label)
        if unit == "%" or (not unit and pctish and abs(x) <= 100):
            ratio = not unit and abs(x) <= 1                  # "Tỷ lệ hoàn trả = 0.0697" là tỷ lệ 0-1, không phải 0,07%
            val = fmt_pct(x * 100 if ratio else x)
        elif unit in ("đ", "đồng", "vnd", "vnđ") or MONEY_WORDS.search(label):
            val = fmt_val(x, "đ")                             # tiền ghi đủ số, đơn vị đ
        else:
            val = vn(x)
    elif not matched and isinstance(val, str):
        val = fix_text(val, known)
    k["value"] = val if val is not None else ""
    if k.get("delta"):
        k["delta"] = fix_text(str(k["delta"]), known)
    k["label"] = fix_text(label, known)
    return k


def fix_kpis(ks, known=None):
    return [fix_kpi(k, known) for k in (ks or []) if isinstance(k, dict)]


def has_value(k):
    v = k.get("value")
    return v is not None and str(v).strip() not in ("", "—", "-", "N/A", "n/a", "None", "nan")


# ------------------------------------------------------------------ đối chiếu số --
_RE_VI_NUM = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)(?:\s*(nghìn tỷ|tỷ|triệu))?(?![\d])")
_SCALE = {"nghìn tỷ": 1e12, "tỷ": 1e9, "triệu": 1e6}


def big_numbers(text):
    """Các số 'cỡ tiền' (từ 1 triệu trở lên, hoặc có chữ tỷ/triệu) trong văn bản đã chuẩn hóa: [(chuỗi, giá trị, sai số làm tròn)]."""
    out = []
    for m in _RE_VI_NUM.finditer(text or ""):
        raw, unit = m.group(1), m.group(2)
        try:
            x = float(raw.replace(".", "").replace(",", ".")) if "," in raw or raw.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", raw) else float(raw)
        except ValueError:
            continue
        dec = len(raw.split(",")[1]) if "," in raw else 0
        if unit:
            v, tol = x * _SCALE[unit], 0.5 * 10 ** -dec * _SCALE[unit]
        else:
            v, tol = x, 0.5 if dec == 0 else 0.5 * 10 ** -dec
        if abs(v) >= 1e6:
            out.append((m.group(0).strip(), v, tol))
    return out


def audit(text, known):
    """Trả về các số lớn trong `text` KHÔNG tìm thấy (kể cả làm tròn) trong bảng kết quả."""
    if not known:
        return []
    return [s for s, v, tol in big_numbers(text) if not known.has(v, tol)]


# ---- tính lại phép tính AI viết trong bằng chứng ("a + b + c = d", "a / b = 31,09%") ----
# AI hay viết phép tính sai (cộng bảy số ra 3.064,28 nhưng ghi 2.152,25). Ở đây CODE tính lại; chỉ nhận số, + - × / và ngoặc,
# KHÔNG dùng eval. Biểu thức không phân tích được thì bỏ qua (kết luận là "chưa kiểm được", không phải "sai").
_CN = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?"
_CALC_TOK = re.compile(
    rf"(?P<num>(?<![\w.,])(?:{_CN})(?:\s*(?:nghìn tỷ|tỷ|triệu|nghìn)(?!\w))?(?:\s*(?:%|đồng(?!\w)|đ(?!\w)))?)"
    r"|(?P<op>(?<=\s)[-−–](?=\s)|(?<=[=≈])\s?[-−–](?=\d)|\s[xX]\s(?=\d)|[+×*/÷])"
    r"|(?P<lp>\()|(?P<rp>\))|(?P<eq>[=≈])|(?P<sp>\s+)|(?P<other>.)", re.S)
_CALC_SCALE = {"nghìn tỷ": 1e12, "tỷ": 1e9, "triệu": 1e6, "nghìn": 1e3}
_CALC_MAX = 60                                   # tối đa số phép tính kiểm trong một đoạn (tránh chạy lâu với đoạn dị dạng)


def _calc_num(tok, alt):
    """'2.152,25 tỷ' -> (giá trị, số chữ số thập phân, hệ số đơn vị, có %). alt=True: hiểu '2.240' là 2,24 và '1,234' là 1234 (kiểu Anh)."""
    m = re.match(rf"\s*({_CN})", tok)
    raw = m.group(1)
    pct = "%" in tok
    sc = next((v for k, v in _CALC_SCALE.items() if re.search(rf"\b{k}\b", tok)), 1.0)
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", raw) and not (alt and re.fullmatch(r"\d{1,3}\.\d{3}", raw)):
        ip, _, fp = raw.partition(",")
        return float(ip.replace(".", "") + ("." + fp if fp else "")), len(fp), sc, pct
    if alt and re.fullmatch(r"\d{1,3}(?:,\d{3})+", raw):
        return float(raw.replace(",", "")), 0, sc, pct
    raw2 = raw.replace(",", ".")
    return float(raw2), (len(raw2.split(".")[1]) if "." in raw2 else 0), sc, pct


def _calc_eval(toks, alt):
    """Phân tích cú pháp expr := term (('+'|'-') term)* ; term := factor (('*'|'/') factor)* ; factor := số | '(' expr ')'.
    Tính bằng SỐ HỌC KHOẢNG: mỗi số hạng mang sai số làm tròn của nó (2,5 nghĩa là 2,45 đến 2,55), nên kết quả là một khoảng [thấp, cao].
    Trả về (thấp, cao) hoặc None nếu sai cú pháp / chia cho khoảng chứa 0."""
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else (None, None)

    def factor():
        k, v = peek()
        if k == "num":
            pos[0] += 1
            x, dec, sc, _ = _calc_num(v, alt)
            t = 0 if (dec == 0 and sc == 1.0) else 0.5 * 10 ** -dec          # số nguyên trơn (3 người, chia 3, nhân 100) là chính xác; số thập phân / có tỷ, triệu thì đã làm tròn
            return ((x - t) * sc, (x + t) * sc)
        if k == "lp":
            pos[0] += 1
            r = expr()
            if peek()[0] != "rp":
                raise ValueError
            pos[0] += 1
            return r
        raise ValueError

    def mul(a, b):
        ps = [a[0] * b[0], a[0] * b[1], a[1] * b[0], a[1] * b[1]]
        return (min(ps), max(ps))

    def term():
        x = factor()
        while peek()[0] == "op" and peek()[1].strip() in ("*", "×", "x", "X", "/", "÷"):
            o = toks[pos[0]][1].strip()
            pos[0] += 1
            y = factor()
            if o in ("/", "÷"):
                if y[0] <= 0 <= y[1]:
                    raise ZeroDivisionError
                x = mul(x, (1 / y[1], 1 / y[0]))
            else:
                x = mul(x, y)
        return x

    def expr():
        x = term()
        while peek()[0] == "op" and peek()[1].strip() in ("+", "-", "−", "–"):
            o = toks[pos[0]][1].strip()
            pos[0] += 1
            y = term()
            x = (x[0] + y[0], x[1] + y[1]) if o == "+" else (x[0] - y[1], x[1] - y[0])
        return x

    try:
        r = expr()
        return r if pos[0] == len(toks) else None
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def calc_check(text, rel=0.005):
    """Tìm các phép tính dạng `biểu thức = kết quả` trong `text`, tính lại bằng code.
    Trả về {"checked": số phép tính kiểm được, "bad": [{"text": 'a + b = c', "calc": giá trị tính lại (chữ), "stated": giá trị AI ghi}]}.
    Sai khi khoảng tính lại và khoảng của số AI ghi KHÔNG chạm nhau, kể cả sau khi nới thêm `rel` (0,5%): lệch do làm tròn không bị coi là sai.
    Ô nguồn dạng `[bảng, hàng, cột] = giá trị` không phải phép tính nên không bị xét."""
    out = {"checked": 0, "bad": []}
    if not isinstance(text, str) or ("=" not in text and "≈" not in text):
        return out
    toks = [(m.lastgroup, m.group(m.lastgroup)) for m in _CALC_TOK.finditer(text) if m.lastgroup != "sp"]
    chains, cur = [], [[]]
    for k, v in toks:
        if k == "eq":
            cur.append([])
        elif k == "other":
            chains.append(cur)
            cur = [[]]                           # chữ xen giữa phá vỡ chuỗi: không đoán nghĩa
        else:
            cur[-1].append((k, v))
    chains.append(cur)
    n = 0
    for items in chains:
        for left, right in zip(items, items[1:]):
            if n >= _CALC_MAX or not left or not any(k == "op" for k, _ in left) or any(k == "num" and re.match(r"\s*0\d", v) for k, v in left):
                continue                         # không có phép tính (chỉ một ô), hoặc dạng ngày 03-04
            neg = len(right) == 2 and right[0][0] == "op" and right[0][1].strip() in ("-", "−", "–")
            rt = right[1:] if neg else right
            if len(rt) != 1 or rt[0][0] != "num":
                continue
            ok, shown, evaluated = False, None, False
            for alt in (False, True):            # '2.240' hiểu là hai nghìn hai trăm bốn mươi (kiểu Việt) hoặc 2,24 (kiểu Anh): khớp một trong hai là không sai
                r = _calc_eval(left, alt)
                if r is None:
                    break
                evaluated = True
                sv, sdec, ssc, spct = _calc_num(rt[0][1], alt)
                sv, st = (-sv if neg else sv) * ssc, 0.5 * 10 ** -sdec * ssc
                s_lo, s_hi = sv - st, sv + st
                for k_ in ((1, 100) if spct else (1,)):          # kết quả ghi bằng % thì tỷ lệ 0,3109 tương ứng 31,09%
                    lo, hi = r[0] * k_, r[1] * k_
                    slack = rel * max(abs(lo), abs(hi))
                    if lo - slack <= s_hi and s_lo <= hi + slack:
                        ok = True
                if shown is None:
                    shown = ((r[0] + r[1]) / 2, sv)
                if ok:
                    break
            if not evaluated:
                continue
            n += 1
            out["checked"] += 1
            if not ok:
                expr_txt = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", " ".join(v.strip() for _, v in left)))
                out["bad"].append({"text": f"{expr_txt} = {('-' if neg else '') + rt[0][1].strip()}", "calc": vn(shown[0], 2), "stated": vn(shown[1], 2)})
    return out


_CITE = re.compile(rf"\[([^\[\]]+)\]\s*=\s*(-?(?:{_CN})(?:\s*(?:nghìn tỷ|tỷ|triệu|nghìn)(?!\w))?)")


def check_cells(text, known):
    """Đối chiếu các ô AI trích dạng `[bảng, hàng, cột] = giá trị` với bảng kết quả thật.
    Trả về {"ok": số ô khớp, "bad": [ô lệch giá trị], "unlocated": số ô không tìm thấy hàng/cột}.
    CHỈ coi là sai khi ô định vị được (có cột đó, có hàng đó) mà giá trị lệch; AI viết lệch tên hàng/cột thì là 'chưa kiểm được', không báo sai oan."""
    out = {"ok": 0, "bad": [], "unlocated": 0}
    frames = getattr(known, "frames", None)
    if not isinstance(text, str) or not frames:
        return out
    from . import labels as lb
    for ref, val in _CITE.findall(text)[:_CALC_MAX]:
        parts = [p.strip() for p in ref.split(",")]
        if len(parts) < 3:
            out["unlocated"] += 1
            continue
        row_key, col = lb.fold(parts[-2]), lb.fold(parts[-1])
        cands = []
        for df in frames:
            cmap = {lb.fold(str(c)): c for c in df.columns}
            if col not in cmap:
                continue
            labels = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
            if not labels:
                continue
            hit = np.zeros(len(df), dtype=bool)
            for c in labels:
                hit |= df[c].astype(str).map(lb.fold).to_numpy() == row_key
            cands += pd.to_numeric(df.loc[hit, cmap[col]], errors="coerce").dropna().tolist()
        if not cands:
            out["unlocated"] += 1
            continue
        good = False
        for alt in (False, True):
            v, dec, sc, _ = _calc_num(val, alt)
            v, tol = v * sc, 0.5 * 10 ** -dec * sc * 1.001 + 1e-9
            good |= any(abs(c - v) <= max(tol, 1e-6 * abs(v)) for c in cands)
        if good:
            out["ok"] += 1
        else:
            out["bad"].append(f"[{ref}] = {val.strip()} (bảng ghi {vn(cands[0], 2)})")
    return out


def audit_insights(insights, known):
    """Kiểm từng phát hiện và gắn nhãn kết quả, hạ độ tin cậy xuống 'Thấp' nếu có sai sót. Trả về danh sách mới. Thêm các khóa:
    `check` (số lớn không có trong bảng kết quả nào), `calc_mismatch` (phép tính AI ghi không khớp khi tính lại), `cell_mismatch` (ô được trích lệch giá trị so với bảng), và `verify`:
    'ok' (đã kiểm được ít nhất một điều và không có sai sót) · 'mismatch' (có sai sót) · 'unverified' (chưa kiểm được gì, KHÔNG phải là đúng)."""
    out = []
    for x in insights or []:
        if isinstance(x, dict):
            x = dict(x)
            text = f"{x.get('title', '')} ; {x.get('evidence', '')}"
            bad = audit(text, known)
            cc = calc_check(text)
            cells = check_cells(text, known)
            if bad:
                x["check"], x["confidence"] = bad, "Thấp"
            if cc["bad"]:
                x["calc_mismatch"], x["confidence"] = [f"{b['text']} (tính lại ra {b['calc']})" for b in cc["bad"]], "Thấp"
            if cells["bad"]:
                x["cell_mismatch"], x["confidence"] = cells["bad"], "Thấp"
            big = big_numbers(text)
            if bad or cc["bad"] or cells["bad"]:
                x["verify"] = "mismatch"
            elif cc["checked"] or cells["ok"] or (big and known):
                x["verify"] = "ok"
            else:
                x["verify"] = "unverified"
        out.append(x)
    return out


def verify_counts(insights):
    """(số phát hiện đã kiểm được và không sai sót, tổng số phát hiện)."""
    ins = [x for x in insights or [] if isinstance(x, dict)]
    return sum(1 for x in ins if x.get("verify") == "ok"), len(ins)


def all_verified(insights):
    ok, n = verify_counts(insights)
    return n > 0 and ok == n


def verify_label(x):
    """(lớp hiển thị 'ok'|'un'|'bad', nhãn) của trạng thái kiểm tra một phát hiện; None nếu chưa có thông tin kiểm tra (bản lưu cũ)."""
    v = x.get("verify") if isinstance(x, dict) else None
    if v == "ok":
        return "ok", "Đã kiểm số liệu"
    if v == "mismatch":
        return "bad", "Phép tính không khớp" if x.get("calc_mismatch") else "Số liệu chưa khớp bảng"
    if v == "unverified":
        return "un", "Chưa kiểm được"
    return None


def verify_note(x):
    """Một câu ngắn nói rõ phát hiện này chưa qua kiểm tra vì sao; rỗng nếu đã kiểm được (hoặc chưa có thông tin kiểm tra, vd bản lưu cũ)."""
    if not isinstance(x, dict):
        return ""
    if x.get("calc_mismatch"):
        return "Phép tính không khớp: " + "; ".join(x["calc_mismatch"])
    if x.get("cell_mismatch"):
        return "Số trích không khớp bảng kết quả: " + "; ".join(x["cell_mismatch"])
    if x.get("check"):
        return "Cần kiểm tra số liệu: số " + ", ".join(x["check"]) + " chưa khớp bảng kết quả nào"
    if x.get("verify") == "unverified":
        return "Chưa kiểm được bằng chứng này (không có phép tính để tính lại, ô trích không đối chiếu được với bảng)"
    return ""


# ------------------------------------------------------------------ tiêu đề biểu đồ tính từ dữ liệu --
def pretty_period(label):
    """2026-03-01 -> T3/2026 · 2026-03 -> T3/2026 · giữ nguyên nếu không phải ngày."""
    s = str(label)
    m = re.match(r"^(\d{4})-(\d{1,2})(?:-\d{1,2})?(?:[ T].*)?$", s)
    return f"T{int(m.group(2))}/{m.group(1)}" if m else s


def headline(rows, kind, metric, time_like=False):
    """Một câu kết luận TÍNH TỪ SỐ LIỆU của biểu đồ (không do AI viết). rows = [(nhãn, giá trị)]."""
    if not rows:
        return ""
    metric = re.sub(r"\s*\(.*?\)", "", str(metric or "Giá trị")).strip() or "Giá trị"
    m = metric[:1].upper() + metric[1:]
    if time_like and len(rows) >= 2:
        rs = sorted(rows, key=lambda r: str(r[0]))
        a, b = rs[0], rs[-1]
        if a[1]:
            ch = b[1] / a[1] - 1
            if abs(ch) < 0.005:
                return f"{m} ổn định từ {pretty_period(a[0])} đến {pretty_period(b[0])}"
            return f"{m} {'tăng' if ch > 0 else 'giảm'} {fmt_pct(abs(ch) * 100)} từ {pretty_period(a[0])} đến {pretty_period(b[0])}"
    hi = max(rows, key=lambda r: r[1])
    tot = sum(v for _, v in rows)
    if len(rows) > 1 and all(v >= 0 for _, v in rows) and tot > 0:
        return f"{pretty_period(hi[0])} dẫn đầu {metric[:1].lower() + metric[1:]}, chiếm {fmt_pct(hi[1] / tot * 100)} tổng"
    return f"{pretty_period(hi[0])} có {metric[:1].lower() + metric[1:]} cao nhất"


def _pct_set(rows, time_like):
    """Mọi tỷ lệ % hợp lệ có thể suy ra từ dữ liệu biểu đồ (so đầu-cuối, kỳ liền kề, tỷ trọng từng phần)."""
    out = set()
    vals = [v for _, v in (sorted(rows, key=lambda r: str(r[0])) if time_like else rows)]
    if time_like and len(vals) >= 2:
        if vals[0]:
            out.add(abs(vals[-1] / vals[0] - 1) * 100)
        out.update(abs(b / a - 1) * 100 for a, b in zip(vals, vals[1:]) if a)
    tot = sum(v for v in vals if v > 0)
    if tot > 0:
        out.update(v / tot * 100 for v in vals if v > 0)
    return out


def consistent(insight, rows, time_like=False):
    """Câu kết luận của AI có khớp số liệu biểu đồ không? (hướng tăng/giảm và các tỷ lệ % nêu ra)."""
    t = str(insight or "").lower()
    if not t.strip() or not rows:
        return False
    if time_like and len(rows) >= 2:
        rs = sorted(rows, key=lambda r: str(r[0]))
        if rs[0][1]:
            ch = rs[-1][1] / rs[0][1] - 1
            if abs(ch) >= 0.01 and ((ch > 0 and re.search(r"\bgiảm\b|sụt", t) and not re.search(r"\btăng\b", t)) or (ch < 0 and re.search(r"\btăng\b", t) and not re.search(r"\bgiảm\b|sụt", t))):
                return False
    claims = [float(x.replace(",", ".")) for x in re.findall(r"(\d+(?:,\d+)?)\s*%", t)]
    allowed = _pct_set(rows, time_like)
    return all(any(abs(c - a) <= max(0.15, a * 0.01) for a in allowed) for c in claims) if claims and allowed else True
