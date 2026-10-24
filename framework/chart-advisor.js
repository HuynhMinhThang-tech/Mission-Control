/**
 * chart-advisor.js — Chọn biểu đồ theo (câu hỏi × hình dạng dữ liệu), không theo bộ dữ liệu cụ thể.
 *
 * Luồng:  rows ──profileDataset──▶ profile
 *         (intent, measure, dimension, time) ──recommendCharts──▶ { primary, alternatives, blocked, rationale }
 *         nhiều câu hỏi con ──composeBoard──▶ { hero, supporting, dropped }
 *
 * Output là ChartSpec thuần khai báo (không gắn thư viện) -> map sang ECharts / Chart.js / Recharts / Vega-Lite.
 */

/* ===================== Định dạng số/ngày thống nhất (vi-VN) ===================== */
const nf = (d) => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: d });
export const fmt = {
  number: (n, d = 0) => nf(d).format(n),
  /** 1_250_000 -> "1,25 tr"  |  9_001_000 -> "9 tr"  |  1.2e9 -> "1,2 tỷ" */
  compact(n, { digits } = {}) {
    const a = Math.abs(n);
    const [v, u] = a >= 1e9 ? [n / 1e9, ' tỷ'] : a >= 1e6 ? [n / 1e6, ' tr'] : a >= 1e3 ? [n / 1e3, ' nghìn'] : [n, ''];
    const d = digits ?? (Math.abs(v) < 10 && u ? 2 : Math.abs(v) < 100 && u ? 1 : 0);
    return nf(d).format(v) + u;
  },
  currency: (n, sym = 'đ') => `${nf(0).format(n)} ${sym}`,
  percent: (ratio, d = 1) => `${nf(d).format(ratio * 100)}%`,
  delta(n, f = (x) => fmt.number(x)) { return `${n > 0 ? '+' : n < 0 ? '−' : ''}${f(Math.abs(n))}`; },
  date(d, gran = 'day') {
    const dt = d instanceof Date ? d : new Date(d); const p = (x) => String(x).padStart(2, '0');
    return gran === 'month' ? `${p(dt.getUTCMonth() + 1)}/${dt.getUTCFullYear()}` : gran === 'year' ? `${dt.getUTCFullYear()}` : `${p(dt.getUTCDate())}/${p(dt.getUTCMonth() + 1)}`;
  },
};

/* ===================== Parse "lỏng" cho dữ liệu thực tế ===================== */
const MISSING = new Set(['', 'null', 'undefined', 'nan', 'n/a', 'na', '-', '--', '(thiếu)', 'thiếu', 'unknown', '(blank)', 'none']);
export const isMissing = (v) => v === null || v === undefined || (typeof v === 'number' && Number.isNaN(v)) || MISSING.has(String(v).trim().toLowerCase());

/** Hiểu "1.234.567", "1,234.56", "12,5%", "(1.200)", "-3 000 000 đ" ... Trả về number|null */
export function parseNumberLoose(v) {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (v == null) return null;
  let s = String(v).trim().replace(/[\s\u00a0₫đ$€£%]|vnd|vnđ|usd/gi, '');
  let neg = false;
  if (/^\(.*\)$/.test(s)) { neg = true; s = s.slice(1, -1); }
  if (s[0] === '-' || s[0] === '−') { neg = !neg; s = s.slice(1); }
  if (!/^[\d.,]+$/.test(s) || !/\d/.test(s)) return null;
  const dots = (s.match(/\./g) || []).length, commas = (s.match(/,/g) || []).length;
  let out = s;
  if (dots && commas) out = s.lastIndexOf('.') > s.lastIndexOf(',') ? s.replace(/,/g, '') : s.replace(/\./g, '').replace(',', '.');
  else if (dots > 1) out = s.replace(/\./g, '');
  else if (commas > 1) out = s.replace(/,/g, '');
  else if (dots === 1) out = /^\d{1,3}\.\d{3}$/.test(s) && !/^0\./.test(s) ? s.replace('.', '') : s;
  else if (commas === 1) out = /^\d{1,3},\d{3}$/.test(s) ? s.replace(',', '') : s.replace(',', '.');
  const n = Number(out);
  return Number.isFinite(n) ? (neg ? -n : n) : null;
}

