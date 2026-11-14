# -*- coding: utf-8 -*-
"""Biểu đồ SVG thuần (không phụ thuộc thư viện) cho dashboard HTML."""
import math

from ..utils import E, fmt_num, fmt_pct, fmt_val, vn
from .common import is_time_like, pp, trunc


def _ext(vals):
    lo, hi = min(0, min(vals)), max(0, max(vals))
    return lo, hi, (hi - lo) or 1


def _lab(v, unit=""):
    """Nhãn giá trị trong biểu đồ: số ghi đủ, quy tắc số chung; chỉ phần trăm mới kèm ký hiệu (đơn vị khác nằm ở dòng phụ đề của thẻ). Tiền: nguyên đồng."""
    return fmt_pct(v) if unit == "%" else fmt_num(v, unit)


def bars(rows, unit=""):
    n = len(rows)
    lw, bw, rh = 150, 270, 32
    vw = max(100, int(max(len(fmt_val(v, unit)) for _, v in rows) * 7.4) + 16)          # số đầy đủ dài hơn bản rút gọn nên cột nhãn giá trị tự giãn
    W, H = lw + bw + vw, n * rh + 10
    vals = [v for _, v in rows]
    lo, hi, span = _ext(vals)
    zx = lw + (-lo) / span * bw
    imax = max(range(n), key=lambda i: abs(vals[i]))
    o = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" preserveAspectRatio="xMinYMin meet">']
    if lo < 0:
        o.append(f'<line class="ax" x1="{zx:.1f}" y1="2" x2="{zx:.1f}" y2="{H - 4}"/>')
    for i, (l, v) in enumerate(rows):
        y = 5 + i * rh
        x1 = lw + (v - lo) / span * bw
        x, w = min(zx, x1), max(abs(x1 - zx), 1.5)
        cls = "neg" if v < 0 else "hi" if i == imax else "bar"
        o.append(f'<text class="lb" x="{lw - 10}" y="{y + rh / 2 + 3:.1f}" text-anchor="end">{E(trunc(l, 20))}<title>{E(l)}</title></text>')
        o.append(f'<rect class="{cls}" x="{x:.1f}" y="{y + 4}" width="{w:.1f}" height="{rh - 12}" rx="3"><title>{E(l)}: {E(fmt_val(v, unit))}</title></rect>')
        tx, anc = (x1 + 7, "start") if v >= 0 else (x1 - 7, "end")
        o.append(f'<text class="vl {"b" if i == imax else ""}" x="{tx:.1f}" y="{y + rh / 2 + 3:.1f}" text-anchor="{anc}">{E(fmt_val(v, unit))}</text>')
    return "".join(o) + "</svg>"


def cols(rows, unit=""):
    rows = rows[-16:]
    n = len(rows)
    W, H, pl, pr, pt, pb = 520, 290, 10, 10, 28, 64
    pw, ph = W - pl - pr, H - pt - pb
    vals = [v for _, v in rows]
    lo, hi, span = _ext(vals)
    zy = pt + hi / span * ph
    slot = pw / n
    bwid = min(slot * .62, 58)
    imax = max(range(n), key=lambda i: abs(vals[i]))
    imin = vals.index(min(vals))
    fit = max(len(_lab(v, unit)) for v in vals) * 6.8 <= slot * 1.05            # số đầy đủ chỉ ghi trên mọi cột khi đủ chỗ; không thì chỉ cột cao nhất và thấp nhất, còn lại xem ở chú thích khi rê chuột
    o = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" preserveAspectRatio="xMinYMin meet">',
         f'<line class="ax" x1="{pl}" y1="{zy:.1f}" x2="{W - pr}" y2="{zy:.1f}"/>']
    for i, (l, v) in enumerate(rows):
        cx = pl + slot * (i + .5)
        yv = pt + (hi - v) / span * ph
        y, h = min(yv, zy), max(abs(yv - zy), 1.5)
        cls = "neg" if v < 0 else "hi" if i == imax else "bar"
        o.append(f'<rect class="{cls}" x="{cx - bwid / 2:.1f}" y="{y:.1f}" width="{bwid:.1f}" height="{h:.1f}" rx="3"><title>{E(l)}: {E(fmt_val(v, unit))}</title></rect>')
        vy = y - 6 if v >= 0 else y + h + 14
        if (n <= 8 and fit) or i in (imax, imin):
            o.append(f'<text class="vl {"b" if i == imax else ""}" x="{cx:.1f}" y="{vy:.1f}" text-anchor="middle">{E(_lab(v, unit))}</text>')
        lx, ly = cx, H - pb + 18
        rot = f' transform="rotate(-35 {lx:.1f} {ly})"' if n > 7 else ""
        o.append(f'<text class="lb" x="{lx:.1f}" y="{ly}" text-anchor="{"end" if n > 7 else "middle"}"{rot}>{E(trunc(pp(l), 12))}</text>')
    return "".join(o) + "</svg>"


