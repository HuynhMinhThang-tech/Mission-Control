# -*- coding: utf-8 -*-
"""Tín hiệu PHẠM VI và CHẤT LƯỢNG của dữ liệu, do CODE tính (không nhờ AI đoán), đưa vào prompt của các agent.

Lỗi phổ biến nhất của phân tích tự động: cộng gộp lẫn các nhóm bản ghi không cùng phạm vi (đơn hoàn/hủy với đơn thành công, thu với chi,
dòng tổng với dòng chi tiết...), hoặc so một kỳ chưa đủ ngày với kỳ đủ, hoặc chia cơ cấu theo cột thiếu gần hết giá trị. Ở đây ta chỉ ra *chỗ nào
cần quyết định*, không áp đặt quyết định: agent phải chọn có lý do và ghi rõ phạm vi vào `goal`. Không gắn với lĩnh vực hay tên cột nào.
"""
import calendar
import warnings

import pandas as pd

from .. import labels
from .names import naming_note

# từ gợi ý cột "loại bản ghi" (xét theo TỪ của tên cột, không dấu)
KIND_WORDS = {"loai", "type", "kind", "trang", "thai", "status", "hinh", "thuc", "phuong", "kenh", "channel", "nhom", "direction", "state", "giai", "doan"}
TIME_WORDS = {"ngay", "date", "thang", "month", "time", "ky", "day", "nam", "year"}


def _is_time(name, s):
    return pd.api.types.is_datetime64_any_dtype(s) or (bool(TIME_WORDS & set(labels.tokens(name))) and not pd.api.types.is_numeric_dtype(s))


def _parse_dates(s):
    """Đọc cột chữ thành ngày. Chuỗi dạng năm-tháng-ngày (ISO) thì KHÔNG đảo ngày/tháng; dạng khác ưu tiên ngày trước (dd/mm/yyyy, kiểu Việt Nam).
    (dayfirst=True áp lên chuỗi ISO làm pandas đọc 2026-01-02 thành 1/2/2026.)"""
    iso = s.astype(str).str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}").mean() >= 0.9
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return pd.to_datetime(s, errors="coerce", format="mixed", dayfirst=not iso)
        except (TypeError, ValueError):
            return pd.to_datetime(s, errors="coerce")


def _pct(x):
    return f"{x * 100:.0f}%".replace(".", ",")


def scope_hints(dfs, max_per_table=6):
    """dfs = {tên bảng: DataFrame}. Trả về đoạn văn bản (có thể rỗng) liệt kê các điểm cần quyết định về phạm vi/chất lượng."""
    out = []
    for name, df in (dfs or {}).items():
        if df is None or not len(df):
            continue
        n, notes = len(df), []
        for c in df.columns:
            s = df[c]
            if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s):
                continue
            k = s.nunique(dropna=True)
            if 2 <= k <= 8 and (KIND_WORDS & set(labels.tokens(c))):
                vc = s.value_counts(normalize=True, dropna=True).head(6)
                notes.append(f"Cột phân loại bản ghi «{c}»: " + ", ".join(f"{i} {_pct(v)}" for i, v in vc.items())
                             + " → hãy QUYẾT ĐỊNH nhóm nào được tính vào chỉ số (vd bỏ nhóm hoàn/hủy/nội bộ khỏi doanh thu) và ghi rõ phạm vi lọc vào `goal`.")
        for c in df.columns:
            s = df[c]
            if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
                v = s.dropna()
                if len(v) and (v < 0).any() and (v > 0).any() and not labels.is_id(c):
                    notes.append(f"Cột số «{c}» có cả giá trị âm ({int((v < 0).sum())} dòng) và dương → xác nhận quy ước dấu; đừng cộng gộp nếu âm/dương thuộc hai nhóm khác nhau (vd hoàn tiền, điều chỉnh).")
        for c in df.columns:
            if _is_time(c, df[c]):
                d = _parse_dates(df[c].head(20000)).dropna()
                if len(d) >= max(5, n * 0.5):
                    last = d.max()
                    dim = calendar.monthrange(last.year, last.month)[1]
                    if last.day < dim:
                        notes.append(f"Cột thời gian «{c}»: dữ liệu kết thúc ngày {last.day:02d}/{last.month:02d}/{last.year}, kỳ tháng cuối mới có {last.day}/{dim} ngày → "
                                     "KHÔNG so trực tiếp tháng cuối với tháng đủ ngày; so cùng số ngày, hoặc nêu rõ là tạm tính.")
                    break
        miss = [(c, df[c].isna().mean()) for c in df.columns if df[c].isna().mean() >= .5]
        for c, r in miss[:3]:
            notes.append(f"Cột «{c}» thiếu {_pct(r)} giá trị → KHÔNG dùng để chia cơ cấu hoặc xếp hạng; nếu cần, nêu rõ phần 'chưa phân loại'.")
        if notes:
            out.append(f"[{name}] ({n:,} dòng)".replace(",", ".") + "\n" + "\n".join("- " + x for x in notes[:max_per_table]))
    return "\n".join(out)


