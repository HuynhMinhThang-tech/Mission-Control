# PATCH REPORT

Áp lúc 13:42:55 24/10/2026 · dự án `C:\Users\AUS\OneDrive\Máy tính\mission_control` · đích `framework/`

## Đã cài
- `+` providers.js — thêm mới
- `+` chart-advisor.js — thêm mới
- `+` pipeline-core.js — thêm mới
- `+` deck-builder.js — thêm mới
- `+` agent-playbooks.md — thêm mới
- `+` package.json — khai báo "type":"module" cho thư mục này
- pptxgenjs: không thấy package.json — bỏ qua; khi dùng deck-builder.js hãy cài: npm install pptxgenjs

## Tự kiểm tra
- ✓ Model Gemini dưới provider OpenAI bị bắt + có nút sửa
- ✓ Sửa tự động → Base URL Gemini
- ✓ Đổi provider thì Base URL tuỳ chỉnh được reset
- ✓ Đọc đúng số kiểu 1.234.567 và nhận là chỉ số đo
- ✓ Phát hiện cột phân loại bản ghi cần quyết định phạm vi
- ✓ Chặn biểu đồ cơ cấu trên cột thiếu 80%
- ✓ FactsStore bắt số bịa, chấp nhận số đúng
- ✓ extractJson chịu code fence + dấu phẩy thừa
- ✓ Lỗi "is not defined" được chẩn đoán kèm gợi ý
- ✓ safeRender báo sớm biến thiếu và có phương án thay thế
- – Bộ xuất PowerPoint: bỏ qua (chưa cài pptxgenjs)

## 1. Lỗi `MLAB is not defined`
**Không có nơi nào định nghĩa/import `MLAB`** trong dự án → `ReferenceError` là chắc chắn. Thường do file/thư viện chứa `MLAB` chưa được thêm, hoặc đã bị đổi tên/xoá khi refactor. Hãy khôi phục định nghĩa hoặc thay các chỗ dùng bên dưới.

Các dòng có `MLAB`:
- `apply-patch.mjs:15` — `* Phần quét sẽ chỉ ra chính xác dòng nào cần nối vào (MLAB, báo lỗi bước, Base URL) trong PATCH_REPORT.md.`
- `apply-patch.mjs:194` — `const DEF_RE = [/(?:window|globalThis|self)\s*\.\s*MLAB\s*=/, /\b(?:const|let|var)\s+MLAB\b/, /\bfunction\s+MLAB\b/, /\bclass\s+MLAB\b/, /\bexport\s+(`
- `apply-patch.mjs:196` — `const GLOBAL_RE = /(?:window|globalThis|self)\s*\.\s*MLAB\s*=|\bvar\s+MLAB\b/;`
- `apply-patch.mjs:217` — `log('  • đã quét ${scan.scanned} file; MLAB: ${scan.mlab.length} dòng; hiển thị lỗi bước: ${scan.stepErr.length}; Base URL: ${scan.baseUrl.length}');`
- `apply-patch.mjs:223` — `if (!scan.mlab.length) return 'Không thấy 'MLAB' trong mã nguồn web của dự án (có thể nằm ở thư viện bên ngoài, file đã build, hoặc backend). Bước này`
- `apply-patch.mjs:225` — `if (!scan.defFiles.length) parts.push('**Không có nơi nào định nghĩa/import 'MLAB'** trong dự án → 'ReferenceError' là chắc chắn. Thường do file/thư v`
- `apply-patch.mjs:227` — `parts.push('Có định nghĩa/import \'MLAB\' ở: ${scan.defFiles.map((d) => '\'${d.file}\'${d.global ? ' (gán toàn cục)' : ''}').join(', ')}.');`
- `apply-patch.mjs:228` — `if (scan.useOnlyFiles.length) parts.push('Các file **dùng \'MLAB\' nhưng không tự import/định nghĩa**: ${scan.useOnlyFiles.map((d) => '\'${d.file}\'')`
- `apply-patch.mjs:229` — `else parts.push('Mọi file dùng 'MLAB' đều có khai báo/import — lỗi nhiều khả năng do thứ tự nạp hoặc phạm vi chạy (iframe/Worker/'new Function').');`
- `apply-patch.mjs:246` — `## 1. Lỗi \'MLAB is not defined\'`
- `apply-patch.mjs:249` — `Các dòng có \'MLAB\':`
- `apply-patch.mjs:284` — `log('   MLAB: ${!scan.mlab.length ? 'không thấy trong mã nguồn' : !scan.defFiles.length ? 'KHÔNG có định nghĩa nào → đây là nguyên nhân lỗi' : 'định n`
- `static\js\app.js:131` — `const meth = fill ? '<div class="mt"><span>Cách xử lý:</span>${opts.map(x => '<label class="mc ${m === x ? 'on' : ''}"><input type="radio" name="m${o.`