/** ISO, dd/mm/yyyy (mặc định VN), dd-mm-yyyy, yyyy/mm/dd. Trả về Date(UTC)|null */
export function parseDateLoose(v) {
  if (v instanceof Date) return Number.isNaN(+v) ? null : v;
  if (typeof v !== 'string') return null;
  const s = v.trim(); let y, m, d, x;
  if ((x = s.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[T\s].*)?$/))) [y, m, d] = [+x[1], +x[2], +x[3]];
  else if ((x = s.match(/^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$/))) [d, m, y] = [+x[1], +x[2], +x[3] < 100 ? 2000 + +x[3] : +x[3]];
  else return null;
  if (m < 1 || m > 12 || d < 1 || d > 31) return null;
  const dt = new Date(Date.UTC(y, m - 1, d));
  return dt.getUTCMonth() === m - 1 ? dt : null;
}

/* ===================== Profiler tất định (code tính, không để LLM tính) ===================== */
const q = (sorted, p) => sorted[Math.min(sorted.length - 1, Math.floor(p * (sorted.length - 1)))];

export function profileDataset(rows) {
  const n = rows.length;
  const names = [...new Set(rows.slice(0, 2000).flatMap((r) => Object.keys(r)))];
  const columns = {};
  for (const name of names) {
    const present = rows.map((r) => r[name]).filter((v) => !isMissing(v));
    const nullRatio = n ? 1 - present.length / n : 0;
    const strs = present.map((v) => String(v).trim());
    const distinct = new Set(strs).size;
    const dates = present.map(parseDateLoose).filter(Boolean);
    const nums = present.map(parseNumberLoose).filter((x) => x !== null);
    const boolish = present.length && distinct <= 2 && strs.every((s) => /^(true|false|yes|no|có|không|0|1)$/i.test(s));
    let type = 'string';
    if (!present.length) type = 'empty';
    else if (dates.length / present.length >= 0.9) type = 'date';
    else if (boolish) type = 'boolean';
    else if (nums.length / present.length >= 0.9) type = 'number';

    const col = { name, type, nullRatio, distinct, present: present.length };
    const idName = /(^id$|_id$|\bid\b|^stt$|^mã\b|uuid)/i.test(name);

    if (type === 'number') {
      const s = nums.slice().sort((a, b) => a - b);
      const mean = s.reduce((a, b) => a + b, 0) / s.length;
      const sd = Math.sqrt(s.reduce((a, b) => a + (b - mean) ** 2, 0) / s.length) || 0;
      const q1 = q(s, 0.25), q3 = q(s, 0.75), iqr = q3 - q1;
      Object.assign(col, {
        min: s[0], max: s[s.length - 1], mean, median: q(s, 0.5), sd, q1, q3, p95: q(s, 0.95),
        hasNeg: s[0] < 0, hasPos: s[s.length - 1] > 0,
        outlierShare: iqr > 0 ? s.filter((x) => x < q1 - 1.5 * iqr || x > q3 + 1.5 * iqr).length / s.length : 0,
        skew: sd ? (mean - q(s, 0.5)) / sd : 0,
        maybeCategorical: s.every(Number.isInteger) && distinct <= 8 && n > 30,
      });
      // ID thật = tên gợi ý, hoặc dãy số nguyên gần liên tiếp (1,2,3...). Số tiền/số lượng khác nhau hết KHÔNG phải ID.
      const seq = s.every(Number.isInteger) && distinct / present.length > 0.98 && present.length > 20 && (s[s.length - 1] - s[0]) <= present.length * 1.2;
      col.role = idName || seq ? 'id' : 'measure';
    } else if (type === 'date') {
      const ts = [...new Set(dates.map((d) => +d))].sort((a, b) => a - b);
      const gaps = ts.slice(1).map((t, i) => (t - ts[i]) / 864e5).sort((a, b) => a - b);
      const med = gaps.length ? gaps[Math.floor(gaps.length / 2)] : 0;
      const last = new Date(ts[ts.length - 1]);
      const dim = new Date(Date.UTC(last.getUTCFullYear(), last.getUTCMonth() + 1, 0)).getUTCDate();
      Object.assign(col, {
        role: 'time', min: new Date(ts[0]), max: last, distinctPeriods: ts.length,
        granularity: med <= 1.5 ? 'day' : med <= 8 ? 'week' : med <= 40 ? 'month' : 'year',
        lastMonthCoverage: last.getUTCDate() / dim, // < 1 => tháng cuối chưa đủ ngày
      });
    } else if (type === 'boolean') col.role = 'flag';
    else if (type === 'string') {
      const avgLen = strs.reduce((a, s) => a + s.length, 0) / (strs.length || 1);
      col.avgLen = avgLen;
      col.role = idName || (distinct / present.length > 0.9 && present.length > 20) ? 'id' : avgLen > 40 ? 'text' : distinct <= 50 || distinct / present.length < 0.2 ? 'dimension' : 'dimension_high';
      if (col.role === 'dimension') {
        const cnt = new Map(); strs.forEach((s) => cnt.set(s, (cnt.get(s) || 0) + 1));
        col.topValues = [...cnt].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([value, count]) => ({ value, count, share: count / present.length }));
      }
    }
    columns[name] = col;
  }
  return { rowCount: n, columns };
}

