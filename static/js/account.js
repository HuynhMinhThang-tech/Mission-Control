// Khối tài khoản ở thanh bên + xử lý hết phiên đăng nhập. Nạp TRƯỚC app.js để bọc fetch.
(function () {
  const _fetch = window.fetch.bind(window);
  window.fetch = async function (...a) {
    const r = await _fetch(...a);
    if (r.status === 401) { location.href = '/login' }      // phiên hết hạn / bị khóa -> về trang đăng nhập
    return r;
  };
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const OUT = '<svg class="i" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/></svg>';
  async function init() {
    const host = document.getElementById('side'); if (!host) return;
    let me; try { const r = await _fetch('/api/auth/me'); if (!r.ok) return; me = await r.json() } catch (e) { return }
    const box = document.createElement('div'); box.className = 'acct';
    const initial = (me.display_name || '?').trim().charAt(0).toUpperCase();
    box.innerHTML = `<div class="who" title="${esc(me.email)}"><span class="av" aria-hidden="true">${esc(initial)}</span><span class="txt"><b>${esc(me.display_name)}</b><small>${esc(me.email)}</small></span></div>` +
      (me.role === 'admin' ? `<a class="nv" href="/admin"><span class="ic">${ic('shield')}</span><span class="txt">Quản trị</span>${me.pending ? `<span class="bdg txt">${me.pending}</span>` : ''}</a>` : '') +
      `<button class="nv" id="logoutBtn" type="button"><span class="ic">${OUT}</span><span class="txt">Đăng xuất</span></button>`;
    host.appendChild(box);
    document.getElementById('logoutBtn').onclick = async () => { try { await _fetch('/api/auth/logout', { method: 'POST' }) } catch (e) { } location.href = '/login' };
  }
  document.addEventListener('DOMContentLoaded', init);
})();
