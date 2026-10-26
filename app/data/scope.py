# -*- coding: utf-8 -*-
"""Tín hiệu PHẠM VI và CHẤT LƯỢNG của dữ liệu, do CODE tính (không nhờ AI đoán), đưa vào prompt của các agent.

Lỗi phổ biến nhất của phân tích tự động: cộng gộp lẫn các nhóm bản ghi không cùng phạm vi (đơn hoàn/hủy với đơn thành công, thu với chi,
dòng tổng với dòng chi tiết...), hoặc so một kỳ chưa đủ ngày với kỳ đủ, hoặc chia cơ cấu theo cột thiếu gần hết giá trị. Ở đây ta chỉ ra *chỗ nào
cần quyết định*, không áp đặt quyết định: agent phải chọn có lý do và ghi rõ phạm vi vào `goal`. Không gắn với lĩnh vực hay tên cột nào.
"""
import calendar

import pandas as pd

from .. import labels

# từ gợi ý cột "loại bản ghi" (xét theo TỪ của tên cột, không dấu)
KIND_WORDS = {"loai", "type", "kind", "trang", "thai", "status", "hinh", "thuc", "phuong", "kenh", "channel", "nhom", "direction", "state", "giai", "doan"}
TIME_WORDS = {"ngay", "date", "thang", "month", "time", "ky", "day", "nam", "year"}


def _is_time(name, s):
    return pd.api.types.is_datetime64_any_dtype(s) or (bool(TIME_WORDS & set(labels.tokens(name))) and not pd.api.types.is_numeric_dtype(s))


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
                d = pd.to_datetime(df[c].head(20000), errors="coerce", dayfirst=True)
                d = d.dropna()
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