/* ===================== Ý định (intent) ===================== */
export const INTENTS = ['trend', 'ranking', 'composition', 'distribution', 'relationship', 'deviation', 'comparison'];

export function inferIntent({ question = '', time, dimension, measure, measure2 } = {}) {
  const t = question.toLowerCase();
  const rules = [
    ['trend', /xu hướng|theo thời gian|diễn biến|tăng trưởng|mùa vụ|trend|over time|theo (ngày|tuần|tháng|quý|năm)/],
    ['composition', /cơ cấu|tỷ trọng|tỉ trọng|chiếm|share|composition|mix/],
    ['relationship', /tương quan|liên hệ|ảnh hưởng|quan hệ|correlation|relationship|driver/],
    ['distribution', /phân phối|phân bố|phân tán|bất thường|ngoại lai|distribution|outlier/],
    ['deviation', /mục tiêu|kế hoạch|ngân sách|chênh lệch|vượt|target|budget|variance|plan/],
    ['ranking', /xếp hạng|\btop\b|cao nhất|thấp nhất|lớn nhất|nhiều nhất|ít nhất|rank|best|worst/],
    ['comparison', /so sánh|khác biệt|compare|versus|\bvs\b/],
  ];
  const hit = rules.find(([, re]) => re.test(t));
  if (hit) return hit[0];
  if (time && measure) return 'trend';
  if (measure && measure2) return 'relationship';
  if (dimension && measure) return 'ranking';
  return 'distribution';
}

