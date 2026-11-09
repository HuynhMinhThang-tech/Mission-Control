/* Mission Control · các thành phần giao diện của 5 cải tiến (nạp TRƯỚC app.js; chỉ dùng các hàm/biến của app.js khi được gọi, không dùng lúc nạp).
   1. Bước Phân tích: bộ GHÉP BIẾN (chọn biến từ danh sách cột thật, hoặc mô tả bằng lời để AI nhận diện)
   2. Bước Phân tích: ba pha (đề xuất · code · kết quả) có biến dùng, điểm nổi bật, biểu đồ đi kèm từng bảng
   3. Bước Mô tả dữ liệu: PHÂN BỐ từng biến (histogram cho biến định lượng, giá trị duy nhất cho biến phân loại, theo thời gian cho biến ngày)
   4. Bước Báo cáo: CHỌN biểu đồ cho bảng điều khiển (AI gợi ý trước, bạn chọn thêm)
   5. ĐIỀU CHỈNH: banner "đã cập nhật theo góp ý" + giữ lựa chọn đang chọn dở qua lần chạy lại */

/* ======================= thành phần dùng chung ======================= */
const KL = { num: ['Định lượng', 'num'], cat: ['Phân loại', 'cat'], date: ['Thời gian', 'date'], id: ['Mã', 'id'], text: ['Văn bản', 'text'], empty: ['Trống', 'text'] };
const kbadge = k => `<span class="kb ${(KL[k] || KL.text)[1]}">${(KL[k] || KL.text)[0]}</span>`;
const fnum = v => v == null ? '—' : FMT.num(v);
const pcs = (a, b) => FMT.pct(b ? a * 100 / b : 0);
const SRC = { spec: ['Bạn ghép biến', 'usr'], ai: ['AI viết code', 'ai'], pick: ['Bạn ghép biến', 'usr'], text: ['AI nhận diện', 'ai'] };
const srcTag = s => SRC[s] ? `<span class="srt ${SRC[s][1]}">${SRC[s][0]}</span>` : '';
const colInfo = (cols, name) => { for (const f of (cols || [])) { const c = f.cols.find(x => x.name === name); if (c) return c } return null };
/* chip "biến dùng": nhãn tiếng Việt + loại biến; rê chuột để xem tên cột gốc */
const varChips = (vars, cols) => (vars && vars.length) ? `<span class="vcs"><small>Biến dùng:</small>${vars.map(v => { const c = colInfo(cols, v); return `<span class="vc k-${c ? (KL[c.kind] || KL.text)[1] : 'text'}" title="${esc(v)}${c ? ' · ' + (KL[c.kind] || KL.text)[0] : ''}">${esc(c ? c.label : v)}</span>` }).join('')}</span>` : '';
const api = async (url, body) => { try { const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }); if (!r.ok) { notify(await readError(r)); return null } return await r.json() } catch (e) { netErr(); return null } };

/* ======================= 5. ĐIỀU CHỈNH: banner + thẻ "Mới / Đã sửa" ======================= */
const adjOn = d => !!(d && d.adj && d.adj.gen === d.gen);
const adjTag = (d, t) => !adjOn(d) ? '' : d.adj.added.includes(t) ? '<span class="nw">Mới</span>' : d.adj.changed.includes(t) ? '<span class="nw ch">Đã sửa</span>' : '';
function adjBanner(d) {
  if (!adjOn(d)) return '';
  const a = d.adj, none = !a.added.length && !a.removed.length && !a.changed.length;
  const row = (l, arr, c) => arr.length ? `<div class="adr ${c}"><b>${l}</b>${arr.slice(0, 6).map(x => `<span title="${esc(x)}">${esc(x.length > 60 ? x.slice(0, 59) + '…' : x)}</span>`).join('')}${arr.length > 6 ? `<small>…và ${arr.length - 6} mục khác</small>` : ''}</div>` : '';
  const head = a.ok ? 'Đã cập nhật theo góp ý của bạn' : none ? 'Bản mới chưa có thay đổi nào so với bản trước' : 'AI đã chỉnh nhưng có thể chưa đủ ý bạn';
  return `<div class="adj ${a.ok ? 'ok' : 'warn'}" role="status"><div class="adh">${ico(a.ok ? 'check' : 'alert', 16)}<b>${head}</b><small title="${esc(a.fb)}">Góp ý: «${esc(a.fb.length > 80 ? a.fb.slice(0, 79) + '…' : a.fb)}»</small></div>
${a.done ? `<p>${esc(a.done)}</p>` : ''}${row('Thêm', a.added, 'add')}${row('Sửa', a.changed, 'chg')}${row('Bỏ', a.removed, 'rem')}
${!a.ok && a.missing ? `<p class="adm">Còn thiếu: ${esc(a.missing)}. Bạn có thể bấm <b>Điều chỉnh</b> và nêu cụ thể hơn.</p>` : ''}${a.retried ? '<small class="sub">AI đã tự áp dụng lại một lần vì lần đầu chưa đủ ý.</small>' : ''}</div>` }

/* Giữ các lựa chọn đang chọn dở khi AI chạy lại theo góp ý. KEEP[i] chụp trước khi gửi; carry() ánh xạ sang dữ liệu mới theo TIÊU ĐỀ mục (id đổi mỗi lần chạy). */
const KEEP = {};
function keepSnap(i) {
  const S = S_(), d = S.d[i], s = SEL[i]; if (!d || !s) return;
  const k = { s: { ...s }, t: {} };
  if (i === 2) (d.ops || []).forEach(o => k.t[o.id] = o.title);
  if (i === 3) (d.menu || []).forEach(m => k.t[m.id] = m.title);
  if (i === 4) { (d.insights || []).forEach((x, j) => k.t['i' + j] = x.title); (d.actions || []).forEach((x, j) => k.t['a' + j] = x.text) }
  if (i === 5) { (d.charts || []).forEach((c, j) => k.t[j] = [c.task, c.x, c.y].join('|')); k.title = d.title }
  KEEP[i] = k }
function carry(i, d, n) {
  const k = KEEP[i]; if (!k) return n; delete KEEP[i]; const o = k.s;
  if (i === 2) { const byT = {}; Object.entries(k.t).forEach(([id, t]) => byT[t] = id);
    (d.ops || []).forEach(op => { const old = byT[op.title]; if (old === undefined) return; ['c', 'm', 'v'].forEach(p => { if (o[p + old] !== undefined) n[p + op.id] = o[p + old] }) });
    if (o.mm) n.mm = o.mm; n.needPv = true }
  else if (i === 3) { const byT = {}; Object.entries(k.t).forEach(([id, t]) => byT[t] = id);
    (d.menu || []).forEach(m => { const old = byT[m.title]; if (old === undefined) n['a' + m.id] = !k.more; else if (o['a' + old] !== undefined) n['a' + m.id] = o['a' + old] });   // mục MỚI (do góp ý) mặc định ĐƯỢC CHỌN; mục cũ giữ đúng lựa chọn của bạn
    ['anc', 'specs', 'b', 'btxt', 'bres', 'bprev'].forEach(p => { if (o[p] !== undefined) n[p] = o[p] }) }
  else if (i === 4) { const T = {}; Object.entries(k.t).forEach(([id, t]) => T[t] = id);
    (d.insights || []).forEach((x, j) => { const old = T[x.title]; if (old !== undefined && o[old] !== undefined) n['i' + j] = o[old] });
    (d.actions || []).forEach((x, j) => { const old = T[x.text]; if (old !== undefined && o[old] !== undefined) n['a' + j] = o[old] }) }
  else if (i === 5) { const T = {}; Object.entries(k.t).forEach(([j, key]) => T[key] = j);
    (d.charts || []).forEach((c, j) => { const old = T[[c.task, c.x, c.y].join('|')]; if (old === undefined) return; ['c', 'k', 'x', 'y'].forEach(p => { if (o[p + old] !== undefined) n[p + j] = o[p + old] }) });
    Object.keys(o).forEach(p => { if (/^p\d+$/.test(p)) n[p] = o[p] }); if (o.rt !== undefined && o.rt !== k.title) n.rt = o.rt;
    if (o.dash) { const ai = ((d.dash || {}).ai || []).map(x => ({ ...x })), was = {}; o.dash.forEach(x => was[x.id] = x); ai.forEach(x => { if (was[x.id]) x.on = was[x.id].on });
      const newOf = {}; (d.charts || []).forEach((c, j) => { const old = T[[c.task, c.x, c.y].join('|')]; if (old !== undefined) newOf[old] = j });
      const keep = o.dash.filter(x => x.src === 'user' || (x.type === 'static' && (x.ci === undefined || newOf[x.ci] !== undefined))).map(x => x.type === 'static' && x.ci !== undefined ? { ...x, ci: newOf[x.ci], sid: 'rc' + newOf[x.ci], id: 'static|rc' + newOf[x.ci] } : x);
      n.dash = [...ai, ...keep.filter(x => !ai.some(a => a.id === x.id))]; n.dpd = o.dpd; n.dpb = o.dpb }
    if (o.bp) n.bp = o.bp }
  return n }

/* ======================= 3. PHÂN BỐ TỪNG BIẾN ======================= */
const DIST = { file: null, kind: 'all', more: false };
function histSVG(c) {
  const h = c.hist, W = 300, H = 92, pl = 4, pr = 4, base = H - 17, n = h.counts.length, mx = Math.max(...h.counts, 1), bw = (W - pl - pr) / n;
  const bars = h.counts.map((v, i) => { const bh = v / mx * (base - 8), lab = h.discrete ? String(h.labels[i]) : `${fnum(h.edges[i])} – ${fnum(h.edges[i + 1])}`;
    return `<rect x="${pl + i * bw + 1}" y="${base - bh}" width="${Math.max(1, bw - 2)}" height="${Math.max(bh, v ? 1.5 : 0)}" rx="2" fill="var(--pri)" opacity=".82"><title>${esc(lab)}: ${N(v)} bản ghi</title></rect>` }).join('');
  let mk = '';
  if (!h.discrete) { const lo = h.edges[0], span = (h.edges[n] - lo) || 1;
    [[c.stats.median, 'var(--ok)', ''], [c.stats.mean, 'var(--warn)', '3 2']].forEach(([x, col, dash]) => { const p = (x - lo) / span; if (p >= 0 && p <= 1) { const X = pl + p * (W - pl - pr); mk += `<line x1="${X}" x2="${X}" y1="3" y2="${base}" stroke="${col}" stroke-width="1.7" ${dash ? `stroke-dasharray="${dash}"` : ''}/>` } }) }
  const lab = h.discrete && n <= 12 ? h.labels.map((l, i) => `<text x="${pl + (i + .5) * bw}" y="${H - 4}" font-size="9" text-anchor="middle" fill="var(--sub)">${l}</text>`).join('')
    : `<text x="${pl}" y="${H - 4}" font-size="9" fill="var(--sub)">${esc(fnum(h.discrete ? h.labels[0] : h.edges[0]))}</text><text x="${W - pr}" y="${H - 4}" font-size="9" text-anchor="end" fill="var(--sub)">${esc(fnum(h.discrete ? h.labels[n - 1] : h.edges[n]))}</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" class="hs" role="img" aria-label="Phân bố của ${esc(c.label)}"><line x1="${pl}" x2="${W - pr}" y1="${base}" y2="${base}" stroke="var(--line)"/>${bars}${mk}${lab}</svg>` }
