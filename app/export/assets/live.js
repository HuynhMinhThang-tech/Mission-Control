(function () {
  const D = JSON.parse(document.getElementById('data').textContent);
  const $ = (s, r = document) => r.querySelector(s);
  const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const PAL = ['#1B3A5C', '#2A9D8F', '#E9A23B', '#E76F51', '#6C7A89', '#7B6CD9', '#5BA55B', '#D1627F', '#3D8BCD', '#B5A642'];
  const nf = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 }), nf2 = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 });
  const fmt = (v, u) => { if (v == null || !isFinite(v)) return '—'; const a = Math.abs(v); let s;
    if (a >= 1e9) s = nf.format(v / 1e9) + ' tỷ'; else if (a >= 1e6) s = nf.format(v / 1e6) + ' triệu'; else if (a >= 1e4) s = nf.format(v / 1e3) + ' nghìn'; else s = nf.format(v);
    return u ? s + ' ' + u : s };
  const AGG = { sum: 'Tổng', avg: 'Trung bình', count: 'Số dòng' };
  const TYPES = { bar: 'Cột ngang', col: 'Cột dọc', line: 'Đường', donut: 'Tròn' };
  let ds, C, V, L, M, st, openK = new Set();

  function init(i) {
    if ($('#fb')) $('#app').innerHTML = '';
    ds = D.datasets[i]; C = {}; V = {}; L = {}; M = {};
    ds.dims.forEach(d => { C[d.k] = d.codes; V[d.k] = d.vals; L[d.k] = d.label });
    if (ds.time) { C.t = ds.time.codes; V.t = ds.time.vals; L.t = ds.time.label }
    ds.meas.forEach(m => M[m.k] = m.vals);
    const m0 = ds.meas[0] ? ds.meas[0].k : '', ag = m0 ? (ds.meas[0].avg ? 'avg' : 'sum') : 'count', cfg = [];
    if (ds.time && V.t.length > 1) cfg.push({ type: 'line', by: 't', m: m0, agg: ag });
    ds.dims.slice(0, 3).forEach((d, j) => cfg.push({ type: j === 1 && V[d.k].length <= 8 ? 'donut' : 'bar', by: d.k, m: m0, agg: ag }));
    if (ds.meas[1] && ds.dims[0]) cfg.push({ type: 'col', by: ds.dims[0].k, m: ds.meas[1].k, agg: ds.meas[1].avg ? 'avg' : 'sum' });
    st = { sel: {}, from: 0, to: ds.time ? V.t.length - 1 : 0, cfg, tbl: { mode: 'group', by: (ds.dims[0] || { k: 't' }).k, sort: 'v', dir: -1 } };
    render();
  }
  const unitOf = k => { const m = ds.meas.find(x => x.k === k); return m ? m.unit : '' };
  const labOf = k => { const m = ds.meas.find(x => x.k === k); return m ? m.label : 'Số dòng' };
  const keys = () => Object.keys(L);

  function pass(i, skip) {
    if (ds.time) { const c = C.t[i], full = st.from === 0 && st.to === V.t.length - 1; if (c < 0 ? !full : (c < st.from || c > st.to)) return false }
    for (const k in st.sel) { if (k === skip) continue; const s = st.sel[k]; if (s.size && !s.has(C[k][i])) return false }
    return true;
  }
  function groupBy(by, mk, agg) {
    const K = V[by].length, s = new Float64Array(K), c = new Float64Array(K), r = new Float64Array(K), codes = C[by], mv = mk ? M[mk] : null;
    const mj = mk ? ds.meas.findIndex(m => m.k === mk) : -1, mcc = mk && ds.mc ? ds.mc[mj] : null;
    for (let i = 0; i < ds.n; i++) { if (!pass(i, by)) continue; const q = codes[i]; if (q < 0) continue; const w = ds.w ? ds.w[i] : 1; r[q] += w;
      if (mv) { const v = mv[i]; if (v != null) { s[q] += v; c[q] += mcc ? mcc[i] : 1 } } }
    const a = mk ? agg : 'count';
    return V[by].map((l, q) => ({ q, l, rows: r[q], v: a === 'count' ? r[q] : a === 'avg' ? (c[q] ? s[q] / c[q] : null) : s[q] })).filter(g => g.rows > 0 && g.v != null);
  }
  function kpiData() {
    let rows = 0; const S = ds.meas.map(() => 0), Cn = ds.meas.map(() => 0);
    for (let i = 0; i < ds.n; i++) { if (!pass(i, null)) continue; rows += ds.w ? ds.w[i] : 1;
      ds.meas.forEach((m, j) => { const v = M[m.k][i]; if (v != null) { S[j] += v; Cn[j] += ds.mc ? ds.mc[j][i] : 1 } }) }
    return { rows, S, Cn };
  }

  /* ---------- biểu đồ SVG ---------- */
  const tt = (g, c) => esc(`${g.l}: ${nf2.format(g.v)}${unitOf(c.m) ? ' ' + unitOf(c.m) : ''} · ${nf.format(g.rows)} dòng`);
  const isSel = (k, q) => { const s = st.sel[k]; return !s || !s.size || s.has(q) };
  const mk = (k, q, g, c) => `class="mk ${isSel(k, q) ? '' : 'dim'}" data-k="${k}" data-q="${q}" data-tt="${tt(g, c)}"`;
  function barSVG(g, c) {
    const rows = g.sort((a, b) => b.v - a.v).slice(0, 10), W = 520, rh = 27, H = rows.length * rh + 6, lw = 138, mx = Math.max(...rows.map(r => r.v), 0) || 1, u = unitOf(c.m);
    return `<svg viewBox="0 0 ${W} ${H}">${rows.map((r, i) => { const y = 4 + i * rh, w = Math.max(0, (W - lw - 96) * r.v / mx);
      return `<g ${mk(c.by, r.q, r, c)}><rect x="0" y="${y - 2}" width="${W}" height="${rh - 2}" fill="transparent"/><text x="${lw - 8}" y="${y + 14}" text-anchor="end">${esc(r.l.length > 22 ? r.l.slice(0, 21) + '…' : r.l)}</text><rect x="${lw}" y="${y + 2}" width="${w}" height="${rh - 10}" rx="4" fill="${PAL[(c.by === 't' ? 0 : 1)]}"/><text class="v" x="${lw + w + 6}" y="${y + 14}">${esc(fmt(r.v, u))}</text></g>` }).join('')}</svg>`;
  }
  function colSVG(g, c) {
    const rows = c.by === 't' || /^Thứ|Chủ/.test(g[0] ? g[0].l : '') ? g : g.sort((a, b) => b.v - a.v).slice(0, 12), W = 520, H = 250, pb = 52, pt = 18, n = rows.length, bw = Math.min(46, (W - 20) / n * .62), mx = Math.max(...rows.map(r => r.v), 0) || 1, u = unitOf(c.m);
    return `<svg viewBox="0 0 ${W} ${H}">${rows.map((r, i) => { const x = 10 + (i + .5) * (W - 20) / n, h = Math.max(0, (H - pb - pt) * r.v / mx), y = H - pb - h;
      return `<g ${mk(c.by, r.q, r, c)}><rect x="${x - bw / 2 - 4}" y="${pt}" width="${bw + 8}" height="${H - pb - pt}" fill="transparent"/><rect x="${x - bw / 2}" y="${y}" width="${bw}" height="${h}" rx="3" fill="${PAL[1]}"/><text class="v" x="${x}" y="${y - 4}" text-anchor="middle">${esc(fmt(r.v, ''))}</text><text x="${x}" y="${H - pb + 14}" text-anchor="${n <= 6 ? 'middle' : 'end'}" ${n <= 6 ? '' : `transform="rotate(-30 ${x} ${H - pb + 14})"`}>${esc(r.l.length > (n <= 6 ? 20 : 12) ? r.l.slice(0, n <= 6 ? 19 : 11) + '…' : r.l)}</text></g>` }).join('')}</svg>`;
  }
  function lineSVG(g, c) {
    if (g.length < 2) return barSVG(g, c);
    const W = 1200, H = 270, pl = 84, pr = 36, pt = 16, pb = 32, vals = g.map(r => r.v), mx = Math.max(...vals, 0), mn = Math.min(...vals, 0), sp = (mx - mn) || 1, u = unitOf(c.m);
    const X = i => pl + i * (W - pl - pr) / (g.length - 1), Y = v => pt + (mx - v) / sp * (H - pt - pb);
    const pts = g.map((r, i) => [X(i), Y(r.v)]), every = Math.ceil(g.length / 10);
    const grid = [0, .25, .5, .75, 1].map(t => { const v = mn + sp * t, y = Y(v); return `<line x1="${pl}" x2="${W - pr}" y1="${y}" y2="${y}" stroke="var(--line)"/><text x="${pl - 6}" y="${y + 4}" text-anchor="end">${esc(fmt(v, ''))}</text>` }).join('');
    return `<svg viewBox="0 0 ${W} ${H}">${grid}<path d="M${pts.map(p => p.join(',')).join('L')}L${X(g.length - 1)},${Y(0 < mn ? mn : 0)}L${X(0)},${Y(0 < mn ? mn : 0)}Z" fill="${PAL[0]}" opacity=".08"/><polyline fill="none" stroke="${PAL[0]}" stroke-width="2.4" points="${pts.map(p => p.join(',')).join(' ')}"/>${g.map((r, i) =>
      `<g ${mk('t', r.q, r, c)}><circle cx="${pts[i][0]}" cy="${pts[i][1]}" r="11" fill="transparent"/><circle cx="${pts[i][0]}" cy="${pts[i][1]}" r="${isSel('t', r.q) && st.sel.t && st.sel.t.size ? 5.5 : 3.6}" fill="${PAL[0]}" stroke="var(--panel)" stroke-width="1.5"/>${i % every === 0 || i === g.length - 1 ? `<text x="${pts[i][0]}" y="${H - 8}" text-anchor="${i === g.length - 1 ? 'end' : i === 0 ? 'start' : 'middle'}">${esc(r.l)}</text>` : ''}</g>`).join('')}</svg>`;
  }
  function donutSVG(g, c) {
    let rows = g.filter(r => r.v > 0).sort((a, b) => b.v - a.v);
    if (rows.length > 7) { const rest = rows.slice(6); rows = [...rows.slice(0, 6), { q: -1, l: 'Khác', v: rest.reduce((s, r) => s + r.v, 0), rows: rest.reduce((s, r) => s + r.rows, 0) }] }
    const tot = rows.reduce((s, r) => s + r.v, 0) || 1, R = 62, Cc = 2 * Math.PI * R; let acc = 0;
    const segs = rows.map((r, i) => { const len = r.v / tot * Cc, o = acc; acc += len;
      return `<circle ${r.q < 0 ? `class="mk" data-tt="${tt(r, c)}"` : mk(c.by, r.q, r, c)} cx="85" cy="85" r="${R}" fill="none" stroke="${PAL[i % PAL.length]}" stroke-width="30" stroke-dasharray="${len} ${Cc - len}" stroke-dashoffset="${-o}" transform="rotate(-90 85 85)"/>` }).join('');
    return `<div class="donut"><svg viewBox="0 0 170 170">${segs}<text x="85" y="82" text-anchor="middle" class="v" style="font-size:13px">${esc(fmt(tot, unitOf(c.m)))}</text><text x="85" y="98" text-anchor="middle">tổng</text></svg><div class="legend">${rows.map((r, i) => `<div class="${r.q >= 0 && !isSel(c.by, r.q) ? 'dim' : ''}" ${r.q >= 0 ? `data-k="${c.by}" data-q="${r.q}"` : ''}><i style="background:${PAL[i % PAL.length]}"></i>${esc(r.l)} <b>${nf.format(r.v / tot * 100)}%</b></div>`).join('')}</div></div>`;
  }
  function chartCard(c, i) {
    const g = groupBy(c.by, c.m, c.agg), u = unitOf(c.m);
    const body = !g.length ? '<div class="empty">Không có dữ liệu với bộ lọc hiện tại.</div>' : c.type === 'line' ? lineSVG(g, c) : c.type === 'col' ? colSVG(g, c) : c.type === 'donut' ? donutSVG(g, c) : barSVG(g, c);
    const so = (o, cur) => Object.entries(o).map(([v, l]) => `<option value="${v}" ${v === cur ? 'selected' : ''}>${esc(l)}</option>`).join('');
    const mo = `<option value="" ${c.m ? '' : 'selected'}>Số dòng</option>` + ds.meas.map(m => `<option value="${m.k}" ${m.k === c.m ? 'selected' : ''}>${esc(m.label)}</option>`).join('');
    return `<div class="card ${c.type === 'line' ? 'c12' : 'c6'}"><div class="ch"><h3>${esc((c.m ? AGG[c.agg] + ' ' : '') + labOf(c.m))} theo ${esc(L[c.by])}</h3><div class="opts">
<select data-ci="${i}" data-f="m" aria-label="Chỉ số">${mo}</select>${c.m ? `<select data-ci="${i}" data-f="agg" aria-label="Cách tính">${so(AGG, c.agg)}</select>` : ''}
<select data-ci="${i}" data-f="by" aria-label="Theo">${keys().map(k => `<option value="${k}" ${k === c.by ? 'selected' : ''}>${esc(L[k])}</option>`).join('')}</select><select data-ci="${i}" data-f="type" aria-label="Loại biểu đồ">${so(TYPES, c.type)}</select></div></div>${body}</div>`;
  }
  function tableCard() {
    const t = st.tbl, mcols = ds.meas.slice(0, 4);
    let head, rows;
    if (t.mode === 'raw' && !ds.cube) {
      const ks = keys(); head = [...ks.map(k => [k, L[k], false]), ...mcols.map(m => [m.k, m.label, true])]; rows = [];
      for (let i = 0; i < ds.n && rows.length < 100; i++) if (pass(i, null)) rows.push(Object.fromEntries(head.map(([k]) => [k, M[k] ? M[k][i] : (C[k][i] >= 0 ? V[k][C[k][i]] : '')])));
    } else {
      head = [['l', L[t.by], false], ['rows', 'Số dòng', true], ...mcols.map(m => [m.k, (m.avg ? 'TB ' : 'Tổng ') + m.label, true])];
      if (mcols[0] && !mcols[0].avg) head.push(['avg', 'TB ' + mcols[0].label, true]);
      const by = {}; mcols.forEach(m => by[m.k] = groupBy(t.by, m.k, m.avg ? 'avg' : 'sum')); const base = groupBy(t.by, '', 'count'), avg = mcols[0] ? groupBy(t.by, mcols[0].k, 'avg') : [];
      rows = base.map(b => { const o = { l: b.l, rows: b.rows }; mcols.forEach(m => { const x = by[m.k].find(y => y.q === b.q); o[m.k] = x ? x.v : null }); const a = avg.find(y => y.q === b.q); o.avg = a ? a.v : null; return o });
      rows.sort((a, b) => (typeof a[t.sort] === 'string' ? a[t.sort].localeCompare(b[t.sort]) : (a[t.sort] ?? -Infinity) - (b[t.sort] ?? -Infinity)) * t.dir); rows = rows.slice(0, 100);
    }
    const cell = (v, num, k) => v == null ? '' : num ? esc(k === 'rows' ? nf.format(v) : nf2.format(v)) : esc(v);
    return `<div class="card c12"><div class="ch"><h3>Bảng chi tiết</h3><div class="opts"><select data-t="mode"><option value="group" ${t.mode === 'group' ? 'selected' : ''}>Gộp theo nhóm</option>${ds.cube ? '' : `<option value="raw" ${t.mode === 'raw' ? 'selected' : ''}>Dòng dữ liệu</option>`}</select>
${t.mode === 'group' || ds.cube ? `<select data-t="by">${keys().map(k => `<option value="${k}" ${k === t.by ? 'selected' : ''}>${esc(L[k])}</option>`).join('')}</select>` : ''}</div></div>
<div class="tw"><table><thead><tr>${head.map(([k, l, n]) => `<th class="${n ? 'n' : ''}" data-sort="${k}">${esc(l)}${t.sort === k ? (t.dir < 0 ? ' ↓' : ' ↑') : ''}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${head.map(([k, , n]) => `<td class="${n ? 'n' : ''}">${cell(r[k], n, k)}</td>`).join('')}</tr>`).join('')}</tbody></table></div><div class="note" style="margin-bottom:0">Hiển thị tối đa 100 dòng. Bấm tiêu đề cột để sắp xếp.</div></div>`;
  }

  /* ---------- khung trang ---------- */
  function slicers() {
    const one = k => { const s = st.sel[k] || new Set(), act = s.size > 0;
      return `<details class="sl ${act ? 'act' : ''}" data-sl="${k}" ${openK.has(k) ? 'open' : ''}><summary>${esc(L[k])}${act ? ` <span class="tag">${s.size}</span>` : ''}</summary><div class="slp"><div class="row"><button class="btn" data-clr="${k}">Bỏ chọn</button></div>${V[k].map((v, q) => `<label><input type="checkbox" data-sc="${k}" data-q="${q}" ${s.has(q) ? 'checked' : ''}> ${esc(v)}</label>`).join('')}</div></details>` };
    const rng = ds.time ? `<div class="rng" title="Khoảng thời gian"><span class="lbl">Từ</span><select data-r="from">${V.t.map((v, i) => `<option value="${i}" ${i === st.from ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select><span class="lbl">đến</span><select data-r="to">${V.t.map((v, i) => `<option value="${i}" ${i === st.to ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select></div>` : '';
    const n = kpiData().rows, filtered = Object.values(st.sel).some(s => s.size) || (ds.time && (st.from > 0 || st.to < V.t.length - 1));
    return `<span class="lbl">Bộ lọc</span>${rng}${ds.dims.map(d => one(d.k)).join('')}${ds.time ? one('t').replace(esc(L.t), 'Chọn tháng') : ''}<button class="btn" data-reset="1" ${filtered ? '' : 'disabled'}>Xóa bộ lọc</button><span class="status"><b>${nf.format(n)}</b>/${nf.format(ds.n_src)} dòng ${filtered ? 'sau lọc' : ''}</span>`;
  }
  function kpiHTML() {
    const k = kpiData(), cards = [['Số dòng dữ liệu', nf.format(k.rows), '']];
    ds.meas.slice(0, 3).forEach((m, j) => cards.push(m.avg ? ['Trung bình ' + m.label, fmt(k.Cn[j] ? k.S[j] / k.Cn[j] : null, m.unit), 'mỗi dòng'] : ['Tổng ' + m.label, fmt(k.S[j], m.unit), '']));
    if (ds.meas[0] && !ds.meas[0].avg) cards.push(['Trung bình ' + ds.meas[0].label, fmt(k.Cn[0] ? k.S[0] / k.Cn[0] : null, ds.meas[0].unit), 'mỗi dòng']);
    return cards.map(([l, v, s]) => `<div class="kpi"><span>${esc(l)}</span><b>${esc(v)}</b>${s ? `<small>${esc(s)}</small>` : ''}</div>`).join('');
  }
  function narrative() {
    const ins = D.insights.map((x, i) => `<div class="card in"><div class="n">${i + 1}</div><div><h4>${esc(x.title)} <span class="tag">${esc(x.confidence || '')}</span></h4><p><b>Bằng chứng:</b> ${esc(x.evidence || '')}</p></div></div>`).join('');
    const acts = [...D.actions].sort((a, b) => ({ Cao: 0, 'Trung bình': 1, 'Thấp': 2 }[a.priority] ?? 9) - ({ Cao: 0, 'Trung bình': 1, 'Thấp': 2 }[b.priority] ?? 9)).map(a => `<tr><td><span class="pr ${esc((a.priority || '').split(' ')[0])}">${esc(a.priority || '')}</span></td><td style="white-space:normal"><b>${esc(a.text)}</b></td><td style="white-space:normal">${esc(a.impact || '')}</td></tr>`).join('');
    return (ins ? `<h2 class="sec">Insight chính</h2><div class="ins">${ins}</div>` : '') +
      (acts ? `<h2 class="sec">Khuyến nghị hành động</h2><div class="tw" style="max-height:none"><table><thead><tr><th>Ưu tiên</th><th>Hành động</th><th>Tác động kỳ vọng</th></tr></thead><tbody>${acts}</tbody></table></div>` : '') +
      (D.risks.length ? `<h2 class="sec">Rủi ro cần lưu ý</h2><div class="card"><ul style="margin:0;padding-left:18px">${D.risks.map(r => `<li>${esc(r)}</li>`).join('')}</ul></div>` : '');
  }
  function shell() {
    const sw = D.datasets.length > 1 ? `<select id="dsw" aria-label="Bảng dữ liệu">${D.datasets.map((d, i) => `<option value="${i}" ${d === ds ? 'selected' : ''}>${esc(d.name)} (${nf.format(d.n_src)} dòng)</option>`).join('')}</select>` : '';
    $('#app').innerHTML = `<header class="top"><div class="wrap"><div><p class="eyebrow">Dashboard · ${esc(D.date)}</p><h1>${esc(D.title)}</h1><p>${esc(D.question)}</p></div><div class="tools">${sw}<button id="th">Sáng/Tối</button><button onclick="print()">In</button></div></div></header>
<div class="wrap">${D.summary ? `<div class="ans"><b>Câu trả lời ngắn</b><p>${esc(D.summary)}</p></div>` : ''}<div class="filters"><div class="fbar" id="fb"></div></div><div class="kpis" id="kp"></div><div class="grid" id="gr"></div>
${ds.cube ? `<div class="note">Dữ liệu lớn (${nf.format(ds.n_src)} dòng) nên được gộp theo các chiều trước khi nhúng${ds.dropped.length ? ` (bỏ chiều: ${esc(ds.dropped.join(', '))})` : ''}. Tổng, trung bình và số dòng vẫn chính xác; không xem được từng dòng gốc.</div>` : ''}
<div id="nar">${narrative()}</div><div class="foot">Tạo bởi Mission Control · số liệu tính từ dữ liệu đã làm sạch (${esc(ds.name)}), lọc và tính toán ngay trong trình duyệt.</div></div><div id="tt"></div>`;
  }
  function render() { if (!$('#fb')) shell(); $('#fb').innerHTML = slicers(); $('#kp').innerHTML = kpiHTML(); $('#gr').innerHTML = st.cfg.map(chartCard).join('') + tableCard(); }

  /* ---------- sự kiện ---------- */
  document.addEventListener('click', e => {
    const t = e.target, rs = t.closest('[data-reset]'), cl = t.closest('[data-clr]'), q = t.closest('[data-q][data-k]'), so = t.closest('[data-sort]');
    if (rs) { st.sel = {}; st.from = 0; st.to = ds.time ? V.t.length - 1 : 0; render() }
    else if (cl) { delete st.sel[cl.dataset.clr]; render() }
    else if (so) { const k = so.dataset.sort; st.tbl.dir = st.tbl.sort === k ? -st.tbl.dir : -1; st.tbl.sort = k; render() }
    else if (q && !t.closest('input')) { const k = q.dataset.k, v = +q.dataset.q, s = st.sel[k] = st.sel[k] || new Set(); s.has(v) ? s.delete(v) : s.add(v); render() }
    else if (t.id === 'th') { const r = document.documentElement; r.dataset.theme = r.dataset.theme === 'dark' ? 'light' : 'dark'; render() }
  });
  document.addEventListener('change', e => { const t = e.target;
    if (t.dataset.sc) { const k = t.dataset.sc, v = +t.dataset.q, s = st.sel[k] = st.sel[k] || new Set(); t.checked ? s.add(v) : s.delete(v); render() }
    else if (t.dataset.r) { st[t.dataset.r] = +t.value; if (st.from > st.to) { if (t.dataset.r === 'from') st.to = st.from; else st.from = st.to } render() }
    else if (t.dataset.ci != null) { const c = st.cfg[+t.dataset.ci]; c[t.dataset.f] = t.value; if (t.dataset.f === 'm') c.agg = t.value ? (c.agg === 'count' ? 'sum' : c.agg) : 'count'; if (t.dataset.f === 'by' && c.type === 'line' && t.value !== 't') c.type = 'bar'; if (t.dataset.f === 'by' && t.value === 't' && c.type !== 'col') c.type = 'line'; render() }
    else if (t.dataset.t) { st.tbl[t.dataset.t] = t.value; if (t.dataset.t === 'mode') st.tbl.sort = 'v'; render() }
    else if (t.id === 'dsw') { openK.clear(); init(+t.value) } });
  document.addEventListener('toggle', e => { const d = e.target; if (d.dataset && d.dataset.sl) d.open ? openK.add(d.dataset.sl) : openK.delete(d.dataset.sl) }, true);
  document.addEventListener('mousemove', e => { const el = e.target.closest('[data-tt]'), b = $('#tt'); if (!b) return;
    if (!el) { b.style.display = 'none'; return } b.textContent = el.dataset.tt; b.style.display = 'block'; b.style.left = Math.min(e.clientX + 14, innerWidth - 270) + 'px'; b.style.top = (e.clientY + 14) + 'px' });
  document.addEventListener('mousedown', e => { document.querySelectorAll('details.sl[open]').forEach(d => { if (!d.contains(e.target)) { d.open = false; openK.delete(d.dataset.sl) } }) });
  if (!D.datasets.length) { $('#app').innerHTML = `<div class="wrap"><h1>${esc(D.title)}</h1><div class="note">Không có bảng dữ liệu phù hợp để dựng dashboard tương tác (cần ít nhất một cột phân loại hoặc cột ngày tháng).</div></div>` } else init(0);
})();