/* ===================== Bộ gợi ý biểu đồ ===================== */
export function recommendCharts({ profile, intent, question, measure, measure2, dimension, series, time } = {}) {
  const C = (n) => (n && profile.columns[n]) || null;
  const cd = C(dimension), cm = C(measure), ct = C(time);
  const card = cd ? cd.distinct : 0;
  const pts = ct ? ct.distinctPeriods : 0;
  const it = intent || inferIntent({ question, time, dimension, measure, measure2 });
  const cands = [];
  const add = (type, score, why, encoding, extra = {}) => cands.push({ type, score, why, encoding, ...extra });
  const longLabels = (cd?.avgLen ?? 0) > 14;

  switch (it) {
    case 'trend':
      if (pts >= 4) add('line', 0.95, 'Chuỗi thời gian từ 4 điểm trở lên: đường cho thấy xu hướng rõ nhất.', { x: time, y: measure, color: series });
      add('column', pts && pts < 4 ? 0.92 : pts <= 24 ? 0.7 : 0.4, 'Cột dễ so sánh từng kỳ khi số kỳ ít.', { x: time, y: measure, color: series });
      if (pts >= 4) add('area', 0.5, 'Nhấn mạnh quy mô tích luỹ theo thời gian.', { x: time, y: measure });
      if (series && C(series)?.distinct > 5) add('small_multiples', 0.8, 'Nhiều chuỗi (>5): tách thành lưới nhỏ thay vì chồng đường.', { x: time, y: measure, facet: series });
      break;
    case 'ranking':
    case 'comparison':
      add('bar', longLabels || card > 6 ? 0.95 : 0.85, 'Thanh ngang, sắp xếp giảm dần: nhãn dài đọc dễ, so sánh độ dài chính xác.', { x: measure, y: dimension }, { transform: { sort: 'desc', topN: 10, otherLabel: 'Khác' } });
      if (card <= 7) add('column', 0.7, 'Ít nhóm: cột đứng vẫn rõ.', { x: dimension, y: measure }, { transform: { sort: 'desc' } });
      if (card > 8) add('pareto', 0.8, 'Nhiều nhóm: Pareto cho thấy nhóm nào tạo ra phần lớn tổng (quy tắc 80/20).', { x: dimension, y: measure, line: 'cumulative_share' }, { transform: { sort: 'desc', topN: 15 } });
      if (measure2) add('grouped_bar', 0.75, 'Hai chỉ số trên cùng nhóm.', { x: dimension, y: [measure, measure2] });
      break;
    case 'composition':
      if (card && card <= 5) add('donut', 0.8, 'Tối đa 5 phần: donut đủ rõ tỷ trọng.', { value: measure, color: dimension });
      if (card && card <= 5) add('stacked_100', 0.75, 'Thanh chồng 100% so sánh cơ cấu giữa các nhóm.', { x: series || dimension, y: measure, color: dimension });
      add('bar', card > 5 ? 0.9 : 0.7, 'Từ 6 phần trở lên: thanh ngang chính xác hơn tròn/donut.', { x: measure, y: dimension }, { transform: { sort: 'desc', topN: 10, otherLabel: 'Khác', asShare: true } });
      if (card >= 8) add('treemap', 0.6, 'Nhiều phần và có phân cấp: treemap tận dụng diện tích.', { size: measure, group: dimension });
      break;
    case 'distribution':
      add('histogram', 0.9, 'Xem hình dạng phân phối và độ lệch.', { x: measure }, { transform: { bins: 'freedman-diaconis' } });
      if (dimension) add('boxplot', 0.85, 'So sánh phân phối giữa các nhóm, thấy ngoại lai.', { x: dimension, y: measure });
      break;
    case 'relationship':
      add('scatter', 0.92, 'Hai biến số: scatter cho thấy tương quan và ngoại lai.', { x: measure, y: measure2, color: dimension }, { transform: { aggregateAbove: 2000 } });
      if (dimension) add('bubble', 0.6, 'Thêm biến thứ ba bằng kích thước điểm.', { x: measure, y: measure2, size: measure2, color: dimension });
      break;
    case 'deviation':
      add('bullet', 0.88, 'So thực tế với mục tiêu/ngưỡng trên cùng một thang.', { x: dimension, y: measure, target: measure2 });
      add('waterfall', 0.8, 'Giải thích từ giá trị A sang B qua từng yếu tố đóng góp.', { x: dimension, y: measure });
      add('diverging_bar', 0.75, 'Chênh lệch dương/âm quanh mức tham chiếu.', { x: measure, y: dimension });
      break;
    default:
      add('table', 0.5, 'Không đủ tín hiệu để chọn biểu đồ.', {});
  }
  if (dimension && time && measure && !['trend'].includes(it)) add('heatmap', 0.55, 'Hai chiều rời rạc × một chỉ số: nhìn ra mẫu hình lặp lại.', { x: time, y: dimension, color: measure });

  /* ---- Lớp bảo vệ chất lượng: áp cho MỌI biểu đồ, không phụ thuộc dữ liệu ---- */
  const blocked = [];
  for (const c of cands) {
    c.warnings = c.warnings || [];
    if (cd && cd.nullRatio >= 0.5 && ['donut', 'stacked_100', 'treemap', 'bar', 'pareto', 'column'].includes(c.type) && ['composition', 'ranking', 'comparison'].includes(it)) {
      c.blocked = `Cột "${dimension}" thiếu ${fmt.percent(cd.nullRatio, 0)} giá trị — biểu đồ ${it === 'composition' ? 'cơ cấu' : 'xếp hạng'} sẽ gây hiểu lầm. Hiển thị cảnh báo chất lượng dữ liệu, kèm đề xuất bổ sung/phân loại.`;
    } else if (cd && cd.nullRatio >= 0.2) c.warnings.push(`Cột "${dimension}" thiếu ${fmt.percent(cd.nullRatio, 0)} — ghi chú rõ phần "chưa phân loại".`);
    if (cm?.hasNeg && cm?.hasPos) c.warnings.push(`"${measure}" có cả giá trị âm và dương — xác nhận phạm vi (loại bản ghi nào được cộng) trước khi tổng hợp.`);
    if (cm?.hasNeg && ['donut', 'treemap', 'stacked_100'].includes(c.type)) c.blocked = c.blocked || 'Có giá trị âm: không dùng biểu đồ phần-trên-tổng.';
    if (ct && ct.lastMonthCoverage < 1 && ['line', 'column', 'area'].includes(c.type)) {
      c.warnings.push(`Kỳ cuối chỉ có ${fmt.percent(ct.lastMonthCoverage, 0)} số ngày — vẽ đoạn cuối nét đứt và không so sánh trực tiếp với kỳ đủ.`);
      c.annotations = [{ type: 'partial_period', at: ct.max }];
    }
    if (card > 8 && c.type === 'donut') c.score *= 0.3;
    if (cd?.avgLen > 14) c.truncate = { maxChars: 22, tooltip: true }; // cắt nhãn dài + tooltip đầy đủ, không để mất chữ lặng lẽ
    if (c.type === 'line' && pts && pts < 3) c.blocked = 'Dưới 3 điểm: không vẽ đường.';
  }
  const ok = cands.filter((c) => !c.blocked).sort((a, b) => b.score - a.score);
  blocked.push(...cands.filter((c) => c.blocked));
  return {
    intent: it, primary: ok[0] || null, alternatives: ok.slice(1, 4),
    blocked, rationale: ok[0] ? ok[0].why : (blocked[0]?.blocked || 'Không có biểu đồ phù hợp.'),
  };
}