function distBody(c) {
  if (c.kind === 'num' && c.stats) { const s = c.stats, h = c.hist, trim = h && h.trim && (h.trim.low || h.trim.high);
    return `${histSVG(c)}${c.hist.discrete ? '' : '<div class="hlg"><span><i class="m1"></i>Trung vị</span><span><i class="m2"></i>Trung bình</span></div>'}
<div class="st6">${[['Nhỏ nhất', s.min], ['Q1', s.q1], ['Trung vị', s.median], ['Trung bình', s.mean], ['Q3', s.q3], ['Lớn nhất', s.max]].map(([l, v]) => `<div><small>${l}</small><b>${fnum(v)}</b></div>`).join('')}</div>
<ul class="dn">${c.shape ? `<li>${esc(c.shape)}</li>` : ''}${s.std != null ? `<li>Độ lệch chuẩn ${fnum(s.std)}</li>` : ''}${c.outliers ? `<li class="w">${N(c.outliers)} giá trị ngoại lai (theo IQR)</li>` : ''}${c.negative ? `<li class="w">${N(c.negative)} giá trị âm</li>` : ''}${trim ? `<li>Biểu đồ ẩn ${N(h.trim.low + h.trim.high)} giá trị nằm quá xa (ngoài p1–p99) để thân phân bố dễ đọc</li>` : ''}</ul>` }
  if (c.kind === 'cat') { const mx = Math.max(...c.top.map(r => r[1]), 1);
    return `<div class="uq"><b>${N(c.unique)}</b> giá trị duy nhất${c.single ? ' <span class="tag w">chỉ 1 giá trị, không giúp phân biệt nhóm</span>' : c.top_share > .9 ? ` <span class="tag w">một giá trị chiếm ${pcs(c.top_share, 1)}</span>` : ''}</div>
${c.top.map(([k, n]) => `<div class="cr"><span class="l" title="${esc(k)}">${esc(k)}</span><span class="tr"><i style="width:${Math.max(2, n / mx * 100)}%"></i></span><span class="v">${N(n)} <small>${pcs(n, c.total)}</small></span></div>`).join('')}
${c.rest_n ? `<small class="sub">+ ${N(c.rest_n)} giá trị khác (${N(c.rest)} bản ghi)</small>` : ''}` }
  if (c.kind === 'date' && c.labels) { const mx = Math.max(...c.counts, 1);
    return `<div class="uq"><b>${esc(c.min)}</b> → <b>${esc(c.max)}</b> · số bản ghi theo ${esc(c.unit)}</div><div class="dm">${c.counts.map((v, i) => `<i title="${esc(c.labels[i])}: ${N(v)} bản ghi" style="height:${Math.max(4, v / mx * 100)}%"></i>`).join('')}</div>
<div class="dmr"><span>${esc(c.labels[0])}</span><span>${esc(c.labels[c.labels.length - 1])}</span></div>${c.gaps ? `<small class="w">Không có dữ liệu ở ${c.gaps} ${esc(c.unit)} trong khoảng này</small>` : ''}` }
  return `<div class="uq"><b>${N(c.unique)}</b> giá trị khác nhau trên ${N(c.n)} dòng${c.kind === 'id' ? ' · mã định danh, không vẽ phân bố' : ''}</div>${(c.sample || []).length ? `<small class="sub">Ví dụ: ${c.sample.map(x => esc(x.length > 28 ? x.slice(0, 27) + '…' : x)).join(' · ')}</small>` : ''}` }
function distCard(c) {
  const tot = c.n + c.missing, mp = tot ? c.missing / tot : 0;
  return `<div class="dc"><div class="dch"><b title="${esc(c.col)}">${esc(c.label && c.label !== c.col ? c.label : c.col)}</b>${kbadge(c.kind)}${c.missing ? `<span class="tag ${mp > .05 ? 'w' : ''}" title="${N(c.missing)} ô trống">thiếu ${pcs(c.missing, tot)}</span>` : ''}</div>${distBody(c)}${c.note ? `<small class="sub">${esc(c.note)}</small>` : ''}</div>` }
function distPanel(d) {
  if (!d.dist || !d.dist.length) return '';
  const f = d.dist.find(x => x.file === DIST.file) || d.dist[0]; DIST.file = f.file;
  const cnt = { all: f.cols.length, num: 0, cat: 0, date: 0, id: 0 }; f.cols.forEach(c => { const k = c.kind === 'text' ? 'id' : c.kind; if (cnt[k] != null) cnt[k]++ });
  const FL = [['all', 'Tất cả'], ['num', 'Định lượng'], ['cat', 'Phân loại'], ['date', 'Thời gian'], ['id', 'Mã / văn bản']].filter(([k]) => k === 'all' || cnt[k]);
  if (!FL.some(([k]) => k === DIST.kind)) DIST.kind = 'all';
  const cols = f.cols.filter(c => DIST.kind === 'all' || (DIST.kind === 'id' ? ['id', 'text'].includes(c.kind) : c.kind === DIST.kind)), LIM = 12, shown = DIST.more ? cols : cols.slice(0, LIM);
  return `<div class="dpn"><div class="dph"><div><h3>Phân bố từng biến</h3><p>Biến <b>định lượng</b>: biểu đồ cột (histogram) cho thấy giá trị tập trung ở đâu, vạch xanh là trung vị, vạch đứt là trung bình. Biến <b>phân loại</b>: các giá trị duy nhất và số lần xuất hiện. Biến <b>thời gian</b>: số bản ghi theo kỳ.</p></div></div>
<div class="dfl">${d.dist.length > 1 ? `<span class="seg" role="group" aria-label="Bảng dữ liệu">${d.dist.map(x => `<button type="button" class="${x.file === f.file ? 'on' : ''}" data-dk="file:${esc(x.file)}">${esc(String(x.file).replace(/\.[^.]+$/, ''))}</button>`).join('')}</span>` : ''}
<span class="seg" role="group" aria-label="Loại biến">${FL.map(([k, l]) => `<button type="button" class="${DIST.kind === k ? 'on' : ''}" data-dk="kind:${k}">${l} <small>${cnt[k]}</small></button>`).join('')}</span><small class="sub">${N(f.rows)} dòng${f.skipped ? ` · chỉ mô tả ${f.cols.length} cột đầu, còn ${f.skipped} cột nữa` : ''}</small></div>
<div class="dg">${shown.map(distCard).join('') || '<p class="sub">Không có biến thuộc loại này.</p>'}</div>
${cols.length > LIM ? `<div class="act"><button type="button" class="btn g sm" data-dk="more">${DIST.more ? 'Thu gọn' : `Xem thêm ${cols.length - LIM} biến`}</button></div>` : ''}</div>` }

/* ======================= 1. BỘ GHÉP BIẾN ======================= */
const BTYPES = [['compare', 'So sánh theo nhóm', 'Chỉ số chia theo nhóm. Ví dụ: doanh thu theo khu vực'], ['trend', 'Xu hướng theo thời gian', 'Chỉ số theo ngày, tuần, tháng, quý, năm'],
  ['cross', 'Chéo hai biến phân loại', 'Bảng hàng × cột. Ví dụ: khu vực × sản phẩm'], ['correlate', 'Tương quan hai biến số', 'Hai biến số có đi cùng nhau không'], ['distribution', 'Phân bố một biến', 'Giá trị tập trung ở đâu'],
  ['rate', 'Tỷ lệ đạt / tuân thủ', 'Tỷ lệ Đạt của cột Đạt / Không đạt, theo nhóm hoặc thời gian'], ['pareto', 'Xếp hạng và 80/20', 'Nhóm nào tạo ra phần lớn tổng']];
const BAGG = [['sum', 'Tổng'], ['mean', 'Trung bình'], ['median', 'Trung vị'], ['min', 'Nhỏ nhất'], ['max', 'Lớn nhất'], ['count', 'Đếm có giá trị'], ['nunique', 'Đếm giá trị khác nhau']];
const BGRAIN = [['day', 'Ngày'], ['week', 'Tuần'], ['month', 'Tháng'], ['quarter', 'Quý'], ['year', 'Năm']];
const bFile = (d, b) => (d.cols || []).find(f => f.file === b.file) || (d.cols || [])[0];
const isNum = c => c.kind === 'num', isTime = c => c.kind === 'date', isDim = c => (c.kind === 'cat' || (c.kind === 'num' && c.unique <= 20)) && c.unique >= 2 && c.unique <= 60;
function bState(d, s) {
  if (!s.b) { const f = (d.cols || [])[0]; s.b = { mode: 'pick', type: 'compare', file: f ? f.file : '', m: [{ col: '', agg: 'sum' }, { col: '', agg: 'sum' }], by: ['', ''], tc: '', grain: 'month', x: '', y: '', c: '', rc: [], rg: 'none' }; bDefaults(d, s.b) }
  return s.b }
function bDefaults(d, b) {                                  // chọn sẵn các biến hợp lý để người dùng chỉ việc chỉnh
  const f = bFile(d, b); if (!f) return; const nums = f.cols.filter(isNum).sort((p, q) => (q.unit ? 1 : 0) - (p.unit ? 1 : 0) || q.unique - p.unique), dims = f.cols.filter(isDim).sort((p, q) => (p.kind === 'cat' ? 0 : 1) - (q.kind === 'cat' ? 0 : 1)), tms = f.cols.filter(isTime);
  if (!b.m[0].col) b.m[0].col = nums[0] ? nums[0].name : '*'; if (!b.by[0] && dims[0]) b.by[0] = dims[0].name; if (!b.tc && tms[0]) b.tc = tms[0].name;
  if (b.type === 'rate' && !b.rc.length) b.rc = f.cols.filter(c => c.bin).slice(0, 3).map(c => c.name);
  if (!b.x && nums[0]) b.x = nums[0].name; if (!b.y && nums[1]) b.y = nums[1].name; if (!b.c && f.cols.length) b.c = (dims[0] || nums[0] || f.cols[0]).name }
