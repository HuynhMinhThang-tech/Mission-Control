/**
 * deck-builder.js — DeckSpec (JSON) -> .pptx, độc lập với nội dung/dataset.  Cần: npm i pptxgenjs
 *
 * DeckSpec = {
 *   meta:  { title, subtitle?, author?, date?, footer? },
 *   theme?: { primary, dark, accent, surface, text, muted, positive, negative, headFont, bodyFont },  // hex không có '#'
 *   slides: [
 *     { type:'summary',  title, answer, points:[{head,text}] (≤4), notes? },
 *     { type:'kpi',      title, kpis:[{label,value,delta?,tone?:'positive'|'negative'|'neutral'}] (≤4), takeaway?, notes? },
 *     { type:'chart',    title, chart:{ type:'column'|'bar'|'stacked'|'line'|'area'|'doughnut'|'pie'|'scatter',
 *                                       labels:[], series:[{name,values:[]}], format?:'number'|'percent'|'compact_vnd', highlight?:[idx] },
 *                         takeaway, callouts?:[string], source?, notes? },
 *     { type:'compare',  title, columns:[{head, big?, bigLabel?, items:[]}] (≤4), notes? },
 *     { type:'actions',  title, rows:[{action, impact, effort, effortLevel?:1|2|3, metric?, when?}], notes? },
 *     { type:'table',    title, columns:[], rows:[[]], notes? },
 *     { type:'appendix', title, sections:[{head, items:[]}] (≤4), notes? }
 *   ]
 * }
 * Quy ước: title của slide nội dung là "action title" (một câu khẳng định kết luận, ≤ 110 ký tự).
 * Số liệu trong DeckSpec phải đã render từ FactsStore — builder KHÔNG tự tính hay sửa số.
 */
import pptxgen from 'pptxgenjs';

export const DEFAULT_THEME = {
  primary: '4F46E5', dark: '1E1B4B', accent: 'F59E0B', surface: 'F3F4F8',
  text: '1F2430', muted: '667085', positive: '0E9F6E', negative: 'D92D20',
  headFont: 'Cambria', bodyFont: 'Calibri', // đều có đủ dấu tiếng Việt, có sẵn trên Office
};
const W = 13.33, M = 0.6, CW = W - 2 * M;
const FMT = { number: '#,##0', percent: '0.0%', compact_vnd: '#,##0.0,,"tr"' };
const clip = (s, n) => (s && s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s || '');

/* ---------- Lint: bắt lỗi nội dung trước khi dựng ---------- */
export function lintDeck(spec) {
  const w = [];
  const n = spec.slides.length;
  if (n > 14) w.push(`Deck có ${n} slide (>14): cân nhắc chuyển bớt sang phụ lục.`);
  spec.slides.forEach((s, i) => {
    const at = `Slide ${i + 1} (${s.type})`;
    if (s.type !== 'title' && !s.title) w.push(`${at}: thiếu action title.`);
    if (s.title && s.title.length > 110) w.push(`${at}: title ${s.title.length} ký tự (>110), sẽ bị cắt.`);
    if (s.type === 'chart') {
      const c = s.chart || {};
      if (!c.labels?.length || !c.series?.length) w.push(`${at}: thiếu dữ liệu biểu đồ.`);
      if (['doughnut', 'pie'].includes(c.type) && c.labels?.length > 6) w.push(`${at}: ${c.labels.length} phần cho biểu đồ tròn (>6) — sẽ gộp phần nhỏ vào "Khác".`);
      if (['column', 'bar', 'stacked'].includes(c.type) && c.labels?.length > 12) w.push(`${at}: ${c.labels.length} nhóm (>12) — chỉ giữ top 10 + "Khác".`);
      if (!s.takeaway) w.push(`${at}: thiếu takeaway (biểu đồ không có thông điệp).`);
    }
    if (s.type === 'summary' && (s.points || []).some((p) => (p.text || '').length > 170)) w.push(`${at}: có ý dài >170 ký tự.`);
    if (!s.notes && s.type !== 'title') w.push(`${at}: thiếu speaker notes (nên ghi phương pháp, nguồn, giả định).`);
  });
  return w;
}