/* ===================== Dựng bảng biểu đồ từ Kế hoạch phân tích ===================== */
/**
 * items = [{ id, question, intent?, measure, dimension?, time?, measure2?, priority (1 = hero) }]
 * Mỗi biểu đồ PHẢI gắn với một câu hỏi con; không có "bộ biểu đồ mặc định".
 */
export function composeBoard(items, profile, { max = 5 } = {}) {
  const seen = new Set(), chosen = [], dropped = [];
  for (const it of [...items].sort((a, b) => (a.priority ?? 9) - (b.priority ?? 9))) {
    const rec = recommendCharts({ profile, ...it });
    const key = rec.primary ? `${rec.primary.type}|${it.measure}|${it.dimension}|${it.time}` : null;
    if (!rec.primary) dropped.push({ id: it.id, reason: rec.rationale, blocked: rec.blocked });
    else if (seen.has(key)) dropped.push({ id: it.id, reason: 'Trùng biểu đồ đã có.' });
    else if (chosen.length >= max) dropped.push({ id: it.id, reason: `Vượt giới hạn ${max} biểu đồ/bảng — đưa vào phụ lục.` });
    else { seen.add(key); chosen.push({ ...it, rec }); }
  }
  return { hero: chosen[0] || null, supporting: chosen.slice(1), dropped };
}
