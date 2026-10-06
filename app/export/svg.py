# -*- coding: utf-8 -*-
"""Biểu đồ SVG thuần (không phụ thuộc thư viện) cho dashboard HTML."""
import math

from ..utils import E, compact, vn
from .common import is_time_like, trunc


def _ext(vals):
    lo, hi = min(0, min(vals)), max(0, max(vals))
    return lo, hi, (hi - lo) or 1


def bars(rows):
    n = len(rows)
    lw, bw, vw, rh = 170, 380, 120, 32
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
        o.append(f'<text class="lb" x="{lw - 10}" y="{y + rh / 2 + 3:.1f}" text-anchor="end">{E(trunc(l, 24))}<title>{E(l)}</title></text>')
        o.append(f'<rect class="{cls}" x="{x:.1f}" y="{y + 4}" width="{w:.1f}" height="{rh - 12}" rx="3"><title>{E(l)}: {vn(v)}</title></rect>')
        tx, anc = (x1 + 7, "start") if v >= 0 else (x1 - 7, "end")
        o.append(f'<text class="vl {"b" if i == imax else ""}" x="{tx:.1f}" y="{y + rh / 2 + 3:.1f}" text-anchor="{anc}">{E(compact(v))}</text>')
    return "".join(o) + "</svg>"


def cols(rows):
    rows = rows[-16:]
    n = len(rows)
    W, H, pl, pr, pt, pb = 680, 300, 10, 10, 28, 64
    pw, ph = W - pl - pr, H - pt - pb
    vals = [v for _, v in rows]
    lo, hi, span = _ext(vals)
    zy = pt + hi / span * ph
    slot = pw / n
    bwid = min(slot * .62, 58)
    imax = max(range(n), key=lambda i: abs(vals[i]))
    o = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" preserveAspectRatio="xMinYMin meet">',
         f'<line class="ax" x1="{pl}" y1="{zy:.1f}" x2="{W - pr}" y2="{zy:.1f}"/>']
    for i, (l, v) in enumerate(rows):
        cx = pl + slot * (i + .5)
        yv = pt + (hi - v) / span * ph
        y, h = min(yv, zy), max(abs(yv - zy), 1.5)
        cls = "neg" if v < 0 else "hi" if i == imax else "bar"
        o.append(f'<rect class="{cls}" x="{cx - bwid / 2:.1f}" y="{y:.1f}" width="{bwid:.1f}" height="{h:.1f}" rx="3"><title>{E(l)}: {vn(v)}</title></rect>')
        vy = y - 6 if v >= 0 else y + h + 14
        o.append(f'<text class="vl {"b" if i == imax else ""}" x="{cx:.1f}" y="{vy:.1f}" text-anchor="middle">{E(compact(v))}</text>')
        lx, ly = cx, H - pb + 18
        rot = f' transform="rotate(-35 {lx:.1f} {ly})"' if n > 7 else ""
        o.append(f'<text class="lb" x="{lx:.1f}" y="{ly}" text-anchor="{"end" if n > 7 else "middle"}"{rot}>{E(trunc(l, 12))}</text>')
    return "".join(o) + "</svg>"


def line(rows):
    rows = rows[-36:]
    n = len(rows)
    W, H, pl, pr, pt, pb = 680, 300, 24, 24, 30, 56
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
         f'<path class="area" d="{area}"/>',
         '<polyline class="ln" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + '"/>']
    key = {0, n - 1, vals.index(max(vals)), vals.index(min(vals))}
    for i, ((l, v), (x, y)) in enumerate(zip(rows, pts)):
        o.append(f'<circle class="dot{" k" if i in key else ""}" cx="{x:.1f}" cy="{y:.1f}" r="{4.5 if i in key else 2.5}"><title>{E(l)}: {vn(v)}</title></circle>')
        if i in key:
            anc = "start" if i == 0 else "end" if i == n - 1 else "middle"
            o.append(f'<text class="vl b" x="{x:.1f}" y="{y - 10:.1f}" text-anchor="{anc}">{E(compact(v))}</text>')
    step = max(1, n // 8)
    for i in range(0, n, step):
        o.append(f'<text class="lb" x="{pts[i][0]:.1f}" y="{H - pb + 18}" text-anchor="middle">{E(trunc(rows[i][0], 10))}</text>')
    return "".join(o) + "</svg>"


PAL = ["#4F46E5", "#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#64748B"]


def donut(rows):
    rows = sorted([(l, v) for l, v in rows if v > 0], key=lambda r: -r[1])
    if len(rows) > 7:
        rows = rows[:6] + [("Khác", sum(v for _, v in rows[6:]))]
    tot = sum(v for _, v in rows) or 1
    H = max(250, 30 * len(rows) + 40)
    cx, cy, r, sw = 130, H / 2, 82, 34
    C = 2 * math.pi * r
    o = [f'<svg class="chart" viewBox="0 0 680 {H}" role="img" preserveAspectRatio="xMinYMin meet">']
    off = 0
    for i, (l, v) in enumerate(rows):
        seg = v / tot * C
        o.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{PAL[i % 7]}" stroke-width="{sw}" stroke-dasharray="{seg:.2f} {C - seg:.2f}" '
                 f'stroke-dashoffset="{-off:.2f}" transform="rotate(-90 {cx} {cy})"><title>{E(l)}: {vn(v)}</title></circle>')
        off += seg
    o.append(f'<text class="vl b" x="{cx}" y="{cy - 2}" text-anchor="middle" style="font-size:18px">{E(compact(tot))}</text>'
             f'<text class="lb" x="{cx}" y="{cy + 16}" text-anchor="middle">Tổng</text>')
    top = (H - 30 * len(rows)) / 2 + 8
    for i, (l, v) in enumerate(rows):
        y = top + i * 30
        o.append(f'<rect x="270" y="{y - 11}" width="14" height="14" rx="3" fill="{PAL[i % 7]}"/>'
                 f'<text class="lb" x="292" y="{y}" style="fill:var(--ink)">{E(trunc(l, 30))}</text>'
                 f'<text class="vl" x="660" y="{y}" text-anchor="end">{E(compact(v))} · {vn(v / tot * 100, 1)}%</text>')
    return "".join(o) + "</svg>"


def chart_svg(kind, rows):
    if not rows:
        return ""
    if kind == "line" and len(rows) >= 2:
        return line(rows)
    if kind == "donut" and all(v >= 0 for _, v in rows) and len(rows) >= 2:
        return donut(rows)
    if kind == "cols" or kind == "line":
        return cols(rows)
    return bars(rows)