/* ---------- Dựng ---------- */
export async function buildDeck(spec, { out, outputType = 'nodebuffer' } = {}) {
  const T = { ...DEFAULT_THEME, ...(spec.theme || {}) };
  const meta = spec.meta || {};
  const pres = new pptxgen();
  pres.layout = 'LAYOUT_WIDE'; // 13.33 x 7.5
  pres.title = meta.title || 'Báo cáo'; pres.author = meta.author || '';
  const warnings = lintDeck(spec);

  pres.defineSlideMaster({ title: 'TITLE_DARK', background: { color: T.dark } });
  pres.defineSlideMaster({
    title: 'CONTENT', background: { color: 'FFFFFF' },
    objects: [
      { placeholder: { options: { name: 'title', type: 'title', x: M, y: 0.4, w: CW, h: 1.2, fontFace: T.headFont, fontSize: 28, bold: true, color: T.text, align: 'left', valign: 'top', margin: 0 }, text: '' } },
      { text: { text: meta.footer || meta.title || '', options: { x: M, y: 7.0, w: 9, h: 0.3, fontSize: 10, color: T.muted, fontFace: T.bodyFont, margin: 0 } } },
    ],
    slideNumber: { x: W - M - 0.6, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: T.muted, fontFace: T.bodyFont, align: 'right' },
  });

  const base = (s) => {
    const sl = pres.addSlide({ masterName: 'CONTENT' });
    sl.addText(clip(s.title, 110), { placeholder: 'title' });
    if (s.notes) sl.addNotes(s.notes);
    return sl;
  };
  const txt = (sl, text, o) => sl.addText(text, { fontFace: T.bodyFont, color: T.text, margin: 0, isTextBox: true, ...o });
  const card = (sl, x, y, w, h, fill = T.surface) => sl.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill, width: 0 }, rectRadius: 0.08 });
  const tone = (t) => (t === 'positive' ? T.positive : t === 'negative' ? T.negative : T.muted);
  const colX = (k, i, gap = 0.35) => { const w = (CW - gap * (k - 1)) / k; return { x: M + i * (w + gap), w }; };

  /* Slide tiêu đề */
  const ts = pres.addSlide({ masterName: 'TITLE_DARK' });
  txt(ts, clip(meta.title, 90), { x: 0.9, y: 2.3, w: W - 1.8, h: 1.8, fontFace: T.headFont, fontSize: 44, bold: true, color: 'FFFFFF', valign: 'bottom' });
  if (meta.subtitle) txt(ts, clip(meta.subtitle, 140), { x: 0.9, y: 4.25, w: W - 1.8, h: 0.9, fontSize: 20, color: 'C7C9F5', valign: 'top' });
  txt(ts, [meta.author, meta.date].filter(Boolean).join('  ·  '), { x: 0.9, y: 6.4, w: W - 1.8, h: 0.4, fontSize: 14, color: 'A5A8E8' });

  for (const s of spec.slides) {
    if (s.type === 'summary') {
      const sl = base(s);
      card(sl, M, 1.75, CW, 1.65, T.primary);
      txt(sl, clip(s.answer, 260), { x: M + 0.35, y: 1.75, w: CW - 0.7, h: 1.65, fontSize: 20, bold: true, color: 'FFFFFF', valign: 'middle' });
      const pts = (s.points || []).slice(0, 4);
      pts.forEach((p, i) => {
        const { x, w } = colX(pts.length, i);
        sl.addShape(pres.shapes.RECTANGLE, { x, y: 3.85, w, h: 0.05, fill: { color: T.accent }, line: { color: T.accent, width: 0 } });
        txt(sl, clip(p.head, 40), { x, y: 4.05, w, h: 0.45, fontSize: 18, bold: true, color: T.primary });
        txt(sl, clip(p.text, 170), { x, y: 4.55, w, h: 2.2, fontSize: 16, valign: 'top' });
      });
    } else if (s.type === 'kpi') {
      const sl = base(s);
      const ks = (s.kpis || []).slice(0, 4);
      ks.forEach((k, i) => {
        const { x, w } = colX(ks.length, i, 0.3);
        card(sl, x, 1.9, w, 2.5);
        txt(sl, clip(k.value, 14), { x: x + 0.3, y: 2.15, w: w - 0.6, h: 0.9, fontFace: T.headFont, fontSize: 40, bold: true, color: T.text, valign: 'middle' });
        txt(sl, clip(k.label, 48), { x: x + 0.3, y: 3.1, w: w - 0.6, h: 0.5, fontSize: 14, color: T.muted, valign: 'top' });
        if (k.delta) txt(sl, clip(k.delta, 40), { x: x + 0.3, y: 3.65, w: w - 0.6, h: 0.4, fontSize: 14, bold: true, color: tone(k.tone) });
      });
      if (s.takeaway) { card(sl, M, 4.85, CW, 1.5, 'EEF0FF'); txt(sl, clip(s.takeaway, 240), { x: M + 0.35, y: 4.85, w: CW - 0.7, h: 1.5, fontSize: 18, valign: 'middle' }); }
    } else if (s.type === 'chart') {
      const sl = base(s);
      addChart(pres, sl, s.chart || {}, T);
      const px = 9.0, pw = W - M - px;
      card(sl, px, 1.75, pw, 4.8, 'EEF0FF');
      txt(sl, clip(s.takeaway, 200), { x: px + 0.3, y: 1.95, w: pw - 0.6, h: 2.3, fontSize: 18, bold: true, color: T.primary, valign: 'top' });
      if (s.callouts?.length) txt(sl, s.callouts.slice(0, 3).map((c, i, a) => ({ text: clip(c, 90), options: { bullet: true, breakLine: i < a.length - 1 } })), { x: px + 0.3, y: 4.3, w: pw - 0.6, h: 2.1, fontSize: 14, valign: 'top', paraSpaceAfter: 6 });
      if (s.source) txt(sl, 'Nguồn: ' + clip(s.source, 120), { x: M, y: 6.65, w: 8.2, h: 0.3, fontSize: 10, color: T.muted });
    } else if (s.type === 'compare') {
      const sl = base(s);
      const cs = (s.columns || []).slice(0, 4);
      cs.forEach((c, i) => {
        const { x, w } = colX(cs.length, i, 0.3);
        card(sl, x, 1.75, w, 4.85);
        txt(sl, clip(c.head, 30), { x: x + 0.3, y: 1.95, w: w - 0.6, h: 0.5, fontSize: 18, bold: true });
        if (c.big) txt(sl, clip(c.big, 14), { x: x + 0.3, y: 2.5, w: w - 0.6, h: 0.9, fontFace: T.headFont, fontSize: 36, bold: true, color: T.primary, valign: 'middle' });
        if (c.bigLabel) txt(sl, clip(c.bigLabel, 40), { x: x + 0.3, y: 3.4, w: w - 0.6, h: 0.4, fontSize: 12, color: T.muted });
        txt(sl, (c.items || []).slice(0, 5).map((t, j, a) => ({ text: clip(t, 80), options: { bullet: true, breakLine: j < a.length - 1 } })), { x: x + 0.3, y: 3.95, w: w - 0.6, h: 2.5, fontSize: 14, valign: 'top', paraSpaceAfter: 6 });
      });
    } else if (s.type === 'actions' || s.type === 'table') {
      const isAct = s.type === 'actions';
      const header = isAct ? ['#', 'Hành động', 'Tác động', 'Nỗ lực', 'Theo dõi bằng', 'Khi nào'] : s.columns;
      const rows = isAct ? s.rows.map((r, i) => [String(i + 1), r.action, r.impact, r.effort, r.metric || '', r.when || '']) : s.rows;
      const widths = isAct ? [0.5, 4.6, 1.8, 1.3, 2.4, 1.5] : header.map(() => CW / header.length);
      const per = isAct ? 6 : 7;
      for (let p = 0; p * per < rows.length; p++) {
        const sl = base({ ...s, title: p ? `${s.title} (tiếp)` : s.title, notes: p ? null : s.notes });
        const hdr = header.map((h) => ({ text: h, options: { bold: true, color: 'FFFFFF', fill: { color: T.dark } } }));
        const body = rows.slice(p * per, (p + 1) * per).map((r, ri) => r.map((cell, ci) => {
          const lvl = isAct && ci === 3 ? s.rows[p * per + ri].effortLevel : null;
          return { text: clip(String(cell ?? ''), 90), options: { color: lvl ? (lvl === 1 ? T.positive : lvl === 3 ? T.negative : T.text) : T.text, bold: lvl != null || (isAct && ci === 2), fill: { color: ri % 2 ? T.surface : 'FFFFFF' } } };
        }));
        sl.addTable([hdr, ...body], { x: M, y: 1.75, w: CW, colW: widths, fontFace: T.bodyFont, fontSize: 14, border: { type: 'solid', pt: 0.5, color: 'E5E7EB' }, valign: 'middle', margin: [0.06, 0.1, 0.06, 0.1], rowH: 0.62 });
      }
    } else if (s.type === 'appendix') {
      const sl = base(s);
      const secs = (s.sections || []).slice(0, 4), cols = secs.length > 2 ? 2 : secs.length;
      secs.forEach((sec, i) => {
        const { x, w } = colX(cols, i % cols, 0.5), y = 1.75 + Math.floor(i / cols) * 2.55;
        txt(sl, clip(sec.head, 40), { x, y, w, h: 0.4, fontSize: 16, bold: true, color: T.primary });
        txt(sl, (sec.items || []).slice(0, 5).map((t, j, a) => ({ text: clip(t, 100), options: { bullet: true, breakLine: j < a.length - 1 } })), { x, y: y + 0.5, w, h: 1.9, fontSize: 14, valign: 'top', paraSpaceAfter: 4 });
      });
    } else warnings.push(`Loại slide không hỗ trợ: ${s.type}`);
  }

  const result = out ? await pres.writeFile({ fileName: out }) : await pres.write({ outputType });
  return { result, warnings };
}

