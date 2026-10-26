// Tab "API & Model": mỗi người dùng tự nhập khóa API (lưu mã hóa), nhà cung cấp và model của riêng mình.
// Base URL KHÔNG phải ô nhập độc lập: nó tự điền theo nhà cung cấp, chỉ nhập tay khi chọn "Tuỳ chỉnh".
(function () {
  const $s = id => document.getElementById(id);
  const E = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  async function api(url, body) {
    const r = await fetch(url, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    let j = {}; try { j = await r.json() } catch (e) { }
    if (!r.ok) throw new Error(j.error || ('Lỗi máy chủ (' + r.status + ')'));
    return j;
  }
  let PS = [], SAVED = 'custom', HAS_KEY = false;
  const prov = id => PS.find(p => p.id === id) || PS[PS.length - 1];
  const host = u => { try { return new URL(u).hostname } catch (e) { return '' } };
  const byHost = u => { const h = host(u); return h ? PS.find(p => !p.custom && p.base_url && host(p.base_url) === h) : null };
  const family = m => { m = (m || '').trim(); return m ? PS.find(p => p.model_re && new RegExp(p.model_re, 'i').test(m)) || null : null };
  const fits = (p, m) => !p.model_re || new RegExp(p.model_re, 'i').test(m);
  const form = () => { const p = prov($s('sProv').value); return { base_url: p.custom ? $s('sBase').value.trim() : p.base_url, api_key: $s('sKey').value.trim(), model: $s('sModel').value.trim() } };

  function hints() {
    const p = prov($s('sProv').value), m = $s('sModel').value.trim(), f = family(m), mh = $s('sModelHint'), kh = $s('sKeyHint');
    if (m && f && f.id !== p.id && !p.gateway) {
      mh.className = 'sh warn';
      mh.innerHTML = `Model "${E(m)}" thuộc ${E(f.label)}, nhưng nhà cung cấp đang chọn là ${E(p.label)}. <button type="button" class="lnk" id="sFix">Chuyển sang ${E(f.label)}</button>`;
      $s('sFix').onclick = () => setProvider(f.id, false);
    } else { mh.className = 'sh'; mh.textContent = 'Gõ tên model, hoặc bấm "Tải danh sách" để chọn từ chính API key này.' }
    const changed = HAS_KEY && p.id !== SAVED && !$s('sKey').value.trim();
    kh.className = 'sh' + (changed ? ' warn' : '');
    kh.textContent = changed ? `API key đang lưu thuộc nhà cung cấp khác. Hãy nhập API key của ${p.label}; key cũ sẽ không được gửi sang địa chỉ mới.` : '';
  }

  function setProvider(id, clearModel) {
    const p = prov(id), b = $s('sBase'), m = $s('sModel');
    $s('sProv').value = p.id;
    if (!p.custom) b.value = p.base_url;                       // đổi nhà cung cấp -> Base URL tự khớp, không bao giờ "kẹt" ở nhà cũ
    b.readOnly = !p.custom; b.classList.toggle('ro', !p.custom);
    $s('sBaseNote').textContent = p.custom ? 'Nhập địa chỉ endpoint tương thích OpenAI (thường kết thúc bằng /v1).' : 'Tự điền theo nhà cung cấp, không cần sửa. Muốn dùng địa chỉ riêng, hãy chọn "Tuỳ chỉnh".';
    $s('sProvNote').textContent = p.note || '';
    m.placeholder = 'vd: ' + p.hint;
    if (clearModel && m.value && !fits(p, m.value.trim())) { m.value = ''; $s('sModels').innerHTML = '' }
    if (!$s('sModels').innerHTML) $s('sModels').innerHTML = `<option value="${E(p.hint)}">`;
    hints();
  }

  function paint(S, defModel) {
    SAVED = S.provider || (byHost(S.base_url) || {}).id || 'custom'; HAS_KEY = !!S.has_key;
    $s('sBase').value = S.base_url || '';
    setProvider(SAVED, false);
    $s('sModel').value = S.model || (S.configured ? '' : (SAVED === 'gemini' ? defModel : '') || '');
    $s('sKey').value = '';
    $s('sKey').placeholder = S.has_key ? 'Đã lưu (…' + S.key_hint + ')' : 'API key';
    $s('sState').className = 'pill ' + (S.broken ? 'w' : S.has_key ? 'g' : 'w');
    $s('sState').textContent = S.broken ? 'Không đọc được key, hãy nhập lại' : S.has_key ? 'Đã có API key' : 'Chưa có API key';
    $s('sClear').hidden = !S.has_key && !S.broken;
    hints();
  }
  async function busy(btn, label, fn) {
    const old = btn.textContent; btn.disabled = true; btn.textContent = label;
    try { await fn() } catch (e) { notify(e.message, 'error') } finally { btn.disabled = false; btn.textContent = old }
  }
  window.renderSettings = async function () {
    const box = $s('vSet');
    try {
      const S = await api('/api/settings/llm'); PS = S.providers || [];
      box.innerHTML = `<div class="card"><h2>API &amp; Model</h2>
      <div class="sf">
        <div><label for="sProv">Nhà cung cấp</label><select id="sProv">${PS.map(p => `<option value="${E(p.id)}">${E(p.label)}</option>`).join('')}</select><small id="sProvNote" class="sh"></small></div>
        <div><label for="sKey">API key <span id="sState" class="pill w"></span></label><input id="sKey" type="password" autocomplete="off" spellcheck="false"><small id="sKeyHint" class="sh"></small></div>
        <div><label for="sBase">Base URL</label><input id="sBase" type="url" autocomplete="off" spellcheck="false" placeholder="https://..."><small id="sBaseNote" class="sh"></small></div>
        <div><label for="sModel">Model</label><div class="sr"><input id="sModel" list="sModels" autocomplete="off" spellcheck="false"><datalist id="sModels"></datalist><button class="btn g" id="sList" type="button">Tải danh sách</button></div>
          <small id="sModelHint" class="sh"></small></div>
        <div class="sb"><button class="btn" id="sSave" type="button">Lưu và kiểm tra kết nối</button><button class="btn g" id="sClear" type="button" hidden>Xóa API key</button></div>
      </div></div>`;
      paint(S, S.default_model);
      $s('sProv').onchange = e => setProvider(e.target.value, true);
      $s('sModel').oninput = hints; $s('sKey').oninput = hints;
      $s('sBase').oninput = e => { const hp = byHost(e.target.value); if (hp && prov($s('sProv').value).custom) $s('sProvNote').textContent = `Địa chỉ này là của ${hp.label}: nên chọn đúng nhà cung cấp ở trên để Base URL tự khớp.` };
      $s('sSave').onclick = e => busy(e.currentTarget, 'Đang kiểm tra...', async () => {
        const r = await api('/api/settings/llm', form()); paint({ ...r.settings, provider: (byHost(r.settings.base_url) || {}).id || 'custom' }, '');
        if (r.test.ok) notify(r.test.message, 'ok', 'Đã lưu'); else notify(r.test.message, 'error', 'Đã lưu, nhưng kết nối bị lỗi');
      });
      $s('sList').onclick = e => busy(e.currentTarget, 'Đang tải...', async () => {
        const f = form(); const r = await api('/api/settings/llm/models', { base_url: f.base_url, api_key: f.api_key, model: '' });
        $s('sModels').innerHTML = r.models.map(m => `<option value="${E(m)}">`).join('');
        notify(`Tìm thấy ${r.models.length} model. Bấm vào ô Model để chọn.`, 'ok'); $s('sModel').focus();
      });
      $s('sClear').onclick = async e => {
        if (!(await askConfirm('Xóa API key đã lưu? Bạn sẽ cần nhập lại để chạy phân tích.', 'Xóa key'))) return;
        busy(e.currentTarget, 'Đang xóa...', async () => { const r = await api('/api/settings/llm/clear', {}); paint({ ...r.settings, provider: SAVED }, ''); notify('Đã xóa API key.', 'ok') });
      };
    } catch (e) { notify(e.message, 'error') }
  };
})();
