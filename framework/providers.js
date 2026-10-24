/**
 * providers.js — Registry nhà cung cấp LLM + đồng bộ Base URL tự động (ESM, không phụ thuộc thư viện)
 *
 * QUY TẮC CỐT LÕI
 *   Base URL KHÔNG phải một ô nhập độc lập. Nó được SUY RA từ Provider.
 *   Chỉ khi người dùng chủ động bật "Tuỳ chỉnh" (baseUrlOverride) thì mới giữ giá trị riêng.
 *
 * STATE CẦN LƯU
 *   { provider, model, baseUrlOverride: string|null, keys: { [provider]: string } }
 *   -> API key lưu THEO PROVIDER, đổi qua lại không mất key và không gửi nhầm key sang host khác.
 *
 * UI NÊN LÀM
 *   1. Chọn Provider (chính)  ->  Base URL tự điền (readonly, có nút "Tuỳ chỉnh" / "Khôi phục mặc định").
 *   2. Danh sách Model lấy từ listModels() (fallback: gõ tay), lọc theo provider.
 *   3. Nút "Kiểm tra kết nối" -> testConnection(); nếu validateConfig() có fix -> hiện nút "Sửa tự động".
 */

export const PROVIDERS = {
  openai:     { label: 'OpenAI',                        style: 'openai',    baseUrl: 'https://api.openai.com/v1',                               modelMatch: /^(gpt-|o\d|chatgpt-)/i, tokenParam: 'max_completion_tokens' },
  anthropic:  { label: 'Anthropic (Claude)',            style: 'anthropic', baseUrl: 'https://api.anthropic.com/v1',                            modelMatch: /^claude/i,              tokenParam: 'max_tokens' },
  // Gemini dùng endpoint tương thích OpenAI chính thức của Google (đã đối chiếu tài liệu ai.google.dev)
  gemini:     { label: 'Google Gemini',                 style: 'openai',    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai', modelMatch: /^(models\/)?gemini/i,   tokenParam: 'max_tokens' },
  deepseek:   { label: 'DeepSeek',                      style: 'openai',    baseUrl: 'https://api.deepseek.com',                                modelMatch: /^deepseek/i,            tokenParam: 'max_tokens' },
  groq:       { label: 'Groq',                          style: 'openai',    baseUrl: 'https://api.groq.com/openai/v1',                          modelMatch: null,                    tokenParam: 'max_tokens' },
  openrouter: { label: 'OpenRouter',                    style: 'openai',    baseUrl: 'https://openrouter.ai/api/v1',                            modelMatch: null,                    tokenParam: 'max_tokens' },
  ollama:     { label: 'Ollama (máy cục bộ)',           style: 'openai',    baseUrl: 'http://localhost:11434/v1',                               modelMatch: null,                    tokenParam: 'max_tokens', keyOptional: true },
  custom:     { label: 'Tuỳ chỉnh (OpenAI-compatible)', style: 'openai',    baseUrl: '',                                                        modelMatch: null,                    tokenParam: 'max_tokens', custom: true },
};

// Provider "đa model" (gateway): không ép khớp họ model với provider
const GATEWAYS = new Set(['openrouter', 'groq', 'ollama', 'custom']);

const HOSTS = [
  [/api\.openai\.com/i, 'openai'], [/api\.anthropic\.com/i, 'anthropic'],
  [/generativelanguage\.googleapis\.com/i, 'gemini'], [/api\.deepseek\.com/i, 'deepseek'],
  [/api\.groq\.com/i, 'groq'], [/openrouter\.ai/i, 'openrouter'], [/(localhost|127\.0\.0\.1)/i, 'ollama'],
];

/* ---------- Cấu hình ---------- */

export function createConfig(provider = 'openai') {
  return { provider, model: '', baseUrlOverride: null, keys: {} };
}

export function normalizeBaseUrl(raw) {
  let u = String(raw || '').trim();
  if (!u) return '';
  if (!/^https?:\/\//i.test(u)) u = (/^(localhost|127\.|192\.168\.)/.test(u) ? 'http://' : 'https://') + u;
  // người dùng hay dán nhầm cả endpoint đầy đủ
  return u.replace(/\/+$/, '').replace(/\/(chat\/completions|completions|messages)$/i, '');
}

export function resolveBaseUrl(cfg) {
  const p = PROVIDERS[cfg.provider];
  return normalizeBaseUrl(cfg.baseUrlOverride || (p && p.baseUrl) || '');
}

/** Đổi provider: Base URL quay về mặc định; model chỉ giữ nếu còn khớp họ model của provider mới. */
export function changeProvider(cfg, provider) {
  const p = PROVIDERS[provider];
  if (!p) throw new Error(`Provider không hợp lệ: ${provider}`);
  const keepModel = !!(cfg.model && p.modelMatch && p.modelMatch.test(cfg.model));
  return { ...cfg, provider, model: keepModel ? cfg.model : '', baseUrlOverride: p.custom ? (cfg.baseUrlOverride || '') : null };
}

export function detectProviderFromModel(model) {
  if (!model) return null;
  for (const id of ['anthropic', 'gemini', 'deepseek', 'openai']) {
    if (PROVIDERS[id].modelMatch.test(model)) return id;
  }
  return null;
}

export function detectProviderFromUrl(url) {
  const hit = HOSTS.find(([re]) => re.test(url || ''));
  return hit ? hit[1] : null;
}

/** Kiểm tra chéo Provider ↔ Base URL ↔ Model ↔ Key. Trả về lỗi kèm gợi ý sửa. */
export function validateConfig(cfg) {
  const errors = [], warnings = [], fixes = [];
  const p = PROVIDERS[cfg.provider];
  if (!p) return { ok: false, errors: ['Chưa chọn provider hợp lệ.'], warnings, fixes };

  const base = resolveBaseUrl(cfg);
  if (!base) errors.push('Thiếu Base URL (provider "Tuỳ chỉnh" bắt buộc nhập).');
  else { try { new URL(base); } catch { errors.push(`Base URL không hợp lệ: ${base}`); } }
  if (!cfg.model) errors.push('Chưa chọn model.');
  if (!p.keyOptional && !(cfg.keys && cfg.keys[cfg.provider])) errors.push(`Chưa nhập API key cho ${p.label}.`);

  const hostProvider = detectProviderFromUrl(base);
  if (hostProvider && hostProvider !== cfg.provider && !p.custom) {
    errors.push(`Base URL đang trỏ tới ${PROVIDERS[hostProvider].label} nhưng provider là ${p.label}.`);
    fixes.push({ type: 'resetBaseUrl', label: `Dùng Base URL mặc định của ${p.label}` });
  }
  const effective = hostProvider || cfg.provider;
  const family = detectProviderFromModel(cfg.model);
  if (family && family !== effective && !GATEWAYS.has(effective)) {
    errors.push(`Model "${cfg.model}" thuộc ${PROVIDERS[family].label} nhưng đang gọi tới ${PROVIDERS[effective].label}.`);
    fixes.push({ type: 'switchProvider', to: family, label: `Chuyển sang ${PROVIDERS[family].label} (tự đổi Base URL)` });
  }
  if (cfg.baseUrlOverride && !p.custom) warnings.push('Đang dùng Base URL tuỳ chỉnh thay cho mặc định của provider.');
  return { ok: errors.length === 0, errors, warnings, fixes };
}

export function applyFix(cfg, fix) {
  if (fix.type === 'switchProvider') return { ...changeProvider(cfg, fix.to), model: cfg.model };
  if (fix.type === 'resetBaseUrl') return { ...cfg, baseUrlOverride: null };
  return cfg;
}

/* ---------- Gọi API ---------- */

export class LLMError extends Error {
  constructor(kind, message, extra = {}) { super(message); this.name = 'LLMError'; this.kind = kind; Object.assign(this, extra); }
}

function classify(status, msg) {
  const tail = msg ? ` — ${msg.slice(0, 200)}` : '';
  if (status === 401 || status === 403) return new LLMError('auth', `API key sai hoặc không có quyền với provider này${tail}`, { status });
  if (status === 404) return new LLMError('not_found', `Không tìm thấy endpoint hoặc model. Kiểm tra Base URL phải khớp provider và tên model${tail}`, { status });
  if (status === 429) return new LLMError('rate_limit', `Hết hạn mức hoặc bị giới hạn tốc độ${tail}`, { status });
  if (status >= 500) return new LLMError('server', `Provider đang lỗi (${status})${tail}`, { status });
  return new LLMError('bad_request', `Yêu cầu bị từ chối (${status})${tail}`, { status });
}

export function buildRequest(cfg, { system, messages = [], temperature, maxTokens = 4096 } = {}) {
  const p = PROVIDERS[cfg.provider];
  const base = resolveBaseUrl(cfg);
  const key = (cfg.keys && cfg.keys[cfg.provider]) || '';
  const inBrowser = typeof window !== 'undefined';

  if (p.style === 'anthropic') {
    const headers = { 'content-type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01' };
    if (inBrowser) headers['anthropic-dangerous-direct-browser-access'] = 'true'; // gọi thẳng từ trình duyệt; khuyến nghị đi qua proxy server
    const body = { model: cfg.model, max_tokens: maxTokens, messages };
    if (system) body.system = system;
    if (temperature != null) body.temperature = temperature;
    return { url: `${base}/messages`, headers, body };
  }
  const headers = { 'content-type': 'application/json' };
  if (key) headers.authorization = `Bearer ${key}`;
  const body = { model: cfg.model, messages: system ? [{ role: 'system', content: system }, ...messages] : messages, [p.tokenParam]: maxTokens };
  if (temperature != null) body.temperature = temperature;
  return { url: `${base}/chat/completions`, headers, body };
}

export function parseResponse(style, json) {
  if (style === 'anthropic') return (json.content || []).filter(b => b.type === 'text').map(b => b.text).join('');
  return (json.choices && json.choices[0] && json.choices[0].message && json.choices[0].message.content) || '';
}

/** Gọi 1 lần, tự sửa tham số không được model chấp nhận (temperature, max_tokens <-> max_completion_tokens). */
export async function callLLM(cfg, input, fetchImpl = globalThis.fetch) {
  const style = PROVIDERS[cfg.provider].style;
  const req = buildRequest(cfg, input);
  for (let attempt = 0; attempt < 3; attempt++) {
    let res, json;
    try {
      res = await fetchImpl(req.url, { method: 'POST', headers: req.headers, body: JSON.stringify(req.body) });
      json = await res.json().catch(() => ({}));
    } catch (e) {
      throw new LLMError('network', 'Không kết nối được (mạng hoặc CORS). Một số provider không cho gọi trực tiếp từ trình duyệt — hãy đi qua proxy phía server.', { detail: e.message });
    }
    if (res.ok) return { text: parseResponse(style, json), usage: json.usage, raw: json };
    const msg = String((json.error && json.error.message) || json.message || '');
    if (res.status === 400 && attempt < 2) {
      if (/temperature/i.test(msg) && 'temperature' in req.body) { delete req.body.temperature; continue; }
      if (/max_tokens/i.test(msg) && /max_completion_tokens/i.test(msg) && 'max_tokens' in req.body) { req.body.max_completion_tokens = req.body.max_tokens; delete req.body.max_tokens; continue; }
      if (/max_completion_tokens/i.test(msg) && 'max_completion_tokens' in req.body) { req.body.max_tokens = req.body.max_completion_tokens; delete req.body.max_completion_tokens; continue; }
    }
    throw classify(res.status, msg);
  }
}

const NON_CHAT = /embed|whisper|tts|dall-e|moderation|image|imagen|veo|aqa|audio|realtime|transcribe/i;

export async function listModels(cfg, fetchImpl = globalThis.fetch) {
  const style = PROVIDERS[cfg.provider].style;
  const base = resolveBaseUrl(cfg);
  const { headers } = buildRequest(cfg, {});
  delete headers['content-type'];
  const url = style === 'anthropic' ? `${base}/models?limit=100` : `${base}/models`;
  let res;
  try { res = await fetchImpl(url, { headers }); }
  catch (e) { throw new LLMError('network', 'Không tải được danh sách model (mạng/CORS).', { detail: e.message }); }
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw classify(res.status, String((json.error && json.error.message) || ''));
  return (json.data || json.models || [])
    .map(m => String(m.id || m.name || '').replace(/^models\//, ''))
    .filter(id => id && !NON_CHAT.test(id)).sort();
}

export async function testConnection(cfg, fetchImpl = globalThis.fetch) {
  const v = validateConfig(cfg);
  if (!v.ok) return { ok: false, stage: 'config', errors: v.errors, fixes: v.fixes };
  const t0 = Date.now();
  try {
    let models = null;
    try { models = await listModels(cfg, fetchImpl); } catch { /* một số gateway không có /models */ }
    if (models && models.length && !models.includes(cfg.model.replace(/^models\//, ''))) {
      return { ok: false, stage: 'model', errors: [`Model "${cfg.model}" không có trong danh sách của provider.`], suggestions: models.slice(0, 10) };
    }
    await callLLM(cfg, { messages: [{ role: 'user', content: 'ping' }], maxTokens: 8 }, fetchImpl);
    return { ok: true, latencyMs: Date.now() - t0 };
  } catch (e) {
    return { ok: false, stage: 'request', errors: [e.message], kind: e.kind };
  }
}