def line(rows, unit="", strong=False):
    """Biểu đồ đường. strong=True là biểu đồ VÙNG: vùng dưới đường tô đậm, chỉ đánh dấu các điểm chính."""
    rows = rows[-36:]
    n = len(rows)
    W, H, pl, pr, pt, pb = 520, 290, 24, 24, 30, 56
    pw, ph = W - pl - pr, H - pt - pb
    vals = [v for _, v in rows]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * .12 or 1
    lo, hi = lo - pad, hi + pad
    pts = [(pl + pw * (i / max(n - 1, 1)), pt + (hi - v) / (hi - lo) * ph) for i, (_, v) in enumerate(rows)]
    base = pt + ph
    area = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f" L{pts[-1][0]:.1f},{base} L{pts[0][0]:.1f},{base} Z"
    o = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" preserveAspectRatio="xMinYMin meet">',
         f'<line class="ax" x1="{pl}" y1="{base}" x2="{W - pr}" y2="{base}"/>',
         f'<path class="area{" s" if strong else ""}" d="{area}"/>',
         '<polyline class="ln" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + '"/>']
    key = {0, n - 1, vals.index(max(vals)), vals.index(min(vals))}
    for i, ((l, v), (x, y)) in enumerate(zip(rows, pts)):
        if strong and i not in key:
            continue
        o.append(f'<circle class="dot{" k" if i in key else ""}" cx="{x:.1f}" cy="{y:.1f}" r="{4.5 if i in key else 2.5}"><title>{E(pp(l))}: {E(fmt_val(v, unit))}</title></circle>')
        if i in key:
            anc = "start" if i == 0 else "end" if i == n - 1 else "middle"
            o.append(f'<text class="vl b" x="{x:.1f}" y="{y - 10:.1f}" text-anchor="{anc}">{E(_lab(v, unit))}</text>')
    step = max(1, n // 8)
    for i in range(0, n, step):
        o.append(f'<text class="lb" x="{pts[i][0]:.1f}" y="{H - pb + 18}" text-anchor="middle">{E(trunc(pp(rows[i][0]), 10))}</text>')
    return "".join(o) + "</svg>"


PAL = ["#4F46E5", "#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#64748B"]


def donut(rows, unit="", hole=True):
    """Biểu đồ tròn. hole=True: vành khuyên (có tổng ở giữa); hole=False: tròn đặc (pie)."""
    rows = sorted([(l, v) for l, v in rows if v > 0], key=lambda r: -r[1])
    if len(rows) > 7:
        rows = rows[:6] + [("Khác", sum(v for _, v in rows[6:]))]
    tot = sum(v for _, v in rows) or 1
    H = max(220, 30 * len(rows) + 40)
    cx, cy, r, sw = (92, H / 2, 64, 26) if hole else (92, H / 2, 32, 64)         # tròn đặc: vòng bán kính r/2 với nét dày r phủ kín hình tròn
    C = 2 * math.pi * r
    o = [f'<svg class="chart" viewBox="0 0 520 {H}" role="img" preserveAspectRatio="xMinYMin meet">']
    off = 0
    for i, (l, v) in enumerate(rows):
        seg = v / tot * C
        o.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{PAL[i % 7]}" stroke-width="{sw}" stroke-dasharray="{seg:.2f} {C - seg:.2f}" '
                 f'stroke-dashoffset="{-off:.2f}" transform="rotate(-90 {cx} {cy})"><title>{E(l)}: {E(fmt_val(v, unit))}</title></circle>')
        off += seg
    if hole:
        tl = _lab(tot, unit)
        fs = max(10, min(15, int(96 / max(len(tl), 1) * 1.55)))                  # số tổng ghi đủ có thể dài: chữ tự co để nằm gọn trong lỗ của vành khuyên
        o.append(f'<text class="vl b" x="{cx}" y="{cy - 2}" text-anchor="middle" style="font-size:{fs}px">{E(tl)}</text>'
                 f'<text class="lb" x="{cx}" y="{cy + 16}" text-anchor="middle">Tổng</text>')
    top = (H - 30 * len(rows)) / 2 + 8
    for i, (l, v) in enumerate(rows):
        y = top + i * 30
        o.append(f'<rect x="190" y="{y - 11}" width="14" height="14" rx="3" fill="{PAL[i % 7]}"/>'
                 f'<text class="lb" x="212" y="{y}" style="fill:var(--ink)">{E(trunc(l, 20))}</text>'
                 f'<text class="vl" x="512" y="{y}" text-anchor="end">{fmt_pct(v / tot * 100)}</text>')
    return "".join(o) + "</svg>"


