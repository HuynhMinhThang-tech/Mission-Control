# -*- coding: utf-8 -*-
"""Mô tả dữ liệu + quét vấn đề chất lượng."""
import re
import unicodedata

import pandas as pd

from ..utils import vn  # noqa: F401  (giữ để các agent import chung)


def norm_key(v):
    """Khóa so sánh: bỏ hoa/thường, dấu tiếng Việt, khoảng trắng thừa và dấu câu. «Ban Giám đốc» = «ban giam doc» = «BAN GIÁM ĐỐC »."""
    t = unicodedata.normalize("NFD", str(v))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn").replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[\W_]+", " ", t.lower()).strip()


_ISO_START = re.compile(r"^\d{4}\s*[-/.]\s*\d{1,2}\s*[-/.]\s*\d{1,2}")                       # 2026-01-03 (năm đứng trước: không mơ hồ)
_DMY_START = re.compile(r"^(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{2,4})")                  # 05/01/2026 (mơ hồ giữa ngày/tháng và tháng/ngày)


def _parse_dt(x, dayfirst):
    try:
        return pd.to_datetime(x, errors="coerce", format="mixed", dayfirst=dayfirst)
    except (TypeError, ValueError):
        return pd.to_datetime(x, errors="coerce", dayfirst=dayfirst)


def day_order(t):
    """Thứ tự ngày-tháng của các giá trị dạng d/m/y trong `t` (Series chữ): (ngày_trước_tháng, chắc_chắn).
    Có giá trị mà số đầu > 12 thì chắc chắn NGÀY/THÁNG; có số thứ hai > 12 thì chắc chắn THÁNG/NGÀY; không có gì chứng minh thì mặc định
    NGÀY/THÁNG (chuẩn Việt Nam) và chắc_chắn=False để giao diện nói rõ điều này."""
    m = t.astype(str).str.strip().str.extract(_DMY_START)
    a, b = pd.to_numeric(m[0], errors="coerce"), pd.to_numeric(m[1], errors="coerce")
    if (a > 12).any():
        return True, True
    if (b > 12).any():
        return False, True
    return True, False


def to_dt(s):
    """Đọc cột chữ thành ngày. Dạng năm-trước (2026-01-03) đọc đúng kiểu ISO; dạng d/m/y đọc theo NGÀY/THÁNG (Việt Nam), chỉ đổi sang
    THÁNG/NGÀY khi dữ liệu chứng minh được (xem day_order). Trước đây mọi chuỗi đọc theo kiểu Mỹ nên 05/01/2026 thành 1 tháng 5."""
    if not isinstance(s, pd.Series) or pd.api.types.is_datetime64_any_dtype(s) or not is_text(s):
        return _parse_dt(s, False)
    idx = s.index
    t = s.reset_index(drop=True)
    t = t.where(t.isna(), t.astype(str).str.strip())
    iso = t.str.match(_ISO_START, na=False)
    rest = t.notna() & ~iso
    parts = []
    if iso.any():
        parts.append(_parse_dt(t[iso], False))
    if rest.any():
        parts.append(_parse_dt(t[rest], day_order(t[rest])[0]))
    out = pd.concat(parts).reindex(t.index) if parts else pd.to_datetime(t, errors="coerce")
    out.index = idx
    return out


def is_text(s):
    return not (pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s) or pd.api.types.is_bool_dtype(s))


def date_like(s):
    t = s.dropna().astype(str).head(50)
    return len(t) > 0 and t.str.contains(r"[-/]").mean() > 0.8 and to_dt(t).notna().mean() > 0.8


def schema(dfs, sample=3):
    return {n: {"shape": list(d.shape), "columns": {c: str(d[c].dtype) for c in d.columns},
                "sample": d.head(sample).astype(str).to_dict("records")} for n, d in dfs.items()}