def scope_block(dfs):
    """Khối chữ sẵn sàng ghép vào prompt; rỗng nếu không có điểm nào cần lưu ý."""
    t = scope_hints(dfs)
    return ("TÍN HIỆU PHẠM VI & CHẤT LƯỢNG DỮ LIỆU (do máy tính từ dữ liệu thật, bạn phải xử lý từng điểm):\n" + t + "\n\n") if t else ""


# ---------------------------------------------------------------- thẻ dữ liệu: ranh giới những gì AI được phép nói tới --
def _col_kind(s):
    """Phân loại cột THEO THỐNG KÊ (không dựa vào từ khóa trong tên): thời gian · số · phân loại · văn bản."""
    if pd.api.types.is_bool_dtype(s):
        return "đúng/sai"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "thời gian"
    if pd.api.types.is_numeric_dtype(s):
        return "số"
    v = s.dropna().astype(str).head(200)
    if len(v) >= 5 and v.str.contains(r"[-/.]", regex=True).mean() >= 0.9:          # trông như ngày tháng thì thử đọc
        if _parse_dates(v).notna().mean() >= 0.9:
            return "thời gian"
    return "phân loại" if s.nunique(dropna=True) <= max(20, 0.05 * max(len(s), 1)) else "văn bản"


def _time_range(s):
    if pd.api.types.is_datetime64_any_dtype(s):
        d = s.dropna()
    else:
        d = _parse_dates(s.head(50000)).dropna()
    return (d.min(), d.max()) if len(d) else None


def data_card(dfs, max_tables=6, max_cols=40):
    """Đoạn ngắn do CODE tạo, liệt kê bảng/cột/kỳ thời gian thật của dữ liệu, kèm câu giới hạn: AI chỉ được dựa vào đây (không bịa cột, thực thể, nguyên nhân).
    Trung lập lĩnh vực: không dùng từ khóa theo ngành. Rỗng nếu không có bảng nào."""
    out = []
    for name, df in list((dfs or {}).items())[:max_tables]:
        if df is None or not hasattr(df, "columns") or not len(df.columns):
            continue
        cols = [f"{c} ({_col_kind(df[c])})" for c in list(df.columns)[:max_cols]]
        more = f" … và {len(df.columns) - max_cols} cột khác" if len(df.columns) > max_cols else ""
        rng = next((r for r in (_time_range(df[c]) for c in df.columns[:max_cols] if _col_kind(df[c]) == "thời gian") if r), None)
        kỳ = f" Kỳ thời gian: {rng[0]:%d/%m/%Y} đến {rng[1]:%d/%m/%Y}." if rng else ""
        out.append(f"- [{name}] {len(df):,} dòng.{kỳ} Cột: ".replace(",", ".") + "; ".join(cols) + more)
    if not out:
        return ""
    return ("THẺ DỮ LIỆU (do máy lập từ dữ liệu thật):\n" + "\n".join(out) + "\n"
            "Chỉ được dựa vào những bảng, cột và kỳ thời gian nêu trên. Điều gì không có ở đây (vd nguyên nhân, chi phí, thiết bị, con người) KHÔNG được khẳng định; "
            "chỉ nêu như giả thuyết cần kiểm chứng kèm dữ liệu cần thu thêm.\n\n" + naming_note(dfs))