def lollipop(rows, unit=""):
    """Kẹo mút: thanh mảnh + chấm tròn ở đầu. Xếp hạng gọn hơn cột ngang, ít mực hơn khi có nhiều nhóm."""
    n = len(rows)
    lw, bw, rh = 150, 270, 30
    vw = max(100, int(max(len(fmt_val(v, unit)) for _, v in rows) * 7.4) + 16)
    W, H = lw + bw + vw, n * rh + 10
    vals = [v for _, v in rows]
    lo, hi, span = _ext(vals)
    zx = lw + (-lo) / span * bw
    imax = max(range(n), key=lambda i: abs(vals[i]))
    o = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" preserveAspectRatio="xMinYMin meet">',
         f'<line class="ax" x1="{zx:.1f}" y1="2" x2="{zx:.1f}" y2="{H - 4}"/>']
    for i, (l, v) in enumerate(rows):
        y = 5 + i * rh + rh / 2 - 2
        x1 = lw + (v - lo) / span * bw
        cls = "neg" if v < 0 else "hi" if i == imax else "bar"
        o.append(f'<text class="lb" x="{lw - 10}" y="{y + 4:.1f}" text-anchor="end">{E(trunc(l, 20))}<title>{E(l)}</title></text>')
        o.append(f'<line class="stem {cls}" x1="{zx:.1f}" y1="{y:.1f}" x2="{x1:.1f}" y2="{y:.1f}"/>')
        o.append(f'<circle class="pop {cls}" cx="{x1:.1f}" cy="{y:.1f}" r="6"><title>{E(l)}: {E(fmt_val(v, unit))}</title></circle>')
        tx, anc = (x1 + 12, "start") if v >= 0 else (x1 - 12, "end")
        o.append(f'<text class="vl {"b" if i == imax else ""}" x="{tx:.1f}" y="{y + 4:.1f}" text-anchor="{anc}">{E(fmt_val(v, unit))}</text>')
    return "".join(o) + "</svg>"


def pareto_rows(rows, limit=12):
    """Nhóm sắp giảm dần + tỷ lệ cộng dồn (%). Chỉ dùng cho giá trị không âm."""
    rs = sorted([(l, v) for l, v in rows if v > 0], key=lambda r: -r[1])[:limit]
    tot = sum(v for _, v in rs) or 1
    acc, out = 0, []
    for l, v in rs:
        acc += v
        out.append((l, v, acc / tot * 100))
    return out