def profile_rows(dfs):
    return [{"file": n, "shape": list(d.shape),
             "rows": [[c, str(d[c].dtype), int(d[c].isna().sum()), round(float(d[c].isna().mean() * 100), 2), int(d[c].nunique()),
                       ", ".join(d[c].dropna().astype(str).head(3))] for c in d.columns]} for n, d in dfs.items()]


def date_range(dfs):
    for n, d in dfs.items():
        for c in d.columns:
            s = d[c]
            t = s if pd.api.types.is_datetime64_any_dtype(s) else (to_dt(s) if is_text(s) and date_like(s) else None)
            if t is not None and t.notna().any():
                return f"{t.min():%d/%m/%Y} → {t.max():%d/%m/%Y}"
    return None


def join_info(dfs):
    best = None
    names = list(dfs)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            big, small = (a, b) if len(dfs[a]) >= len(dfs[b]) else (b, a)
            for c in set(dfs[a].columns) & set(dfs[b].columns):
                if not dfs[small][c].is_unique or dfs[small][c].nunique() < 2:
                    continue
                m = float(dfs[big][c].dropna().isin(set(dfs[small][c].dropna())).mean() * 100)
                key = dfs[small][c].nunique()  # ưu tiên khóa có nhiều giá trị (vd customer_id)
                if best is None or key > best[4]:
                    best = (big, small, c, m, key)
    return best


CAT = {"Giá trị thiếu": "Thiếu", "Dòng trùng lặp": "Trùng", "Thừa khoảng trắng": "Định dạng", "Không nhất quán hoa/thường": "Định dạng",
       "Số đang lưu dạng text": "Định dạng", "Ngày đang lưu dạng text": "Định dạng", "Ngày sai định dạng": "Định dạng",
       "Giá trị viết khác nhau": "Định dạng", "Ngoại lai (IQR)": "Ngoại lai", "Giá trị âm": "Giá trị âm"}


# Phương án đề xuất xử lý cho từng loại vấn đề. Do CODE tạo (không nhờ AI) nên luôn có và luôn khớp tên thao tác của bước Làm sạch;
# người dùng vẫn là người quyết định ở bước đó.
FIX_GENERIC = {
    "Dòng trùng lặp": "Xóa dòng trùng, giữ lại 1 bản. Kiểm tra trước: hai khoản giống hệt nhau có thể là hai giao dịch có thật",
    "Giá trị thiếu": "Điền giá trị thay thế hoặc xóa dòng thiếu, tùy cột",
    "Thừa khoảng trắng": "Cắt khoảng trắng đầu/cuối ô",
    "Không nhất quán hoa/thường": "Chuẩn hóa về một kiểu chữ để cùng một giá trị không bị tách thành nhiều nhóm",
    "Số đang lưu dạng text": "Bỏ dấu ngăn nghìn và ký hiệu tiền tệ rồi chuyển cột sang kiểu số",
    "Ngày đang lưu dạng text": "Chuyển cột sang kiểu ngày (đọc theo thứ tự ngày/tháng/năm) để lọc và nhóm theo thời gian",
    "Ngày sai định dạng": "Thống nhất một định dạng ngày rồi chuyển sang kiểu ngày; kiểm tra tay các ô không đọc được",
    "Giá trị viết khác nhau": "Gộp các cách viết khác nhau về một giá trị chuẩn (bước Làm sạch, phần Gộp giá trị)",
    "Ngoại lai (IQR)": "Kiểm tra từng giá trị: sửa nếu là lỗi nhập, giữ nếu có thật. Chỉ cắt ngoại lai khi chắc chắn, vì có thể mất dữ liệu đúng",
    "Giá trị âm": "Xác định số âm có hợp lý không (hoàn tiền, điều chỉnh). Nếu không, gắn cờ để rà lại; nếu có, giữ và tách riêng khi phân tích",
}


