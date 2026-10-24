# -*- coding: utf-8 -*-
"""Chính sách ngôn ngữ: mọi thứ người dùng đọc (kết quả phân tích, báo cáo, dashboard) viết HOÀN TOÀN bằng tiếng Việt,
không xen tiếng Anh. Phần này gồm câu luật đưa vào mọi prompt, và bước đổi tên cột kết quả từ tiếng Anh sang tiếng Việt."""
import re

RULE = ("NGÔN NGỮ: viết TOÀN BỘ bằng tiếng Việt có dấu (tiêu đề, nhận định, tên bảng, tên cột kết quả, nhãn biểu đồ, đơn vị). "
        "Không xen tiếng Anh (không viết insight, dashboard, KPI, count, avg, total, ratio...). Tên cột kết quả phải đọc tự nhiên như người Việt viết, "
        "viết hoa chữ cái đầu, có dấu cách, ví dụ 'Số lượng nhân sự', 'Lương trung bình', 'Tỷ trọng (%)'; tuyệt đối không dùng snake_case hay chữ IN HOA. "
        "Chỉ giữ nguyên tên riêng, mã và giá trị gốc có trong dữ liệu.")

COLNAME_RULE = ("TÊN CỘT của `result` PHẢI là tiếng Việt có dấu, tự nhiên (vd 'Cấp bậc', 'Số lượng nhân sự', 'Lương trung bình', 'Tỷ trọng (%)'): "
                "đặt tên ngay khi tổng hợp hoặc đổi tên ở cuối code bằng result = result.rename(columns={...}). Không dùng tên tiếng Anh, snake_case hay chữ IN HOA.")

# Từ điển dự phòng khi không gọi được AI để dịch tên cột
TOK = {"count": "số lượng", "cnt": "số lượng", "num": "số", "number": "số", "avg": "trung bình", "average": "trung bình", "mean": "trung bình", "median": "trung vị",
       "total": "tổng", "sum": "tổng", "max": "cao nhất", "min": "thấp nhất", "per": "theo", "by": "theo", "of": "của", "and": "và", "vs": "so với",
       "perc": "tỷ lệ (%)", "percent": "tỷ lệ (%)", "percentage": "tỷ lệ (%)", "pct": "tỷ lệ (%)", "ratio": "tỷ lệ", "rate": "tỷ lệ", "share": "tỷ trọng", "growth": "tăng trưởng",
       "level": "cấp bậc", "salary": "lương", "wage": "lương", "pay": "lương", "income": "thu nhập", "allowance": "phụ cấp", "bonus": "thưởng", "base": "cơ bản",
       "department": "phòng ban", "dept": "phòng ban", "employee": "nhân viên", "employees": "nhân viên", "emp": "nhân viên", "staff": "nhân sự", "headcount": "số nhân sự",
       "month": "tháng", "year": "năm", "quarter": "quý", "week": "tuần", "day": "ngày", "date": "ngày", "period": "kỳ", "time": "thời gian",
       "revenue": "doanh thu", "sales": "doanh số", "cost": "chi phí", "profit": "lợi nhuận", "amount": "giá trị", "value": "giá trị", "price": "đơn giá",
       "qty": "số lượng", "quantity": "số lượng", "customer": "khách hàng", "product": "sản phẩm", "region": "khu vực", "category": "nhóm", "group": "nhóm", "type": "loại",
       "name": "tên", "id": "mã", "code": "mã", "forecast": "dự báo", "lower": "cận dưới", "upper": "cận trên", "gap": "chênh lệch", "diff": "chênh lệch", "change": "thay đổi",
       "top": "cao nhất", "rank": "thứ hạng", "status": "trạng thái", "note": "ghi chú", "notes": "ghi chú", "order": "đơn hàng", "orders": "đơn hàng"}


def foreign(name, known=()):
    """Tên cột chỉ gồm chữ không dấu/ký tự Latin cơ bản (vd COUNT_PER_LEVEL, avg_salary) và không phải tên cột gốc của dữ liệu."""
    s = str(name).strip()
    return s not in known and bool(re.fullmatch(r"[A-Za-z0-9_ ()%/.\-]+", s)) and bool(re.search(r"[A-Za-z]{2,}", s))


def humanize(name):
    """Dự phòng: tách snake_case/camelCase, dịch từng từ bằng từ điển, viết hoa chữ đầu."""
    t = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(name))
    words = [w for w in re.split(r"[_\s]+", t.strip()) if w]
    out = " ".join(TOK.get(w.lower(), w.lower()) for w in words).strip()
    return (out[:1].upper() + out[1:]) or str(name)


def _unique(names):
    seen, out = {}, []
    for n in names:
        k = seen.get(n, 0)
        seen[n] = k + 1
        out.append(n if not k else f"{n} ({k + 1})")
    return out


def localize(dfs, titles, known, ask):
    """Đổi tên cột kết quả không phải tiếng Việt. ask(ctx, cand) -> dict {"map": {...}} hoặc ném lỗi (khi đó dùng từ điển dự phòng).
    Trả về (dfs mới, số cột đã đổi)."""
    cand = []
    for df in dfs:
        if df is not None:
            cand += [str(c) for c in df.columns if foreign(c, known)]
    cand = list(dict.fromkeys(cand))
    if not cand:
        return dfs, 0
    mp = {}
    try:
        ctx = {t: [str(c) for c in df.columns] for t, df in zip(titles, dfs) if df is not None}
        r = ask(ctx, cand)
        raw = (r or {}).get("map") or {}
        mp = {k: v.strip() for k, v in raw.items() if k in cand and isinstance(v, str) and v.strip() and len(v.strip()) <= 60 and not foreign(v.strip(), ())}
    except Exception:                                     # noqa: BLE001  (hết hạn mức, JSON hỏng... -> dùng từ điển)
        mp = {}
    for c in cand:
        mp.setdefault(c, humanize(c))
    out = []
    for df in dfs:
        if df is None:
            out.append(None)
            continue
        d = df.copy()
        d.columns = _unique([mp.get(str(c), c) for c in d.columns])
        out.append(d)
    return out, len(mp)
