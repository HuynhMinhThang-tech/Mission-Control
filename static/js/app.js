/* Mission Control · giao diện. ST = phiên đang làm (live); R = bản lưu đang xem lại (chỉ đọc). */
const $ = id => document.getElementById(id), esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const STEPS = [{ t: 'Dữ liệu và bối cảnh', i: 'database' }, { t: 'Kiểm tra và mô tả dữ liệu', i: 'search' }, { t: 'Làm sạch dữ liệu', i: 'sparkles' }, { t: 'Phân tích', i: 'chart' },
  { t: 'Insight và hành động', i: 'bulb' }, { t: 'Báo cáo', i: 'file' }, { t: 'Review và export', i: 'shield' }];
const N = v => Number(v).toLocaleString('vi-VN', { maximumFractionDigits: 2 }), NC = v => new Intl.NumberFormat('vi-VN', { notation: 'compact', maximumFractionDigits: 1 }).format(v);
const pad = n => String(n).padStart(2, '0');
const fmtDate = d => d ? `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}` : '—';
const fmtTime = d => d ? `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}` : '—';
const fmtDur = (a, b) => { if (!a || !b) return '—'; let s = Math.max(0, Math.round((b - a) / 1000)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60); s %= 60; return h ? `${h} giờ ${m} phút` : m ? `${m} phút ${s} giây` : `${s} giây` };

let ST = null, R = null, SAVEV = 0, V = 0, NAV = 'flow', TAB = 'dash', FB = false, BUSY = false, SEL = {};
const U = { ctx: '', fbt: '' };
const S_ = () => R || ST, RO = () => !!R;
const sel = i => { const d = S_().d[i], g = d && d.gen; if (!SEL[i] || SEL[i].g !== g) SEL[i] = { g }; return SEL[i] };

/* ---------- thành phần hiển thị ---------- */
const bar = (rows, u = '') => { if (!rows.length) return ''; const m = Math.max(...rows.map(r => Math.abs(r[1]))) || 1, sg = rows.some(r => r[1] < 0);
  return rows.map(([l, v]) => `<div class="br"><span class="l" title="${esc(l)}">${esc(l)}</span><span class="tr"><span class="bf ${v < 0 ? 'neg' : ''}" style="width:${Math.abs(v) / m * 100}%"></span></span><span class="v">${sg ? (v > 0 ? '+' : v < 0 ? '−' : '') : ''}${N(Math.abs(v))}${esc(u)}</span></div>`).join('') };
const cols = rows => { rows = rows.slice(-14); const m = Math.max(...rows.map(r => Math.abs(r[1]))) || 1, hi = rows.findIndex(r => Math.abs(r[1]) === m);
  return `<div class="cols">${rows.map(([l, v], i) => `<div><i class="${i === hi ? 'hi' : ''}" style="height:${Math.abs(v) / m * 80}px"></i>${esc(String(l).slice(0, 8))}<br>${NC(v)}</div>`).join('')}</div>` };
