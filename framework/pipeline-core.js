/**
 * pipeline-core.js — Hạ tầng chung cho hệ thống Agent phân tích dữ liệu (không gắn với dataset nào).
 *
 *  1. STAGES            : 7 bước + đầu vào/đầu ra/cổng qua bước
 *  2. extractJson/validate : đọc JSON từ LLM chắc chắn + kiểm schema
 *  3. FactsStore        : MỌI con số trong báo cáo/slide phải đến từ đây (LLM chỉ tham chiếu {{fact:id}})
 *  4. scopeCandidates / qualityReport / reconcile : cổng chất lượng & phạm vi, dùng cho mọi dataset
 *  5. runStage / safeRender : chạy bước có tự sửa; lỗi hiển thị được, không bao giờ "trắng màn hình"
 */
import { fmt, parseNumberLoose } from './chart-advisor.js';

/* ============ 1. Hợp đồng các bước ============ */
export const STAGES = [
  { id: 'context',  label: 'Dữ liệu và bối cảnh',     out: 'AnalysisPlan',   gate: 'Câu hỏi đã được phân rã thành câu hỏi con, có chỉ số đích + giả định ghi rõ' },
  { id: 'profile',  label: 'Kiểm tra và mô tả dữ liệu', out: 'DataProfile',   gate: 'Mỗi cột có vai trò + đơn vị; đã liệt kê phạm vi cần quyết định (scope)' },
  { id: 'clean',    label: 'Làm sạch dữ liệu',        out: 'CleaningLog',    gate: 'Mọi thao tác có số dòng ảnh hưởng, đảo ngược được; dòng vào/ra khớp' },
  { id: 'analyze',  label: 'Phân tích',               out: 'Findings+Facts', gate: 'Metric Contract được duyệt; tổng thành phần = tổng; mọi phát hiện có bằng chứng' },
  { id: 'act',      label: 'Phát hiện và hành động',  out: 'Actions',        gate: 'Mỗi hành động có quy mô tác động, độ chắc chắn, chỉ số theo dõi' },
  { id: 'report',   label: 'Báo cáo',                 out: 'Report',         gate: 'Trả lời câu hỏi trong 3 dòng đầu; mọi số liệu khớp Facts Store' },
  { id: 'export',   label: 'Duyệt và xuất file',      out: 'DeckSpec',       gate: 'Reviewer không còn lỗi mức "error"; lint deck sạch' },
];

