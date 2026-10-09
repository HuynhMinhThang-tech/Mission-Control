/* Chỉ báo "đang tải" dùng chung cho mọi trang: thanh chạy ở mép trên + khung nhỏ có vòng xoay và dòng mô tả.
   Tự bắt mọi fetch do người dùng bấm (trừ các lần hỏi trạng thái định kỳ), nên không phải sửa từng nút.
   Thao tác nhanh (dưới ~0,3 giây) không hiện gì để tránh nhấp nháy. API: Loading.hold('mô tả') giữ chỉ báo khi tác vụ nền đang chạy; Loading.hold('') để tắt. */
(function () {
  if (window.Loading) return;
  const css = `
#ldbar{position:fixed;left:0;right:0;top:0;height:3px;z-index:200;overflow:hidden;pointer-events:none;opacity:0;visibility:hidden;transition:opacity .15s,visibility 0s .15s}
#ldbar.on{opacity:1;visibility:visible;transition:opacity .2s .3s,visibility 0s .3s}
#ldbar::before{content:"";position:absolute;top:0;bottom:0;width:40%;border-radius:2px;background:var(--pri,#4F46E5);animation:ldbar 1.1s ease-in-out infinite}
@keyframes ldbar{0%{left:-40%}100%{left:100%}}
#ldpill{position:fixed;top:14px;left:50%;transform:translateX(-50%);z-index:200;display:flex;align-items:center;gap:10px;max-width:calc(100vw - 32px);padding:9px 16px;border-radius:999px;
background:var(--panel,#fff);color:var(--ink,#14161F);border:1px solid var(--line,#E4E6EE);box-shadow:0 6px 24px rgba(0,0,0,.16);font:600 13px/1.3 var(--f,system-ui,sans-serif);pointer-events:none;
opacity:0;visibility:hidden;transition:opacity .15s,visibility 0s .15s}
#ldpill.on{opacity:1;visibility:visible;transition:opacity .2s .3s,visibility 0s .3s}
#ldpill span.t{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.spin{display:inline-block;width:16px;height:16px;flex:none;vertical-align:-3px;border:2px solid var(--line,#E4E6EE);border-top-color:var(--pri,#4F46E5);border-radius:50%;animation:ldspin .75s linear infinite}
.spin.sm{width:14px;height:14px}.spin.lg{width:28px;height:28px;border-width:3px}
@keyframes ldspin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.spin,#ldbar::before{animation-duration:2.4s}}`;
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  const MSG = [
    [/^\/api\/inspect/, 'Đang đọc danh sách sheet…'], [/^\/api\/upload/, 'Đang tải và đọc tệp…'], [/^\/api\/sample/, 'Đang tạo dữ liệu mẫu…'],
    [/^\/api\/start/, 'Đang bắt đầu phân tích…'], [/^\/api\/run\//, 'Đang gửi yêu cầu…'], [/^\/api\/accept\/6/, 'Đang tạo báo cáo, dashboard và slide…'],
    [/^\/api\/accept\//, 'Đang lưu lựa chọn…'], [/^\/api\/a3\//, 'Đang gửi yêu cầu…'], [/^\/api\/preview_clean/, 'Đang tính kết quả làm sạch…'],
    [/^\/api\/preview/, 'Đang tải dữ liệu xem trước…'], [/^\/api\/history\/[^/]+\/delete/, 'Đang xóa phân tích…'], [/^\/api\/history\//, 'Đang mở bản lưu…'],
    [/^\/api\/struct\//, 'Đang cập nhật tệp…'], [/^\/api\/remove_file/, 'Đang xóa tệp…'], [/^\/api\/redo\//, 'Đang quay lại bước trước…'], [/^\/api\/new/, 'Đang tạo phân tích mới…'],
    [/^\/api\/auth\/login/, 'Đang đăng nhập…'], [/^\/api\/auth\/register/, 'Đang gửi đăng ký…'], [/^\/api\/auth\/reset-request/, 'Đang gửi yêu cầu…'], [/^\/api\/auth\/logout/, 'Đang đăng xuất…'],
    [/^\/api\/settings\/llm\/models/, 'Đang tải danh sách model…'], [/^\/api\/settings\/llm\/clear/, 'Đang xóa API key…'], [/^\/api\/settings\/llm/, 'Đang lưu và kiểm tra kết nối…'],
    [/^\/api\/admin\//, 'Đang cập nhật…']];
  const QUIET = /^\/api\/(state|admin\/users)$/;          // các lần hỏi định kỳ: không hiện chỉ báo
  const stack = []; let hold = '', bar, pill, txt;

  function ensure() {
    if (bar || !document.body) return !!bar;
    bar = document.createElement('div'); bar.id = 'ldbar'; bar.setAttribute('aria-hidden', 'true');
    pill = document.createElement('div'); pill.id = 'ldpill'; pill.setAttribute('role', 'status'); pill.setAttribute('aria-live', 'polite');
    pill.innerHTML = '<span class="spin" aria-hidden="true"></span><span class="t"></span>'; txt = pill.lastChild;
    document.body.append(bar, pill); return true;
  }
  function paint() {
    if (!ensure()) return;
    const m = stack.length ? stack[stack.length - 1].m : hold;
    bar.classList.toggle('on', !!m); pill.classList.toggle('on', !!m); if (m) txt.textContent = m;
  }
  const label = path => { for (const [re, m] of MSG) if (re.test(path)) return m; return 'Đang xử lý…' };

  const raw = window.fetch.bind(window);
  window.fetch = function (input, init) {
    let path = '', method = 'GET';
    try { path = new URL(typeof input === 'string' ? input : input.url, location.href).pathname; method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase() } catch (e) { }
    if (method === 'GET' && QUIET.test(path)) return raw(input, init);
    const tok = { m: label(path) }; stack.push(tok); paint();
    return raw(input, init).finally(() => { const i = stack.indexOf(tok); if (i >= 0) stack.splice(i, 1); paint() });
  };
  window.Loading = { hold(m) { hold = m || ''; paint() } };
})();