def pareto(rows, unit=""):
    """Pareto (80/20): cột sắp giảm dần + đường cộng dồn %, vạch 80%. Cho thấy ít nhóm nào tạo phần lớn tổng."""
    pr_ = pareto_rows(rows)
    n = len(pr_)
    W, H, pl, pr, pt, pb = 520, 290, 10, 46, 28, 64
    pw, ph = W - pl - pr, H - pt - pb
    mx = max(v for _, v, _ in pr_) or 1
    slot = pw / n
    bwid = min(slot * .62, 58)
    base = pt + ph
    y80 = pt + (1 - .8) * ph
    k80 = next((i for i, (_, _, c) in enumerate(pr_) if c >= 80), n - 1)
    fit = max(len(_lab(v, unit)) for _, v, _ in pr_) * 6.8 <= slot * 1.05
    o = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" preserveAspectRatio="xMinYMin meet">',
         f'<line class="ax" x1="{pl}" y1="{base}" x2="{W - pr}" y2="{base}"/>',
         f'<line class="ref" x1="{pl}" y1="{y80:.1f}" x2="{W - pr}" y2="{y80:.1f}"/>',
         f'<text class="lb" x="{W - pr + 6}" y="{y80 + 4:.1f}">80%</text>',
         f'<text class="lb" x="{W - pr + 6}" y="{pt + 4}">100%</text>']
    pts = []
    for i, (l, v, c) in enumerate(pr_):
        cx = pl + slot * (i + .5)
        h = max(v / mx * ph, 1.5)
        cls = "hi" if i <= k80 else "bar"
        o.append(f'<rect class="{cls}" x="{cx - bwid / 2:.1f}" y="{base - h:.1f}" width="{bwid:.1f}" height="{h:.1f}" rx="3"><title>{E(l)}: {E(fmt_val(v, unit))} · cộng dồn {E(fmt_pct(c))}</title></rect>')
        if n <= 8 and fit:
            o.append(f'<text class="vl" x="{cx:.1f}" y="{base - h - 5:.1f}" text-anchor="middle">{E(_lab(v, unit))}</text>')
        lx, ly = cx, H - pb + 18
        rot = f' transform="rotate(-35 {lx:.1f} {ly})"' if n > 7 else ""
        o.append(f'<text class="lb" x="{lx:.1f}" y="{ly}" text-anchor="{"end" if n > 7 else "middle"}"{rot}>{E(trunc(pp(l), 12))}</text>')
        pts.append((cx, pt + (1 - c / 100) * ph, c))
    o.append('<polyline class="ln" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts) + '"/>')
    for i, (x, y, c) in enumerate(pts):
        o.append(f'<circle class="dot{" k" if i == k80 else ""}" cx="{x:.1f}" cy="{y:.1f}" r="{4.5 if i == k80 else 2.5}"><title>{E(fmt_pct(c))}</title></circle>')
    x, y, c = pts[k80]
    o.append(f'<text class="vl b" x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle">{E(fmt_pct(c))}</text>')
    return "".join(o) + "</svg>"


def tm_layout(items, x, y, w, h, out):
    """Chia hình chữ nhật cho các phần theo giá trị: mỗi lần tách thành hai nhóm có tổng gần bằng nhau, cắt theo cạnh dài hơn. Dùng cho treemap."""
    if not items:
        return
    if len(items) == 1:
        out.append((items[0], x, y, w, h))
        return
    s = sum(v for _, v in items) or 1
    acc, k, best = 0, 1, None
    for j in range(1, len(items)):
        acc += items[j - 1][1]
        d = abs(acc - s / 2)
        if best is None or d < best:
            best, k = d, j
    a, b = items[:k], items[k:]
    sa = sum(v for _, v in a) / s
    if w >= h:
        tm_layout(a, x, y, w * sa, h, out)
        tm_layout(b, x + w * sa, y, w * (1 - sa), h, out)
    else:
        tm_layout(a, x, y, w, h * sa, out)
        tm_layout(b, x, y + h * sa, w, h * (1 - sa), out)


TM_PAL = ["#4F46E5", "#0369A1", "#047857", "#B45309", "#B91C1C", "#6D28D9", "#475569"]       # đủ đậm để chữ trắng đọc rõ


def treemap(rows, unit=""):
    """Treemap: diện tích mỗi ô tỷ lệ với giá trị. Cho thấy cơ cấu của nhiều nhóm cùng lúc mà không cần chú giải."""
    rs = sorted([(l, v) for l, v in rows if v > 0], key=lambda r: -r[1])[:16]
    tot = sum(v for _, v in rs) or 1
    W, H = 520, 290
    cells = []
    tm_layout(rs, 0, 0, W, H, cells)
    o = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" preserveAspectRatio="xMinYMin meet">']
    order = {l: i for i, (l, _) in enumerate(rs)}
    for (l, v), x, y, w, h in cells:
        i = order[l]
        o.append(f'<rect class="tm" x="{x + 1:.1f}" y="{y + 1:.1f}" width="{max(w - 2, 1):.1f}" height="{max(h - 2, 1):.1f}" rx="4" fill="{TM_PAL[i % 7]}"><title>{E(l)}: {E(fmt_val(v, unit))} ({E(fmt_pct(v / tot * 100))})</title></rect>')
        if w >= 74 and h >= 40:
            o.append(f'<text class="tmt" x="{x + 9:.1f}" y="{y + 20:.1f}">{E(trunc(l, max(6, int(w / 7.2))))}</text>'
                     f'<text class="tmt s" x="{x + 9:.1f}" y="{y + 36:.1f}">{E(_lab(v, unit))} · {E(fmt_pct(v / tot * 100))}</text>')
    return "".join(o) + "</svg>"


def chart_svg(kind, rows, unit=""):
    if not rows:
        return ""
    pos = all(v >= 0 for _, v in rows)
    if kind == "area" and len(rows) >= 2:
        return line(rows, unit, strong=True)
    if kind == "line" and len(rows) >= 2:
        return line(rows, unit)
    if kind in ("donut", "pie") and pos and len(rows) >= 2:
        return donut(rows, unit, hole=kind == "donut")
    if kind == "lollipop":
        return lollipop(rows, unit)
    if kind == "pareto" and pos and len(rows) >= 3 and sum(v for _, v in rows) > 0:
        return pareto(rows, unit)
    if kind == "treemap" and pos and len(rows) >= 2 and sum(v for _, v in rows) > 0:
        return treemap(rows, unit)
    if kind == "cols" and len(rows) > 5 and not is_time_like(rows):
        return bars(rows, unit)                # nhiều nhóm có tên dài: thanh ngang dễ đọc hơn cột đứng
    if kind in ("cols", "line", "area"):
        return cols(rows, unit)
    return bars(rows, unit)