def fix_for(issue, s=None, n=0):
    """Phương án xử lý đề xuất cho MỘT vấn đề. `s` là cột (nếu có) để chọn cách điền thiếu hợp kiểu dữ liệu."""
    base = FIX_GENERIC.get(issue, "Xem lại thủ công")
    if issue != "Giá trị thiếu" or s is None or len(s) == 0:
        return base
    share = float(n) / len(s)
    if share > 0.5:
        return "Thiếu hơn một nửa số dòng: cân nhắc bỏ cột này, hoặc chỉ phân tích trên các dòng có dữ liệu"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "Giữ ô trống (không tự đoán ngày); các dòng này sẽ không vào phân tích theo thời gian"
    if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
        return "Điền trung vị (ít bị ngoại lai kéo lệch), hoặc xóa dòng thiếu nếu số dòng ít"
    return "Điền giá trị phổ biến nhất hoặc «Không rõ», hoặc xóa dòng thiếu nếu số dòng ít"


def quality(dfs, with_fix=False):
    """Quét vấn đề chất lượng. with_fix=True thêm cột `fix` (phương án đề xuất xử lý); mặc định giữ 4 cột cũ vì bảng này còn được đưa vào prompt của các Agent."""
    rows = []

    def add(f, c, i, n, s=None):
        r = {"file": f, "col": str(c), "issue": i, "n": int(n)}
        if with_fix:
            r["fix"] = fix_for(i, s, int(n))
        rows.append(r)

    for n, d in dfs.items():
        if d.duplicated().sum():
            add(n, "(toàn bảng)", "Dòng trùng lặp", d.duplicated().sum(), None)
        for c in d.columns:
            s = d[c]
            if s.isna().sum():
                add(n, c, "Giá trị thiếu", s.isna().sum(), s)
            if is_text(s) and not pd.api.types.is_datetime64_any_dtype(s):
                t = s.dropna().astype(str)
                if len(t) == 0:
                    continue
                if (t != t.str.strip()).any():
                    add(n, c, "Thừa khoảng trắng", (t != t.str.strip()).sum())
                if t.nunique() != t.str.lower().str.strip().nunique():
                    add(n, c, "Không nhất quán hoa/thường", t.nunique() - t.str.lower().str.strip().nunique())
                if pd.to_numeric(t.str.replace(r"[,\s]", "", regex=True), errors="coerce").notna().mean() > 0.8:
                    add(n, c, "Số đang lưu dạng text", len(t))
                elif date_like(s):
                    shapes = t.str.replace(r"\d", "9", regex=True).value_counts()
                    if len(shapes) > 1:
                        add(n, c, "Ngày sai định dạng", len(t) - shapes.iloc[0])
                    else:
                        add(n, c, "Ngày đang lưu dạng text", len(t))
                else:
                    u = pd.Series(t.unique())
                    if len(u) <= 20000:       # cùng một giá trị nhưng khác dấu/ký tự: bị đếm thành nhiều giá trị riêng
                        extra = int(u.str.strip().str.lower().nunique()) - int(pd.Series([norm_key(x) or x for x in u]).nunique())
                        if extra > 0:
                            add(n, c, "Giá trị viết khác nhau", extra)
            elif pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
                q1, q3 = s.quantile(.25), s.quantile(.75)
                i = q3 - q1
                o = int(((s < q1 - 1.5 * i) | (s > q3 + 1.5 * i)).sum()) if i > 0 else 0
                if o:
                    add(n, c, "Ngoại lai (IQR)", o)
                if (s < 0).sum():
                    add(n, c, "Giá trị âm", (s < 0).sum())
    return pd.DataFrame(rows, columns=["file", "col", "issue", "n"] + (["fix"] if with_fix else []))


def issue_counts(dfs):
    out = {k: 0 for k in ["Thiếu", "Trùng", "Định dạng", "Ngoại lai", "Giá trị âm"]}
    for r in quality(dfs).to_dict("records"):
        out[CAT[r["issue"]]] += r["n"]
    return out
