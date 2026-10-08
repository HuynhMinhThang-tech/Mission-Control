// Tab "API & Model": mỗi người dùng tự nhập khóa API (lưu mã hóa), Base URL và model của riêng mình.
(function () {
  const $s = id => document.getElementById(id);
  const E = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  async function api(url, body) {
    const r = await fetch(url, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    let j = {}; try { j = await r.json() } catch (e) { }
    if (!r.ok) throw new Error(j.error || ('Lỗi máy chủ (' + r.status + ')'));
    return j;
  }
  const form = () => ({ base_url: $s('sBase').value.trim(), api_key: $s('sKey').value.trim(), model: $s('sModel').value.trim() });
  function paint(S, defModel) {
    $s('sBase').value = S.base_url || '';
    $s('sModel').value = S.model || (S.configured ? '' : defModel || '');
    $s('sKey').value = '';
    $s('sKey').placeholder = S.has_key ? 'Đã lưu (kết thúc bằng ' + S.key_hint + '). Để trống nếu muốn giữ nguyên' : 'Dán API key của bạn';
    $s('sState').className = 'pill ' + (S.broken ? 'w' : S.has_key ? 'g' : 'w');
    $s('sState').textContent = S.broken ? 'Không đọc được key, hãy nhập lại' : S.has_key ? 'Đã có API key' : 'Chưa có API key';
    $s('sClear').hidden = !S.has_key && !S.broken;
  }
  async function busy(btn, label, fn) {
    const old = btn.textContent; btn.disabled = true; btn.textContent = label;
    try { await fn() } catch (e) { notify(e.message, 'error') } finally { btn.disabled = false; btn.textContent = old }
  }
  window.renderSettings = async function () {
    const box = $s('vSet');
    box.innerHTML = `<div class="card"><h2>API &amp; Model</h2>
      <p class="lead">Mỗi người dùng khóa API riêng. Khóa được mã hóa trước khi lưu vào cơ sở dữ liệu nên admin hay người quản lý dữ liệu đều không xem lại được. Bất kỳ endpoint nào tương thích OpenAI đều dùng được.</p>
      <div class="sf">
        <div><label for="sKey">API key <span id="sState" class="pill w"></span></label><input id="sKey" type="password" autocomplete="off" spellcheck="false"></div>
        <div><label for="sBase">Base URL</label><input id="sBase" type="url" autocomplete="off" spellcheck="false" placeholder="https://..."><small>Mặc định là Gemini. Đổi nếu dùng nhà cung cấp khác (OpenAI, OpenRouter...).</small></div>
        <div><label for="sModel">Model</label><div class="sr"><input id="sModel" list="sModels" autocomplete="off" spellcheck="false" placeholder="vd: gemini-2.5-flash"><datalist id="sModels"></datalist><button class="btn g" id="sList" type="button">Tải danh sách model</button></div>
          <small>Gõ tên model, hoặc bấm tải danh sách từ chính API key này rồi chọn.</small></div>
        <div class="sb"><button class="btn" id="sSave" type="button">Lưu và kiểm tra kết nối</button><button class="btn g" id="sClear" type="button" hidden>Xóa API key</button></div>
      </div></div>`;
    try {
      const S = await api('/api/settings/llm'); paint(S, S.default_model);
      $s('sSave').onclick = e => busy(e.currentTarget, 'Đang kiểm tra...', async () => {
        const r = await api('/api/settings/llm', form()); paint(r.settings, '');
        if (r.test.ok) notify(r.test.message, 'ok', 'Đã lưu'); else notify(r.test.message, 'error', 'Đã lưu, nhưng kết nối bị lỗi');
      });
      $s('sList').onclick = e => busy(e.currentTarget, 'Đang tải...', async () => {
        const f = form(); const r = await api('/api/settings/llm/models', { base_url: f.base_url, api_key: f.api_key });
        $s('sModels').innerHTML = r.models.map(m => `<option value="${E(m)}">`).join('');
        notify(`Tìm thấy ${r.models.length} model. Bấm vào ô Model để chọn.`, 'ok'); $s('sModel').focus();
      });
      $s('sClear').onclick = async e => {
        if (!(await askConfirm('Xóa API key đã lưu? Bạn sẽ cần nhập lại để chạy phân tích.', 'Xóa key'))) return;
        busy(e.currentTarget, 'Đang xóa...', async () => { const r = await api('/api/settings/llm/clear', {}); paint(r.settings, ''); notify('Đã xóa API key.', 'ok') });
      };
    } catch (e) { notify(e.message, 'error') }
  };
})();