const kp = a => `<div class="kpis">${a.map(([l, v, d]) => `<div class="kpi"><b>${esc(v)}</b><small>${esc(l)}${d ? ' · ' + esc(d) : ''}</small></div>`).join('')}</div>`;
const kpo = a => kp(a.map(k => [k.label, k.value, k.delta]));
const tbl = (h, r) => `<div class="tw"><table><thead><tr>${h.map(x => `<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${r.map(x => `<tr>${x.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
const fnd = (t, s, c = '') => `<div class="f ${c}"><span class="tg">${esc(s || 'Phát hiện')}</span>${t}</div>`;
const cell = c => c === null ? '<span style="color:var(--warn)">thiếu</span>' : esc(typeof c === 'number' ? N(c) : c);
const tableOf = t => t.err && !t.cols.length ? `<div class="note">${esc(t.title)}: ${esc(t.err)}</div>` : tbl(t.cols, t.rows.slice(0, 30).map(r => r.map(cell)));
const numCols = t => t.cols.filter((c, i) => t.rows.some(r => typeof r[i] === 'number'));
const PAL = ['#4F46E5', '#0EA5E9', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#64748B'];
const TIME = /^(\d{4}[-\/]\d{1,2}|\d{1,2}[-\/]\d{4}|Q[1-4]|T\d{1,2}|Tháng|W\d|\d{4}$)/i;
function uniq(rows, kind) { const seen = new Set(), o = []; rows.forEach(r => { const k = r[0] + '|' + r[1]; if (!seen.has(k)) { seen.add(k); o.push(r) } });
  if (kind === 'line' || (rows.length >= 4 && rows.filter(r => TIME.test(r[0])).length / rows.length >= .6)) return o;
  const m = new Map(); o.forEach(([l, v]) => m.set(l, (m.get(l) || 0) + v)); return [...m] }
const line = rows => { rows = rows.slice(-24); if (rows.length < 2) return bar(rows); const W = 300, H = 110, mx = Math.max(...rows.map(r => r[1])), mn = Math.min(...rows.map(r => r[1])), sp = (mx - mn) || 1;
  const pts = rows.map((r, i) => [6 + i * (W - 12) / Math.max(rows.length - 1, 1), 8 + (mx - r[1]) / sp * (H - 30)]);
  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:360px;height:auto;display:block"><polyline fill="none" stroke="var(--pri)" stroke-width="2.2" points="${pts.map(p => p.join(',')).join(' ')}"/>${pts.map(p => `<circle cx="${p[0]}" cy="${p[1]}" r="2.6" fill="var(--pri)"/>`).join('')}<text x="6" y="${H - 4}" font-size="9" fill="var(--sub)">${esc(rows[0][0])}</text><text x="${W - 6}" y="${H - 4}" font-size="9" text-anchor="end" fill="var(--sub)">${esc(rows[rows.length - 1][0])}</text></svg>` };
const donut = rows => { rows = rows.filter(r => r[1] > 0).sort((a, b) => b[1] - a[1]); if (rows.length < 2) return bar(rows); if (rows.length > 7) { const rest = rows.slice(6).reduce((s, r) => s + r[1], 0); rows = [...rows.slice(0, 6), ['Khác', rest]] }
  const tot = rows.reduce((s, r) => s + r[1], 0) || 1; let acc = 0; const g = rows.map((r, i) => { const a = acc / tot * 100; acc += r[1]; return `${PAL[i % 7]} ${a}% ${acc / tot * 100}%` }).join(',');
  return `<div style="display:flex;gap:16px;align-items:center"><div style="width:110px;height:110px;border-radius:50%;background:conic-gradient(${g});flex:none;position:relative"><div style="position:absolute;inset:26px;border-radius:50%;background:var(--p2)"></div></div><div style="font-size:12px;flex:1">${rows.map((r, i) => `<div><span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${PAL[i % 7]};margin-right:6px"></span>${esc(r[0])} <b>${N(r[1] / tot * 100)}%</b></div>`).join('')}</div></div>` };
const KIND = { bars: 'Cột ngang', cols: 'Cột dọc', line: 'Đường', donut: 'Tròn' };
const kindSel = (s, k, cur) => `<select data-s="${s}" data-k="${k}">${Object.entries(KIND).map(([v, l]) => `<option value="${v}" ${v === cur ? 'selected' : ''}>${l}</option>`).join('')}</select>`;
function chart(c, T) { const t = T[c.task]; if (!t) return ''; const xi = t.cols.indexOf(c.x), yi = t.cols.indexOf(c.y); if (xi < 0 || yi < 0) return '';
  const rows = uniq(t.rows.map(r => [String(r[xi]), Number(r[yi]) || 0]), c.kind).slice(0, 24);
  return `<div class="box"><h4>${esc(c.title)}${c.unit ? ' (' + esc(c.unit) + ')' : ''}</h4>${c.kind === 'cols' ? cols(rows) : c.kind === 'line' ? line(rows) : c.kind === 'donut' ? donut(rows) : bar(rows, '')}${c.insight ? `<div class="hint">${esc(c.insight)}</div>` : ''}</div>` }
const sel$ = (s, k, opts, cur) => `<select data-s="${s}" data-k="${k}">${opts.map(o => `<option ${o === cur ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select>`;
const ico = (n, s) => ic(n, s);

function structCard(S, f) {
  const m = (S.struct || {})[f.name]; if (!m || m.verdict === 'tidy') return '';
  const edit = S.st[0] !== 'done' && !RO(), nm = esc(f.name);
  const T = { fixed: ['ok', 'Đã tự chuẩn hóa'], warn: ['warn', 'Cấu trúc chưa lý tưởng'], bad: ['bad', 'Cấu trúc không phù hợp'], detected: ['ok', m.rank === 1 && m.sheet_tables > 1 ? 'Tự nhận diện bảng · bảng chính' : 'Tự nhận diện bảng'] }[m.verdict];
  const needAck = m.verdict === 'bad' || (m.verdict === 'fixed' && m.mode === 'original');
  let btn = '';
  if (edit) {
    if (m.verdict === 'fixed' || (m.verdict === 'detected' && m.sheet_tables === 1)) btn += m.mode === 'fixed' ? `<button class="btn g sm" data-a="sorig" data-v="${nm}">Dùng bản gốc</button>` : `<button class="btn sm" data-a="sfixed" data-v="${nm}">Dùng bản đã chuẩn hóa</button>`;
    if (needAck) btn += m.ack ? '<span class="tag">Đã xác nhận vẫn dùng</span>' : `<button class="btn g sm" data-a="sack" data-v="${nm}">Vẫn dùng file này</button>`;
  }
  return `<div class="sc ${T[0]}"><div class="sh"><b>${T[1]}</b><span>${m.verdict === 'detected' ? `Vùng ${esc(m.range)} · độ tin cậy ${m.score}/100${m.sheet_tables > 1 ? ` · ưu tiên #${m.rank}/${m.sheet_tables}` : ''} · đang dùng: ${m.mode === 'fixed' ? 'bảng đã nhận diện' : 'cả sheet gốc'}` : `Điểm cấu trúc gốc ${m.score}/100 · đang dùng: ${m.mode === 'fixed' ? 'bản đã chuẩn hóa' : 'bản gốc'}`}</span></div>
${m.issues.length ? '<div class="sl2">' + (m.verdict === 'detected' ? 'Sheet gốc không chuẩn' : 'Vấn đề phát hiện') + '</div><ul>' + m.issues.map(x => `<li>${esc(x)}</li>`).join('') + '</ul>' : ''}
${m.actions.length ? '<div class="sl2">Hệ thống đã làm</div><ul>' + m.actions.map(x => `<li>${esc(x)}</li>`).join('') + '</ul>' : ''}
<details><summary>Xem trước dữ liệu sẽ được phân tích</summary>${tbl(m.preview.cols, m.preview.rows.map(r => r.map(cell)))}</details>${btn ? `<div class="act" style="margin-top:10px">${btn}</div>` : ''}</div>` }
/* ---------- xem trước dữ liệu của MỌI tệp (sạch hay xấu) ---------- */
let PV = {}, PVC = {};
const PVL = { current: 'Đang dùng', original: 'Bản gốc (cả sheet)', fixed: 'Bản đã chuẩn hóa', clean: 'Sau làm sạch' };
async function pvLoad(name, src) { const k = name + '\u0001' + src; if (PVC[k]) return;
  try { const r = await fetch('/api/preview?name=' + encodeURIComponent(name) + '&src=' + src + '&n=30'); PVC[k] = r.ok ? await r.json() : { err: await readError(r) } } catch (e) { PVC[k] = { err: 'Không kết nối được máy chủ.' } } }
function pvPanel(name) { const p = PV[name], d = PVC[name + '\u0001' + p.src];
  if (!d) return '<div class="pvp"><small>Đang tải dữ liệu…</small></div>'; if (d.err) return `<div class="pvp"><div class="note" style="margin:0">${esc(d.err)}</div></div>`;
  const tabs = d.variants.length > 1 ? `<div class="seg">${d.variants.map(v => `<button class="${v === p.src ? 'on' : ''}" data-a="pvsrc" data-v="${esc(name)}" data-x="${v}">${PVL[v]}</button>`).join('')}</div>` : '';
  const cell2 = v => v === null ? '<span class="nul">∅</span>' : typeof v === 'number' ? N(v) : esc(String(v).length > 60 ? String(v).slice(0, 59) + '…' : v);
  return `<div class="pvp"><div class="pvh"><b>${N(d.shape[0])} dòng × ${N(d.shape[1])} cột</b>${tabs}</div>
<div class="cs">${d.cols.map(c => `<span class="cc ${c.missing ? 'w' : ''}" title="${N(c.unique)} giá trị khác nhau"><b>${esc(c.name)}</b> ${esc(c.dtype)}${c.missing ? ' · thiếu ' + N(c.missing) : ''}</span>`).join('')}${d.extra_cols ? `<span class="cc">+${d.extra_cols} cột nữa</span>` : ''}</div>
<div class="tw"><table><thead><tr><th>#</th>${d.cols.map(c => `<th>${esc(c.name)}</th>`).join('')}</tr></thead><tbody>${d.rows.map((r, i) => `<tr><td class="rn">${i + 1}</td>${r.map(v => `<td>${cell2(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
<small class="hint">Hiển thị ${d.rows.length}/${N(d.shape[0])} dòng đầu${d.src === 'original' || (d.src === 'current' && d.mode === 'original' && d.verdict && d.verdict !== 'tidy') ? '. Đây là dữ liệu thô nên có thể có ô trống, tiêu đề lệch hoặc dòng tổng.' : '.'}</small></div>` }

function fileList(S) {
  const ok = S.st[2] === 'done', edit = S.st[0] !== 'done' && !RO();
  return `<div class="filebar"><label>Danh sách dữ liệu (${S.files.length} tệp)</label>${edit ? '<button class="lnk" data-a="clearfiles">Xóa tất cả</button>' : ''}</div>` + S.files.map(f => `<div class="fl"><span class="dot ${(S.dirty || []).includes(f.name) && !ok ? 'w' : ''}"></span>${esc(f.name)}${f.demo ? ' <span class="tag">mẫu</span>' : ''}<small>${f.rows != null ? N(f.rows) + ' dòng' : ''}</small>${RO() ? '' : `<button class="pvb ${PV[f.name] && PV[f.name].open ? 'on' : ''}" data-a="pv" data-v="${esc(f.name)}" aria-expanded="${!!(PV[f.name] && PV[f.name].open)}">${ic('eye', 15)}Xem trước</button>`}${edit ? `<button class="rm" data-a="rmfile" data-v="${esc(f.name)}" title="Xóa tệp này" aria-label="Xóa tệp ${esc(f.name)}">${ic('trash', 16)}</button>` : ''}</div>` + (PV[f.name] && PV[f.name].open && !RO() ? pvPanel(f.name) : '') + structCard(S, f)).join('')
    + '<div class="hint">Chấm xanh: dữ liệu sạch. Chấm vàng: cần xử lý ở bước làm sạch.</div>' }

/* chọn lựa cuối cùng của bước Báo cáo (live: theo lựa chọn đang chỉnh; sau khi chấp nhận / xem lại: theo bản chốt) */
function selCharts() { const S = S_(), d = S.d[5], s = sel(5); if (d.final && S.st[5] !== 'await') return d.final.charts;
  return d.charts.map((c, i) => ({ ...c, kind: s['k' + i] ?? c.kind, x: s['x' + i] ?? c.x, y: s['y' + i] ?? c.y, on: s['c' + i] ?? c.recommended })).filter(c => c.on) }
function selKpis() { const S = S_(), r = S.d[3].result, s = sel(5), d = S.d[5]; if (d.final && S.st[5] !== 'await') return d.final.kpis.map(i => r.kpis[i]).filter(Boolean);
  return r.kpis.filter((k, i) => s['p' + i] ?? true) }
const outline = (S, ch) => [['Trang bìa', (S.d[5].final || S.d[5]).title], ['Tóm tắt điều hành', 'Câu trả lời trước, bằng chứng sau'], ['Chỉ số then chốt', 'Bức tranh số liệu'],
  ...ch.map(c => [c.insight || c.title, 'Biểu đồ + "điều này có nghĩa là"']), ['Phát hiện chính', 'Kèm bằng chứng và độ tin cậy'], ['Khuyến nghị', 'Sắp theo mức ưu tiên'],
  ['Quyết định và rủi ro', 'Cần lãnh đạo phê duyệt'], ['Phụ lục', 'Dữ liệu, làm sạch, phân tích']];

/* thẻ một thao tác làm sạch: mô tả + cách xử lý + rủi ro + kết quả áp dụng, KHỐI LẠI trong cùng một thẻ */
const MLAB = { median: 'Trung vị', mean: 'Trung bình', mode: 'Phổ biến nhất', drop_rows: 'Xóa dòng thiếu', value: 'Giá trị cố định' };
function opCard(o, d, aw, s, fx) {
  const on = aw ? (s['c' + o.id] ?? o.recommended) : (o.chosen ?? o.recommended), fill = o.op === 'fill_missing', m = aw ? (s['m' + o.id] ?? o.method) : o.method;
  const alt = fill ? (o.alts || []).find(a => a.method === m) : null, MI = d.meth || {};
  const note = fill ? ((alt && alt.reason) || (MI[m] && MI[m][1]) || '') : '', risk = fill ? ((alt && alt.risk) || '') : (o.risk || '');
  const opts = (o.numeric ? ['median', 'mean', 'mode', 'drop_rows', 'value'] : ['mode', 'drop_rows', 'value']);
  const meth = fill ? `<div class="mt"><span>Cách xử lý:</span>${opts.map(x => `<label class="mc ${m === x ? 'on' : ''}"><input type="radio" name="m${o.id}" data-s="2" data-k="m${o.id}" value="${x}" ${m === x ? 'checked' : ''} ${aw ? '' : 'disabled'}>${MLAB[x]}</label>`).join('')}${m === 'value' ? (aw ? `<input class="vi" data-s="2" data-k="v${o.id}" value="${esc(s['v' + o.id] ?? o.value ?? 'Không rõ')}" aria-label="Giá trị điền">` : `<b>= ${esc(o.value)}</b>`) : ''}</div>${note && note !== o.reason ? `<p class="mn">${esc(note)}</p>` : ''}` : '';
  return `<div class="op ${on ? 'on' : ''}"><label class="oph"><input type="checkbox" data-s="2" data-k="c${o.id}" ${on ? 'checked' : ''} ${aw ? '' : 'disabled'}><b>${esc(o.label || o.title)}</b></label>
${o.reason ? `<p class="why">${esc(o.reason)}</p>` : ''}${meth}${risk ? `<p class="rk">Rủi ro: ${esc(risk)}</p>` : ''}
${fx[o.id] ? `<div class="fx ${on ? '' : 'off'}">${ico('check', 14)}<span>${on ? 'Kết quả' : 'Nếu áp dụng'}: <b>${esc(fx[o.id])}</b></span></div>` : ''}</div>` }

/* ---------- 7 bước ---------- */
const VIEW = [
  () => { const S = S_(), d = S.st[0] === 'done', F = S.files, ctx = d ? S.ctx : U.ctx;
    const drop = d ? '' : `<label class="drop ${F.length ? 'has' : ''}" id="dz" for="file">${ico('upload', 24)}<span><b>${F.length ? 'Đã có ' + F.length + ' tệp. Bấm để thêm tệp khác' : 'Kéo thả hoặc bấm để chọn tệp'}</b><small>Hỗ trợ CSV, XLSX, XLS. Chọn nhiều tệp cùng lúc hoặc thêm dần; tệp mới được cộng vào danh sách, trùng tên thì thay tệp cũ.</small></span></label><input type="file" id="file" multiple hidden accept=".csv,.xlsx,.xls,.xlsm">`;
    const none = !d && !F.length ? `<div class="hint">Chưa có tệp nào. Không có tệp trong tay? <button class="lnk" data-a="sample">Dùng bộ dữ liệu mẫu để thử</button></div>` : '';
    return `<h2>Dữ liệu và bối cảnh</h2><p class="lead">${d ? 'Đã nạp xong. Bấm "Làm lại từ bước này" nếu cần đổi tệp hoặc câu hỏi.' : 'Tải tệp dữ liệu, nhập câu hỏi ở ô phía trên và mô tả ngắn về doanh nghiệp. AI sẽ đọc cả ba thông tin này để chọn cách phân tích.'}</p>
<div class="frm"><label>Tệp dữ liệu</label>${drop}${none}${F.length ? fileList(S) : ''}
<label for="ctx">Bối cảnh doanh nghiệp (không bắt buộc)</label><textarea id="ctx" data-i="ctx" ${d ? 'disabled' : ''} placeholder="Mô tả ngắn về doanh nghiệp: ngành, quy mô, khu vực hoạt động và các sự kiện đáng chú ý trong kỳ cần phân tích">${esc(ctx)}</textarea></div>
${d ? '' : '<div class="act"><button class="btn" data-a="start">' + ico('play', 16) + 'Bắt đầu phân tích</button></div>'}` },
  () => { const d = S_().d[1]; return `<h2>Kiểm tra và mô tả dữ liệu</h2><p class="lead">AI đã đọc dữ liệu. Đây là nhận định sơ bộ, bạn xác nhận trước khi làm sạch.</p>${kpo(d.kpis)}${tbl(d.sample.cols, d.sample.rows.map(r => r.map(cell)))}${(d.structure || []).map(x => fnd(`<b>${esc(x.file)}</b>: ${esc(x.issues.join('; ') || 'ổn')}${x.actions.length ? '<br><small>Đã xử lý: ' + esc(x.actions.join('; ')) + '</small>' : ''}`, 'Cấu trúc · ' + ({ fixed: 'đã chuẩn hóa', detected: 'đã nhận diện bảng', warn: 'cần lưu ý', bad: 'không phù hợp' }[x.verdict] || ''), x.verdict === 'bad' ? 'risk' : x.verdict === 'warn' ? '' : 'act')).join('')}${d.findings.map(f => fnd(esc(f.text), f.tag)).join('')}
<details><summary>Thống kê chi tiết theo cột</summary>${d.profile.map(p => `<p><b>${esc(p.file)}</b> · ${N(p.shape[0])} dòng × ${p.shape[1]} cột</p>` + tbl(['Cột', 'Kiểu', 'Thiếu', '% thiếu', 'Duy nhất', 'Ví dụ'], p.rows.map(r => r.map(c => esc(c))))).join('')}</details>
<details><summary>Danh sách vấn đề phát hiện (${d.issues.length})</summary>${d.issues.length ? tbl(['Tệp', 'Cột', 'Vấn đề', 'Số lượng'], d.issues.map(r => [esc(r.file), esc(r.col), esc(r.issue), N(r.n)])) : 'Không phát hiện vấn đề tự động.'}</details>` },
  () => { const S = S_(), d = S.d[2], s = sel(2), aw = S.st[2] === 'await' && !RO(), pv = (aw && s.pv) || d.pv, fx = pv.fx || d.pv.fx || {};
    const groups = new Map(); d.ops.forEach(o => { const k = o.file + '\u0001' + (o.column || ''); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(o) });
    const html = [...groups.values()].map(g => { const f = g[0], found = [...new Set(g.map(o => o.found).filter(Boolean))].join('; ');
      return `<div class="cg"><div class="cgh"><b>${f.column ? esc(f.column) : 'Toàn bảng'}</b><span class="tag">${esc(f.file)}</span>${found ? `<span class="found">Phát hiện: ${esc(found)}</span>` : ''}</div>${g.map(o => opCard(o, d, aw, s, fx)).join('')}</div>` }).join('');
    const keys = Object.keys(pv.before).filter(k => pv.before[k] || pv.after[k]);
    return `<h2>Làm sạch dữ liệu</h2><p class="lead">${aw ? 'Mỗi khối là một cột có vấn đề. Tích chọn cách xử lý; kết quả áp dụng được tính thật trên dữ liệu của bạn. AI chỉ đề xuất, bạn quyết định.' : 'Các thao tác dưới đây là lựa chọn đã chốt (mục được tích là đã áp dụng).'}</p>${html || '<p class="lead">Không có thao tác nào được đề xuất.</p>'}
<div class="two"><div class="box"><h4>Trước</h4>${bar(keys.map(k => [k, pv.before[k]]))}</div><div class="box"><h4>Sau khi áp dụng</h4>${bar(keys.map(k => [k, pv.after[k]]))}</div></div>
<div><small style="color:var(--sub)">Đã xử lý khoảng ${N(pv.n)} mục.${aw ? ' Thao tác rủi ro mặc định không được chọn.' : ''}</small></div>` },
  () => { const S = S_(), d = S.d[3], s = sel(3);
    if (d.phase === 'menu') return `<h2>Phân tích</h2><p class="lead">Chọn các phân tích và chỉ số bạn muốn thực hiện (có thể gồm dự báo). AI chỉ gợi ý, bạn quyết định.</p>
${d.menu.map(m => { const on = s['a' + m.id] ?? m.recommended; return `<label class="opt ${on ? 'on' : ''}"><input type="checkbox" data-s="3" data-k="a${m.id}" ${on ? 'checked' : ''}><span><b>${esc(m.title)}</b> — ${esc(m.goal || '')}<small>Chỉ số: ${esc((m.metrics || []).join('; '))}</small><small>Vì sao: ${esc(m.why || '')}</small></span></label>` }).join('')}
<div class="frm"><label>Phân tích hoặc chỉ số riêng bạn muốn thêm (không bắt buộc)</label><textarea data-s="3" data-i="anc">${esc(s.anc || '')}</textarea></div>`;
    if (d.phase === 'code') return `<h2>Phân tích</h2><p class="lead">AI đã viết code cho các mục bạn chọn. Xem và sửa nếu cần trước khi chạy.</p>
${d.tasks.map((t, i) => `<div class="f"><span class="tg">${i + 1}</span><b>${esc(t.title)}</b> <small>${esc(t.goal || '')}</small><div class="fb"><textarea data-s="3" data-i="code${i}" style="min-height:150px;font-family:ui-monospace,Consolas,monospace;font-size:12px">${esc(s['code' + i] ?? t.code)}</textarea></div></div>`).join('')}
<div class="note">Code do AI viết sẽ chạy trên máy bạn. Hãy xem lại trước khi thực thi.</div>`;
    const r = d.result, T = r.tables;
    return `<h2>Phân tích</h2><p class="lead">Mô tả điều gì đã xảy ra, chẩn đoán vì sao, và dự báo ngắn hạn nếu bạn đã chọn. Tất cả nằm trong một bước.</p>${kpo(r.kpis)}
<div class="two">${r.charts.map(c => chart(c, T)).join('')}</div>${r.findings.map(f => fnd(esc(f.text), f.tag)).join('')}
<details><summary>Bảng kết quả đầy đủ</summary>${T.map(t => `<p><b>${esc(t.title)}</b></p>` + tableOf(t)).join('')}</details>
<details><summary>Code đã chạy</summary>${d.tasks.map(t => `<p><b>${esc(t.title)}</b></p><pre style="white-space:pre-wrap;font-size:12px">${esc(t.code)}</pre>`).join('')}</details>` },
  () => { const S = S_(), d = S.d[4], s = sel(4), aw = S.st[4] === 'await' && !RO(), ck = (k, i) => aw ? `<label style="float:right;font-size:12px;color:var(--sub)"><input type="checkbox" data-s="4" data-k="${k}${i}" ${(s[k + i] ?? true) ? 'checked' : ''}> Đưa vào báo cáo</label>` : '';
    return `<h2>Insight và hành động</h2><p class="lead">Mỗi insight dẫn được về bằng chứng. Mở "Bằng chứng" để kiểm tra phép tính.${aw ? ' Bỏ tích mục bạn không muốn đưa vào báo cáo.' : ''}</p>${d.summary ? fnd(esc(d.summary), 'Tóm tắt', 'sum') : ''}
${d.insights.map((x, i) => `<div class="f ins">${ck('i', i)}<span class="tg">Insight ${i + 1}</span><b>${esc(x.title)}</b> <small>Độ tin cậy: ${esc(x.confidence || '')}</small><details><summary>Bằng chứng</summary>${esc(x.source || '')}: ${esc(x.evidence || '')}</details></div>`).join('')}
${d.actions.map((x, i) => `<div class="f act">${ck('a', i)}<span class="tg">Hành động</span>${esc(x.text)} <small>[${esc(x.priority || '')}] ${esc(x.impact || '')}</small></div>`).join('')}${(d.risks || []).map(x => fnd(esc(x), 'Rủi ro', 'risk')).join('')}` },
  () => { const S = S_(), d = S.d[5], s = sel(5), aw = S.st[5] === 'await' && !RO(), r3 = S.d[3].result, T = r3.tables, sc = selCharts(), sk = selKpis();
    const panel = aw ? `<details open><summary>Chọn biểu đồ và chỉ số đưa lên báo cáo và slide</summary><div class="ask" style="padding-top:10px"><label>Tiêu đề báo cáo</label><input data-s="5" data-i="rt" value="${esc(s.rt ?? d.title)}"></div>
 <p class="hint">Chỉ số (KPI)</p>${r3.kpis.map((k, i) => `<label class="opt ${(s['p' + i] ?? true) ? 'on' : ''}"><input type="checkbox" data-s="5" data-k="p${i}" ${(s['p' + i] ?? true) ? 'checked' : ''}><span><b>${esc(k.value)}</b><small>${esc(k.label)}</small></span></label>`).join('')}
 <p class="hint">Biểu đồ</p>${d.charts.map((c, i) => { const t = T[c.task], on = s['c' + i] ?? c.recommended, kd = s['k' + i] ?? c.kind, x = s['x' + i] ?? c.x, y = s['y' + i] ?? c.y;
      return `<label class="opt ${on ? 'on' : ''}"><input type="checkbox" data-s="5" data-k="c${i}" ${on ? 'checked' : ''}><span><b>${esc(c.title)}</b><small>${esc(c.insight || '')} (từ: ${esc(t.title)})</small></span></label><div class="hint" style="margin:-4px 0 8px 34px">Loại ${kindSel(5, 'k' + i, kd)} Nhãn ${sel$(5, 'x' + i, t.cols, x)} Giá trị ${sel$(5, 'y' + i, numCols(t), y)}</div>` }).join('')}</details>` : '';
    const title = (d.final && !aw) ? d.final.title : (aw ? (s.rt ?? d.title) : d.title);
    return `<h2>Báo cáo</h2><p class="lead">Dashboard để tự lọc và khám phá dữ liệu; báo cáo để đọc kết luận kèm bằng chứng; slide để trình bày nhanh cho lãnh đạo. Cả ba dựng từ cùng một bộ dữ liệu và insight.</p>${panel}
<div class="tb">${[['dash', 'Dashboard tương tác', 'dash'], ['rep', 'Báo cáo', 'file'], ['ppt', 'Slide', 'slides']].map(([k, l, i]) => `<button class="${TAB === k ? 'on' : ''}" data-a="tab" data-v="${k}">${ico(i, 15)}${l}</button>`).join('')}</div>
${TAB === 'dash' ? `<iframe class="dashf" title="Dashboard tương tác" src="${S.approved ? `/api/view/${S.id}/dashboard.html` : '/api/dash_preview?title=' + encodeURIComponent(title)}"></iframe><div class="hint">Dashboard tương tác: bấm vào cột / lát tròn / điểm để lọc chéo, dùng thanh bộ lọc phía trên, đổi chỉ số và cách tính ở đầu mỗi biểu đồ. Số liệu tính từ dữ liệu đã làm sạch.</div>`
      : TAB === 'rep' ? fnd(esc(S.d[4].summary), 'Câu trả lời') + kpo(sk) + `<div class="two">${sc.map(c => chart(c, T)).join('')}</div>` + fnd(esc(d.narrative).replace(/\n/g, '<br>'), 'Tóm tắt') + fnd(esc(S.question) + (S.ctx ? '<br>' + esc(S.ctx) : ''), 'Bối cảnh') + fnd('Dựa trên ' + S.d[3].tasks.length + ' phân tích đã chọn và dữ liệu đã làm sạch.', 'Phương pháp') + fnd(S.d[4].actions.map(a => esc(a.text)).join('<br>') || '—', 'Khuyến nghị')
      : `<div class="slides">${outline(S, sc).map((x, i) => `<div class="sl">${i + 1}. ${esc(i === 0 ? title : x[0])}<small>${esc(x[1])}</small></div>`).join('')}</div>`}` },
  () => { const S = S_(), d = S.d[6], ap = S.approved;
    const dl = ap ? `<div class="dl"><a class="btn" href="/api/view/${S.id}/bao_cao.html" target="_blank" rel="noopener" title="Báo cáo đầy đủ: câu trả lời, insight, bằng chứng, khuyến nghị">${ico('file', 16)}Báo cáo</a><a class="btn" href="/api/view/${S.id}/dashboard.html" target="_blank" rel="noopener" title="Dashboard tương tác: bộ lọc, lọc chéo, biểu đồ">${ico('dash', 16)}Dashboard</a><a class="btn" href="/api/download/${S.id}/bao_cao.pptx" title="Tải file PowerPoint">${ico('slides', 16)}PPT</a><a class="btn" href="/api/download/${S.id}/share.zip" title="Gói chia sẻ: báo cáo, dashboard, PPT, dữ liệu sạch">${ico('archive', 16)}ZIP</a></div>` : '<div class="note">Xuất và chia sẻ bị khóa cho đến khi bạn duyệt.</div>';
    return `<h2>Review và export</h2><p class="lead">Kiểm tra lần cuối. Xuất tệp chỉ mở sau khi bạn duyệt.</p>${d.checks.map(x => fnd('✓ ' + esc(x), 'Đã xong')).join('')}${dl}` }];

function payload(i) { const s = sel(i), S = S_();
  if (i === 2) { const d = S.d[2]; return { sel: Object.fromEntries(d.ops.map(o => [o.id, s['c' + o.id] ?? o.recommended])), meth: Object.fromEntries(d.ops.map(o => [o.id, s['m' + o.id] ?? o.method])), val: Object.fromEntries(d.ops.map(o => [o.id, s['v' + o.id] ?? o.value])) } }
  if (i === 4) { const d = S.d[4]; return { ins: d.insights.map((x, k) => s['i' + k] ?? true), act: d.actions.map((x, k) => s['a' + k] ?? true) } }
  if (i === 5) { const r = S.d[3].result; return { title: s.rt ?? S.d[5].title, charts: selCharts(), kpis: r.kpis.map((k, j) => j).filter(j => s['p' + j] ?? true) } }
  return {} }

const FBP = { menu: ['Ví dụ: thêm phân tích theo khách hàng, bỏ mục về sản phẩm ít bán…', 'Gửi và chỉnh danh sách'], code: ['Ví dụ: nhóm theo tuần thay vì tháng, loại các đơn bị hủy…', 'Gửi và viết lại code'], result: ['Ví dụ: tính thêm lợi nhuận, chỉ lấy khu vực HCM…', 'Gửi, viết lại code và chạy lại'] };
function fbChips(i) { const h = (S_().fbh || {})[i] || []; return h.length ? `<div class="fbh"><b>Góp ý đã gửi:</b>${h.map((t, k) => `<span title="${esc(t)}">${k + 1}. ${esc(t.length > 70 ? t.slice(0, 69) + '…' : t)}</span>`).join('')}</div>` : '' }
function actions(i, s) { if (RO()) return '';
  if (s === 'await' && i > 0) { const ph = i === 3 ? ST.d[3].phase : ''; let m;
    if (ph === 'menu') m = '<button class="btn" data-a="a3code">Tạo code cho mục đã chọn</button>';
    else if (ph === 'code') m = '<button class="btn" data-a="a3exec">Thực thi code phân tích</button><button class="btn g" data-a="a3re">Chọn lại danh sách</button>';
    else m = `<button class="btn" data-a="ok">${i === 6 ? 'Duyệt báo cáo' : 'Chấp nhận và tiếp tục'}</button>`;
    const fp = i === 3 ? FBP[ph] : ['Bạn muốn AI điều chỉnh gì ở bước này?', 'Gửi và chạy lại'];
    return fbChips(i) + `<div class="act">${m}<button class="btn g" data-a="adj">Điều chỉnh</button></div>` + (FB ? `<div class="fb"><textarea data-i="fbt" placeholder="${fp[0]}">${esc(U.fbt)}</textarea><button class="btn" style="margin-top:8px" data-a="fbs">${fp[1]}</button></div>` : '') }
  if (s === 'done' && !ST.approved) return fbChips(i) + '<div class="act"><button class="btn g" data-a="redo">Làm lại từ bước này</button></div>'; return '' }

function stage() { const S = S_(), i = V, s = S.st[i]; let h = '<div class="card">';
  if (s === 'running') h += `<h2>${STEPS[i].t}</h2><p class="lead">AI đang xử lý, các tác vụ hiện ở bảng AI Agent.</p>`;
  else if (s === 'error') h += `<h2>${STEPS[i].t}</h2><div class="note">Lỗi: ${esc(S.err && S.err.msg)}</div><div class="act"><button class="btn" data-a="retry">Thử lại</button></div>`;
  else if (s === 'pending' && i > 0) h += `<p class="lead">Bước này chưa chạy.</p>`;
  else { try { h += VIEW[i]() } catch (e) { h += `<div class="note">Không hiển thị được bước này: ${esc(e.message)}</div>`; console.error(e) } h += actions(i, s) }
  $('stage').innerHTML = h + '</div>'; applyRO() }
function applyRO() { $('vFlow').classList.toggle('ro', RO()); if (!RO()) return;
  document.querySelectorAll('#stage input,#stage select').forEach(e => e.disabled = true);
  document.querySelectorAll('#stage textarea').forEach(e => e.readOnly = true);
  document.querySelectorAll('#stage button[data-a]:not([data-a="tab"])').forEach(e => e.disabled = true) }
function stepper() { const S = S_(); $('stepper').innerHTML = STEPS.map((p, i) => { const s = S.st[i];
  return `<button class="st ${s} ${i === V ? 'view' : ''}" data-a="go" data-v="${i}" ${s === 'pending' && i > 0 ? 'disabled' : ''}><span class="n">${s === 'done' ? ico('check', 14) : ico(p.i, 14)}</span><span class="t">${p.t}</span></button>` }).join('') }

/* ---------- Lịch sử ---------- */
function histRow(h) {
  const t0 = h.started ? new Date(h.started) : null, t1 = h.finished ? new Date(h.finished) : null, q = h.question || h.title || '(không có câu hỏi)';
  const meta = t0 || t1 ? `<span>${ico('calendar', 14)}${fmtDate(t1 || t0)}</span><span>${ico('clock', 14)}Bắt đầu ${fmtTime(t0)}</span><span>${ico('clock', 14)}Kết thúc ${fmtTime(t1)}</span><span>Thời lượng ${fmtDur(t0, t1)}</span>`
    : `<span>${ico('calendar', 14)}${esc(h.date || '—')}</span><span>Bản cũ, không lưu giờ bắt đầu / kết thúc</span>`;
  const has = f => (h.files || []).includes(f), zip = has('share.zip');
  return `<div class="hrow"><div class="hmain"><div class="q">${esc(q)}</div><div class="meta"><span class="pill">Hoàn tất</span>${meta}${h.sources && h.sources.length ? `<span>${ico('database', 14)}${h.sources.length} tệp dữ liệu</span>` : ''}</div></div>
<div class="hbtn"><button class="btn g sm" data-a="viewh" data-v="${esc(h.id)}" ${h.snap ? '' : 'disabled title="Bản cũ, không có dữ liệu để xem lại"'}>${ico('eye', 15)}Xem lại</button>${zip ? `<a class="btn g sm" href="/api/download/${esc(h.id)}/share.zip" title="Tải gói chia sẻ: dashboard, báo cáo, slide và dữ liệu sạch">${ico('archive', 15)}ZIP</a>` : '<button class="btn g sm" disabled>' + ico('archive', 15) + 'ZIP</button>'}<button class="btn g sm dng" data-a="delh" data-v="${esc(h.id)}" title="Xóa toàn bộ phân tích này">${ico('trash', 15)}Xóa</button></div></div>` }
function renderNav() { const n = R ? 'history' : NAV;
  document.querySelectorAll('[data-n]').forEach(b => b.classList.toggle('on', b.dataset.n === n));
  $('vOv').hidden = NAV !== 'overview' || !!R; $('vHi').hidden = NAV !== 'history' || !!R; $('vSet').hidden = NAV !== 'settings' || !!R; $('vFlow').hidden = NAV !== 'flow' && !R;
  const dn = ST.st.filter(x => x === 'done').length, cur = ST.st[0] === 'done' && !ST.approved, H = ST.hist || [];
  const curRow = `<div class="hrow"><div><div class="q">${esc(ST.question || 'Phân tích mới')}</div><div class="meta"><span>${dn}/7 bước hoàn tất</span>${ST.started ? `<span>${ico('clock', 14)}Bắt đầu ${fmtDate(new Date(ST.started))} ${fmtTime(new Date(ST.started))}</span>` : ''}</div></div><div class="hbtn"><span class="pill w">Đang làm</span><button class="btn g sm" data-a="nav" data-v="flow">Mở luồng</button></div></div>`;
  $('vOv').innerHTML = `<div class="card"><h2>Tổng quan</h2><p class="lead">Trạng thái các phân tích của bạn.</p>${kp([['Tổng phân tích', H.length + (cur ? 1 : 0), ''], ['Đang làm', cur ? 1 : 0, ''], ['Hoàn tất', H.length, '']])}${cur ? curRow : ''}${H.slice(0, 5).map(histRow).join('')}${H.length > 5 ? '<div class="hint">Xem đầy đủ ở mục Lịch sử.</div>' : ''}</div>`;
  $('vHi').innerHTML = `<div class="card"><h2>Lịch sử</h2><p class="lead">Các phân tích đã hoàn tất. Bấm "Xem lại" để mở toàn bộ các bước ở chế độ chỉ đọc; chỉ việc tải báo cáo là thao tác được.</p>${H.map(histRow).join('') || '<p class="lead">Chưa có phân tích nào hoàn tất.</p>'}</div>` }
function roBar() { if (!R) { $('robar').innerHTML = ''; return }
  const t0 = R.started ? new Date(R.started) : null, t1 = R.finished ? new Date(R.finished) : null;
  $('robar').innerHTML = `<div class="robar">${ico('lock', 18)}<span>Đang xem lại phân tích đã hoàn tất · chỉ đọc, chỉ tải báo cáo được</span><button class="btn g sm" data-a="backh">${ico('back', 15)}Về Lịch sử</button>
<div class="meta"><span>${ico('calendar', 14)}${fmtDate(t1 || t0)}</span><span>${ico('clock', 14)}Bắt đầu ${fmtTime(t0)}</span><span>${ico('clock', 14)}Kết thúc ${fmtTime(t1)}</span><span>Thời lượng ${fmtDur(t0, t1)}</span></div></div>` }

function paintAgent() { const S = S_(), i = V, a = (S.ag && S.ag[i]) || [], s = S.st[i], run = S.job.running && S.job.step === i, k = run ? S.job.k : s === 'pending' ? -1 : s === 'error' ? S.job.k : 99;
  $('agents').innerHTML = `<div class="stn">${STEPS[i].t}</div>` + (a.length ? a.map((x, j) => `<div class="ag ${j < k ? 'ok' : j === k && run ? 'on' : ''}"><i>${j < k ? '✓' : ''}</i>${esc(x)}</div>`).join('') : '<div class="ag">Bước này do bạn thực hiện.</div>');
  const P = { running: ['Đang chạy', 'w'], await: ['Chờ bạn', 'w'], done: ['Hoàn tất', ''], pending: ['Chưa chạy', 'w'], error: ['Lỗi', 'w'] }[s]; $('ast').textContent = P[0]; $('ast').className = 'pill ' + P[1];
  const L = (S.log || []).slice().reverse(); $('lgc').textContent = L.length + ' mục';
  $('log').innerHTML = L.map(l => { const m = l.match(/^\[(\d\d:\d\d)\]\s*(.*)$/) || [0, '', l], x = m[2], c = /^(Đã|Hoàn)/.test(x) ? 'ok' : /^Chờ/.test(x) ? 'w' : /^(Bắt đầu|Phản hồi|Quay lại)/.test(x) ? 'r' : /^Lỗi/.test(x) ? 'e' : ''; return `<div class="le ${c}"><time>${m[1]}</time><span>${esc(x)}</span></div>` }).join('') || '<div class="stn">Chưa có hoạt động.</div>' }
function all() { const S = S_(), q = $('q'); q.disabled = S.st[0] === 'done' || RO(); if (q.disabled) q.value = S.question || '';
  roBar(); stepper(); stage(); paintAgent(); renderNav() }
async function refresh() { const n = await (await fetch('/api/state')).json(); const ch = !ST || n.ver !== ST.ver; ST = n; if (R) { if (ch) renderNav(); return } if (ch) all(); else paintAgent() }
/* ---------- Thông báo & xác nhận bằng panel (không dùng alert/confirm của trình duyệt) ---------- */
function notify(msg, type = 'error', title) {
  let box = $('toasts'); if (!box) { box = document.createElement('div'); box.id = 'toasts'; box.setAttribute('role', 'alert'); document.body.appendChild(box) }
  const t = document.createElement('div'); t.className = 'toast ' + type;
  const ttl = title || ({ error: 'Có lỗi xảy ra', warn: 'Lưu ý', ok: 'Thành công' }[type] || 'Thông báo');
  t.innerHTML = `<span class="ti">${ic(type === 'ok' ? 'check' : 'alert', 20)}</span><div class="tx"><b>${esc(ttl)}</b><div>${esc(msg)}</div></div><button class="tc" aria-label="Đóng">${ic('x', 16)}</button>`;
  t.querySelector('.tc').onclick = () => t.remove(); box.appendChild(t);
  if (type !== 'error') setTimeout(() => t.remove(), 6000) }
function askConfirm(msg, okText = 'Đồng ý') { return new Promise(res => {
  const ov = document.createElement('div'); ov.className = 'ov';
  ov.innerHTML = `<div class="dlg" role="dialog" aria-modal="true"><div class="dh2">${ic('alert', 22)}<b>Xác nhận</b></div><p>${esc(msg)}</p><div class="act"><button class="btn g" data-r="0">Hủy</button><button class="btn" data-r="1">${esc(okText)}</button></div></div>`;
  const done = v => { ov.remove(); res(v) }; ov.onclick = e => { if (e.target === ov) done(false); const b = e.target.closest('[data-r]'); if (b) done(b.dataset.r === '1') };
  document.body.appendChild(ov); ov.querySelector('[data-r="1"]').focus() }) }
async function readError(r) { let j = {}; try { j = await r.json() } catch (e) { }
  if (j.error) return j.error;
  if (r.status === 404) return 'Máy chủ chưa có chức năng này (404). Hãy chép đủ các file mới vào dự án rồi khởi động lại server (python run.py).';
  if (r.status === 413) return 'Tệp quá lớn so với giới hạn MAX_UPLOAD_MB trong file .env.';
  return `Máy chủ trả về lỗi ${r.status}. Xem cửa sổ terminal đang chạy server để biết chi tiết.` }
const netErr = () => notify('Không kết nối được máy chủ. Hãy kiểm tra server còn chạy (python run.py) rồi thử lại.');
async function post(u, b) { BUSY = true; PVC = {}; try { const r = await fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) });
  if (!r.ok) notify(await readError(r)); await refresh(); return r.ok } catch (e) { netErr(); return false } finally { BUSY = false } }
async function pvClean() { try { const r = await fetch('/api/preview_clean', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload(2)) }); if (r.ok) sel(2).pv = await r.json() } catch (e) { netErr() } }
async function upload(files) { PVC = {}; try { const fd = new FormData();[...files].forEach(f => fd.append('files', f)); const r = await fetch('/api/upload', { method: 'POST', body: fd }); if (!r.ok) notify(await readError(r)); else { const j = await r.json().catch(() => ({})); (j.notices || []).forEach(n => notify(n.msg, n.type, n.title)) } await refresh() } catch (e) { netErr() } }
function leaveRO() { if (R) { R = null; V = SAVEV; FB = false } }
const toTop = () => { $('main').scrollTop = 0 };
function setTheme() { const r = document.documentElement, d = r.dataset.theme ? r.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme:dark)').matches; r.dataset.theme = d ? 'light' : 'dark'; syncIcons() }
function syncIcons() { const dark = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme:dark)').matches; $('themeIc').innerHTML = ic(dark ? 'sun' : 'moon') }

/* ---------- sự kiện ---------- */
document.addEventListener('click', async e => { const b = e.target.closest('[data-a]'); if (!b) return; const a = b.dataset.a, v = b.dataset.v;
  if (a === 'sbt') { const c = $('side').classList.toggle('c'); $('sbi').innerHTML = ic(c ? 'chevR' : 'chevL') }
  else if (a === 'drt') { const o = $('drawer').classList.toggle('open'); $('dri').innerHTML = ic(o ? 'chevR' : 'chevL') }
  else if (a === 'nav') { leaveRO(); NAV = v; all(); if (v === 'settings') window.renderSettings && window.renderSettings(); toTop() }
  else if (a === 'theme') setTheme()
  else if (a === 'new') {
    if (ST.job.running) { notify('Đang có tác vụ chạy, hãy chờ xong rồi tạo phân tích mới.', 'warn'); return }
    if (!R && ST.st[0] === 'done' && !ST.approved && !(await askConfirm('Phân tích hiện tại chưa được duyệt sẽ bị bỏ. Tiếp tục?', 'Tạo phân tích mới'))) return;
    if (await post('/api/new')) { R = null; V = 0; NAV = 'flow'; TAB = 'dash'; FB = false; SEL = {}; U.ctx = ''; U.fbt = ''; $('q').value = ''; all(); toTop() } }
  else if (a === 'pv') { const o = PV[v] = PV[v] || { src: 'current' }; o.open = !o.open; stage(); if (o.open) { await pvLoad(v, o.src); stage() } }
  else if (a === 'pvsrc') { PV[v].src = b.dataset.x; stage(); await pvLoad(v, b.dataset.x); stage() }
  else if (a === 'sample') { await post('/api/sample') }
  else if (a === 'sorig') { await post('/api/struct/use_original', { name: v }) }
  else if (a === 'sfixed') { await post('/api/struct/use_fixed', { name: v }) }
  else if (a === 'sack') { await post('/api/struct/ack', { name: v }) }
  else if (a === 'rmfile') { delete PV[v]; await post('/api/remove_file', { name: v }) }
  else if (a === 'clearfiles') { if (await askConfirm('Xóa tất cả tệp đã tải lên?', 'Xóa tất cả')) await post('/api/remove_file', {}) }
  else if (a === 'start') { const q = $('q').value.trim(); if (!q) { $('q').focus(); return } if (await post('/api/start', { question: q, ctx: U.ctx })) { V = 1; all() } }
  else if (a === 'go') { V = +v; FB = false; all() }
  else if (a === 'tab') { TAB = v; stage() }
  else if (a === 'adj') { FB = !FB; stage() }
  else if (a === 'fbs') { const t = U.fbt.trim(); if (!t) return; U.fbt = ''; FB = false; await post('/api/run/' + V, { feedback: t }) }
  else if (a === 'retry') { await post('/api/run/' + V, {}) }
  else if (a === 'ok') { const i = V; if (await post('/api/accept/' + i, payload(i)) && i < 6) { V = i + 1; all() } }
  else if (a === 'redo') { FB = false; await post('/api/redo/' + V) }
  else if (a === 'a3code') { const d = ST.d[3], s = sel(3); await post('/api/a3/code', { ids: d.menu.filter(m => s['a' + m.id] ?? m.recommended).map(m => m.id), custom: s.anc || '' }) }
  else if (a === 'a3exec') { const d = ST.d[3], s = sel(3); await post('/api/a3/exec', { codes: d.tasks.map((t, i) => s['code' + i] ?? t.code) }) }
  else if (a === 'a3re') { await post('/api/a3/reselect') }
  else if (a === 'viewh') { let r; try { r = await fetch('/api/history/' + v) } catch (e) { netErr(); return } if (!r.ok) { notify(await readError(r)); return }
    if (!R) SAVEV = V; R = await r.json(); R.job = { running: false, step: null, k: 99 }; V = 0; NAV = 'flow'; TAB = 'dash'; FB = false; all(); toTop() }
  else if (a === 'delh') { if (!(await askConfirm('Xóa toàn bộ phân tích này, gồm bản lưu để xem lại, dashboard, báo cáo, slide và dữ liệu sạch? Không thể hoàn tác.', 'Xóa phân tích'))) return; if (await post('/api/history/' + v + '/delete')) notify('Đã xóa phân tích.', 'ok', 'Đã xóa') }
  else if (a === 'backh') { leaveRO(); NAV = 'history'; all(); toTop() } });
document.addEventListener('change', async e => { const t = e.target;
  if (t.id === 'file' && t.files.length) { await upload(t.files); return }
  if (RO()) return;
  if (t.dataset.k) { const s = sel(+t.dataset.s); s[t.dataset.k] = t.type === 'checkbox' ? t.checked : t.value; if (t.dataset.s === '2' && /^[mv]o/.test(t.dataset.k)) s['c' + t.dataset.k.slice(1)] = true; if (t.dataset.s === '2') await pvClean(); stage() } });
document.addEventListener('input', e => { const t = e.target; if (!t.dataset.i || RO()) return; if (t.dataset.s) sel(+t.dataset.s)[t.dataset.i] = t.value; else U[t.dataset.i] = t.value });
document.addEventListener('dragover', e => { if (e.target.closest('#dz')) e.preventDefault() });
document.addEventListener('drop', e => { if (e.target.closest('#dz')) { e.preventDefault(); if (e.dataTransfer.files.length) upload(e.dataTransfer.files) } });
document.querySelectorAll('[data-ic]').forEach(el => el.innerHTML = ic(el.dataset.ic));
syncIcons(); refresh(); setInterval(() => { if (ST && (ST.job.running || BUSY)) refresh() }, 700);