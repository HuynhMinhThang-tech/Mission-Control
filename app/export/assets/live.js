/* Bảng điều khiển tương tác. Bố cục do hệ thống tự chọn theo dữ liệu (không có ô chọn trên từng biểu đồ);
   người xem chỉ dùng: bộ lọc chung, chọn chỉ số, và bấm vào biểu đồ để lọc chéo. Mọi phép tính chạy trong trình duyệt. */
(function () {
  'use strict';
  const D = JSON.parse(document.getElementById('data').textContent);
  const $ = (s, r = document) => r.querySelector(s);
  const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const PAL = ['#4F46E5', '#06B6D4', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'];
  const mkf = d => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: d });
  const f0 = mkf(0), f1 = mkf(1), f2 = mkf(2);
  const compact = v => { if (v == null || !isFinite(v)) return '—'; const a = Math.abs(v);
    if (a >= 1e9) return f1.format(v / 1e9) + ' tỷ'; if (a >= 1e6) return f1.format(v / 1e6) + ' triệu'; if (a >= 1e4) return f1.format(v / 1e3) + ' nghìn'; return f1.format(v) };
  const val = (v, u) => u ? compact(v) + ' ' + u : compact(v);
  const full = (v, m) => v == null || !isFinite(v) ? '' : (m && m.dec === 0 ? f0 : f2).format(v);
  const pct = x => f1.format(x * 100) + '%';
  const ml = s => { const p = String(s).split('-'); return p.length === 2 && /^\d{4}$/.test(p[0]) ? 'T' + (+p[1]) + '/' + p[0] : s };
  const lc = s => s.charAt(0).toLowerCase() + s.slice(1);
  const stripTong = s => s.replace(/^tổng\s+/i, '');
  const mName = (m, a) => !m ? 'Số bản ghi' : a === 'avg' ? (/^trung bình/i.test(m.label) ? m.label : 'Trung bình ' + lc(stripTong(m.label)))
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
    st = { sel: {}, from: 0, to: ds.time ? V.t.length - 1 : 0, m: ds.meas[0] ? ds.meas[0].k : '', tb: { by: P.tableBy, sort: '', dir: -1 } };
    resetSort(); render();
  }
  const cm = () => ds.meas.find(m => m.k === st.m) || null;
  const agg = () => { const m = cm(); return m ? (m.avg ? 'avg' : 'sum') : 'count' };
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
  function donutHTML(g, by, m, a) {
    let rows = g.filter(r => r.v > 0).sort((x, y) => (x.na - y.na) || (y.v - x.v));
    if (rows.length > 6) { const rest = rows.slice(5); rows = [...rows.slice(0, 5), { q: -1, l: 'Khác', v: rest.reduce((s, r) => s + r.v, 0), rows: rest.reduce((s, r) => s + r.rows, 0), na: false }] }
    const tot = rows.reduce((s, r) => s + r.v, 0) || 1, R = 66, Cc = 2 * Math.PI * R, u = m ? m.unit : ''; let acc = 0, pi = 0;
    const col = r => r.na ? 'var(--na)' : PAL[pi++ % PAL.length], cols = rows.map(col); acc = 0;
    const segs = rows.map((r, i) => { const len = r.v / tot * Cc, o = acc, gap = rows.length > 1 ? 2.5 : 0; acc += len;
      return `<circle class="seg ${r.q >= 0 ? cls(by, r.q) : ''}" ${r.q >= 0 ? `data-k="${by}" data-q="${r.q}"` : ''} data-tt="${tt(r, m, a)}" cx="88" cy="88" r="${R}" fill="none" style="stroke:${cols[i]}" stroke-width="24" stroke-dasharray="${Math.max(len - gap, .1)} ${Cc - len + gap}" stroke-dashoffset="${-o}" transform="rotate(-90 88 88)"/>` }).join('');
    return `<div class="donut"><svg viewBox="0 0 176 176" role="img"><circle cx="88" cy="88" r="${R}" fill="none" stroke-width="24" style="stroke:var(--track)"/>${segs}
<text class="t1" x="88" y="87" text-anchor="middle">${esc(a === 'count' ? f0.format(tot) : compact(tot))}</text><text class="t2" x="88" y="106" text-anchor="middle">${esc(a === 'count' ? 'bản ghi' : (u || 'tổng'))}</text></svg>
<div class="legend">${rows.map((r, i) => `<div class="lg ${r.na ? 'na' : ''} ${r.q >= 0 ? cls(by, r.q) : ''}" ${r.q >= 0 ? `data-k="${by}" data-q="${r.q}"` : ''} data-tt="${tt(r, m, a)}"><i style="background:${cols[i]}"></i><span title="${esc(r.l)}">${esc(r.l)}</span><b>${pct(r.v / tot)}</b></div>`).join('')}</div></div>`;
  }
  /* các mốc trục "tròn" (1, 2, 2,5, 5 × 10^n) để trục dễ đọc */
  function niceTicks(lo, hi, n = 4) {
    const span = (hi - lo) || 1, raw = span / n, p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p, step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
    const a = Math.floor(lo / step + 1e-9) * step, b = Math.ceil(hi / step - 1e-9) * step, t = [];
    for (let v = a; v <= b + step / 2; v += step) t.push(+v.toFixed(8)); return t.length > 1 ? t : [a, a + step];
  }
  function trendSVG(g, W, m, a) {
    const H = 250, pl = 58, pr = 14, pt = 12, pb = 30, n = g.length, vs = g.map(r => r.v);
    const tk = niceTicks(Math.min(...vs, 0), Math.max(...vs, 0)), mn = tk[0], mx = tk[tk.length - 1], sp = (mx - mn) || 1;
    const X = i => n === 1 ? pl + (W - pl - pr) / 2 : pl + i * (W - pl - pr) / (n - 1), Y = v => pt + (mx - v) / sp * (H - pt - pb);
    const grid = tk.map(v => { const y = Y(v); return `<line class="gl" x1="${pl}" x2="${W - pr}" y1="${y}" y2="${y}"/><text x="${pl - 10}" y="${y + 4}" text-anchor="end">${esc(a === 'count' ? f0.format(v) : compact(v))}</text>` }).join('');
    const pts = g.map((r, i) => [X(i), Y(r.v)]), base = Y(Math.max(mn, 0)), every = Math.ceil(n / Math.max(2, Math.floor((W - pl - pr) / 70))), step = n > 1 ? (W - pl - pr) / (n - 1) : 60;
    const id = 'g' + Math.random().toString(36).slice(2, 7), anyS = selOn('t');
    return `<svg viewBox="0 0 ${W} ${H}" role="img"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--acc);stop-opacity:.22"/><stop offset="1" style="stop-color:var(--acc);stop-opacity:0"/></linearGradient></defs>${grid}
<path d="M${pts.map(p => p.join(',')).join('L')}L${X(n - 1)},${base}L${X(0)},${base}Z" fill="url(#${id})"/><polyline class="ln" points="${pts.map(p => p.join(',')).join(' ')}"/>
${g.map((r, i) => `<g data-k="t" data-q="${r.q}" data-tt="${tt({ l: ml(r.l), v: r.v, rows: r.rows }, m, a)}"><rect class="hit" x="${pts[i][0] - step / 2}" y="${pt}" width="${step}" height="${H - pt - pb}"/>
${n <= 18 || (anyS && isSel('t', r.q)) ? `<circle class="pt ${anyS && isSel('t', r.q) ? 'sel' : ''}" cx="${pts[i][0]}" cy="${pts[i][1]}" r="4.5" style="${anyS && !isSel('t', r.q) ? 'opacity:.35' : ''}"/>` : ''}
${i % every === 0 || i === n - 1 && (n - 1) % every > every / 2 ? `<text x="${pts[i][0]}" y="${H - 8}" text-anchor="${i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle'}">${esc(ml(r.l))}</text>` : ''}</g>`).join('')}</svg>`;
  }

  /* dòng nhận xét ngắn dưới tiêu đề, tính trực tiếp từ dữ liệu đang hiển thị */
  function lead(type, g, m, a) {
    if (!g.length) return '';
    const u = m ? m.unit : '', v = x => a === 'count' ? f0.format(x) : val(x, u), real = g.filter(r => !r.na), add = a !== 'avg';
    if (type === 'trend') { const f = g[0], l = g[g.length - 1], pk = g.reduce((b, r) => r.v > b.v ? r : b, g[0]);
      const ch = f.v ? (l.v / f.v - 1) : null;
      return g.length > 1 ? `${ml(f.l)} đến ${ml(l.l)}${ch == null ? '' : (ch >= 0 ? ': tăng ' : ': giảm ') + f1.format(Math.abs(ch) * 100) + '%'} · cao nhất <b>${esc(ml(pk.l))}</b> (${esc(v(pk.v))})` : '' }
    const top = (real.length ? real : g).reduce((b, r) => r.v > b.v ? r : b), tot = g.reduce((s, r) => s + Math.max(r.v, 0), 0);
    return add && tot > 0 ? `<b>${esc(top.l)}</b> dẫn đầu, chiếm ${pct(top.v / tot)} tổng` : `Cao nhất: <b>${esc(top.l)}</b> (${esc(v(top.v))})`;
  }
  function chartsHTML() {
    const m = cm(), a = agg(), cards = []; jobs = [];
    if (P.timeOk) cards.push({ t: 'trend', by: 't' });
    if (P.donutK) cards.push({ t: a === 'avg' ? 'bars' : 'donut', by: P.donutK });
    P.bars.forEach(k => cards.push({ t: 'bars', by: k }));
    const sp = cards.map(() => 6); let i0 = 0;
    if (cards[0] && cards[0].t === 'trend') { if (cards[1] && cards[1].by === P.donutK) { sp[0] = 8; sp[1] = 4; i0 = 2 } else { sp[0] = 12; i0 = 1 } }
    else if (cards[0] && cards[0].by === P.donutK && cards[1]) { sp[0] = 4; sp[1] = 8; i0 = 2 }
    if ((cards.length - i0) % 2 === 1) sp[cards.length - 1] = 12;
    return cards.map((c, i) => {
      const g = groupBy(c.by, m ? m.k : '', a), name = mName(m, a), title = `${name} theo ${c.t === 'trend' ? 'tháng' : lc(L[c.by])}`;
      const body = !g.length ? '<div class="empty">Không có dữ liệu với bộ lọc hiện tại.</div>' : c.t === 'trend' ? (jobs.push({ id: 'tr' + i, g, m, a }), `<div class="trend" id="tr${i}"></div>`) : c.t === 'donut' ? donutHTML(g, c.by, m, a) : barsHTML(g, c.by, m, a);
      return `<section class="card c${sp[i]}"><div class="ch"><h3>${esc(title)}</h3><p>${lead(c.t, g, m, a)}</p></div>${body}</section>`;
    }).join('');
  }
  function paintTrends() { jobs.forEach(j => { const el = document.getElementById(j.id); if (el) el.innerHTML = trendSVG(j.g, Math.max(320, Math.floor(el.clientWidth)), j.m, j.a) }) }

  function tableCard() {
    const t = st.tb, by = t.by; if (!by) return '';
    const mc = ds.meas.slice(0, 4), head = [['l', L[by], false], ['rows', 'Số bản ghi', true], ...mc.map(m => [m.k, mName(m, m.avg ? 'avg' : 'sum'), true])];
    const by2 = {}; mc.forEach(m => by2[m.k] = groupBy(by, m.k, m.avg ? 'avg' : 'sum')); const base = groupBy(by, '', 'count');
    let rows = base.map(b => { const o = { l: b.l, rows: b.rows }; mc.forEach(m => { const x = by2[m.k].find(y => y.q === b.q); o[m.k] = x ? x.v : null }); return o });
    rows.sort((x, y) => (typeof x[t.sort] === 'string' ? x[t.sort].localeCompare(y[t.sort], 'vi', { numeric: true }) : (x[t.sort] ?? -Infinity) - (y[t.sort] ?? -Infinity)) * t.dir); rows = rows.slice(0, 60);
    const cell = (v, k) => k === 'l' ? esc(by === 't' ? ml(v) : v) : k === 'rows' ? f0.format(v) : esc(full(v, mc.find(m => m.k === k)));
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
    return `${rng}${P.filters.map(one).join('')}${met}<button class="lnk" data-reset="1" ${filtered ? '' : 'disabled'}>Xóa bộ lọc</button><span class="sp"></span><span class="status"><b>${f0.format(n)}</b> / ${f0.format(ds.n_src)} bản ghi</span>`;
  }
  function kpiHTML() {
    const k = kpiData(), m = cm(), j = m ? ds.meas.indexOf(m) : -1, a = agg(), cards = [];
    if (m) cards.push([mName(m, a), val(a === 'avg' ? (k.Cn[j] ? k.S[j] / k.Cn[j] : null) : k.S[j], m.unit), '', true]);
    cards.push(['Số bản ghi', f0.format(k.rows), '']);
    if (m && a !== 'avg') cards.push(['Trung bình mỗi bản ghi', val(k.Cn[j] ? k.S[j] / k.Cn[j] : null, m.unit), esc(lc(stripTong(m.label)))]);
    const o = ds.meas.findIndex((x, i) => i !== j); if (o >= 0 && cards.length < 4) { const mo = ds.meas[o], ao = mo.avg ? 'avg' : 'sum'; cards.push([mName(mo, ao), val(ao === 'avg' ? (k.Cn[o] ? k.S[o] / k.Cn[o] : null) : k.S[o], mo.unit), '']) }
    return `<div class="kpis" style="--n:${cards.length}">${cards.map(([l, v, s, h]) => `<div class="kpi ${h ? 'hero' : ''}"><span title="${esc(l)}">${esc(l)}</span><b>${esc(v)}</b>${s ? `<small>${s}</small>` : ''}</div>`).join('')}</div>`;
  }
  function narrative() {
    const first = c => String(c || '').split(' ')[0], order = { Cao: 0, 'Trung bình': 1, 'Thấp': 2 };
    const ins = D.insights.map((x, i) => `<div class="card in"><div class="n">${i + 1}</div><div><h4>${esc(x.title)}${x.confidence ? `<span class="tag ${esc(first(x.confidence))}">Độ tin cậy: ${esc(x.confidence)}</span>` : ''}${(x.check || []).length ? `<span class="tag Thấp" title="Số ${esc(x.check.join(', '))} chưa khớp bảng kết quả nào">Cần kiểm tra số liệu</span>` : ''}</h4><p><b>Bằng chứng:</b> ${esc(x.evidence || '')}</p></div></div>`).join('');
    const acts = [...D.actions].sort((a, b) => (order[a.priority] ?? 9) - (order[b.priority] ?? 9)).map(a => `<div class="act"><span class="pr ${esc(first(a.priority))}">${esc(a.priority || '')}</span><b>${esc(a.text)}</b><span class="im">${esc(a.impact || '')}</span></div>`).join('');
    return (ins ? `<h2 class="sec">Phát hiện chính</h2><div class="ins">${ins}</div>` : '') + (acts ? `<h2 class="sec">Khuyến nghị hành động</h2><div class="acts">${acts}</div>` : '') +
      (D.risks.length ? `<h2 class="sec">Rủi ro cần lưu ý</h2><div class="card"><ul class="risks">${D.risks.map(r => `<li>${esc(r)}</li>`).join('')}</ul></div>` : '');
  }
  function shell() {
    const parts = d => String(d.name).split('::'), files = new Set(D.datasets.map(d => parts(d)[0]));
    const tabLabel = d => { const p = parts(d), sh = d.title && p.length > 1 ? d.title : p.slice(1).join(' · '); return files.size > 1 ? (sh ? `${p[0].replace(/\.[^.]+$/, '')} · ${sh}` : p[0].replace(/\.[^.]+$/, '')) : (sh || p[0]) };
    const sw = D.datasets.length > 1 ? `<nav class="dtabs" role="tablist" aria-label="Bảng dữ liệu (đổi góc nhìn)">${D.datasets.map((d, i) => `<button role="tab" class="dtab ${d === ds ? 'on' : ''}" aria-selected="${d === ds}" data-ds="${i}" title="${esc(d.name)}"><span>${esc(tabLabel(d))}</span><small>${f0.format(d.n_src)} dòng</small></button>`).join('')}</nav>` : '';
    $('#app').innerHTML = `<header class="top"><div class="wrap"><div><span class="eyebrow">Bảng điều khiển · ${esc(D.date)}</span><h1>${esc(D.title)}</h1>${D.question ? `<p class="q">${esc(D.question)}</p>` : ''}</div>
<div class="tools"><button class="ibtn" id="th" title="Đổi giao diện sáng hoặc tối" aria-label="Đổi giao diện sáng hoặc tối">${I.moon}</button><button class="ibtn" id="pr" title="In" aria-label="In">${I.print}</button></div></div></header>
<div class="wrap">${sw}${D.summary ? `<div class="ans"><span class="ic">${I.check}</span><div><b>Câu trả lời ngắn</b><p>${esc(D.summary)}</p></div></div>` : ''}
<div class="filters"><div class="fbar" id="fb"></div></div><div id="kp"></div><div class="grid" id="gr"></div>
${ds.cube ? `<div class="note">Dữ liệu lớn (${f0.format(ds.n_src)} dòng) nên được gộp theo các chiều trước khi nhúng${ds.dropped.length ? ` (bỏ chiều: ${esc(ds.dropped.join(', '))})` : ''}. Tổng, trung bình và số bản ghi vẫn chính xác; không xem được từng dòng gốc.</div>` : ''}
<div id="nar">${narrative()}</div><div class="foot">Số liệu tính từ dữ liệu đã làm sạch (${esc(ds.name)}). Lọc và tính toán ngay trong trình duyệt, không cần kết nối mạng.</div></div><div id="tt"></div>`;
  }
  function render() { if (!$('#fb')) shell(); $('#fb').innerHTML = filtersHTML(); $('#kp').innerHTML = kpiHTML(); $('#gr').innerHTML = chartsHTML() + tableCard(); paintTrends(); }

  /* ---- sự kiện ---- */
  document.addEventListener('click', e => {
    const t = e.target, rs = t.closest('[data-reset]'), cl = t.closest('[data-clr]'), q = t.closest('[data-q][data-k]'), so = t.closest('[data-sort]'), mm = t.closest('[data-m]');
    if (rs) { st.sel = {}; st.from = 0; st.to = ds.time ? V.t.length - 1 : 0; render() }
    else if (cl) { delete st.sel[cl.dataset.clr]; render() }
    else if (mm) { st.m = mm.dataset.m; render() }
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
  let rz; window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => { if (ds) paintTrends() }, 120) });
  if (!D.datasets.length) { $('#app').innerHTML = `<div class="wrap"><h1>${esc(D.title)}</h1><div class="note">Không có bảng dữ liệu phù hợp để dựng bảng điều khiển tương tác (cần ít nhất một cột phân loại hoặc cột ngày tháng).</div></div>` } else init(0);
})();