## 2. Nơi hiển thị "Không hiển thị được bước này"
Bọc hàm render của từng bước bằng `safeRender` ở đây để lỗi hiện kèm chẩn đoán + nút thử lại, và để dấu ✓ lấy từ kết quả chạy thật:
- `apply-patch.mjs:214` — `lineHits(src, /Không hiển thị được bước này|Khong hien thi duoc buoc nay/, 10, file, scan.stepErr);`
- `apply-patch.mjs:252` — `## 2. Nơi hiển thị "Không hiển thị được bước này"`
- `static\js\app.js:208` — `else { try { h += VIEW[i]() } catch (e) { h += '<div class="note">Không hiển thị được bước này: ${esc(e.message)}</div>'; console.error(e) } h += acti`

## 3. Base URL đang viết cứng / lưu độc lập
Thay bằng `resolveBaseUrl(cfg)`; ô Provider gọi `changeProvider`:
- `apply-patch.mjs:15` — `* Phần quét sẽ chỉ ra chính xác dòng nào cần nối vào (MLAB, báo lỗi bước, Base URL) trong PATCH_REPORT.md.`
- `apply-patch.mjs:149` — `t('Sửa tự động → Base URL Gemini', P.resolveBaseUrl(P.applyFix(cfg, v.fixes[0])).includes('generativelanguage.googleapis.com'));`
- `apply-patch.mjs:150` — `t('Đổi provider thì Base URL tuỳ chỉnh được reset', P.changeProvider({ ...cfg, baseUrlOverride: 'https://x.y' }, 'gemini').baseUrlOverride === null);`
- `apply-patch.mjs:199` — `const scan = { mlab: [], stepErr: [], stepName: [], baseUrl: [], defFiles: [], useOnlyFiles: [], scanned: 0 };`
- `apply-patch.mjs:215` — `lineHits(src, /api\.openai\.com|generativelanguage\.googleapis\.com|api\.anthropic\.com|\bbase[_\s-]?url\b/i, 40, file, scan.baseUrl);`
- `apply-patch.mjs:217` — `log('  • đã quét ${scan.scanned} file; MLAB: ${scan.mlab.length} dòng; hiển thị lỗi bước: ${scan.stepErr.length}; Base URL: ${scan.baseUrl.length}');`
- `apply-patch.mjs:256` — `## 3. Base URL đang viết cứng / lưu độc lập`
- `apply-patch.mjs:258` — `${table(scan.baseUrl, 'không tìm thấy')}`
- `apply-patch.mjs:264` — `//  - đổi Provider  : cfg = changeProvider(cfg, providerId)          // Base URL tự về mặc định`
- `static\js\settings.js:1` — `// Tab "API & Model": mỗi người dùng tự nhập khóa API (lưu mã hóa), Base URL và model của riêng mình.`
- `static\js\settings.js:11` — `const form = () => ({ base_url: $s('sBase').value.trim(), api_key: $s('sKey').value.trim(), model: $s('sModel').value.trim() });`
- `static\js\settings.js:13` — `$s('sBase').value = S.base_url || '';`
- `static\js\settings.js:30` — `<div><label for="sBase">Base URL</label><input id="sBase" type="url" autocomplete="off" spellcheck="false" placeholder="https://..."><small>Mặc định l`
- `static\js\settings.js:42` — `const f = form(); const r = await api('/api/settings/llm/models', { base_url: f.base_url, api_key: f.api_key });`

## 4. Nối vào (copy–paste)
```js
// Tab API & Model
import { PROVIDERS, createConfig, changeProvider, resolveBaseUrl, validateConfig, applyFix, listModels, testConnection, callLLM } from './framework/providers.js';
//  - đổi Provider  : cfg = changeProvider(cfg, providerId)          // Base URL tự về mặc định
//  - hiển thị URL  : resolveBaseUrl(cfg)                             // readonly; nút "Tuỳ chỉnh" mới ghi cfg.baseUrlOverride
//  - trước khi chạy: const v = validateConfig(cfg); nếu !v.ok -> hiện v.errors và nút cho từng v.fixes (cfg = applyFix(cfg, fix))
//  - nút Kiểm tra  : await testConnection(cfg)

// Mỗi bước của pipeline
import { runStage, safeRender, FactsStore } from './framework/pipeline-core.js';
const r = safeRender('clean', () => renderCleanStep(state));        // thay cho render trực tiếp
if (!r.ok) showStepError(r.diagnostics);                             // .message, .hint, .stack; r.fallback = ['show-raw-output','retry','copy-diagnostics']
```
Chi tiết prompt và quy tắc cho các Agent: `framework/agent-playbooks.md`.

Hoàn tác: `node apply-patch.mjs --undo`