function bSpec(b) {
  const m = b.m.filter(x => x.col !== '').map(x => x.col === '*' ? { col: null, agg: 'count' } : { col: x.col, agg: x.agg });
  if (b.type === 'compare') return { type: 'compare', file: b.file, measures: m, by: b.by.filter(Boolean) };
  if (b.type === 'trend') return { type: 'trend', file: b.file, measures: m.slice(0, 1), time: { col: b.tc, grain: b.grain }, by: b.by[0] ? [b.by[0]] : [] };
  if (b.type === 'cross') return { type: 'cross', file: b.file, measures: m.slice(0, 1), by: b.by.slice(0, 2).filter(Boolean) };
  if (b.type === 'rate') return { type: 'rate', file: b.file, cols: b.rc, ...(b.rg === 'time' ? { time: { col: b.tc, grain: b.grain === 'week' ? 'month' : b.grain } } : b.rg === 'by' && b.by[0] ? { by: [b.by[0]] } : {}) };
  if (b.type === 'pareto') return { type: 'pareto', file: b.file, measures: [m[0] && m[0].col ? { col: m[0].col, agg: 'sum' } : { col: null, agg: 'count' }], by: b.by[0] ? [b.by[0]] : [] };
  if (b.type === 'correlate') return { type: 'correlate', file: b.file, x: b.x, y: b.y };
  return { type: 'distribution', file: b.file, col: b.c } }
function bMissing(b) {
  if (b.type === 'rate') return !b.rc.length ? 'Chọn ít nhất một tiêu chí Đạt / Không đạt.' : b.rg === 'by' && !b.by[0] ? 'Chọn nhóm để chia.' : b.rg === 'time' && !b.tc ? 'Bảng này chưa có cột thời gian để chọn.' : '';
  if (b.type === 'pareto') return b.by[0] ? '' : 'Chọn biến để xếp hạng.';
  if (b.type === 'compare') return b.by[0] ? '' : 'Chọn ít nhất một biến để chia nhóm.';
  if (b.type === 'trend') return b.tc ? '' : 'Bảng này chưa có cột thời gian để chọn.';
  if (b.type === 'cross') return b.by[0] && b.by[1] ? (b.by[0] === b.by[1] ? 'Hai biến hàng và cột phải khác nhau.' : '') : 'Chọn đủ hai biến phân loại (hàng và cột).';
  if (b.type === 'correlate') return b.x && b.y ? (b.x === b.y ? 'Hai biến phải khác nhau.' : '') : 'Chọn đủ hai biến số.';
  return b.c ? '' : 'Chọn biến cần xem phân bố.' }
let BTM = 0;
function bValidate() {                                       // hỏi server: spec hợp lệ không, tiêu đề / mô tả là gì (cùng một nơi quyết định, không lặp logic ở trình duyệt)
  clearTimeout(BTM); BTM = setTimeout(async () => {
    const d = S_().d[3]; if (!d || V !== 3) return; const s = sel(3); if (!s.b || d.phase !== 'menu') return; const b = s.b, miss = bMissing(b), sp = bSpec(b), key = JSON.stringify(sp);
    if (miss) s.bprev = { key, ok: false, error: miss }; else { const r = await api('/api/a3/spec', { spec: sp }); if (!r) return; s.bprev = { key, ok: r.ok, spec: r.spec, error: r.error } }
    const el = document.getElementById('bprev'); if (el) el.innerHTML = bPrevHTML(s) }, 120) }
function bPrevHTML(s) {
  const p = s.bprev, full = (s.specs || []).length >= 12;
  if (!p) return '<span class="sub">Chọn biến ở trên để xem hệ thống hiểu thế nào.</span>';
  const add = `<button type="button" class="btn sm" data-a="badd" ${p.ok && !full ? '' : 'disabled'}>+ Thêm vào danh sách phân tích</button>`;
  return p.ok ? `<div class="bpo"><span class="ar">→</span><div><b>${esc(p.spec.title)}</b><small>${esc(p.spec.goal)}</small></div></div>${add}${full ? '<small class="w">Đã đủ 12 phân tích tự ghép.</small>' : ''}` : `<div class="bpo bad"><span class="ar">!</span><div><small>${esc(p.error || '')}</small></div></div>${add}` }