/* ---------- Biểu đồ native (sửa được trong PowerPoint) ---------- */
function addChart(pres, sl, ch, T) {
  let labels = ch.labels || [], series = (ch.series || []).map((s) => ({ ...s, values: [...s.values] }));
  const single = series.length === 1;
  const limit = ['doughnut', 'pie'].includes(ch.type) ? 6 : ['column', 'bar', 'stacked'].includes(ch.type) ? 10 : Infinity;
  if (labels.length > limit + 1) { // top-N + "Khác"
    const order = labels.map((_, i) => i).sort((a, b) => series.reduce((s, x) => s + Math.abs(x.values[b]), 0) - series.reduce((s, x) => s + Math.abs(x.values[a]), 0));
    const keep = order.slice(0, limit).sort((a, b) => a - b), rest = order.slice(limit);
    series = series.map((s) => ({ ...s, values: [...keep.map((i) => s.values[i]), rest.reduce((t, i) => t + s.values[i], 0)] }));
    labels = [...keep.map((i) => labels[i]), 'Khác'];
  }
  const data = ch.type === 'scatter'
    ? [{ name: 'X', values: series[0].values }, ...series.slice(1).map((s) => ({ name: s.name, values: s.values }))]
    : series.map((s) => ({ name: s.name, labels, values: s.values }));
  // Không chỉ định format: số lớn (≥ 1 triệu) tự rút gọn để trục/nhãn không dài lê thê
  const maxAbs = Math.max(...series.flatMap((s) => s.values.map(Math.abs)), 0);
  const code = FMT[ch.format] || (maxAbs >= 1e6 ? FMT.compact_vnd : FMT.number);
  const o = {
    x: M, y: 1.75, w: 8.2, h: 4.8, showTitle: false, showLegend: series.length > 1 || ['doughnut', 'pie'].includes(ch.type), legendPos: 'b',
    legendFontFace: T.bodyFont, legendFontSize: 12, catAxisLabelFontFace: T.bodyFont, valAxisLabelFontFace: T.bodyFont,
    catAxisLabelFontSize: 12, valAxisLabelFontSize: 12, catAxisLabelColor: T.muted, valAxisLabelColor: T.muted,
    valGridLine: { color: 'E5E7EB', size: 0.5 }, catGridLine: { style: 'none' }, valAxisLabelFormatCode: code,
    dataLabelFontFace: T.bodyFont, dataLabelFontSize: 12, dataLabelColor: T.text, dataLabelFormatCode: code,
    chartColors: [T.primary, T.accent, T.positive, T.negative, '7C8DB5', 'A78BFA'],
  };
  const highlight = (n) => (single && ch.highlight?.length ? Array.from({ length: n }, (_, i) => (ch.highlight.includes(i) ? T.primary : 'B8BCD9')) : null);
  switch (ch.type) {
    case 'bar': sl.addChart(pres.charts.BAR, data, { ...o, barDir: 'bar', catAxisOrientation: 'maxMin', valAxisHidden: true, valGridLine: { style: 'none' }, barGapWidthPct: 40, showValue: true, dataLabelPosition: 'outEnd', chartColors: highlight(labels.length) || o.chartColors }); break;
    case 'stacked': sl.addChart(pres.charts.BAR, data, { ...o, barDir: 'col', barGrouping: 'stacked', barGapWidthPct: 50, showValue: false }); break;
    case 'line': sl.addChart(pres.charts.LINE, data, { ...o, lineSize: 3, lineDataSymbolSize: 7, showValue: labels.length <= 8, dataLabelPosition: 't' }); break;
    case 'area': sl.addChart(pres.charts.AREA, data, { ...o, showValue: false }); break;
    case 'doughnut': sl.addChart(pres.charts.DOUGHNUT, data, { ...o, holeSize: 58, showPercent: true, showValue: false, showLegend: true, legendPos: 'r', dataLabelColor: 'FFFFFF', dataLabelFormatCode: '0%' }); break;
    case 'pie': sl.addChart(pres.charts.PIE, data, { ...o, showPercent: true, showValue: false, showLegend: true, legendPos: 'r', dataLabelColor: 'FFFFFF', dataLabelFormatCode: '0%' }); break;
    case 'scatter': sl.addChart(pres.charts.SCATTER, data, { ...o, lineSize: 0, lineDataSymbolSize: 9, showLegend: false }); break;
    default: sl.addChart(pres.charts.BAR, data, { ...o, barDir: 'col', barGapWidthPct: 50, showValue: true, dataLabelPosition: 'outEnd', chartColors: highlight(labels.length) || o.chartColors });
  }
}
