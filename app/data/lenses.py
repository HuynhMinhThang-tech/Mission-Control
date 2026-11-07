# -*- coding: utf-8 -*-
"""GÓC NHÌN PHÂN TÍCH khả dụng cho một bộ dữ liệu (bước Phân tích).

Trước đây AI chỉ nhận một khuôn cố định (mô tả / chẩn đoán / dự báo) nên các đề xuất giống nhau giữa mọi bộ dữ liệu. Ở đây CODE nhìn vào dữ liệu thật
(cột nhị phân Đạt / Không đạt, cột thời gian, nhóm lệch, ô thiếu...) và liệt kê những góc nhìn thật sự làm được, kèm tên cột cụ thể. AI chọn và
sáng tạo trên danh sách đó; mọi con số vẫn do code tính trong sandbox và qua kiểm số như trước, nên sáng tạo ở CÁCH NHÌN chứ không ở số liệu."""
from .. import labels as lb
from .binary import sides
from .describe import kind_of

MAX_SHOW = 4            # số tên cột nêu trong mỗi góc nhìn


def _cols(d):
    bin_, dims, nums, times, miss = [], [], [], [], []
    for c in d.columns:
        if str(c).endswith("_nghi_van"):
            continue
        s = d[c]
        kind = kind_of(c, s)[0]
        if kind in ("empty", "id"):
            continue
        u = int(s.nunique(dropna=True))
        if sides(s) is not None:
            bin_.append(c)
        elif kind == "cat" and 2 <= u <= 60:
            dims.append(c)
        elif kind == "num":
            nums.append(c)
        elif kind == "date":
            times.append(c)
        p = float(s.isna().mean())
        if p >= .05:
            miss.append((c, p))
    return bin_, dims, nums, times, miss


def _n(cols):
    cs = [lb.label(c) for c in cols[:MAX_SHOW]]
    return ", ".join(cs) + (f" (+{len(cols) - MAX_SHOW} cột khác)" if len(cols) > MAX_SHOW else "")


def available(clean):
    """[(tên góc nhìn, mô tả cụ thể theo dữ liệu)] cho mọi bảng. Chỉ nêu góc nhìn mà dữ liệu có ĐỦ cột để làm."""
    out, seen = [], set()
    for f, d in (clean or {}).items():
        bin_, dims, nums, times, miss = _cols(d)
        add = lambda name, txt: (name, txt) not in seen and not seen.add((name, txt)) and out.append((name, f"[{f}] {txt}" if len(clean) > 1 else txt))   # noqa: E731
        if bin_:
            add("Tỷ lệ đạt / tuân thủ", f"tỷ lệ Đạt của {_n(bin_)}" + (f" theo {_n(dims)}" if dims else "") + (" và theo thời gian" if times else "") + " (kiểu phân tích «Tỷ lệ đạt»)")
        if len(bin_) >= 2:
            add("Tiêu chí hay trượt cùng nhau", f"những tiêu chí trong {_n(bin_)} có hay cùng «Không đạt» trên một bản ghi không (chỉ ra khâu yếu có liên quan nhau)")
        if dims and (nums or bin_):
            add("Xếp hạng và 80/20 (Pareto)", f"nhóm {_n(dims)} nào tạo ra phần lớn tổng (kiểu «Xếp hạng 80/20»)" + (f" của {_n(nums)}" if nums else ""))
            add("Khoảng cách so với mức giữa (trung vị)", f"nhóm nào lệch xa nhất so với trung vị của {_n(nums or bin_)} (nhóm đáng chú ý ở CẢ hai đầu)")
        if times and dims and nums:
            add("Nhóm nào kéo kỳ này tăng / giảm", f"so kỳ gần nhất với kỳ trước, nhóm {_n(dims)} đóng góp bao nhiêu vào thay đổi của {_n(nums)}")
        if nums or (times and bin_):
            add("Bất thường và ngoại lai", f"điểm dữ liệu hoặc kỳ lệch hẳn khỏi bình thường ở {_n(nums or bin_)}")
        if times and (nums or bin_):
            add("Nhịp theo thứ trong tuần / mùa vụ", f"{_n(nums or bin_)} có nhịp lặp theo thứ trong tuần hoặc theo tháng không")
        if miss and dims:
            add("Dữ liệu thiếu tập trung ở đâu", f"cột thiếu từ 5% ({_n([c for c, _ in miss])}) có thiếu dồn vào nhóm nào trong {_n(dims)} không (thiếu có thể là tín hiệu)")
        if dims and nums:
            add("Nhóm cao và nhóm thấp khác nhau thế nào", f"so nhóm đứng đầu và đứng cuối của {_n(dims)} trên {_n(nums)}: khác nhau ở những cột nào")
    return out


def block(clean, avoid=()):
    """Đoạn chữ đưa vào prompt: góc nhìn khả dụng (nếu có) + yêu cầu tránh các mục đã đề xuất."""
    L = available(clean)
    txt = ""
    if L:
        txt = "GÓC NHÌN KHẢ DỤNG CHO ĐÚNG DỮ LIỆU NÀY (hệ thống đã kiểm tra có đủ cột để làm; chọn cái hợp với câu hỏi, đừng dùng hết):\n" + "\n".join(f"- {n}: {t}" for n, t in L) + "\n"
    if avoid:
        txt += "ĐÃ CÓ các mục sau, hãy đề xuất mục KHÁC HẲN (góc nhìn khác, không trùng ý, không đổi tên mục cũ): " + "; ".join(str(a)[:80] for a in avoid) + "\n"
    return txt