function bSelect(b, key, opts, cur, placeholder) { return `<select data-b="${key}">${placeholder ? `<option value="">${esc(placeholder)}</option>` : ''}${opts.map(([v, l]) => `<option value="${esc(v)}" ${v === cur ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>` }
const cOpt = (cols, f, withN = true) => cols.filter(f).map(c => [c.name, `${c.label}${withN && (c.kind === 'num' && c.unique <= 20 || c.kind === 'cat') ? ' · ' + c.unique + ' nhóm' : ''}`]);
function bSlots(d, b) {
  const f = bFile(d, b); if (!f) return ''; const nums = f.cols.filter(isNum), meas = [['*', 'Đếm số bản ghi'], ...cOpt(f.cols, isNum, false)];
  const mrow = (i, opt) => `<div class="bro"><label>${i ? 'Chỉ số thứ hai' : 'Chỉ số'}</label>${bSelect(b, 'mcol' + i, meas, b.m[i].col, opt ? '— không thêm' : '')}${b.m[i].col && b.m[i].col !== '*' ? bSelect(b, 'magg' + i, BAGG, b.m[i].agg) : ''}</div>`;
  const dimO = cOpt(f.cols, isDim), timO = cOpt(f.cols, isTime), tm = !timO.length ? '<span class="w">Bảng này không có cột thời gian.</span>' : '';
  if (b.type === 'compare') return mrow(0) + (nums.length ? mrow(1, true) : '') + `<div class="bro"><label>Chia theo</label>${bSelect(b, 'by0', dimO, b.by[0], '— chọn biến')}${bSelect(b, 'by1', dimO.filter(o => o[0] !== b.by[0]), b.by[1], '— thêm biến thứ hai (tùy chọn)')}</div>`;
  if (b.type === 'trend') return mrow(0) + `<div class="bro"><label>Cột thời gian</label>${timO.length ? bSelect(b, 'tc', timO, b.tc) : tm}<span class="seg" role="group" aria-label="Theo">${BGRAIN.map(([v, l]) => `<button type="button" class="${b.grain === v ? 'on' : ''}" data-a="bgrain" data-v="${v}">${l}</button>`).join('')}</span></div><div class="bro"><label>Tách đường theo</label>${bSelect(b, 'by0', dimO, b.by[0], '— không tách')}</div>`;
  if (b.type === 'cross') return `<div class="bro"><label>Hàng</label>${bSelect(b, 'by0', dimO, b.by[0], '— chọn biến')}<label class="x">Cột</label>${bSelect(b, 'by1', dimO.filter(o => o[0] !== b.by[0]), b.by[1], '— chọn biến')}</div>` + mrow(0);
  if (b.type === 'rate') { const bins = f.cols.filter(c => c.bin), dimR = dimO.filter(o => !b.rc.includes(o[0]));
    return (bins.length ? `<div class="bro"><label>Tiêu chí</label><span class="bcr">${bins.map(c => `<label class="bc2"><input type="checkbox" data-b="rcx" value="${esc(c.name)}" ${b.rc.includes(c.name) ? 'checked' : ''}> ${esc(c.label)}</label>`).join('')}</span></div>` : '<div class="bro"><span class="w">Bảng này chưa có cột Đạt / Không đạt (cột chỉ có hai giá trị kiểu Đạt / Không đạt, Có / Không).</span></div>')
      + `<div class="bro"><label>Xem</label><span class="seg" role="group" aria-label="Xem theo">${[['none', 'Chung'], ['by', 'Theo nhóm'], ['time', 'Theo thời gian']].map(([v, l]) => `<button type="button" class="${b.rg === v ? 'on' : ''}" data-a="brg" data-v="${v}">${l}</button>`).join('')}</span></div>`
      + (b.rg === 'by' ? `<div class="bro"><label>Chia theo</label>${bSelect(b, 'by0', dimR, b.by[0], '— chọn biến')}</div>` : '') + (b.rg === 'time' ? `<div class="bro"><label>Cột thời gian</label>${timO.length ? bSelect(b, 'tc', timO, b.tc) : tm}<span class="seg" role="group" aria-label="Theo">${BGRAIN.filter(g => g[0] !== 'week').map(([v, l]) => `<button type="button" class="${b.grain === v ? 'on' : ''}" data-a="bgrain" data-v="${v}">${l}</button>`).join('')}</span></div>` : '') }
  if (b.type === 'pareto') return `<div class="bro"><label>Chỉ số</label>${bSelect(b, 'mcol0', meas, b.m[0].col)}<small class="sub">Tính theo Tổng (80/20 chỉ dùng cho chỉ số cộng được)</small></div><div class="bro"><label>Xếp hạng theo</label>${bSelect(b, 'by0', dimO, b.by[0], '— chọn biến')}</div>`;
  if (b.type === 'correlate') return `<div class="bro"><label>Biến X</label>${bSelect(b, 'x', cOpt(f.cols, isNum, false), b.x, '— chọn biến')}<label class="x">Biến Y</label>${bSelect(b, 'y', cOpt(f.cols, isNum, false).filter(o => o[0] !== b.x), b.y, '— chọn biến')}</div>`;
  return `<div class="bro"><label>Biến</label>${bSelect(b, 'c', cOpt(f.cols, c => isNum(c) || c.kind === 'cat'), b.c, '— chọn biến')}</div>` }
function bChips(d, b) {                                       // danh sách MỌI biến của bảng: bấm một biến để đưa vào ô còn trống phù hợp
  const f = bFile(d, b); if (!f) return '';
  const used = new Set([...b.m.map(x => x.col), ...b.by, ...(b.rc || []), b.tc, b.x, b.y, b.c]);
  return `<div class="bch"><small>Biến của bảng (${f.cols.length}) · bấm để đưa vào ô còn trống phù hợp:</small><div class="bcl">${f.cols.map(c => `<button type="button" class="vc k-${(KL[c.kind] || KL.text)[1]} ${used.has(c.name) ? 'used' : ''}" data-a="bchip" data-v="${esc(c.name)}" title="${esc(c.name)} · ${(KL[c.kind] || KL.text)[0]} · ${N(c.unique)} giá trị khác nhau${c.missing ? ' · thiếu ' + N(c.missing) : ''}">${esc(c.label)}<i>${(KL[c.kind] || KL.text)[0]}</i></button>`).join('')}</div></div>` }
function bAssign(d, b, name) {
  const f = bFile(d, b), c = f && f.cols.find(x => x.name === name); if (!c) return;
  const put = (arr, i) => { arr[i] = name };
  if (b.type === 'rate') { if (c.bin) { if (!b.rc.includes(name)) b.rc.push(name) } else if (isTime(c)) { b.tc = name; b.rg = 'time' } else if (isDim(c)) { b.by[0] = name; b.rg = 'by' } return }
  if (b.type === 'compare' || b.type === 'trend' || b.type === 'cross' || b.type === 'pareto') {
    if (isNum(c) && b.type !== 'cross' || (isNum(c) && !isDim(c))) { const i = b.m[0].col && b.m[0].col !== '*' ? 1 : 0; if (b.type === 'compare' || i === 0) b.m[i] = { col: name, agg: b.m[i].agg }; else b.m[0] = { col: name, agg: b.m[0].agg }; return }
    if (isTime(c) && b.type === 'trend') { b.tc = name; return }
    if (isDim(c)) { const lim = b.type === 'cross' ? 2 : b.type === 'trend' || b.type === 'pareto' ? 1 : 2; const i = b.by.slice(0, lim).findIndex(x => !x); put(b.by, i >= 0 ? i : lim - 1); return } }
  else if (b.type === 'correlate' && isNum(c)) { if (!b.x || b.y) b.x = name; else b.y = name; if (b.x === b.y) b.y = ''; return }
  else if (b.type === 'distribution') { b.c = name; return } }
function specCard(x, i) { const sp = x.spec;
  return `<div class="spc3"><div class="spch"><b>${esc(sp.title)}</b>${srcTag(x.src)}<button type="button" class="rm" data-a="brm" data-v="${i}" title="Bỏ phân tích này" aria-label="Bỏ phân tích này">${ico('trash', 15)}</button></div><p>${esc(sp.goal || '')}</p>${varChips(sp.vars, S_().d[3].cols)}</div>` }
function bBuilder(d, s) {
  const b = bState(d, s), mode = b.mode, f = bFile(d, b), files = d.cols || [];
  const tabs = `<span class="seg" role="group" aria-label="Cách ghép biến"><button type="button" class="${mode === 'pick' ? 'on' : ''}" data-a="bmode" data-v="pick">Chọn biến</button><button type="button" class="${mode === 'text' ? 'on' : ''}" data-a="bmode" data-v="text">Mô tả bằng lời</button></span>`;
  const list = (s.specs || []).length ? `<div class="spl"><b>Phân tích bạn đã ghép (${s.specs.length})</b>${s.specs.map(specCard).join('')}</div>` : '';
  let body;
  if (mode === 'pick') body = `${files.length > 1 ? `<div class="bro"><label>Bảng dữ liệu</label>${bSelect(b, 'file', files.map(x => [x.file, `${x.file} · ${N(x.rows)} dòng`]), b.file)}</div>` : ''}
${bChips(d, b)}<div class="btp" role="group" aria-label="Kiểu phân tích">${BTYPES.map(([k, l, t]) => `<button type="button" class="${b.type === k ? 'on' : ''}" data-a="btype" data-v="${k}"><b>${l}</b><small>${t}</small></button>`).join('')}</div>
<div class="bsl">${bSlots(d, b)}</div><div class="bpv" id="bprev">${bPrevHTML(s)}</div>`;
  else { const r = s.bres;
    body = `<p class="sub">Viết điều bạn muốn xem. AI đọc, <b>nhận diện đúng biến trong dữ liệu</b> rồi đưa vào danh sách bên dưới để bạn kiểm tra trước khi chạy. Ví dụ: <i>“doanh thu theo khu vực và theo tháng”</i>, <i>“đơn giá có liên quan tới số lượng bán không”</i>.</p>
<textarea data-b="text" data-pn="Mô tả biến cần ghép" class="bta" placeholder="Bạn muốn ghép biến nào với biến nào?">${esc(s.btxt || '')}</textarea>
<div class="act"><button type="button" class="btn sm" data-a="bparse" ${s.bbusy ? 'disabled' : ''}>${s.bbusy ? '<span class="spin sm"></span> AI đang đọc…' : 'AI nhận diện biến'}</button></div>
${r ? `${r.rejected.map(x => `<div class="note" style="margin-top:8px">Chưa nhận diện được: ${esc(x)}</div>`).join('')}${r.unclear ? `<div class="note" style="margin-top:8px">Chưa rõ phần: «${esc(r.unclear)}». <button type="button" class="lnk" data-a="bfree" data-v="${esc(r.unclear)}">Giữ làm yêu cầu riêng cho AI viết code</button></div>` : ''}${!r.n && !r.rejected.length && !r.unclear ? '<div class="note">AI không nhận diện được yêu cầu nào. Thử nêu rõ tên biến hơn.</div>' : ''}` : ''}` }
  return `<section class="a3b"><div class="a3bh"><div><h3>Tự ghép biến để phân tích</h3><p>Chọn biến nào ghép với biến nào, hoặc mô tả bằng lời.</p></div>${tabs}</div>${body}${list}</section>` }

/* ======================= 2. BƯỚC PHÂN TÍCH: ba pha ======================= */
function a3Menu(d, s) {
  const on = m => s['a' + m.id] ?? m.recommended, nA = d.menu.filter(on).length, nS = (s.specs || []).length;
  const card = m => `<div class="mc3 ${on(m) ? 'on' : ''}"><label class="mch"><input type="checkbox" data-s="3" data-k="a${m.id}" ${on(m) ? 'checked' : ''}><span class="mct"><b>${esc(m.title)}</b>${adjTag(d, m.title)}${m.recommended ? '<span class="rec">Khuyên dùng</span>' : ''}</span></label>
<p class="mg">${esc(m.goal || '')}</p>${m.action ? `<p class="mact">${esc(m.action)}</p>` : ''}${varChips(m.vars, d.cols)}${(m.metrics || []).length ? `<div class="mm">${m.metrics.map(x => `<code>${esc(x)}</code>`).join('')}</div>` : ''}${m.why ? `<details><summary>Vì sao nên làm</summary><p>${esc(m.why)}</p></details>` : ''}</div>`;
  const ang = m => m.angle || m.type || 'Phân tích', names = [...new Set(d.menu.map(ang))].sort((p, q) => (q === 'Góc nhìn mới') - (p === 'Góc nhìn mới')), grp = names.map(t => [t, d.menu.filter(m => ang(m) === t)]);
  return `<h2>Phân tích</h2><p class="lead">Chọn các phân tích AI đề xuất và/hoặc tự ghép biến ở bên dưới. Sau đó hệ thống viết code, chạy trên dữ liệu đã làm sạch, và cho bạn xem kết quả trước khi đi tiếp.</p>${adjBanner(d)}
<div class="a3h"><b>AI đề xuất (${d.menu.length})</b><span><button type="button" class="lnk" data-a="a3sel" data-v="all">Chọn tất cả</button> · <button type="button" class="lnk" data-a="a3sel" data-v="none">Bỏ chọn</button></span></div>
${grp.map(([t, ms]) => `<div class="a3g"><h4>${t === 'Phân tích' ? 'Khác' : t === 'Góc nhìn mới' ? '✦ Góc nhìn mới' : t} <small>${ms.length}</small></h4><div class="a3c">${ms.map(card).join('')}</div></div>`).join('')}
<div class="a3more"><button type="button" class="btn g sm" data-a="a3more">${ico('sparkles', 15)} Cho tôi góc nhìn khác</button><small>AI nghĩ thêm các mục khác hẳn những mục trên; lựa chọn của bạn được giữ nguyên.</small></div>
${bBuilder(d, s)}
<div class="frm" style="margin-top:14px"><label>Yêu cầu riêng khác (không bắt buộc, AI sẽ viết code theo ý bạn)</label><textarea data-s="3" data-i="anc" data-pn="Yêu cầu riêng khác" placeholder="Mô tả điều bạn muốn phân tích thêm, AI sẽ viết code theo ý bạn">${esc(s.anc || '')}</textarea></div>
<div class="a3sum"><b>Sẽ chạy:</b> ${nA} gợi ý của AI · ${nS} phân tích bạn ghép${(s.anc || '').trim() ? ' · 1 yêu cầu riêng' : ''}</div>` }
function a3Code(d, s) {
  return `<h2>Phân tích</h2><p class="lead">Đã chuẩn bị ${d.tasks.length} phân tích. Mỗi phân tích cho thấy <b>làm gì</b> và <b>dùng biến nào</b>. Mở “Xem / sửa code” nếu muốn chỉnh trước khi chạy.</p>${adjBanner(d)}
${d.tasks.map((t, i) => `<div class="tk"><div class="tkh"><span class="no">${i + 1}</span><b>${esc(t.title)}</b>${srcTag(t.src)}${adjTag(d, t.title)}</div>${t.goal ? `<p class="tg2">${esc(t.goal)}</p>` : ''}${varChips(t.vars, d.cols)}
<details data-o="o${i}" data-s="3" ${s['o' + i] ? 'open' : ''}><summary>Xem / sửa code</summary><textarea data-s="3" data-i="code${i}" data-pn="Sửa code · ${esc(t.title)}" data-mono class="code">${esc(s['code' + i] ?? t.code)}</textarea></details></div>`).join('')}
<div class="note">Code chạy trong môi trường cô lập (không import, không đọc/ghi tệp). Phân tích “Bạn ghép biến” được hệ thống sinh code trực tiếp từ biến bạn chọn.</div>` }
function resCard(t, i, r, d) {
  const ch = (r.charts || []).filter(c => c.task === i), rows = t.rows || [], tk = (d.tasks || [])[i] || {};
  return `<div class="rc"><div class="rch"><b>${esc(t.title)}</b>${srcTag(t.src || tk.src)}${adjTag(d, t.title)}<small>${N(rows.length)} dòng</small></div>${(t.goal || tk.goal) ? `<p class="tg2">${esc(t.goal || tk.goal)}</p>` : ''}
${(t.facts || []).length ? `<ul class="fx3">${t.facts.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
${ch.length ? `<div class="two">${ch.map(c => chart(c, r.tables)).join('')}</div>` : ''}
${t.err && !t.cols.length ? tableOf(t) : `<div class="tw"><table><thead><tr>${t.cols.map(x => `<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${rows.slice(0, 8).map(x => `<tr>${x.map(c => `<td>${cell(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>${rows.length > 8 ? `<details><summary>Xem tất cả ${N(rows.length)} dòng</summary>${tableOf(t)}</details>` : ''}`}
${varChips(t.vars || tk.vars, d.cols)}${tk.code ? `<details><summary>Cách tính (code đã chạy)</summary><pre class="codepre">${esc(tk.code)}</pre></details>` : ''}</div>` }
function a3Result(d, s) {
  const r = d.result, T = r.tables;
  return `<h2>Phân tích</h2>${kpo(r.kpis)}${adjBanner(d)}${(r.findings || []).length ? `<h3 class="sh3">Điểm chính</h3>${r.findings.map(f => fnd(esc(f.text), f.tag)).join('')}` : ''}
<h3 class="sh3">Kết quả từng phân tích <small>${T.length}</small></h3>${T.map((t, i) => resCard(t, i, r, d)).join('')}` }
const waitList = (S, i) => { const a = (S.ag && S.ag[i]) || [], k = S.job.running && S.job.step === i ? S.job.k : 99; return a.length ? a.map((x, j) => `<div class="wl ${j < k ? 'ok' : j === k ? 'on' : ''}"><i>${j < k ? '✓' : j === k ? '<span class="spin sm"></span>' : ''}</i>${esc(x)}</div>`).join('') : '' };

/* ======================= 4. THƯ VIỆN BIỂU ĐỒ (bước Báo cáo) =======================
   MỘT nơi chọn mọi biểu đồ: từ dữ liệu, từ kết quả phân tích, bảng điểm / ma trận cho dữ liệu đạt-không đạt, kèm thẻ KPI, bố cục, các khối chữ.
   Mỗi biểu đồ có 2 công tắc: hiện trên Bảng điều khiển · đưa vào Báo cáo + Slide (báo cáo và slide dùng chung một danh sách).
   "+ Thêm" mở ngăn kéo bên phải. Bản xem thử cập nhật ngay, không tải lại khung; rê chuột vào biểu đồ trên bản xem thử để ẩn, đổi dạng, di chuyển. */
const DKIND = { bars: 'Cột ngang', cols: 'Cột dọc', donut: 'Tròn (cơ cấu)', trend: 'Đường theo thời gian', line: 'Đường', score: 'Bảng điểm tiêu chí', heat: 'Ma trận nhiệt', static: 'Từ phân tích' };
const FONTS = { claude: 'Giống Claude (mặc định)', app: 'Giống giao diện ứng dụng', inter: 'Hiện đại (Inter)', bevn: 'Tối ưu tiếng Việt (Be Vietnam Pro)', serif: 'Báo chí, chữ có chân (Source Serif 4)', system: 'Phông hệ thống (nhẹ nhất, dùng được ngoại tuyến)' };
const LAYOUTS = { auto: 'Tự động', overview: 'Tổng quan và xu hướng', rank: 'Xếp hạng các nhóm', compliance: 'Tuân thủ đạt / không đạt', story: 'Kể chuyện (kết luận trước)' };
const KPIK = { sum: 'Tổng của một chỉ số', avg: 'Trung bình của một chỉ số', rate: 'Tỷ lệ đạt của một tiêu chí', rate_all: 'Tỷ lệ đạt chung', rate_low: 'Tiêu chí có tỷ lệ thấp nhất', count: 'Số bản ghi', distinct: 'Số nhóm khác nhau', latest: 'Kỳ gần nhất so với kỳ trước', top: 'Nhóm cao nhất', missing: 'Tỷ lệ chưa có dữ liệu' };
const BLOCKS = [['ans', 'Câu trả lời ngắn'], ['ins', 'Phát hiện chính'], ['act', 'Khuyến nghị hành động'], ['risk', 'Rủi ro cần lưu ý']];
const lc1 = t => t.charAt(0).toLowerCase() + t.slice(1);
const catOf = d => (d.dash || {}).catalog || [];
function dpState(d, s) { if (!s.dash) s.dash = ((d.dash || {}).ai || []).map(x => ({ ...x })); return s.dash }
function bpState(d, s) { if (!s.bp) { const b = (d.dash || {}).bp; s.bp = b ? JSON.parse(JSON.stringify(b)) : { layout: 'auto', kpis: [], table: { on: true }, blocks: {} } } return s.bp }
function dpTitle(it, cat) {
  if (it.type === 'static') return it.title || 'Biểu đồ từ phân tích';
  const c = cat.find(x => x.name === it.ds); if (!c) return it.title || '';
  if (it.type === 'score') return it.title || 'Tỷ lệ đạt theo từng tiêu chí';
  if (it.type === 'heat') return it.title || 'Tỷ lệ đạt theo ' + lc1(((c.dims.find(x => x.k === it.by) || {}).label) || 'nhóm') + ' và tiêu chí';
  const by = it.by === 't' ? 'tháng' : lc1(((c.dims.find(x => x.k === it.by) || {}).label) || it.by); let m;
  if (it.m === '') m = 'Số bản ghi'; else if (it.m === '*') m = 'Chỉ số đang chọn'; else { const x = c.meas.find(y => y.k === it.m);
    m = !x ? '?' : x.rate ? x.label : it.agg === 'avg' ? (/^trung bình/i.test(x.label) ? x.label : 'Trung bình ' + lc1(x.label.replace(/^tổng\s+/i, ''))) : (/^(tổng|số)(\s|$)/i.test(x.label) ? x.label : 'Tổng ' + lc1(x.label)) }
  return `${m} theo ${by}` }
function kpiTitle(it, cat) {
  if (it.label) return it.label; const c = cat.find(x => x.name === it.ds) || { dims: [], meas: [] }, m = c.meas.find(x => x.k === it.m), dm = c.dims.find(x => x.k === it.by), k = it.kind;
  if (k === 'count') return 'Số bản ghi'; if (k === 'rate_all') return 'Tỷ lệ đạt chung'; if (k === 'rate_low') return 'Tiêu chí có tỷ lệ thấp nhất';
  if (k === 'distinct') return dm ? 'Số ' + lc1(dm.label) : 'Số nhóm'; if (k === 'missing') return 'Chưa có dữ liệu' + (m ? ': ' + (m.short || m.label) : '');
  if (!m) return KPIK[k] || 'KPI'; const b = m.label;
  if (k === 'rate') return b; if (k === 'top') return (dm ? dm.label : 'Nhóm') + ' cao nhất theo ' + lc1(b); if (k === 'latest') return b + ' kỳ gần nhất';
  return /^(tổng|trung bình|số|tỷ lệ)/i.test(b) ? b : (k === 'avg' ? 'Trung bình ' : 'Tổng ') + lc1(b) }
const b64u = o => btoa(unescape(encodeURIComponent(JSON.stringify(o)))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const dpSrc = (title, plan, bp, edit) => `/api/dash_preview?title=${encodeURIComponent(title)}&plan=${b64u(plan)}${bp ? '&bp=' + b64u(bp) : ''}${edit ? '&edit=1' : ''}`;

/* biểu đồ từ kết quả phân tích (bước 4) -> thẻ tĩnh trên dashboard; dựng lại theo loại và trục đang chọn */
function makeStatic(c, i, s, T) {
  const kd = s['k' + i] ?? c.kind, cc = { ...c, kind: kd, x: s['x' + i] ?? c.x, y: s['y' + i] ?? c.y }, rows = (chartRows(cc, T) || []).filter(r => typeof r[1] === 'number' && isFinite(r[1])).slice(0, 40);
  if (rows.length < 2) return null;
  return { type: 'static', sid: 'rc' + i, ci: i, ds: '', by: '', m: '', agg: '', kind: kd === 'line' ? 'line' : kd === 'cols' ? 'cols' : 'bars', title: c.title || '', why: c.insight || '', labels: rows.map(r => String(r[0])), values: rows.map(r => r[1]), unit: c.unit || '', src: 'analysis', on: true, id: 'static|rc' + i } }
function syncStatic(d, s, T) { const plan = dpState(d, s); plan.forEach((x, k) => { if (x.type === 'static' && x.ci !== undefined && d.charts[x.ci]) { const n = makeStatic(d.charts[x.ci], x.ci, s, T); if (n) plan[k] = { ...n, on: x.on } } }) }

function libRows(d, s, T) {
  const plan = dpState(d, s), rows = [];
  d.charts.forEach((c, i) => { if (T[c.task]) rows.push({ k: 'rc', i, c, st: plan.find(x => x.type === 'static' && x.ci === i) }) });
  plan.forEach(x => { if (!(x.type === 'static' && x.ci !== undefined)) rows.push({ k: 'dp', it: x }) });
  return rows }
function libRow(r, d, s, T, cat) {
  if (r.k === 'rc') { const { c, i, st } = r, on = s['c' + i] ?? c.recommended, dOn = !!(st && st.on), t = T[c.task], kd = s['k' + i] ?? c.kind, x = s['x' + i] ?? c.x, y = s['y' + i] ?? c.y, cc = { ...c, kind: kd, x, y }, rows = chartRows(cc, T) || [], ks = kindsFor(rows), all = [...new Set([...ks, kd])];
    return `<div class="lrow ${on || dOn ? 'on' : ''}"><div class="lt"><b>${esc(c.title)}</b><small>Từ phân tích · ${esc(t.title)}</small></div>
<div class="lsw"><label class="sw"><input type="checkbox" data-lb="dash" data-ci="${i}" ${dOn ? 'checked' : ''}><span>Dashboard</span></label><label class="sw"><input type="checkbox" data-s="5" data-k="c${i}" ${on ? 'checked' : ''}><span>Báo cáo · Slide</span></label></div>
<details class="cpa" data-s="5" data-o="cpa${i}" ${s['cpa' + i] ? 'open' : ''}><summary>Xem trước và tùy chỉnh</summary><div class="cpb"><div class="cpv">${rows.length ? chartBody(cc, T) : '<small class="sub">Chưa có dữ liệu cho cặp trục này.</small>'}</div>
<div class="seg" role="group" aria-label="Loại biểu đồ">${all.map(k => `<button type="button" class="${k === kd ? 'on' : ''}" data-a="ckind" data-i="${i}" data-v="${k}" title="${esc(KWHY[k])}">${KIND[k]}</button>`).join('')}</div>
<div class="axes"><label>Nhãn${sel$(5, 'x' + i, t.cols, x)}</label><label>Giá trị${sel$(5, 'y' + i, numCols(t), y)}</label></div></div></details></div>` }
  const it = r.it, tag = it.type === 'static' ? 'Từ phân tích' : it.src === 'user' ? 'Bạn thêm' : 'AI gợi ý', kd = it.type === 'score' || it.type === 'heat' ? DKIND[it.type] : (DKIND[it.kind] || '');
  return `<div class="lrow ${it.on ? 'on' : ''}"><div class="lt"><b>${esc(dpTitle(it, cat))}</b><small>${tag}${kd ? ' · ' + kd : ''}${cat.length > 1 && it.ds ? ' · ' + esc(it.ds) : ''}${it.m === '*' ? ' · theo chỉ số đang chọn' : ''}${it.type === 'static' ? ' · không đổi theo bộ lọc' : ''}${it.why && it.src === 'ai' ? ' · ' + esc(it.why) : ''}</small></div>
<div class="lsw"><label class="sw"><input type="checkbox" data-dp="${esc(it.id)}" ${it.on ? 'checked' : ''}><span>Dashboard</span></label>${it.src !== 'ai' ? `<button type="button" class="rm" data-dpa="rm" data-v="${esc(it.id)}" title="Bỏ khỏi thư viện" aria-label="Bỏ khỏi thư viện">${ico('trash', 15)}</button>` : ''}</div></div>` }
function libInner(d, s, T, r3) {
  const cat = catOf(d), plan = dpState(d, s), bp = bpState(d, s), rows = libRows(d, s, T), nDash = plan.filter(x => x.on).length, nRep = d.charts.filter((c, i) => T[c.task] && (s['c' + i] ?? c.recommended)).length;
  const kp = bp.kpis || [], blk = bp.blocks || {};
  return `<div class="lh"><b>Thư viện biểu đồ</b><small>${nDash} trên bảng điều khiển · ${nRep} trong báo cáo</small></div>
<div class="ask" style="padding:6px 0 0"><label for="rt5">Tiêu đề báo cáo</label><input id="rt5" data-s="5" data-i="rt" value="${esc(s.rt ?? d.title)}"></div>
<label class="lsel">Phông chữ báo cáo và bảng điều khiển<select data-bp="font">${Object.entries(FONTS).map(([v, l]) => `<option value="${v}" ${(bp.font || 'claude') === v ? 'selected' : ''}>${l}</option>`).join('')}</select><small class="sub">Bản trình chiếu PowerPoint luôn dùng Arial.</small></label>
${d.dash ? `<label class="lsel">Kiểu bố cục bảng điều khiển<select data-bp="layout">${Object.entries(LAYOUTS).map(([v, l]) => `<option value="${v}" ${bp.layout === v ? 'selected' : ''}>${l}</option>`).join('')}</select></label>` : ''}
<details class="lsec" data-s="5" data-o="sec_ch" ${s.sec_ch === false ? '' : 'open'}><summary>Biểu đồ <small>${rows.length}</small></summary>${rows.map(r => libRow(r, d, s, T, cat)).join('') || '<small class="sub">Chưa có biểu đồ nào.</small>'}
<button type="button" class="btn g sm lbtn" data-dw="open" data-t="data">+ Thêm biểu đồ</button></details>
${d.dash ? `<details class="lsec" data-s="5" data-o="sec_kp" ${s.sec_kp === false ? '' : 'open'}><summary>Thẻ KPI trên bảng điều khiển <small>${kp.filter(x => x.on !== false).length}/${kp.length}</small></summary>${kp.map(k => `<label class="lk"><input type="checkbox" data-bpk="${esc(k.id)}" ${k.on !== false ? 'checked' : ''}><span>${esc(kpiTitle(k, cat))}</span></label>`).join('') || '<small class="sub">Chưa có thẻ KPI. Bảng điều khiển sẽ không hiện thẻ nào.</small>'}
<button type="button" class="btn g sm lbtn" data-dw="open" data-t="kpi">+ Thêm thẻ KPI</button></details>
<details class="lsec" data-s="5" data-o="sec_bl" ${s.sec_bl ? 'open' : ''}><summary>Các khối trên trang</summary>${BLOCKS.map(([k, l]) => `<label class="lk"><input type="checkbox" data-bpb="${k}" ${blk[k] !== false ? 'checked' : ''}><span>${l}</span></label>`).join('')}<label class="lk"><input type="checkbox" data-bpb="table" ${bp.table && bp.table.on === false ? '' : 'checked'}><span>Bảng chi tiết</span></label></details>` : ''}
<details class="lsec" data-s="5" data-o="sec_rk" ${s.sec_rk ? 'open' : ''}><summary>Chỉ số (KPI) trong báo cáo và slide</summary>${r3.kpis.map((k, i) => !String(k.value ?? '').trim() ? '' : `<label class="opt ${(s['p' + i] ?? true) ? 'on' : ''}"><input type="checkbox" data-s="5" data-k="p${i}" ${(s['p' + i] ?? true) ? 'checked' : ''}><span><b>${esc(fv(k.value))}</b><small>${esc(k.label)}</small></span></label>`).join('')}</details>` }
const libHTML = (d, s, T, r3) => `<aside class="s6l" id="lib"><div id="libin">${libInner(d, s, T, r3)}</div></aside>`;
/* vẽ lại thư viện và đẩy kế hoạch + bản thiết kế sang bản xem thử, KHÔNG tải lại khung */
function libPaint() { const S = S_(), d = S.d[5], s = sel(5), T = S.d[3].result.tables, el = document.getElementById('libin'); syncStatic(d, s, T); if (el) el.innerHTML = libInner(d, s, T, S.d[3].result);
  const f = document.querySelector('iframe.dashf'); if (f && f.contentWindow) f.contentWindow.postMessage({ type: 'mc-plan', plan: dpState(d, s), bp: bpState(d, s) }, location.origin); if (DW.el) dwPaint() }
const dpPaint = libPaint;

/* ---- ngăn kéo "Thêm": biểu đồ từ dữ liệu · từ kết quả phân tích · thẻ KPI ---- */
const DW = { el: null, t: 'data', ds: 0, b: null, f: null, k: null, q: '' };
function dpKinds(c, b) { const m = c.meas.find(x => x.k === b.m), agg = b.m === '' ? 'count' : (m && m.rate ? 'avg' : b.agg); return b.by === 't' ? ['trend', 'cols'] : ['bars', 'cols', ...(agg !== 'avg' && (c.dims.find(x => x.k === b.by) || { n: 99 }).n <= 12 ? ['donut'] : [])] }
function dwData(d, s) {
  const cat = catOf(d), plan = dpState(d, s); if (!cat.length) return '<small class="sub">Dữ liệu chưa đủ cột phân loại hoặc ngày tháng để dựng biểu đồ từ dữ liệu.</small>';
  const c = cat[Math.min(DW.ds, cat.length - 1)], rates = c.meas.filter(x => x.rate), q = lc1(DW.q.trim());
  const b = DW.b = (DW.b && DW.b.ds === c.name) ? DW.b : { ds: c.name, by: c.dims[0] ? c.dims[0].k : (c.time ? 't' : ''), m: c.meas[0] ? c.meas[0].k : '', agg: c.meas[0] && c.meas[0].avg ? 'avg' : 'sum', kind: '' };
  const m = c.meas.find(x => x.k === b.m), agg = b.m === '' ? 'count' : (m && m.rate ? 'avg' : b.agg), kinds = dpKinds(c, b), kind = kinds.includes(b.kind) ? b.kind : kinds[0]; b.kind = kind;
  const id = [c.name, b.by, b.m, agg, kind].join('|'), dup = plan.some(x => x.id === id), full = plan.length >= 16;
  const dims = [...(c.time ? [['t', 'Thời gian (theo tháng)']] : []), ...c.dims.map(x => [x.k, `${x.label} · ${x.n} nhóm`])].filter(([k, l]) => !q || lc1(l).includes(q) || k === b.by);
  const so = (key, opts, cur) => `<select data-dwi="${key}">${opts.map(([v, l]) => `<option value="${esc(v)}" ${v === cur ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
  const quick = [...(rates.length >= 1 ? [`<button type="button" class="chip" data-dw="addrate" data-v="score">Bảng điểm: tỷ lệ đạt từng tiêu chí</button>`] : []), ...(rates.length >= 1 && c.dims.length ? c.dims.slice(0, 6).map(x => `<button type="button" class="chip" data-dw="addrate" data-v="heat" data-by="${x.k}">Ma trận: ${esc(x.label)} × tiêu chí</button>`) : [])];
  return `${cat.length > 1 ? `<div class="seg" role="group" aria-label="Bảng dữ liệu">${cat.map((x, i) => `<button type="button" class="${i === DW.ds ? 'on' : ''}" data-dw="ds" data-v="${i}">${esc(x.title || x.name)}</button>`).join('')}</div>` : ''}
${quick.length ? `<h5>Gợi ý nhanh cho dữ liệu đạt / không đạt</h5><div class="chips">${quick.join('')}</div>` : ''}
<h5>Tự chọn</h5><div class="dwf"><label>Tìm cột<input data-dwi="q" value="${esc(DW.q)}" placeholder="Gõ tên cột…"></label>
<label>Xem theo ${so('by', dims, b.by)}</label><label>Đo bằng ${so('m', [['', 'Số bản ghi'], ...c.meas.map(x => [x.k, x.label])], b.m)}</label>
${b.m !== '' && !(m && m.rate) ? `<label>Tính theo ${so('agg', [['sum', 'Tổng'], ['avg', 'Trung bình']], agg)}</label>` : ''}<label>Dạng biểu đồ ${so('kind', kinds.map(k => [k, DKIND[k]]), kind)}</label></div>
<button type="button" class="btn" data-dw="add" ${dup || full || !b.by ? 'disabled' : ''}>${dup ? 'Biểu đồ này đã có' : full ? 'Đã đủ 16 biểu đồ' : '+ Thêm vào bảng điều khiển'}</button>` }
function dwAnalysis(d, s, T) {
  const plan = dpState(d, s), have = new Set(plan.filter(x => x.type === 'static').map(x => x.ci)), left = d.charts.map((c, i) => [c, i]).filter(([c, i]) => T[c.task] && !have.has(i));
  const f = DW.f = DW.f || { task: 0, x: '', y: '', kind: 'bars' }, tabs = T.map((t, i) => [t, i]).filter(([t]) => t.cols.length >= 2 && numCols(t).length), t0 = T[f.task] && tabs.some(([, i]) => i === f.task) ? T[f.task] : (tabs[0] ? tabs[0][0] : null);
  if (t0) { f.task = T.indexOf(t0); if (!t0.cols.includes(f.x)) f.x = t0.cols[0]; if (!numCols(t0).includes(f.y)) f.y = numCols(t0)[0] }
  const so = (key, opts, cur) => `<select data-dwi="${key}">${opts.map(o => `<option value="${esc(o)}" ${o === cur ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select>`;
  return `<h5>Biểu đồ AI đã đề xuất từ phân tích</h5>${left.map(([c, i]) => `<div class="lrow on"><div class="lt"><b>${esc(c.title)}</b><small>${esc(c.insight || '')}</small></div><button type="button" class="btn g sm" data-dw="addrc" data-i="${i}">+ Thêm</button></div>`).join('') || '<small class="sub">Mọi biểu đồ AI đề xuất đã có trên bảng điều khiển.</small>'}
<h5>Tự chọn từ một bảng kết quả</h5>${t0 ? `<div class="dwf"><label>Bảng kết quả<select data-dwi="task">${tabs.map(([t, i]) => `<option value="${i}" ${i === f.task ? 'selected' : ''}>${esc(t.title)}</option>`).join('')}</select></label><label>Nhãn ${so('fx', t0.cols, f.x)}</label><label>Giá trị ${so('fy', numCols(t0), f.y)}</label>
<label>Dạng<select data-dwi="fkind">${[['bars', 'Cột ngang'], ['cols', 'Cột dọc'], ['line', 'Đường']].map(([v, l]) => `<option value="${v}" ${f.kind === v ? 'selected' : ''}>${l}</option>`).join('')}</select></label></div>
<button type="button" class="btn" data-dw="addfree" ${f.x === f.y ? 'disabled' : ''}>+ Thêm vào bảng điều khiển</button><p class="hint">Biểu đồ từ kết quả phân tích đã được tổng hợp sẵn nên không đổi theo bộ lọc của bảng điều khiển.</p>` : '<small class="sub">Chưa có bảng kết quả có cột số.</small>'}` }
function dwKpi(d, s) {
  const cat = catOf(d), bp = bpState(d, s); if (!cat.length) return '<small class="sub">Chưa có dữ liệu để tạo thẻ KPI.</small>';
  const c = cat[Math.min(DW.ds, cat.length - 1)], k = DW.k = (DW.k && DW.k.ds === c.name) ? DW.k : { ds: c.name, kind: c.meas.some(x => x.rate) ? 'rate_all' : 'count', m: '', by: '', label: '' };
  const needM = ['sum', 'avg', 'rate', 'latest', 'top', 'missing'].includes(k.kind), needBy = ['distinct', 'top'].includes(k.kind), rates = c.meas.filter(x => x.rate), nums = c.meas.filter(x => !x.rate);
  const mOpts = k.kind === 'rate' || k.kind === 'missing' ? rates : k.kind === 'sum' ? nums : c.meas;
  const kinds = Object.keys(KPIK).filter(x => !(['rate', 'rate_all', 'rate_low'].includes(x) && !rates.length) && !(x === 'latest' && !c.time) && !(['distinct', 'top'].includes(x) && !c.dims.length) && !(['sum', 'avg', 'latest', 'top'].includes(x) && !nums.length && !rates.length));
  if (!kinds.includes(k.kind)) k.kind = kinds[0]; if (needM && !mOpts.some(x => x.k === k.m)) k.m = (mOpts[0] || {}).k || ''; if (needBy && !c.dims.some(x => x.k === k.by)) k.by = (c.dims[0] || {}).k || '';
  const it = { ds: c.name, kind: k.kind, m: needM ? k.m : '', by: needBy ? k.by : '', label: k.label.trim() }, id = 'kpi|' + [it.ds, it.kind, it.m, it.by].join('|'), dup = (bp.kpis || []).some(x => x.id === id), full = (bp.kpis || []).length >= 12;
  const so = (key, opts, cur) => `<select data-dwi="${key}">${opts.map(([v, l]) => `<option value="${esc(v)}" ${v === cur ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
  return `${cat.length > 1 ? `<div class="seg" role="group" aria-label="Bảng dữ liệu">${cat.map((x, i) => `<button type="button" class="${i === DW.ds ? 'on' : ''}" data-dw="ds" data-v="${i}">${esc(x.title || x.name)}</button>`).join('')}</div>` : ''}
<div class="dwf"><label>Loại thẻ ${so('kk', kinds.map(x => [x, KPIK[x]]), k.kind)}</label>${needM ? `<label>Chỉ số ${so('km', mOpts.map(x => [x.k, x.label]), k.m)}</label>` : ''}${needBy ? `<label>Nhóm theo ${so('kb', c.dims.map(x => [x.k, x.label]), k.by)}</label>` : ''}
<label>Tên thẻ (tùy chọn)<input data-dwi="kl" value="${esc(k.label)}" placeholder="${esc(kpiTitle(it, cat))}"></label></div>
<button type="button" class="btn" data-dw="addkpi" ${dup || full || (needM && !k.m) ? 'disabled' : ''}>${dup ? 'Thẻ này đã có' : '+ Thêm thẻ KPI'}</button><p class="hint">Thẻ KPI tính lại theo bộ lọc của người xem. "Số bản ghi" chỉ nên dùng khi câu hỏi của bạn thật sự là đếm.</p>` }
function dwHTML() { const S = S_(), d = S.d[5], s = sel(5), T = S.d[3].result.tables;
  return `<div class="tph"><b>Thêm vào bảng điều khiển</b><button type="button" class="ib tpx" data-dw="close" aria-label="Đóng">${ico('x', 16)}</button></div>
<div class="seg" role="tablist">${[['data', 'Từ dữ liệu'], ['an', 'Từ phân tích'], ['kpi', 'Thẻ KPI']].map(([k, l]) => `<button type="button" role="tab" class="${DW.t === k ? 'on' : ''}" data-dw="tab" data-v="${k}">${l}</button>`).join('')}</div>
<div class="dwb">${DW.t === 'data' ? dwData(d, s) : DW.t === 'an' ? dwAnalysis(d, s, T) : dwKpi(d, s)}</div>` }
function dwPaint() { if (!DW.el) return; const y = DW.el.querySelector('.dwb') ? DW.el.querySelector('.dwb').scrollTop : 0; DW.el.firstElementChild.innerHTML = dwHTML(); const b = DW.el.querySelector('.dwb'); if (b) b.scrollTop = y }
function dwOpen(t) { if (DW.el) return; DW.t = t || 'data'; const ov = document.createElement('div'); ov.className = 'ov dwr'; ov.innerHTML = '<div class="dlg drw" role="dialog" aria-modal="true" aria-label="Thêm vào bảng điều khiển"></div>'; document.body.appendChild(ov); DW.el = ov; dwPaint();
  ov.addEventListener('click', e => { if (e.target === ov) dwClose() }); DW.key = e => { if (e.key === 'Escape') { e.stopPropagation(); dwClose() } }; document.addEventListener('keydown', DW.key, true) }
function dwClose() { if (!DW.el) return; document.removeEventListener('keydown', DW.key, true); DW.el.remove(); DW.el = null }
function dwAddPlan(it) { const S = S_(), d = S.d[5], s = sel(5), plan = dpState(d, s); if (plan.some(x => x.id === it.id) || plan.length >= 16) return false; plan.push(it); libPaint(); return true }
/* bản xem thử báo cáo thay đổi (ẩn / đổi dạng / di chuyển / thêm) -> cập nhật kế hoạch */
function nextKind(it, cat) { if (it.type) return null; const c = cat.find(x => x.name === it.ds); if (!c) return null; const m = c.meas.find(x => x.k === it.m), rate = m && m.rate, dn = (c.dims.find(x => x.k === it.by) || { n: 99 }).n;
  const ks = it.by === 't' ? ['trend', 'cols'] : ['bars', 'cols', ...(it.m !== '*' && it.agg !== 'avg' && !rate && dn <= 12 ? ['donut'] : [])]; return ks[(ks.indexOf(it.kind) + 1) % ks.length] }
function dpEdit(op, id) {
  const S = S_(), d = S.d[5], s = sel(5), plan = dpState(d, s), bp = bpState(d, s), cat = catOf(d); if (RO() || S.st[5] !== 'await') return;
  if (op === 'add') { dwOpen('data'); return }
  if (id.startsWith('kpi|')) { const k = (bp.kpis || []).find(x => x.id === id); if (k && op === 'hide') k.on = false; libPaint(); return }
  const k = plan.findIndex(x => x.id === id); if (k < 0) return; const it = plan[k], on = x => x.on !== false;
  if (op === 'hide') it.on = false;
  else if (op === 'kind') { const nk = nextKind(it, cat); if (nk) { it.kind = nk; it.id = [it.ds, it.by, it.m, it.agg, it.kind].join('|'); if (plan.some((x, q) => q !== k && x.id === it.id)) plan.splice(k, 1) } }
  else if (op === 'up' || op === 'down') { const dir = op === 'up' ? -1 : 1; let q = k + dir; while (q >= 0 && q < plan.length && !(on(plan[q]) && (plan[q].ds === it.ds || plan[q].type === 'static' || it.type === 'static'))) q += dir; if (q >= 0 && q < plan.length) { const tmp = plan[k]; plan[k] = plan[q]; plan[q] = tmp } }
  libPaint() }
window.addEventListener('message', e => { const m = e.data, f = document.querySelector('iframe.dashf'); if (e.origin !== location.origin || !m || m.type !== 'mc-edit' || !f || e.source !== f.contentWindow) return; dpEdit(String(m.op || ''), String(m.id || '')) });

/* ======================= sự kiện của các thành phần trên ======================= */
document.addEventListener('click', e => {
  const t = e.target;
  const dk = t.closest('[data-dk]'); if (dk) { const [k, ...v] = dk.dataset.dk.split(':'), val = v.join(':'); if (k === 'file') { DIST.file = val; DIST.more = false } else if (k === 'kind') { DIST.kind = val; DIST.more = false } else if (k === 'more') DIST.more = !DIST.more; stage(); return }
  const dpa = t.closest('[data-dpa]'); if (dpa && !RO()) { const S = S_(), d = S.d[5], s = sel(5), plan = dpState(d, s); if (dpa.dataset.dpa === 'rm') s.dash = plan.filter(x => x.id !== dpa.dataset.v); libPaint(); return }
  const dw = t.closest('[data-dw]'); if (dw && !RO()) { const S = S_(), d = S.d[5], s = sel(5), T = S.d[3].result.tables, cat = catOf(d), a = dw.dataset.dw, v = dw.dataset.v;
    if (a === 'open') dwOpen(dw.dataset.t); else if (a === 'close') dwClose(); else if (a === 'tab') { DW.t = v; dwPaint() } else if (a === 'ds') { DW.ds = +v; DW.b = DW.k = null; dwPaint() }
    else if (a === 'add') { const c = cat[Math.min(DW.ds, cat.length - 1)], b = DW.b, m = c.meas.find(x => x.k === b.m), agg = b.m === '' ? 'count' : (m && m.rate ? 'avg' : b.agg), it = { ds: c.name, by: b.by, m: b.m, agg, kind: b.kind, title: '', why: 'Bạn chọn', src: 'user', on: true }; it.id = [it.ds, it.by, it.m, it.agg, it.kind].join('|'); dwAddPlan(it) }
    else if (a === 'addrate') { const c = cat[Math.min(DW.ds, cat.length - 1)], it = { type: v, ds: c.name, by: dw.dataset.by || '', m: '', agg: 'avg', kind: v, ms: [], title: '', why: 'Bạn chọn', src: 'user', on: true }; it.id = v === 'score' ? `score|${c.name}|` : `heat|${c.name}|${it.by}|`; dwAddPlan(it) }
    else if (a === 'addrc') { const i = +dw.dataset.i, n = makeStatic(d.charts[i], i, s, T); if (n) dwAddPlan(n) }
    else if (a === 'addfree') { const f = DW.f, t0 = T[f.task]; if (t0) { const rows = (t0.rows || []).map(r => [String(r[t0.cols.indexOf(f.x)]), r[t0.cols.indexOf(f.y)]]).filter(r => typeof r[1] === 'number' && isFinite(r[1])).slice(0, 40);
      if (rows.length >= 2) { const sid = `free${f.task}-${f.x}-${f.y}`.slice(0, 70); dwAddPlan({ type: 'static', sid, ds: '', by: '', m: '', agg: '', kind: f.kind, title: `${f.y} theo ${lc1(f.x)}`, why: t0.title, labels: rows.map(r => r[0]), values: rows.map(r => r[1]), unit: '', src: 'analysis', on: true, id: 'static|' + sid }) } } }
    else if (a === 'addkpi') { const k = DW.k, bp = bpState(d, s), needM = ['sum', 'avg', 'rate', 'latest', 'top', 'missing'].includes(k.kind), needBy = ['distinct', 'top'].includes(k.kind), it = { ds: k.ds, kind: k.kind, m: needM ? k.m : '', by: needBy ? k.by : '', label: k.label.trim(), on: true }; it.id = 'kpi|' + [it.ds, it.kind, it.m, it.by].join('|');
      bp.kpis = bp.kpis || []; if (!bp.kpis.some(x => x.id === it.id)) { bp.kpis.push(it); libPaint() } }
    return }
  const b = t.closest('[data-a]'); if (!b || RO()) return; const a = b.dataset.a, v = b.dataset.v, S = S_(), d = S.d[3], s = d && SEL[3] ? sel(3) : null;
  if (!s || V !== 3 || !d || d.phase !== 'menu') return;
  if (a === 'a3sel') { d.menu.forEach(m => s['a' + m.id] = v === 'all'); stage() }
  else if (a === 'a3more') { sel(3); keepSnap(3); if (KEEP[3]) KEEP[3].more = true; post('/api/a3/more').then(ok => { if (!ok) delete KEEP[3] }) }       // giữ lựa chọn đang chọn dở; mục mới do «góc nhìn khác» để bạn tự tick
  else if (a === 'bmode') { bState(d, s).mode = v; stage() }
  else if (a === 'btype') { const bb = bState(d, s); bb.type = v; bDefaults(d, bb); stage(); bValidate() }
  else if (a === 'brg') { bState(d, s).rg = v; stage(); bValidate() }
  else if (a === 'bgrain') { bState(d, s).grain = v; stage(); bValidate() }
  else if (a === 'bchip') { const bb = bState(d, s); bAssign(d, bb, v); stage(); bValidate() }
  else if (a === 'badd') { const p = s.bprev; if (p && p.ok && (s.specs || []).length < 12) { s.specs = s.specs || []; if (!s.specs.some(x => JSON.stringify(x.spec) === JSON.stringify(p.spec))) s.specs.push({ spec: p.spec, src: 'pick' }); stage() } }
  else if (a === 'brm') { (s.specs || []).splice(+v, 1); stage() }
  else if (a === 'bfree') { s.specs = s.specs || []; s.specs.push({ spec: { type: 'free', text: v, title: v.slice(0, 70), goal: v, vars: [] }, src: 'text' }); if (s.bres) s.bres.unclear = ''; stage() }
  else if (a === 'bparse') { const txt = (s.btxt || '').trim(); if (!txt) { notify('Hãy mô tả điều bạn muốn phân tích.', 'warn'); return } s.bbusy = true; stage();
    api('/api/a3/parse', { text: txt }).then(r => { s.bbusy = false; if (r) { s.specs = s.specs || []; let n = 0; r.specs.forEach(sp => { if (s.specs.length < 12 && !s.specs.some(x => JSON.stringify(x.spec) === JSON.stringify(sp))) { s.specs.push({ spec: sp, src: 'text' }); n++ } }); s.bres = { rejected: r.rejected || [], unclear: r.unclear || '', n } } stage() }) }
});
document.addEventListener('change', e => {
  const t = e.target;
  if (t.dataset.dp !== undefined && !RO()) { const S = S_(), d = S.d[5], it = dpState(d, sel(5)).find(x => x.id === t.dataset.dp); if (it) it.on = t.checked; libPaint(); return }
  if (t.dataset.lb === 'dash' && !RO()) { const S = S_(), d = S.d[5], s = sel(5), T = S.d[3].result.tables, i = +t.dataset.ci, plan = dpState(d, s), st = plan.find(x => x.type === 'static' && x.ci === i);
    if (st) st.on = t.checked; else if (t.checked) { const n = makeStatic(d.charts[i], i, s, T); if (n) plan.push(n); else notify('Biểu đồ này chưa có đủ dữ liệu để đưa lên bảng điều khiển.', 'warn') } libPaint(); return }
  if (t.dataset.bpk && !RO()) { const S = S_(), bp = bpState(S.d[5], sel(5)), k = (bp.kpis || []).find(x => x.id === t.dataset.bpk); if (k) k.on = t.checked; libPaint(); return }
  if (t.dataset.bpb && !RO()) { const S = S_(), bp = bpState(S.d[5], sel(5)), k = t.dataset.bpb; if (k === 'table') bp.table = { on: t.checked }; else { bp.blocks = bp.blocks || {}; bp.blocks[k] = t.checked } libPaint(); return }
  if (t.dataset.bp === 'layout' && !RO()) { bpState(S_().d[5], sel(5)).layout = t.value; libPaint(); return }
  if (t.dataset.bp === 'font' && !RO()) { bpState(S_().d[5], sel(5)).font = t.value; libPaint(); return }
  if (t.dataset.dwi !== undefined && !RO()) { const S = S_(), d = S.d[5], k = t.dataset.dwi, v = t.value, b = DW.b, f = DW.f, kp = DW.k;
    if (k === 'q') { DW.q = v; dwPaint(); const q = DW.el && DW.el.querySelector('[data-dwi="q"]'); if (q) { q.focus(); q.setSelectionRange(v.length, v.length) } return }
    if (b && ['by', 'm', 'agg', 'kind'].includes(k)) { b[k] = v; if (k === 'by' || k === 'm') b.kind = ''; if (k === 'm') { const c = catOf(d).find(x => x.name === b.ds), x = c && c.meas.find(y => y.k === v); b.agg = x && x.avg ? 'avg' : 'sum' } }
    else if (f && ['task', 'fx', 'fy', 'fkind'].includes(k)) { if (k === 'task') { f.task = +v; f.x = f.y = '' } else if (k === 'fx') f.x = v; else if (k === 'fy') f.y = v; else f.kind = v }
    else if (kp && ['kk', 'km', 'kb', 'kl'].includes(k)) { if (k === 'kk') { kp.kind = v; kp.m = kp.by = '' } else if (k === 'km') kp.m = v; else if (k === 'kb') kp.by = v; else kp.label = v }
    dwPaint(); return }
  if (t.dataset.b && !RO()) { const S = S_(), d = S.d[3], s = sel(3), b = bState(d, s), k = t.dataset.b, v = t.value;
    if (k === 'file') { b.file = v; b.m = [{ col: '', agg: 'sum' }, { col: '', agg: 'sum' }]; b.by = ['', '']; b.tc = b.x = b.y = b.c = ''; b.rc = []; b.rg = 'none'; bDefaults(d, b) }
    else if (k === 'rcx') { const i = b.rc.indexOf(v); if (t.checked && i < 0) b.rc.push(v); else if (!t.checked && i >= 0) b.rc.splice(i, 1) }
    else if (/^mcol\d$/.test(k)) { b.m[+k[4]].col = v } else if (/^magg\d$/.test(k)) { b.m[+k[4]].agg = v }
    else if (/^by\d$/.test(k)) { b.by[+k[2]] = v; if (b.by[0] && b.by[0] === b.by[1]) b.by[1] = '' } else if (k !== 'text') b[k] = v;
    if (k !== 'text') { stage(); bValidate() } } });
document.addEventListener('input', e => { const t = e.target; if (t.dataset.b === 'text' && !RO()) sel(3).btxt = t.value;
  if (t.dataset.dwi === 'q' && !RO()) { DW.q = t.value; dwPaint(); const q = DW.el && DW.el.querySelector('[data-dwi="q"]'); if (q) { q.focus(); q.setSelectionRange(q.value.length, q.value.length) } }
  else if (t.dataset.dwi === 'kl' && DW.k) DW.k.label = t.value });
document.addEventListener('toggle', e => { const d = e.target; if (d.dataset && d.dataset.o && !RO()) sel(+d.dataset.s)[d.dataset.o] = d.open }, true);