/* ============ 2. JSON & schema ============ */
export function extractJson(text) {
  if (typeof text !== 'string') throw new Error('Phản hồi rỗng');
  const s = text.replace(/```(?:json)?/gi, '').trim();
  const start = s.search(/[{[]/);
  if (start < 0) throw new Error('Không tìm thấy JSON trong phản hồi');
  const open = s[start], close = open === '{' ? '}' : ']';
  let depth = 0, inStr = false, esc = false;
  for (let i = start; i < s.length; i++) {
    const ch = s[i];
    if (inStr) { if (esc) esc = false; else if (ch === '\\') esc = true; else if (ch === '"') inStr = false; continue; }
    if (ch === '"') inStr = true;
    else if (ch === open) depth++;
    else if (ch === close && --depth === 0) {
      const raw = s.slice(start, i + 1).replace(/,\s*([}\]])/g, '$1'); // bỏ dấu phẩy thừa
      return JSON.parse(raw);
    }
  }
  throw new Error('JSON bị cắt dở (có thể vượt max tokens)');
}

/** Schema con: type, required, properties, items, enum, minItems. Trả về mảng lỗi dạng chuỗi. */
export function validate(data, schema, path = '$') {
  const errs = [];
  const t = Array.isArray(data) ? 'array' : data === null ? 'null' : typeof data;
  if (schema.type && !(schema.type === t || (schema.type === 'integer' && Number.isInteger(data)))) return [`${path}: cần ${schema.type}, nhận ${t}`];
  if (schema.enum && !schema.enum.includes(data)) errs.push(`${path}: phải thuộc ${JSON.stringify(schema.enum)}`);
  if (t === 'object') {
    for (const k of schema.required || []) if (!(k in data)) errs.push(`${path}.${k}: bắt buộc`);
    for (const [k, sub] of Object.entries(schema.properties || {})) if (k in data) errs.push(...validate(data[k], sub, `${path}.${k}`));
  }
  if (t === 'array') {
    if (schema.minItems && data.length < schema.minItems) errs.push(`${path}: cần ≥ ${schema.minItems} phần tử`);
    if (schema.items) data.forEach((x, i) => errs.push(...validate(x, schema.items, `${path}[${i}]`)));
  }
  return errs;
}

/* ============ 3. Facts Store: nguồn sự thật duy nhất của mọi con số ============ */
const UNIT_FMT = {
  currency: (v, mod) => (mod === 'compact' ? fmt.compact(v) + ' đ' : fmt.currency(v)),
  percent: (v) => fmt.percent(v),            // lưu dạng tỷ lệ 0–1
  count: (v) => fmt.number(v),
  number: (v, mod) => (mod === 'compact' ? fmt.compact(v) : fmt.number(v, Math.abs(v) < 100 ? 1 : 0)),
  days: (v) => `${fmt.number(v, 1)} ngày`,
};
const NUM_RE = /(\d{1,3}(?:[.,]\d{3})+(?!\d)|\d+(?:[.,]\d+)?)\s*(%|tỷ|triệu|tr|nghìn|ngàn|k)?(?![\p{L}\d])/giu;
const SCALE = { tỷ: 1e9, triệu: 1e6, tr: 1e6, nghìn: 1e3, ngàn: 1e3, k: 1e3 };

export class FactsStore {
  constructor() { this.map = new Map(); }
  add({ id, label, value, unit = 'number', formula = '', source = '', confidence = 'high' }) {
    if (!id || this.map.has(id)) throw new Error(`Fact id trống hoặc trùng: ${id}`);
    if (!Number.isFinite(value)) throw new Error(`Fact "${id}" không phải số hữu hạn`);
    this.map.set(id, { id, label, value, unit, formula, source, confidence });
    return id;
  }
  get(id) { return this.map.get(id); }
  all() { return [...this.map.values()]; }
  format(id, mod) { const f = this.get(id); if (!f) throw new Error(`Không có fact "${id}"`); return (UNIT_FMT[f.unit] || UNIT_FMT.number)(f.value, mod); }
  /** Thay {{fact:id}} hoặc {{fact:id|compact}} bằng số đã định dạng. Id lạ -> lỗi rõ ràng (không bao giờ im lặng). */
  render(text) { return text.replace(/\{\{\s*fact:([\w.-]+)(?:\|(\w+))?\s*\}\}/g, (_, id, mod) => this.format(id, mod)); }
  /** Đối chiếu số viết tay trong văn bản với Facts. Heuristic: bỏ qua số nguyên nhỏ ≤ 12 và năm. */
  verify(text, { ignoreSmallInts = 12 } = {}) {
    const unmatched = [];
    for (const m of text.matchAll(NUM_RE)) {
      const raw = m[1], unit = m[2] ? m[2].toLowerCase() : '';
      let v = parseNumberLoose(raw); if (v === null) continue;
      const decimals = (String(v).split('.')[1] || '').length;
      if (!unit && Number.isInteger(v) && (Math.abs(v) <= ignoreSmallInts || (v >= 1990 && v <= 2100))) continue;
      let tol; // sai số = nửa đơn vị của chữ số cuối được hiển thị
      if (unit === '%') { v /= 100; tol = (0.5 * 10 ** -decimals) / 100 * 1.01; }
      else if (SCALE[unit]) { const s = SCALE[unit]; v *= s; tol = 0.5 * 10 ** -decimals * s * 1.01; }
      else tol = Math.max(0.5 * 10 ** -decimals, Math.abs(v) * 1e-9);
      const hit = this.all().some((f) => Math.abs(Math.abs(f.value) - Math.abs(v)) <= tol + 1e-9);
      if (!hit) unmatched.push(m[0].trim());
    }
    return { ok: unmatched.length === 0, unmatched };
  }
}

/* ============ 4. Cổng chất lượng & phạm vi (generic) ============ */
/**
 * Cột nào quyết định "bản ghi nào được tính" cho chỉ số? (loại giao dịch, trạng thái, kênh, đơn vị tiền...)
 * Agent phải CHỌN include/exclude có lý do cho từng giá trị — không được cộng toàn bộ mặc định.
 * Đây là phòng ngừa lỗi kinh điển: tổng bị lẫn nhóm bản ghi không thuộc phạm vi câu hỏi.
 */
export function scopeCandidates(profile) {
  const out = [];
  for (const c of Object.values(profile.columns)) {
    if (c.role === 'dimension' && c.distinct >= 2 && c.distinct <= 12) {
      const nameHint = /(loại|type|kind|direction|status|trạng thái|nhóm|category|channel|kênh|hình thức|phân loại)/i.test(c.name);
      out.push({ column: c.name, kind: 'discriminator', priority: nameHint ? 'high' : 'normal', values: c.topValues, needsDecision: true });
    }
    if (c.role === 'measure' && c.hasNeg && c.hasPos) out.push({ column: c.name, kind: 'mixed_sign', priority: 'high', note: 'Có cả giá trị âm và dương: xác nhận quy ước dấu và có cộng gộp được không.', needsDecision: true });
  }
  return out.sort((a, b) => (a.priority === 'high' ? -1 : 1) - (b.priority === 'high' ? -1 : 1));
}

export function duplicateShare(rows) {
  const seen = new Set(); let dup = 0;
  for (const r of rows) { const k = JSON.stringify(r); if (seen.has(k)) dup++; else seen.add(k); }
  return rows.length ? dup / rows.length : 0;
}

/** usedColumns: các cột thực sự dùng trong phân tích. Cột thiếu ≥ 50% => blocker cho mọi biểu đồ/nhận định dựa vào nó. */
export function qualityReport(profile, { usedColumns = null, rows = null } = {}) {
  const issues = [];
  for (const c of Object.values(profile.columns)) {
    if (usedColumns && !usedColumns.includes(c.name)) continue;
    if (c.nullRatio >= 0.5) issues.push({ level: 'blocker', column: c.name, msg: `Thiếu ${fmt.percent(c.nullRatio, 0)} giá trị` });
    else if (c.nullRatio >= 0.2) issues.push({ level: 'warn', column: c.name, msg: `Thiếu ${fmt.percent(c.nullRatio, 0)} giá trị` });
    if (c.outlierShare > 0.05) issues.push({ level: 'warn', column: c.name, msg: `${fmt.percent(c.outlierShare, 0)} giá trị ngoại lai (IQR) — kiểm tra trước khi loại` });
    if (c.type === 'date' && c.lastMonthCoverage < 1) issues.push({ level: 'warn', column: c.name, msg: `Kỳ cuối chưa đủ (${fmt.percent(c.lastMonthCoverage, 0)} số ngày của tháng)` });
  }
  if (rows) { const d = duplicateShare(rows); if (d > 0.01) issues.push({ level: d > 0.1 ? 'blocker' : 'warn', column: '*', msg: `${fmt.percent(d)} dòng trùng lặp hoàn toàn` }); }
  const score = Math.max(0, 100 - issues.reduce((s, i) => s + (i.level === 'blocker' ? 25 : 8), 0));
  return { score, issues, blockers: issues.filter((i) => i.level === 'blocker') };
}

/** Kiểm tra phần tử cộng lại bằng tổng (cùng 1 chỉ số, 2 cách chia). */
export function reconcile(parts, total, tolRel = 1e-3) {
  const sum = parts.reduce((a, b) => a + b, 0);
  const diff = sum - total;
  return { ok: Math.abs(diff) <= Math.abs(total) * tolRel, sum, total, diff };
}

/* ============ 5. Chạy bước & render an toàn ============ */
export function diagnose(e) {
  const d = { name: e.name || 'Error', message: e.message || String(e), stack: e.stack, hint: null };
  const m = /(\S+) is not defined/.exec(d.message);
  if (m) {
    d.hint = `"${m[1]}" được dùng nhưng chưa khai báo/import trong phạm vi của bước này. Kiểm tra: ` +
      `(1) tìm nơi định nghĩa "${m[1]}" (grep); (2) thứ tự nạp script/import có đặt nó trước khi bước chạy không; ` +
      `(3) bước có chạy trong iframe/Function/Worker (không thừa hưởng biến toàn cục) không; (4) sai hoa/thường hoặc đổi tên khi refactor.`;
  }
  return d;
}

/**
 * Chạy 1 bước: run(ctx, feedback) -> output. Kiểm schema + cổng; nếu sai, đưa lỗi cho chính agent tự sửa (tối đa maxRepairs).
 * gates: [(output, ctx) => ({ errors:[], warnings:[] }) | string[]]
 * Trạng thái trả về là NGUỒN DUY NHẤT để UI vẽ dấu ✓/⚠/✕ — không vẽ ✓ chỉ vì đã "đi qua" bước.
 */
export async function runStage({ id, run, schema, gates = [], maxRepairs = 2 }, ctx = {}) {
  let feedback = null, warnings = [];
  for (let attempt = 0; ; attempt++) {
    try {
      const output = await run(ctx, feedback);
      const errors = schema ? validate(output, schema) : [];
      warnings = [];
      for (const g of gates) {
        const r = g(output, ctx) || [];
        if (Array.isArray(r)) errors.push(...r); else { errors.push(...(r.errors || [])); warnings.push(...(r.warnings || [])); }
      }
      if (!errors.length) return { stage: id, status: warnings.length ? 'ok_with_warnings' : 'ok', output, warnings, attempts: attempt + 1 };
      if (attempt >= maxRepairs) return { stage: id, status: 'failed_validation', output, errors, warnings, attempts: attempt + 1 };
      feedback = errors;
    } catch (e) {
      return { stage: id, status: 'error', error: diagnose(e), attempts: attempt + 1 };
    }
  }
}

/**
 * Bọc hàm render của một bước. Lỗi -> trả diagnostics + phương án hiển thị thay thế, KHÔNG làm vỡ các bước khác.
 * requires: tên biến toàn cục bắt buộc phải có (kiểm trước khi render để báo lỗi sớm, rõ nguyên nhân).
 */
export function safeRender(stageId, renderFn, { requires = [], onError = console.error } = {}) {
  try {
    const missing = requires.filter((n) => typeof globalThis[n] === 'undefined');
    if (missing.length) throw new ReferenceError(`${missing[0]} is not defined`);
    return { ok: true, view: renderFn() };
  } catch (e) {
    const diagnostics = diagnose(e);
    onError(`[step:${stageId}]`, e);
    return {
      ok: false, diagnostics,
      // UI nên hiện: thông báo thân thiện + [Xem dữ liệu thô] [Thử lại] [Sao chép chẩn đoán]; kết quả bước vẫn dùng tiếp được.
      fallback: ['show-raw-output', 'retry', 'copy-diagnostics'],
    };
  }
}
