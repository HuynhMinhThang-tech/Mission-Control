/* Bảng điều khiển tương tác. Bố cục do hệ thống tự chọn theo dữ liệu (không có ô chọn trên từng biểu đồ);
   người xem chỉ dùng: bộ lọc chung, chọn chỉ số, và bấm vào biểu đồ để lọc chéo. Mọi phép tính chạy trong trình duyệt. */
(function () {
  'use strict';
  const D = JSON.parse(document.getElementById('data').textContent);
  const $ = (s, r = document) => r.querySelector(s);
  const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const PAL = ['#4F46E5', '#06B6D4', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'];
  /* QUY TẮC SỐ (giống app/utils.py và static/js/fmt.js; sửa ở đâu thì sửa cả ba):
     nguyên 1.234.567 · lẻ 1.234,50 (luôn 2 chữ số) · tỷ lệ 54,20% · tiền ghi ĐỦ số kèm đơn vị của dữ liệu (1.234.567 đ), không viết tắt nghìn/triệu/tỷ,
     và KHÔNG có phần thập phân (3.724.488.031,25 đ hiện là 3.724.488.031 đ). Chỉ tiền bị bỏ phần thập phân; số lẻ khác (kg, điểm, trung bình) giữ 2 chữ số. */
  const mkf = d => new Intl.NumberFormat('vi-VN', { minimumFractionDigits: d, maximumFractionDigits: d });
  const f0 = mkf(0), f2 = mkf(2);
  const ok = v => v != null && v !== '' && typeof v !== 'boolean' && isFinite(+v), isInt = x => Math.abs(x - Math.round(x)) < 1e-9;
  const num = v => !ok(v) ? '—' : isInt(+v) ? f0.format(Math.round(+v)) : f2.format(+v);
  const isMoney = u => /^(đ|đồng|vnd|vnđ|₫)$/i.test(String(u ?? '').trim());
  const nu = (v, u) => !ok(v) ? '—' : isMoney(u) ? f0.format(+v) : num(v);                    // số theo đơn vị: tiền thì nguyên đồng (Intl làm tròn nửa ra xa số 0, giống Python)
  const compact = num;                                                                     // tên cũ, nay KHÔNG còn rút gọn
  const pctv = x => ok(x) ? f2.format(+x) + '%' : '—';                                     // x theo đơn vị %
  const pct = x => ok(x) ? f2.format(+x * 100) + '%' : '—';                                // x là tỷ lệ 0..1
  const val = (v, u) => u === '@rate' ? pct(v) : u === '%' ? pctv(v) : !ok(v) ? '—' : isMoney(u) ? f0.format(+v) + ' đ' : u ? num(v) + ' ' + u : num(v);        // '@rate': chỉ số tỷ lệ (0..1) hiện dạng %
  const full = (v, m) => !ok(v) ? '' : m && m.rate ? pct(v) : m && m.unit === '%' ? pctv(v) : nu(v, m && m.unit);
  const fv = (v, m, a) => a === 'count' ? f0.format(v) : (m && m.rate ? pct(v) : m && m.unit === '%' ? pctv(v) : nu(v, m && m.unit));          // giá trị trên trục / đầu cột
  const colFmt = (vs, u) => isMoney(u) ? (v => ok(v) ? f0.format(+v) : '') : vs.some(v => ok(v) && !isInt(+v)) ? (v => ok(v) ? f2.format(+v) : '') : (v => ok(v) ? f0.format(Math.round(+v)) : '');
  const ml = s => { const p = String(s).split('-'); return p.length === 2 && /^\d{4}$/.test(p[0]) ? 'T' + (+p[1]) + '/' + p[0] : s };
  const lc = s => s.charAt(0).toLowerCase() + s.slice(1);
  const stripTong = s => s.replace(/^tổng\s+/i, '');
  const mName = (m, a) => !m ? 'Số bản ghi' : m.rate ? m.label : a === 'avg' ? (/^trung bình/i.test(m.label) ? m.label : 'Trung bình ' + lc(stripTong(m.label)))
    : (/^(tổng|số)(?=\s|$)/i.test(m.label) ? m.label : 'Tổng ' + lc(m.label));
  const I = { moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>',
    print: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="7" rx="1"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>' };

  let ds, C, V, L, NA, M, st, P, openK = new Set(), jobs = [];

  function init(i) {
    if ($('#fb')) $('#app').innerHTML = '';
    ds = D.datasets[i]; C = {}; V = {}; L = {}; NA = {}; M = {};
    ds.dims.forEach(d => { C[d.k] = d.codes; V[d.k] = d.vals; L[d.k] = d.label; NA[d.k] = d.na });
    if (ds.time) { C.t = ds.time.codes; V.t = ds.time.vals; L.t = ds.time.label; NA.t = -1 }
    ds.meas.forEach(m => M[m.k] = m.vals);
    P = makePlan();
    st = { sel: {}, from: 0, to: ds.time ? V.t.length - 1 : 0, m: ds.meas[0] ? ds.meas[0].k : '', ag: {}, tb: { by: P.tableBy, sort: '', dir: -1 } };
    resetSort(); render();
  }
  const cm = () => ds.meas.find(m => m.k === st.m) || null;
  const aggOf = m => (st.ag && st.ag[m.k]) || (m.avg ? 'avg' : 'sum');          // mặc định an toàn do máy chủ chọn; người xem đổi tay ở thẻ chỉ số
  const agg = () => { const m = cm(); return m ? aggOf(m) : 'count' };
  const keys = () => Object.keys(L);
  const resetSort = () => { const t = st.tb; if (t.by === 't') { t.sort = 'l'; t.dir = 1 } else { t.sort = ds.meas[0] ? ds.meas[0].k : 'rows'; t.dir = -1 } };

  /* ---- chọn biểu đồ và bộ lọc phù hợp với dữ liệu ---- */
  function makePlan() {
    const kk = d => d.vals.length - (d.na >= 0 ? 1 : 0);
    const rank = d => { const k = kk(d), len = d.vals.reduce((s, v) => s + v.length, 0) / (d.vals.length || 1);
      return (k >= 3 && k <= 12 ? 0 : k === 2 ? 2 : k <= 20 ? 1 : 3) + (len > 26 ? 1 : 0) + (d.miss > .3 ? 2 : 0) };
    const ok = ds.dims.filter(d => d.miss < .6 && kk(d) >= 2).map((d, i) => ({ d, i, r: rank(d) })).sort((a, b) => a.r - b.r || a.i - b.i);
    const timeOk = !!ds.time && V.t.length >= 3;
    const dn = ok.find(x => x.r < 3 && kk(x.d) <= 6 && x.d.miss <= .3 && !x.d.ord);
    const donutK = dn ? dn.d.k : null;
    return { timeOk, donutK, bars: ok.filter(x => x.r < 3 && x.d.k !== donutK).slice(0, timeOk && donutK ? 3 : 4).map(x => x.d.k),
      filters: ok.filter(x => x.d.vals.length <= 30 && x.d.miss < .4).slice(0, 3).map(x => x.d.k),
      tableBy: ok.length ? ok[0].d.k : (ds.time ? 't' : (ds.dims[0] || {}).k) };
  }

  /* ---- tính toán ---- */
  function pass(i, skip) {
    if (ds.time) { const c = C.t[i], full = st.from === 0 && st.to === V.t.length - 1; if (c < 0 ? !full : (c < st.from || c > st.to)) return false }
    for (const k in st.sel) { if (k === skip) continue; const s = st.sel[k]; if (s.size && !s.has(C[k][i])) return false }
    return true;
  }
  function groupBy(by, mk, a) {
    const K = V[by].length, s = new Float64Array(K), c = new Float64Array(K), r = new Float64Array(K), codes = C[by], mv = mk ? M[mk] : null;
    const mj = mk ? ds.meas.findIndex(m => m.k === mk) : -1, mcc = mk && ds.mc ? ds.mc[mj] : null;
    for (let i = 0; i < ds.n; i++) { if (!pass(i, by)) continue; const q = codes[i]; if (q < 0) continue; const w = ds.w ? ds.w[i] : 1; r[q] += w;
      if (mv) { const v = mv[i]; if (v != null) { s[q] += v; c[q] += mcc ? mcc[i] : 1 } } }
    const ag = mk ? a : 'count';
    return V[by].map((l, q) => ({ q, l, rows: r[q], na: q === NA[by], v: ag === 'count' ? r[q] : ag === 'avg' ? (c[q] ? s[q] / c[q] : null) : s[q] })).filter(g => g.rows > 0 && g.v != null);
  }
  function kpiData() {
    let rows = 0; const S = ds.meas.map(() => 0), Cn = ds.meas.map(() => 0);
    for (let i = 0; i < ds.n; i++) { if (!pass(i, null)) continue; rows += ds.w ? ds.w[i] : 1;
      ds.meas.forEach((m, j) => { const v = M[m.k][i]; if (v != null) { S[j] += v; Cn[j] += ds.mc ? ds.mc[j][i] : 1 } }) }
    return { rows, S, Cn };
  }
  const selOn = k => { const s = st.sel[k]; return !!(s && s.size) };
  const isSel = (k, q) => { const s = st.sel[k]; return !s || !s.size || s.has(q) };
  const cls = (k, q) => selOn(k) ? (isSel(k, q) ? 'sel' : 'dim') : '';
  const tt = (g, m, a) => esc(`${g.l}: ${a === 'count' ? f0.format(g.v) + ' bản ghi' : val(g.v, m ? m.unit : '')} · ${f0.format(g.rows)} bản ghi`);

  /* ---- các loại biểu đồ ---- */
  function barsHTML(g, by, m, a) {
    const ord = (ds.dims.find(d => d.k === by) || {}).ord, add = a !== 'avg';
    let rows = ord ? g.slice().sort((x, y) => x.q - y.q) : g.slice().sort((x, y) => (x.na - y.na) || (y.v - x.v));
    const tot = rows.reduce((s, r) => s + Math.max(r.v, 0), 0) || 1; let extra = 0;
    if (!ord && rows.length > 8) {
      if (add) { const keep = rows.slice(0, 7), rest = rows.slice(7);
        keep.push({ q: -1, l: `Khác (${rest.length} nhóm)`, v: rest.reduce((s, r) => s + r.v, 0), rows: rest.reduce((s, r) => s + r.rows, 0), na: false }); rows = keep }
      else { rows = rows.slice(0, 10); extra = g.length - rows.length }
    }
    const mx = Math.max(...rows.map(r => r.v), 0) || 1, u = m ? m.unit : '';
    return `<div class="bars">${rows.map(r => `<div class="bar ${r.na ? 'na' : ''} ${r.q >= 0 ? cls(by, r.q) : ''}" ${r.q >= 0 ? `data-k="${by}" data-q="${r.q}"` : ''} data-tt="${tt(r, m, a)}">
<span class="bl" title="${esc(r.l)}">${esc(r.l)}</span><span class="bt"><i style="width:${Math.max(0, r.v / mx * 100)}%"></i></span>
<span class="bv">${a === 'count' ? f0.format(r.v) : val(r.v, u)}${add && tot > 0 ? `<small>${pct(Math.max(r.v, 0) / tot)}</small>` : ''}</span></div>`).join('')}</div>${extra > 0 ? `<p class="more">và ${extra} nhóm khác không hiển thị</p>` : ''}`;
  }
  function donutHTML(g, by, m, a, hole = true) {                  // hole=false: tròn đặc (pie)
    let rows = g.filter(r => r.v > 0).sort((x, y) => (x.na - y.na) || (y.v - x.v));
    if (rows.length > 6) { const rest = rows.slice(5); rows = [...rows.slice(0, 5), { q: -1, l: 'Khác', v: rest.reduce((s, r) => s + r.v, 0), rows: rest.reduce((s, r) => s + r.rows, 0), na: false }] }
    const tot = rows.reduce((s, r) => s + r.v, 0) || 1, R = hole ? 66 : 33, SW = hole ? 24 : 66, Cc = 2 * Math.PI * R, u = m ? m.unit : ''; let acc = 0, pi = 0;
    const col = r => r.na ? 'var(--na)' : PAL[pi++ % PAL.length], cols = rows.map(col); acc = 0;
    const segs = rows.map((r, i) => { const len = r.v / tot * Cc, o = acc, gap = rows.length > 1 ? 2.5 : 0; acc += len;
      return `<circle class="seg ${r.q >= 0 ? cls(by, r.q) : ''}" ${r.q >= 0 ? `data-k="${by}" data-q="${r.q}"` : ''} data-tt="${tt(r, m, a)}" cx="88" cy="88" r="${R}" fill="none" style="stroke:${cols[i]}" stroke-width="${SW}" stroke-dasharray="${Math.max(len - gap, .1)} ${Cc - len + gap}" stroke-dashoffset="${-o}" transform="rotate(-90 88 88)"/>` }).join('');
    return `<div class="donut"><svg viewBox="0 0 176 176" role="img"><circle cx="88" cy="88" r="${R}" fill="none" stroke-width="${SW}" style="stroke:var(--track)"/>${segs}
${hole ? `<text class="t1" x="88" y="87" text-anchor="middle">${esc(a === 'count' ? f0.format(tot) : nu(tot, u))}</text><text class="t2" x="88" y="106" text-anchor="middle">${esc(a === 'count' ? 'bản ghi' : (u || 'tổng'))}</text>` : ''}</svg>
<div class="legend">${rows.map((r, i) => `<div class="lg ${r.na ? 'na' : ''} ${r.q >= 0 ? cls(by, r.q) : ''}" ${r.q >= 0 ? `data-k="${by}" data-q="${r.q}"` : ''} data-tt="${tt(r, m, a)}"><i style="background:${cols[i]}"></i><span title="${esc(r.l)}">${esc(r.l)}</span><b>${pct(r.v / tot)}</b></div>`).join('')}</div></div>`;
  }
  /* các mốc trục "tròn" (1, 2, 2,5, 5 × 10^n) để trục dễ đọc */
  function niceTicks(lo, hi, n = 4) {
    const span = (hi - lo) || 1, raw = span / n, p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p, step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
    const a = Math.floor(lo / step + 1e-9) * step, b = Math.ceil(hi / step - 1e-9) * step, t = [];
    for (let v = a; v <= b + step / 2; v += step) t.push(+v.toFixed(8)); return t.length > 1 ? t : [a, a + step];
  }
  function trendSVG(g, W, m, a, ro) {
    const H = 250, pr = 14, pt = 12, pb = 30, n = g.length, vs = g.map(r => r.v);
    const tk = niceTicks(Math.min(...vs, 0), Math.max(...vs, 0)), mn = tk[0], mx = tk[tk.length - 1], sp = (mx - mn) || 1;
    const tl = tk.map(v => fv(v, m, a)), pl = Math.max(58, Math.max(...tl.map(s => s.length)) * 6.6 + 18);        // số đầy đủ rộng hơn bản rút gọn nên lề trái tự giãn theo nhãn trục
    const X = i => n === 1 ? pl + (W - pl - pr) / 2 : pl + i * (W - pl - pr) / (n - 1), Y = v => pt + (mx - v) / sp * (H - pt - pb);
    const grid = tk.map((v, ti) => { const y = Y(v); return `<line class="gl" x1="${pl}" x2="${W - pr}" y1="${y}" y2="${y}"/><text x="${pl - 10}" y="${y + 4}" text-anchor="end">${esc(tl[ti])}</text>` }).join('');
    const pts = g.map((r, i) => [X(i), Y(r.v)]), base = Y(Math.max(mn, 0)), every = Math.ceil(n / Math.max(2, Math.floor((W - pl - pr) / 70))), step = n > 1 ? (W - pl - pr) / (n - 1) : 60;
    const id = 'g' + Math.random().toString(36).slice(2, 7), anyS = selOn('t');
    return `<svg viewBox="0 0 ${W} ${H}" role="img"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--acc);stop-opacity:.22"/><stop offset="1" style="stop-color:var(--acc);stop-opacity:0"/></linearGradient></defs>${grid}
<path d="M${pts.map(p => p.join(',')).join('L')}L${X(n - 1)},${base}L${X(0)},${base}Z" fill="url(#${id})"/><polyline class="ln" points="${pts.map(p => p.join(',')).join(' ')}"/>
${g.map((r, i) => `<g ${ro ? '' : `data-k="t" data-q="${r.q}"`} data-tt="${tt({ l: ml(r.l), v: r.v, rows: r.rows }, m, a)}"><rect class="hit" x="${pts[i][0] - step / 2}" y="${pt}" width="${step}" height="${H - pt - pb}"/>
${n <= 18 || (anyS && isSel('t', r.q)) ? `<circle class="pt ${anyS && isSel('t', r.q) ? 'sel' : ''}" cx="${pts[i][0]}" cy="${pts[i][1]}" r="4.5" style="${anyS && !isSel('t', r.q) ? 'opacity:.35' : ''}"/>` : ''}
${i % every === 0 || i === n - 1 && (n - 1) % every > every / 2 ? `<text x="${pts[i][0]}" y="${H - 8}" text-anchor="${i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle'}">${esc(ml(r.l))}</text>` : ''}</g>`).join('')}</svg>`;
  }

  /* dòng nhận xét ngắn dưới tiêu đề, tính trực tiếp từ dữ liệu đang hiển thị */
  function lead(type, g, m, a) {
    if (!g.length) return '';
    const u = m ? m.unit : '', v = x => a === 'count' ? f0.format(x) : val(x, u), real = g.filter(r => !r.na), add = a !== 'avg';
    if (type === 'trend') { const f = g[0], l = g[g.length - 1], pk = g.reduce((b, r) => r.v > b.v ? r : b, g[0]);
      const ch = f.v ? (l.v / f.v - 1) : null;
      return g.length > 1 ? `${ml(f.l)} đến ${ml(l.l)}${ch == null ? '' : (ch >= 0 ? ': tăng ' : ': giảm ') + f2.format(Math.abs(ch) * 100) + '%'} · cao nhất <b>${esc(ml(pk.l))}</b> (${esc(v(pk.v))})` : '' }
    const top = (real.length ? real : g).reduce((b, r) => r.v > b.v ? r : b), tot = g.reduce((s, r) => s + Math.max(r.v, 0), 0);
    return add && tot > 0 ? `<b>${esc(top.l)}</b> dẫn đầu, chiếm ${pct(top.v / tot)} tổng` : `Cao nhất: <b>${esc(top.l)}</b> (${esc(v(top.v))})`;
  }
  /* ---- biểu đồ cột dọc (so sánh ít nhóm, hoặc chuỗi thời gian dạng cột) ---- */
  function colsHTML(g, by, m, a) {
    const isT = by === 't', ord = isT || (ds.dims.find(d => d.k === by) || {}).ord, u = m ? m.unit : '';
    let rows = ord ? g.slice().sort((x, y) => x.q - y.q) : g.slice().sort((x, y) => (x.na - y.na) || (y.v - x.v));
    const cap = isT ? 24 : 10, cut = rows.length - cap; if (cut > 0) rows = isT ? rows.slice(-cap) : rows.slice(0, cap);
    const mx = Math.max(...rows.map(r => r.v), 0) || 1, txt = rows.map(r => fv(r.v, m, a)), wide = rows.length > 5 && Math.max(...txt.map(s => s.length)) * 6.4 > 560 / rows.length;
    const hi = rows.findIndex(r => r.v === mx), lo = rows.reduce((b, r, i) => r.v < rows[b].v ? i : b, 0);
    return `<div class="cols">${rows.map((r, i) => `<div class="col ${r.na ? 'na' : ''} ${cls(by, r.q)}" data-k="${by}" data-q="${r.q}" data-tt="${tt({ ...r, l: isT ? ml(r.l) : r.l }, m, a)}">
<span class="cv">${wide && i !== hi && i !== lo ? '' : txt[i]}</span><span class="cb"><i style="height:${Math.max(2, r.v / mx * 100)}%"></i></span><span class="cl" title="${esc(isT ? ml(r.l) : r.l)}">${esc(isT ? ml(r.l) : r.l)}</span></div>`).join('')}</div>${cut > 0 ? `<p class="more">và ${cut} ${isT ? 'kỳ trước đó' : 'nhóm khác'} không hiển thị</p>` : ''}`;
  }

  /* ---- danh sách biểu đồ cần vẽ: theo KẾ HOẠCH do người dùng chọn (D.plan); không có kế hoạch thì tự chọn theo dữ liệu như trước ---- */
  function cardList() {
    const gm = cm(), ga = agg();
    if (!Array.isArray(D.plan)) {
      const c = []; if (P.timeOk) c.push({ t: 'trend', by: 't', m: gm, a: ga });
      if (P.donutK) c.push({ t: ga === 'avg' ? 'bars' : 'donut', by: P.donutK, m: gm, a: ga });
      P.bars.forEach(k => c.push({ t: 'bars', by: k, m: gm, a: ga })); return c;
    }
    const items = D.plan.filter(c => c.on !== false && (c.type === 'static' ? D.datasets.indexOf(ds) === 0 : c.ds === ds.name && (c.type === 'score' || (c.type === 'heat' ? c.by in L : (c.by === 't' ? !!ds.time : c.by in L)))));
    return items.map(c => {
      if (c.type === 'static' || c.type === 'score' || c.type === 'heat') return { t: c.type, c, id: c.id };
      let m, a;
      if (c.m == null || c.m === '*') { m = gm; a = ga } else if (c.m === '') { m = null; a = 'count' } else { m = ds.meas.find(x => x.k === c.m) || gm; a = m && m.k === c.m && c.agg === 'avg' ? 'avg' : 'sum'; if (!m) a = 'count' }
      let t = c.kind === 'line' ? 'trend' : (c.kind || 'bars');
      if (c.by === 't') t = t === 'trend' ? 'trend' : 'cols'; else if (t === 'trend') t = 'bars';
      if (t === 'donut' && a !== 'sum' && a !== 'count') t = 'bars';
      if (m && m.rate) a = 'avg';
      if (t === 'donut' && m && m.rate) t = 'bars';
      return { t, by: c.by, m, a, id: c.id };
    });
  }
  function spansAuto(cards) {                               // bố cục tự động (như trước): đường rộng, tròn hẹp, còn lại ghép đôi
    const sp = []; let i = 0;
    while (i < cards.length) { const c = cards[i], n = cards[i + 1];
      if (c.t === 'heat') { sp.push(12); i += 1; continue }
      if (c.t === 'trend') { if (n && n.t === 'donut') { sp.push(8, 4); i += 2 } else { sp.push(12); i += 1 } }
      else if (c.t === 'donut' && n && n.t !== 'trend') { sp.push(4, 8); i += 2 }
      else if (n && n.t !== 'trend' && c.t !== 'donut') { sp.push(6, 6); i += 2 }
      else { sp.push(12); i += 1 } }
    return sp;
  }
  const pairUp = w => { const sp = []; let i = 0; while (i < w.length) { if (w[i]) { sp.push(12); i += 1 } else if (i + 1 < w.length && !w[i + 1]) { sp.push(6, 6); i += 2 } else { sp.push(12); i += 1 } } return sp };
  function spans(cards) {                                   // bố cục do bản thiết kế chọn; không có thì tự động
    const lay = (D.bp && D.bp.layout) || 'auto', big = c => c.t === 'heat' || c.t === 'trend';
    if (lay === 'compliance') return pairUp(cards.map(c => big(c) || c.t === 'score'));
    if (lay === 'rank') return pairUp(cards.map((c, i) => i === 0 || big(c)));
    if (lay === 'story') return pairUp(cards.map((c, i) => i < 3 || big(c)));
    if (lay === 'overview') return pairUp(cards.map(big));
    return spansAuto(cards);
  }
  /* ---- bảng điểm tiêu chí, ma trận nhiệt, biểu đồ từ phân tích (đã tổng hợp sẵn) ---- */
  const rateKeys = c => (c.ms && c.ms.length ? c.ms : ds.meas.filter(x => x.rate).map(x => x.k));
  function scoreRows(c) { const k = kpiData(); return rateKeys(c).map(q => ds.meas.findIndex(x => x.k === q)).filter(j => j >= 0)
    .map(j => ({ x: ds.meas[j], n: k.Cn[j], v: k.Cn[j] ? k.S[j] / k.Cn[j] : null })).filter(r => r.v != null).sort((a, b) => a.v - b.v) }
  function scoreHTML(rows) { if (!rows.length) return '<div class="empty">Không có dữ liệu với bộ lọc hiện tại.</div>';
    return `<div class="score">${rows.map(r => { const nm = r.x.short || r.x.label; return `<div class="sr ${r.x.k === st.m ? 'sel' : ''}" data-m="${r.x.k}" data-tt="${esc(nm + ': ' + pct(r.v) + ' · ' + f0.format(r.n) + ' lượt đánh giá. Bấm để xem tiêu chí này ở các biểu đồ khác')}"><span class="sn" title="${esc(nm)}">${esc(nm)}</span><span class="bt"><i style="width:${Math.max(1, r.v * 100)}%"></i></span><b>${pct(r.v)}</b><small>${f0.format(r.n)}</small></div>` }).join('')}</div>` }
  function heatHTML(c) {
    const by = c.by, ms = rateKeys(c).map(q => ds.meas.find(x => x.k === q)).filter(Boolean).slice(0, 8);
    const base = groupBy(by, '', 'count').filter(g => !g.na).sort((x, y) => y.rows - x.rows).slice(0, 14), per = ms.map(m => { const o = {}; groupBy(by, m.k, 'avg').forEach(g => { o[g.q] = g }); return o });
    if (!base.length || !ms.length) return '<div class="empty">Không có dữ liệu với bộ lọc hiện tại.</div>';
    const cell = (g, j) => { const x = per[j][g.q]; if (!x) return '<td class="hc na">—</td>';
      return `<td class="hc ${cls(by, g.q)}" data-k="${by}" data-q="${g.q}" style="--v:${Math.round(Math.max(0, Math.min(1, x.v)) * 100)}" data-tt="${esc(g.l + ' · ' + (ms[j].short || ms[j].label) + ': ' + pct(x.v) + ' (' + f0.format(x.rows) + ' lượt)')}">${pct(x.v)}</td>` };
    return `<div class="tw"><table class="heat"><thead><tr><th></th>${ms.map(m => `<th title="${esc(m.label)}">${esc(m.short || m.label)}</th>`).join('')}</tr></thead><tbody>${base.map(g => `<tr><th class="hl ${cls(by, g.q)}" data-k="${by}" data-q="${g.q}" title="${esc(g.l)}">${esc(g.l)}<small>${f0.format(g.rows)}</small></th>${ms.map((m, j) => cell(g, j)).join('')}</tr>`).join('')}</tbody></table></div>` }
  /* Các dạng biểu đồ của thẻ lấy từ kết quả phân tích: kẹo mút, Pareto (80/20), treemap. Cùng thuật toán với static/js/app.js và app/export/svg.py. */
  const TMP = ['#4F46E5', '#0369A1', '#047857', '#B45309', '#B91C1C', '#6D28D9', '#475569'];
  function paretoHTML(labs, vs, u) {
    const rs = labs.map((l, i) => [l, vs[i]]).filter(r => r[1] > 0).sort((a, b) => b[1] - a[1]).slice(0, 12);
    if (rs.length < 3) return '';
    const n = rs.length, tot = rs.reduce((s, r) => s + r[1], 0), W = 520, H = 270, pl = 8, pr = 44, pt = 22, pb = 58, pw = W - pl - pr, ph = H - pt - pb, slot = pw / n, bw = Math.min(slot * .62, 56), base = pt + ph, mx = rs[0][1], y80 = pt + .2 * ph;
    let acc = 0; const cum = rs.map(r => (acc += r[1]) / tot * 100), k80 = cum.findIndex(c => c >= 80) < 0 ? n - 1 : cum.findIndex(c => c >= 80);
    const pts = cum.map((c, i) => [pl + slot * (i + .5), pt + (1 - c / 100) * ph]);
    const bars = rs.map(([l, v], i) => { const cx = pl + slot * (i + .5), h = Math.max(v / mx * ph, 1.5), ly = H - pb + 16;
      return `<g data-tt="${esc(l + ': ' + val(v, u) + ' · cộng dồn ' + pctv(cum[i]))}"><rect x="${(cx - bw / 2).toFixed(1)}" y="${(base - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="3" style="fill:${i <= k80 ? 'var(--acc)' : 'var(--mute)'}"/>${n <= 8 ? `<text x="${cx.toFixed(1)}" y="${(base - h - 5).toFixed(1)}" text-anchor="middle" style="fill:var(--ink);font-size:11px;font-weight:600">${esc(nu(v, u))}</text>` : ''}<text x="${cx.toFixed(1)}" y="${ly}" text-anchor="${n > 7 ? 'end' : 'middle'}" ${n > 7 ? `transform="rotate(-35 ${cx.toFixed(1)} ${ly})"` : ''} style="fill:var(--sub);font-size:11px">${esc(l.length > 12 ? l.slice(0, 11) + '…' : l)}</text></g>` }).join('');
    return `<svg viewBox="0 0 ${W} ${H}" role="img" style="width:100%;height:auto;display:block"><line x1="${pl}" y1="${base}" x2="${W - pr}" y2="${base}" style="stroke:var(--line)"/><line x1="${pl}" y1="${y80.toFixed(1)}" x2="${W - pr}" y2="${y80.toFixed(1)}" style="stroke:var(--bad);stroke-dasharray:5 4;opacity:.7"/><text x="${W - pr + 6}" y="${(y80 + 4).toFixed(1)}" style="fill:var(--mute);font-size:11px">80%</text><text x="${W - pr + 6}" y="${pt + 4}" style="fill:var(--mute);font-size:11px">100%</text>${bars}<polyline points="${pts.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ')}" style="fill:none;stroke:var(--warn);stroke-width:2.4;stroke-linejoin:round"/>${pts.map((p, i) => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="${i === k80 ? 4.5 : 2.6}" style="fill:var(--surface);stroke:var(--warn);stroke-width:2"/>`).join('')}<text x="${pts[k80][0].toFixed(1)}" y="${(pts[k80][1] - 10).toFixed(1)}" text-anchor="middle" style="fill:var(--ink);font-size:11.5px;font-weight:700">${esc(pctv(cum[k80]))}</text></svg><p class="pn">${f0.format(k80 + 1)}/${f0.format(n)} nhóm đầu chiếm ${esc(pctv(cum[k80]))} tổng</p>`;
  }
  function treemapHTML(labs, vs, u) {
    const rs = labs.map((l, i) => [l, vs[i]]).filter(r => r[1] > 0).sort((a, b) => b[1] - a[1]).slice(0, 16), tot = rs.reduce((s, r) => s + r[1], 0) || 1, cells = [];
    if (rs.length < 2) return '';
    const lay = (it, x, y, w, h) => { if (!it.length) return; if (it.length === 1) { cells.push([it[0], x, y, w, h]); return }
      const s = it.reduce((a, r) => a + r[1], 0); let acc = 0, k = 1, best = Infinity;
      for (let j = 1; j < it.length; j++) { acc += it[j - 1][1]; const d = Math.abs(acc - s / 2); if (d < best) { best = d; k = j } }
      const a = it.slice(0, k), b = it.slice(k), sa = a.reduce((q, r) => q + r[1], 0) / s;
      if (w >= h) { lay(a, x, y, w * sa, h); lay(b, x + w * sa, y, w * (1 - sa), h) } else { lay(a, x, y, w, h * sa); lay(b, x, y + h * sa, w, h * (1 - sa)) } };
    lay(rs, 0, 0, 100, 100);
    return `<div class="tmw">${cells.map(([it, x, y, w, h]) => `<div class="tm" style="left:${x.toFixed(2)}%;top:${y.toFixed(2)}%;width:${w.toFixed(2)}%;height:${h.toFixed(2)}%;background:${TMP[rs.indexOf(it) % 7]}" data-tt="${esc(it[0] + ': ' + val(it[1], u) + ' (' + pctv(it[1] / tot * 100) + ')')}">${w >= 12 && h >= 14 ? `<b>${esc(it[0])}</b><span>${esc(nu(it[1], u))} · ${esc(pctv(it[1] / tot * 100))}</span>` : ''}</div>`).join('')}</div>`;
  }
  function staticHTML(c, n) {
    const vs = c.values, labs = c.labels, u = c.unit || '', mx = Math.max(...vs.map(Math.abs), 0) || 1, fmt = v => val(v, u);
    const sw = labs.length > 5 && Math.max(...vs.map(v => nu(v, u).length)) * 6.4 > 560 / labs.length, shi = vs.indexOf(Math.max(...vs)), slo = vs.indexOf(Math.min(...vs));
    if (c.kind === 'cols') return `<div class="cols">${labs.map((l, i) => `<div class="col" data-tt="${esc(l + ': ' + fmt(vs[i]))}"><span class="cv">${sw && i !== shi && i !== slo ? '' : esc(nu(vs[i], u))}</span><span class="cb"><i style="height:${Math.max(2, Math.abs(vs[i]) / mx * 100)}%"></i></span><span class="cl" title="${esc(l)}">${esc(l)}</span></div>`).join('')}</div>`;
    const M = u ? { unit: u } : null, G = () => labs.map((l, i) => ({ q: -1, l, v: vs[i], rows: 0, na: false }));
    if (c.kind === 'donut' || c.kind === 'pie') return donutHTML(G(), '', M, 'sum', c.kind === 'donut');
    if (c.kind === 'pareto') { const h = paretoHTML(labs, vs, u); if (h) return h }
    if (c.kind === 'treemap') { const h = treemapHTML(labs, vs, u); if (h) return h }
    if (c.kind === 'lollipop') return `<div class="bars lp">${labs.map((l, i) => `<div class="bar" data-tt="${esc(l + ': ' + fmt(vs[i]))}"><span class="bl" title="${esc(l)}">${esc(l)}</span><span class="bt"><i style="width:calc(${Math.max(0, vs[i] / mx * 100)}% - 6px)"></i></span><span class="bv">${esc(fmt(vs[i]))}</span></div>`).join('')}</div>`;
    if (c.kind === 'line' || c.kind === 'area') { jobs.push({ id: 'stl' + n, g: labs.map((l, i) => ({ q: -1, l, v: vs[i], rows: 0 })), m: u ? { unit: u } : null, a: 'sum', ro: true }); return `<div class="trend" id="stl${n}"></div>` }
    return `<div class="bars">${labs.map((l, i) => `<div class="bar" data-tt="${esc(l + ': ' + fmt(vs[i]))}"><span class="bl" title="${esc(l)}">${esc(l)}</span><span class="bt"><i style="width:${Math.max(0, vs[i] / mx * 100)}%"></i></span><span class="bv">${esc(fmt(vs[i]))}</span></div>`).join('')}</div>` }
  /* chế độ chỉnh (chỉ ở bản xem thử trong ứng dụng): mỗi thẻ có nút di chuyển, đổi dạng, ẩn; bản xuất ra không có */
  const edBar = (id, i, n, kind) => D.edit ? `<div class="edb"><button data-ed="up" title="Đưa lên" aria-label="Đưa lên" ${i === 0 ? 'disabled' : ''}>↑</button><button data-ed="down" title="Đưa xuống" aria-label="Đưa xuống" ${i === n - 1 ? 'disabled' : ''}>↓</button>${kind ? '<button data-ed="kind" title="Đổi dạng biểu đồ" aria-label="Đổi dạng biểu đồ">⇄</button>' : ''}<button data-ed="hide" title="Ẩn biểu đồ này" aria-label="Ẩn biểu đồ này">✕</button></div>` : '';
  const shellCard = (c, span, title, lead, body, i, n, kind) => `<section class="card c${span}" data-cid="${esc(c.id || '')}">${edBar(c.id, i, n, kind)}<div class="ch"><h3>${esc(title)}</h3><p>${lead || ''}</p></div>${body}</section>`;
  function chartsHTML() {
    const cards = cardList(); jobs = [];
    const add = D.edit ? '<section class="card c12 addc"><button data-ed="add">+ Thêm biểu đồ</button></section>' : '';
    if (!cards.length) return `<section class="card c12"><div class="empty">${Array.isArray(D.plan) ? 'Chưa chọn biểu đồ nào cho bảng này. Hãy bật biểu đồ ở mục chọn biểu đồ.' : 'Không có biểu đồ phù hợp.'}</div></section>` + add;
    const sp = spans(cards), n = cards.length;
    return cards.map((c, i) => {
      if (c.t === 'score') { const rows = scoreRows(c.c), lo = rows[0], hi = rows[rows.length - 1];
        return shellCard(c, sp[i], c.c.title || 'Tỷ lệ đạt theo từng tiêu chí', rows.length > 1 ? `Thấp nhất: <b>${esc(lo.x.short || lo.x.label)}</b> (${pct(lo.v)}) · cao nhất: <b>${esc(hi.x.short || hi.x.label)}</b> (${pct(hi.v)})` : '', scoreHTML(rows), i, n, false) }
      if (c.t === 'heat') return shellCard(c, sp[i], c.c.title || `Tỷ lệ đạt theo ${lc(L[c.c.by] || 'nhóm')} và tiêu chí`, 'Ô càng đậm là tỷ lệ càng cao. Bấm tên nhóm hoặc một ô để lọc.', heatHTML(c.c), i, n, false);
      if (c.t === 'static') return shellCard(c, sp[i], c.c.title || 'Biểu đồ từ phân tích', `${c.c.why ? esc(c.c.why) + ' · ' : ''}<span class="tg">Từ kết quả phân tích · không đổi theo bộ lọc</span>`, staticHTML(c.c, i), i, n, false);
      const { m, a } = c, g = groupBy(c.by, m ? m.k : '', a), name = mName(m, a), title = `${name} theo ${c.by === 't' ? 'tháng' : lc(L[c.by])}`;
      const body = !g.length ? '<div class="empty">Không có dữ liệu với bộ lọc hiện tại.</div> ' : c.t === 'trend' ? (jobs.push({ id: 'tr' + i, g, m, a }), `<div class="trend" id="tr${i}"></div>`)
        : c.t === 'donut' ? donutHTML(g, c.by, m, a) : c.t === 'cols' ? colsHTML(g, c.by, m, a) : barsHTML(g, c.by, m, a);
      return shellCard(c, sp[i], title, lead(c.t === 'cols' && c.by === 't' ? 'trend' : c.t, g, m, a), body, i, n, true);
    }).join('') + add;
  }
  function paintTrends() { jobs.forEach(j => { const el = document.getElementById(j.id); if (el) el.innerHTML = trendSVG(j.g, Math.max(320, Math.floor(el.clientWidth)), j.m, j.a, j.ro) }) }

  function tableCard() {
    const t = st.tb, by = t.by; if (!by || (D.bp && D.bp.table && D.bp.table.on === false)) return '';
    const mc = ds.meas.slice(0, 4), head = [['l', L[by], false], ['rows', 'Số bản ghi', true], ...mc.map(m => [m.k, mName(m, aggOf(m)), true])];
    const by2 = {}; mc.forEach(m => by2[m.k] = groupBy(by, m.k, aggOf(m))); const base = groupBy(by, '', 'count');
    let rows = base.map(b => { const o = { l: b.l, rows: b.rows }; mc.forEach(m => { const x = by2[m.k].find(y => y.q === b.q); o[m.k] = x ? x.v : null }); return o });
    rows.sort((x, y) => (typeof x[t.sort] === 'string' ? x[t.sort].localeCompare(y[t.sort], 'vi', { numeric: true }) : (x[t.sort] ?? -Infinity) - (y[t.sort] ?? -Infinity)) * t.dir); rows = rows.slice(0, 60);
    const cf = {}; mc.forEach(m => { cf[m.k] = m.rate ? pct : m.unit === '%' ? pctv : colFmt(rows.map(r => r[m.k]), m.unit) });
    const cell = (v, k) => k === 'l' ? esc(by === 't' ? ml(v) : v) : k === 'rows' ? f0.format(v) : esc(cf[k](v));
    return `<section class="card c12"><div class="ch row"><div><h3>Bảng chi tiết</h3><p>Tổng hợp theo từng nhóm, bấm tiêu đề cột để sắp xếp.</p></div>
<label class="pill"><span class="k">Nhóm theo</span><select data-tb="by">${keys().map(k => `<option value="${k}" ${k === by ? 'selected' : ''}>${esc(L[k])}</option>`).join('')}</select></label></div>
<div class="tw"><table><thead><tr>${head.map(([k, l, n]) => `<th class="${n ? 'n' : ''}" data-sort="${k}">${esc(l)}${t.sort === k ? (t.dir < 0 ? ' ↓' : ' ↑') : ''}</th>`).join('')}</tr></thead>
<tbody>${rows.map(r => `<tr>${head.map(([k, , n]) => `<td class="${n ? 'n' : ''}">${cell(r[k], k)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`;
  }

  /* ---- khung trang ---- */
  function filtersHTML() {
    const one = k => { const s = st.sel[k] || new Set(), act = s.size > 0;
      return `<details class="sl ${act ? 'act' : ''}" data-sl="${k}" ${openK.has(k) ? 'open' : ''}><summary>${esc(L[k])}${act ? `<span class="cnt">${s.size}</span>` : ''}</summary><div class="slp"><div class="row"><button class="lnk" data-clr="${k}" ${act ? '' : 'disabled'}>Bỏ chọn</button></div>${V[k].map((v, q) => `<label><input type="checkbox" data-sc="${k}" data-q="${q}" ${s.has(q) ? 'checked' : ''}> ${esc(v)}</label>`).join('')}</div></details>` };
    const opt = i => V.t.map((v, j) => `<option value="${j}" ${j === i ? 'selected' : ''}>${esc(ml(v))}</option>`).join('');
    const rng = ds.time ? `<div class="pill"><span class="k">Từ</span><select data-r="from">${opt(st.from)}</select><span class="k">đến</span><select data-r="to">${opt(st.to)}</select></div>` : '';
    const met = ds.meas.length > 1 ? `<div class="seg" role="group" aria-label="Chỉ số">${ds.meas.slice(0, 4).map(m => `<button data-m="${m.k}" class="${m.k === st.m ? 'on' : ''}" title="${esc(m.label)}">${esc(m.label)}</button>`).join('')}</div>` : '';
    const n = kpiData().rows, filtered = Object.values(st.sel).some(s => s.size) || (ds.time && (st.from > 0 || st.to < V.t.length - 1));
    return `${rng}${P.filters.map(one).join('')}${met}${bpAgt()}<button class="lnk" data-reset="1" ${filtered ? '' : 'disabled'}>Xóa bộ lọc</button><span class="sp"></span><span class="status"><b>${f0.format(n)}</b> / ${f0.format(ds.n_src)} bản ghi</span>`;
  }
  const blk = k => !(D.bp && D.bp.blocks) || D.bp.blocks[k] !== false;
  function kpiCard(it, K) {                                    // -> [nhãn, giá trị, dòng phụ (đã thoát HTML)] hoặc null nếu không tính được với bảng này
    const j = it.m ? ds.meas.findIndex(x => x.k === it.m) : -1, m = j >= 0 ? ds.meas[j] : null, rates = ds.meas.map((x, q) => ({ x, q })).filter(r => r.x.rate), by = it.by;
    const lab = d => it.label || d;
    switch (it.kind) {
      case 'count': return [lab('Số bản ghi'), f0.format(K.rows), ''];
      case 'sum': if (!m) return null; return [lab(mName(m, 'sum')), val(K.S[j], m.unit), m.add ? '' : 'Chỉ số này thường không cộng được'];
      case 'avg': if (!m) return null; return [lab(mName(m, 'avg')), val(K.Cn[j] ? K.S[j] / K.Cn[j] : null, m.unit), ''];
      case 'rate': if (!m) return null; return [lab(m.label), val(K.Cn[j] ? K.S[j] / K.Cn[j] : null, '@rate'), K.Cn[j] ? `trên ${f0.format(K.Cn[j])} lượt đánh giá` : ''];
      case 'rate_all': { if (!rates.length) return null; let s = 0, n = 0; rates.forEach(r => { s += K.S[r.q]; n += K.Cn[r.q] }); return [lab('Tỷ lệ đạt chung'), n ? pct(s / n) : '—', `${rates.length} tiêu chí · ${f0.format(n)} lượt đánh giá`] }
      case 'rate_low': { let lo = null; rates.forEach(r => { const n = K.Cn[r.q]; if (n && (!lo || K.S[r.q] / n < lo.v)) lo = { v: K.S[r.q] / n, x: r.x } }); return lo ? [lab('Tiêu chí thấp nhất'), pct(lo.v), esc(lo.x.short || lo.x.label)] : null }
      case 'distinct': if (!(by in L)) return null; return [lab('Số ' + lc(L[by])), f0.format(groupBy(by, '', 'count').filter(g => !g.na).length), ''];
      case 'missing': if (!m) return null; return [lab('Chưa có dữ liệu'), K.rows ? pct(Math.max(0, 1 - K.Cn[j] / K.rows)) : '—', esc(m.short || m.label)];
      case 'latest': { if (!m || !ds.time) return null; const a = aggOf(m), g = groupBy('t', m.k, a).sort((x, y) => x.q - y.q); if (!g.length) return null; const l = g[g.length - 1], p = g[g.length - 2], ch = p && p.v ? l.v / p.v - 1 : null;
        return [lab(mName(m, a) + ' kỳ gần nhất'), val(l.v, m.unit), esc(ml(l.l)) + (ch == null ? '' : ` · ${ch >= 0 ? 'tăng' : 'giảm'} ${f2.format(Math.abs(ch) * 100)}% so với ${esc(ml(p.l))}`)] }
      case 'top': { if (!m || !(by in L)) return null; const a = aggOf(m), g = groupBy(by, m.k, a).filter(r => !r.na); if (!g.length) return null; const t0 = g.reduce((b, r) => r.v > b.v ? r : b, g[0]); return [lab(L[by] + ' cao nhất'), t0.l, `${esc(mName(m, a))}: ${esc(val(t0.v, m.unit))}`] }
    }
    return null;
  }
  function bpKpis() {                                           // thẻ KPI do bản thiết kế chọn; null = không có bản thiết kế cho bảng này (dùng cách cũ)
    if (!D.bp || !Array.isArray(D.bp.kpis)) return null;
    const mine = D.bp.kpis.filter(x => x.ds === ds.name); if (!mine.length) return null;
    const K = kpiData(), cards = mine.filter(x => x.on !== false).map(it => ({ it, c: kpiCard(it, K) })).filter(x => x.c);
    if (!cards.length) return '<div class="kpis none"></div>';
    return `<div class="kpis" style="--n:${Math.min(cards.length, 5)}">${cards.map(({ it, c }, i) => `<div class="kpi ${i === 0 ? 'hero' : ''}" data-cid="${esc(it.id)}">${D.edit ? '<button class="kx" data-ed="hide" title="Ẩn thẻ này" aria-label="Ẩn thẻ này">✕</button>' : ''}<span title="${esc(c[0])}">${esc(c[0])}</span><b class="${String(c[1]).length > 14 ? 'long' : ''}" title="${esc(c[1])}">${esc(c[1])}</b>${c[2] ? `<small>${c[2]}</small>` : ''}</div>`).join('')}</div>` }
  const bpAgt = () => { const m = cm(); if (!(D.bp && Array.isArray(D.bp.kpis) && D.bp.kpis.some(x => x.ds === ds.name)) || !m || m.rate) return ''; const a = agg();
    return `<div class="seg" role="group" aria-label="Cách tổng hợp">${[['sum', 'Tổng'], ['avg', 'Trung bình']].map(([q, l]) => `<button data-ag="${q}" class="${a === q ? 'on' : ''}">${l}</button>`).join('')}</div>` };
  function kpiHTML() {
    const bk = bpKpis(); if (bk != null) return bk;
    const k = kpiData(), m = cm(), j = m ? ds.meas.indexOf(m) : -1, a = agg(), cards = [];
    const agt = `<div class="agt" role="group" aria-label="Cách tổng hợp">${[['sum', 'Tổng'], ['avg', 'Trung bình']].map(([q, t]) => `<button data-ag="${q}" class="${a === q ? 'on' : ''}">${t}</button>`).join('')}</div>`;
    if (m) cards.push([mName(m, a), val(a === 'avg' ? (k.Cn[j] ? k.S[j] / k.Cn[j] : null) : k.S[j], m.unit), m.add || a !== 'sum' ? '' : 'Chỉ số này thường không cộng được; cân nhắc dùng Trung bình', true, agt]);
    if (!(D.bp && Array.isArray(D.bp.kpis))) cards.push(['Số bản ghi', f0.format(k.rows), '']);
    if (m && a !== 'avg' && !(D.bp && Array.isArray(D.bp.kpis))) cards.push(['Trung bình mỗi bản ghi', val(k.Cn[j] ? k.S[j] / k.Cn[j] : null, m.unit), esc(lc(stripTong(m.label)))]);
    const o = ds.meas.findIndex((x, i) => i !== j); if (o >= 0 && cards.length < 4) { const mo = ds.meas[o], ao = aggOf(mo); cards.push([mName(mo, ao), val(ao === 'avg' ? (k.Cn[o] ? k.S[o] / k.Cn[o] : null) : k.S[o], mo.unit), '']) }
    return `<div class="kpis" style="--n:${cards.length}">${cards.map(([l, v, s, h, x]) => `<div class="kpi ${h ? 'hero' : ''}"><span title="${esc(l)}">${esc(l)}</span><b>${esc(v)}</b>${s ? `<small>${s}</small>` : ''}${x || ''}</div>`).join('')}</div>`;
  }
  function narrative() {
    const first = c => String(c || '').split(' ')[0], order = { Cao: 0, 'Trung bình': 1, 'Thấp': 2 };
    const vf = x => ({ ok: ['ok', 'Đã kiểm số liệu'], mismatch: ['Bad', (x.calc_mismatch || []).length ? 'Phép tính không khớp' : 'Số liệu chưa khớp bảng'], unverified: ['Thấp', 'Chưa kiểm được'] })[x.verify];
    const vn = x => (x.calc_mismatch || []).length ? 'Phép tính không khớp: ' + x.calc_mismatch.join('; ') : (x.cell_mismatch || []).length ? 'Số trích không khớp bảng kết quả: ' + x.cell_mismatch.join('; ') : (x.check || []).length ? 'Cần kiểm tra số liệu: số ' + x.check.join(', ') + ' chưa khớp bảng kết quả nào' : x.verify === 'unverified' ? 'Chưa kiểm được bằng chứng này (không có phép tính để tính lại, ô trích không đối chiếu được với bảng)' : '';
    const ins = D.insights.map((x, i) => `<div class="card in"><div class="n">${i + 1}</div><div><h4>${esc(x.title)}${x.confidence ? `<span class="tag ${esc(first(x.confidence))}">Độ tin cậy: ${esc(x.confidence)}</span>` : ''}${(b => b ? `<span class="tag ${b[0]}">${esc(b[1])}</span>` : '')(vf(x))}</h4><p><b>Bằng chứng:</b> ${esc(x.evidence || '')}</p>${vn(x) ? `<p class="vnote ${x.verify === 'unverified' ? 'un' : ''}">${x.verify === 'unverified' ? 'ⓘ' : '⚠'} ${esc(vn(x))}</p>` : ''}</div></div>`).join('');
    const acts = [...D.actions].sort((a, b) => (order[a.priority] ?? 9) - (order[b.priority] ?? 9)).map(a => `<div class="act"><span class="pr ${esc(first(a.priority))}">${esc(a.priority || '')}</span><b>${esc(a.text)}</b><span class="im">${esc(a.impact || '')}</span></div>`).join('');
    return (ins && blk('ins') ? `<h2 class="sec">Phát hiện chính</h2><div class="ins">${ins}</div>` : '') + (acts && blk('act') ? `<h2 class="sec">Khuyến nghị hành động</h2><div class="acts">${acts}</div>` : '') +
      (D.risks.length && blk('risk') ? `<h2 class="sec">Rủi ro cần lưu ý</h2><div class="card"><ul class="risks">${D.risks.map(r => `<li>${esc(r)}</li>`).join('')}</ul></div>` : '');
  }
  function shell() {
    const parts = d => String(d.name).split('::'), files = new Set(D.datasets.map(d => parts(d)[0]));
    const tabLabel = d => { const p = parts(d), sh = d.title && p.length > 1 ? d.title : p.slice(1).join(' · '); return files.size > 1 ? (sh ? `${p[0].replace(/\.[^.]+$/, '')} · ${sh}` : p[0].replace(/\.[^.]+$/, '')) : (sh || p[0]) };
    const sw = D.datasets.length > 1 ? `<nav class="dtabs" role="tablist" aria-label="Bảng dữ liệu (đổi góc nhìn)">${D.datasets.map((d, i) => `<button role="tab" class="dtab ${d === ds ? 'on' : ''}" aria-selected="${d === ds}" data-ds="${i}" title="${esc(d.name)}"><span>${esc(tabLabel(d))}</span><small>${f0.format(d.n_src)} dòng</small></button>`).join('')}</nav>` : '';
    $('#app').innerHTML = `<header class="top"><div class="wrap"><div><span class="eyebrow">Bảng điều khiển · ${esc(D.date)}</span><h1>${esc(D.title)}</h1>${D.question ? `<p class="q">${esc(D.question)}</p>` : ''}</div>
<div class="tools"><button class="ibtn" id="th" title="Đổi giao diện sáng hoặc tối" aria-label="Đổi giao diện sáng hoặc tối">${I.moon}</button><button class="ibtn" id="pr" title="In" aria-label="In">${I.print}</button></div></div></header>
<div class="wrap flx lay-${(D.bp && D.bp.layout) || 'auto'}">${sw}${D.summary && blk('ans') ? `<div class="ans"><span class="ic">${I.check}</span><div><b>Câu trả lời ngắn</b><p>${esc(D.summary)}</p></div></div>` : ''}
<div class="filters"><div class="fbar" id="fb"></div></div><div id="kp"></div><div class="grid" id="gr"></div>
${ds.cube ? `<div class="note">Dữ liệu lớn (${f0.format(ds.n_src)} dòng) nên được gộp theo các chiều trước khi nhúng${ds.dropped.length ? ` (bỏ chiều: ${esc(ds.dropped.join(', '))})` : ''}. Tổng, trung bình và số bản ghi vẫn chính xác; không xem được từng dòng gốc.</div>` : ''}
<div id="nar">${narrative()}</div><div class="foot">Số liệu tính từ dữ liệu đã làm sạch (${esc(ds.name)}). Lọc và tính toán ngay trong trình duyệt, không cần kết nối mạng.</div></div><div id="tt"></div>`;
  }
  function render() { if (!$('#fb')) shell(); $('#fb').innerHTML = filtersHTML(); $('#kp').innerHTML = kpiHTML(); $('#gr').innerHTML = chartsHTML() + tableCard(); paintTrends(); }

  /* ---- sự kiện ---- */
  document.addEventListener('click', e => {
    const t = e.target, ed = t.closest('[data-ed]'), rs = t.closest('[data-reset]'), cl = t.closest('[data-clr]'), q = t.closest('[data-q][data-k]'), so = t.closest('[data-sort]'), mm = t.closest('[data-m]'), ag = t.closest('[data-ag]');
    if (ed && D.edit) { const cd = ed.closest('[data-cid]'); parent.postMessage({ type: 'mc-edit', op: ed.dataset.ed, id: cd ? cd.dataset.cid : '' }, location.origin); return }
    if (rs) { st.sel = {}; st.from = 0; st.to = ds.time ? V.t.length - 1 : 0; render() }
    else if (cl) { delete st.sel[cl.dataset.clr]; render() }
    else if (mm) { st.m = mm.dataset.m; render() }
    else if (ag) { const m = cm(); if (m) { st.ag[m.k] = ag.dataset.ag; render() } }
    else if (so) { const k = so.dataset.sort; st.tb.dir = st.tb.sort === k ? -st.tb.dir : (k === 'l' ? 1 : -1); st.tb.sort = k; render() }
    else if (q && !t.closest('input')) { const k = q.dataset.k, v = +q.dataset.q, s = st.sel[k] = st.sel[k] || new Set(); s.has(v) ? s.delete(v) : s.add(v); render() }
    else if (t.closest('[data-ds]')) { openK.clear(); init(+t.closest('[data-ds]').dataset.ds) }
    else if (t.closest('#th')) { const r = document.documentElement; r.dataset.theme = r.dataset.theme === 'dark' ? 'light' : 'dark'; render() }
    else if (t.closest('#pr')) print();
  });
  document.addEventListener('change', e => { const t = e.target;
    if (t.dataset.sc) { const k = t.dataset.sc, v = +t.dataset.q, s = st.sel[k] = st.sel[k] || new Set(); t.checked ? s.add(v) : s.delete(v); render() }
    else if (t.dataset.r) { st[t.dataset.r] = +t.value; if (st.from > st.to) { if (t.dataset.r === 'from') st.to = st.from; else st.from = st.to } render() }
    else if (t.dataset.tb) { st.tb.by = t.value; resetSort(); render() }
  });
  document.addEventListener('toggle', e => { const d = e.target; if (d.dataset && d.dataset.sl) d.open ? openK.add(d.dataset.sl) : openK.delete(d.dataset.sl) }, true);
  document.addEventListener('mousemove', e => { const el = e.target.closest ? e.target.closest('[data-tt]') : null, b = $('#tt'); if (!b) return;
    if (!el) { b.style.display = 'none'; return } b.textContent = el.dataset.tt; b.style.display = 'block'; b.style.left = Math.min(e.clientX + 14, innerWidth - 300) + 'px'; b.style.top = (e.clientY + 16) + 'px' });
  document.addEventListener('mousedown', e => { document.querySelectorAll('details.sl[open]').forEach(d => { if (!d.contains(e.target)) { d.open = false; openK.delete(d.dataset.sl) } }) });
  window.addEventListener('message', e => { const m = e.data; if (e.origin !== location.origin || !m || m.type !== 'mc-plan' || !Array.isArray(m.plan)) return;
    const was = JSON.stringify([D.bp && D.bp.layout, D.bp && D.bp.blocks]); D.plan = m.plan; if (m.bp && typeof m.bp === 'object') { D.bp = m.bp; applyFont(m.bp.font) }
    if (!ds) return; const y = window.scrollY; if (JSON.stringify([D.bp && D.bp.layout, D.bp && D.bp.blocks]) !== was) $('#app').innerHTML = ''; render(); window.scrollTo(0, y) });
  /* đổi phông tức thì khi người dùng chọn ở thư viện (bản xem thử): cập nhật biến CSS và nạp phông web nếu cần */
  function applyFont(k) { const F = (D.fonts || {})[k]; if (!F) return; let s = document.getElementById('fontvars');
    if (!s) { s = document.createElement('style'); s.id = 'fontvars'; document.head.appendChild(s) } s.textContent = ':root{--font:' + F.body + ';--fh:' + F.head + '}';
    let l = document.getElementById('fontlink'); if (F.url) { if (!l) { l = document.createElement('link'); l.id = 'fontlink'; l.rel = 'stylesheet'; document.head.appendChild(l) } if (l.getAttribute('href') !== F.url) l.href = F.url } else if (l) l.removeAttribute('href') }
  let rz; window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => { if (ds) paintTrends() }, 120) });
  if (!D.datasets.length) { $('#app').innerHTML = `<div class="wrap"><h1>${esc(D.title)}</h1><div class="note">Không có bảng dữ liệu phù hợp để dựng bảng điều khiển tương tác (cần ít nhất một cột phân loại hoặc cột ngày tháng).</div></div>` } else init(0);
})();
