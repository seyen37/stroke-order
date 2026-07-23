// ======================================================================
// gallery/uploader.js — upload dialog with client-side schema preview.
//
// Phase 5b r28: 支援兩種 upload kind
//   - psd     : .json (schema=stroke-order-psd-v1, 抄經軌跡)
//   - mandala : .mandala.md frontmatter 或 .svg 內嵌 metadata
//                (schema=stroke-order-mandala-v1)
//
// 從檔案內容偵測 kind（不靠副檔名）→ 呼叫對應 analyser → 顯示
// kind-specific summary。Submit 時帶 `kind` Form 欄位給後端。
// ======================================================================

const $ = id => document.getElementById(id);

// 5fw：分類單一事實源（與 gallery.js 共用；沿用既有無 ?v= 匯入樣式，
// 避免同模組雙實例——ES 鏈 ?v= 缺口見 backlog §67）
import { EXPORT_KINDS, KIND_LABELS } from './hash.mjs';

const KIND_PSD     = 'psd';
const KIND_MANDALA = 'mandala';
const KIND_POPUP   = 'popup';                       // 5ft：立體字
const PSD_SCHEMA     = 'stroke-order-psd-v1';
const MANDALA_SCHEMA = 'stroke-order-mandala-v1';
const POPUP_SCHEMA   = 'stroke-order-popup-v1';     // 5ft
const EXPORT_SCHEMA  = 'stroke-order-export-v1';    // 5fw：模式匯出信封

let _selectedFile = null;        // File object once user picks
let _selectedAnalysis = null;    // { ok, kind, ... } or null


// ----------------------------------------------------------- helpers

async function _readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file, 'utf-8');
  });
}

async function _sha256HexPrefix(file) {
  // Web crypto: digest the file's bytes; show first 12 hex chars
  // so the user can spot duplicates without overflowing the dialog.
  const buf = await file.arrayBuffer();
  const hashBuf = await crypto.subtle.digest('SHA-256', buf);
  const bytes = new Uint8Array(hashBuf);
  return Array.from(bytes.slice(0, 6))
    .map(b => b.toString(16).padStart(2, '0')).join('');
}

// 從檔案文字偵測 upload kind（不靠副檔名，純看內容開頭）
function _detectKindFromText(text) {
  const t = text.trimStart();
  if (t.startsWith('<svg') || t.startsWith('<?xml')) {
    // 5ft/5fw：SVG 依內嵌 metadata 分流——popup-config＝立體字、
    // stroke-order-export＝模式匯出、mandala-config＝曼陀羅；
    // 都沒有 → 走 export 分析路（錯誤訊息會引導重新匯出）
    if (text.includes('<popup-config'))         return 'popup-svg';
    if (text.includes('<stroke-order-export'))  return 'export-svg';
    if (text.includes('<mandala-config'))       return 'mandala-svg';
    return 'export-svg';
  }
  if (t.startsWith('---'))                             return 'mandala-md';
  if (t.startsWith('{'))                               return 'psd-json';
  return 'unknown';
}

function _analysePsd(json) {
  const traces = Array.isArray(json?.traces) ? json.traces : [];
  const chars = new Set();
  const styles = new Set();
  for (const t of traces) {
    if (t && typeof t === 'object') {
      if (typeof t.char === 'string' && t.char) chars.add(t.char);
      if (typeof t.style === 'string' && t.style) styles.add(t.style);
    }
  }
  return {
    trace_count:  traces.length,
    unique_chars: chars.size,
    styles_used:  Array.from(styles).sort(),
  };
}

function _analyseMandalaState(state) {
  const extra = Array.isArray(state?.extra_layers) ? state.extra_layers : [];
  const rings = new Set();
  for (const l of extra) {
    if (l && typeof l === 'object' && Number.isInteger(l.ring)) {
      rings.add(l.ring);
    }
  }
  return {
    title:              state?.metadata?.title || '',
    layer_count:        extra.length,
    ring_count:         rings.size,
    center_text:        (state?.center?.text || '').slice(0, 8),
    ring_text_short:    (state?.ring?.text || '').slice(0, 16),
    mandala_style:      state?.mandala?.style || '',
    composition_scheme: state?.mandala?.composition_scheme || '',
  };
}


// ----------------------------------------------------------- preview

async function _renderPreview(file) {
  const box = $('gl-upload-preview');
  box.hidden = false;
  box.classList.remove('error');
  box.textContent = '分析中…';
  _selectedAnalysis = null;

  let text;
  try {
    text = await _readFileAsText(file);
  } catch (e) {
    box.classList.add('error');
    box.innerHTML = '<b>⚠ 無法讀取檔案</b>：' + (e?.message || '');
    _selectedAnalysis = { ok: false };
    return;
  }

  const detected = _detectKindFromText(text);

  if (detected === 'psd-json') {
    let json;
    try { json = JSON.parse(text); }
    catch (e) {
      box.classList.add('error');
      box.innerHTML = '<b>⚠ JSON 解析失敗</b>：' + (e?.message || '');
      _selectedAnalysis = { ok: false };
      return;
    }
    if (json?.schema !== PSD_SCHEMA) {
      box.classList.add('error');
      box.innerHTML = (
        `<b>⚠ schema 不符</b>：${json?.schema || '（未指定）'}；` +
        `預期 <code>${PSD_SCHEMA}</code>。`
      );
      _selectedAnalysis = { ok: false };
      return;
    }
    const stats = _analysePsd(json);
    if (stats.trace_count === 0) {
      box.classList.add('error');
      box.innerHTML = '<b>⚠ traces 是空的</b>，無法上傳。';
      _selectedAnalysis = { ok: false };
      return;
    }
    let hashPrefix = '';
    try { hashPrefix = await _sha256HexPrefix(file); } catch (_) {}
    box.innerHTML = (
      `<b>✓ 抄經軌跡 (${PSD_SCHEMA})</b><br>` +
      `<b>${stats.trace_count}</b> 筆軌跡 · ` +
      `<b>${stats.unique_chars}</b> 不重複字<br>` +
      `字型：${stats.styles_used.length
        ? stats.styles_used.map(s => `<span class="pill">${s}</span>`).join(' ')
        : '<i>（未標註）</i>'}<br>` +
      (hashPrefix
        ? `<small>SHA-256 前 12 碼：<span class="pill">${hashPrefix}</span></small>`
        : '')
    );
    _selectedAnalysis = { ok: true, kind: KIND_PSD, ...stats };
    return;
  }

  if (detected === 'mandala-md' || detected === 'mandala-svg') {
    let state;
    try {
      if (detected === 'mandala-md') {
        const m = text.match(/^---\s*\n([\s\S]*?)\n---\s*\n?[\s\S]*$/);
        if (!m) throw new Error('缺少 YAML frontmatter (--- ... ---)');
        if (typeof jsyaml === 'undefined') {
          throw new Error('js-yaml 未載入（CDN 失敗？）');
        }
        state = jsyaml.load(m[1]);
      } else {
        // mandala-svg
        const m = text.match(
          /<mandala-config[^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/mandala-config>/);
        if (!m) {
          throw new Error('SVG 內未找到 <mandala-config> metadata（請從本系統重新匯出 SVG）');
        }
        let json = m[1].replace(/\]\]\]\]><!\[CDATA\[>/g, ']]>');
        state = JSON.parse(json);
      }
    } catch (e) {
      box.classList.add('error');
      box.innerHTML = '<b>⚠ mandala 檔案解析失敗</b>：' + (e?.message || e);
      _selectedAnalysis = { ok: false };
      return;
    }
    if (!state || typeof state !== 'object') {
      box.classList.add('error');
      box.innerHTML = '<b>⚠ frontmatter 不是有效物件</b>';
      _selectedAnalysis = { ok: false };
      return;
    }
    if (state.schema !== MANDALA_SCHEMA) {
      box.classList.add('error');
      box.innerHTML = (
        `<b>⚠ schema 不符</b>：${state.schema || '（未指定）'}；` +
        `預期 <code>${MANDALA_SCHEMA}</code>。`
      );
      _selectedAnalysis = { ok: false };
      return;
    }
    const stats = _analyseMandalaState(state);
    let hashPrefix = '';
    try { hashPrefix = await _sha256HexPrefix(file); } catch (_) {}
    const titleHtml = stats.title
      ? `「${stats.title}」<br>` : '';
    box.innerHTML = (
      `<b>✓ 曼陀羅 (${MANDALA_SCHEMA}, ${detected === 'mandala-svg' ? 'SVG 內嵌' : 'MD frontmatter'})</b><br>` +
      titleHtml +
      `<b>${stats.layer_count}</b> 個裝飾層 · ` +
      `<b>${stats.ring_count}</b> 個環 · ` +
      `中心：${stats.center_text || '<i>（空）</i>'}<br>` +
      `主 mandala：<span class="pill">${stats.mandala_style}</span> ` +
      `<span class="pill">${stats.composition_scheme}</span><br>` +
      (hashPrefix
        ? `<small>SHA-256 前 12 碼：<span class="pill">${hashPrefix}</span></small>`
        : '')
    );
    _selectedAnalysis = { ok: true, kind: KIND_MANDALA, ...stats };
    return;
  }

  if (detected === 'export-svg') {
    // 5fw：模式匯出 SVG——抽信封驗 schema/mode，kind＝檔案聲明的 mode
    const m = /<stroke-order-export><!\[CDATA\[([\s\S]*?)\]\]><\/stroke-order-export>/.exec(text);
    let env = null;
    if (m) { try { env = JSON.parse(m[1]); } catch (_) { env = null; } }
    if (!env) {
      box.classList.add('error');
      box.innerHTML = (
        '<b>⚠ SVG 內未找到本站出口憑據</b>：只接受 v0.14.271 之後' +
        '從本站各模式匯出的 SVG，請回對應模式重新產生並下載。'
      );
      _selectedAnalysis = { ok: false };
      return;
    }
    if (env.schema !== EXPORT_SCHEMA) {
      box.classList.add('error');
      box.innerHTML = (
        `<b>⚠ schema 不符</b>：${env.schema || '（未指定）'}；` +
        `預期 <code>${EXPORT_SCHEMA}</code>。`
      );
      _selectedAnalysis = { ok: false };
      return;
    }
    if (!EXPORT_KINDS.includes(env.mode)) {
      box.classList.add('error');
      box.innerHTML = (
        `<b>⚠ 未知的模式</b>：${env.mode || '（未指定）'}——` +
        '可能是較新版本的檔案，請重新整理頁面後再試。'
      );
      _selectedAnalysis = { ok: false };
      return;
    }
    box.innerHTML = (
      `<b>✓ ${KIND_LABELS[env.mode] || env.mode} (${EXPORT_SCHEMA})</b><br>` +
      `分類：<span class="pill">${KIND_LABELS[env.mode] || env.mode}</span>` +
      (env.app_version
        ? ` · 匯出版本 <span class="pill">v${env.app_version}</span>` : '')
    );
    _selectedAnalysis = { ok: true, kind: env.mode };
    return;
  }

  if (detected === 'popup-svg') {   // 5ft：立體字 SVG
    let state;
    try {
      const m = text.match(
        /<popup-config[^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/popup-config>/);
      if (!m) throw new Error('SVG 內未找到 <popup-config> metadata');
      state = JSON.parse(m[1]);
    } catch (e) {
      box.classList.add('error');
      box.innerHTML = '<b>⚠ 立體字檔案解析失敗</b>：' + (e?.message || e);
      _selectedAnalysis = { ok: false };
      return;
    }
    if (!state || state.schema !== POPUP_SCHEMA) {
      box.classList.add('error');
      box.innerHTML = (
        `<b>⚠ schema 不符</b>：${state?.schema || '（未指定）'}；` +
        `預期 <code>${POPUP_SCHEMA}</code>。`
      );
      _selectedAnalysis = { ok: false };
      return;
    }
    let hashPrefix = '';
    try { hashPrefix = await _sha256HexPrefix(file); } catch (_) {}
    box.innerHTML = (
      `<b>✓ 立體字 (${POPUP_SCHEMA}, SVG 內嵌)</b><br>` +
      `上排：「${state.upper || ''}」` +
      (state.lower ? `　下排：「${state.lower}」` : '') + '<br>' +
      `卡片 ${state.card_w_mm || '?'}×${state.card_h_mm || '?'} mm` +
      (hashPrefix
        ? `<br><small>SHA-256 前 12 碼：<span class="pill">${hashPrefix}</span></small>`
        : '')
    );
    _selectedAnalysis = { ok: true, kind: KIND_POPUP };
    return;
  }

  // unknown
  box.classList.add('error');
  box.innerHTML = (
    '<b>⚠ 無法判斷檔案種類</b><br>' +
    '請使用：抄經軌跡 (.json)、曼陀羅 (.mandala.md / 含 metadata 的 .svg)、' +
    '立體字（含 metadata 的 .svg）。'
  );
  _selectedAnalysis = { ok: false };
}


// ----------------------------------------------------------- public API

export function showUploadDialog() {
  const dlg = $('gl-upload-dialog');
  $('gl-upload-form').reset();
  $('gl-upload-preview').hidden = true;
  $('gl-upload-preview').classList.remove('error');
  $('gl-upload-status').hidden = true;
  $('gl-upload-status').textContent = '';
  $('gl-upload-status').classList.remove('ok', 'error', 'info');
  $('gl-upload-submit').disabled = false;
  _selectedFile = null;
  _selectedAnalysis = null;
  if (typeof dlg.showModal === 'function') dlg.showModal();
  else dlg.setAttribute('open', '');
}

export function hideUploadDialog() {
  const dlg = $('gl-upload-dialog');
  if (dlg.open) dlg.close();
}

async function _onFileChange(ev) {
  const file = ev.target.files?.[0];
  _selectedFile = file || null;
  if (file) await _renderPreview(file);
  else $('gl-upload-preview').hidden = true;
}

async function _onSubmit(ev, ctx) {
  ev.preventDefault();
  const status = $('gl-upload-status');
  const submit = $('gl-upload-submit');
  status.classList.remove('ok', 'error', 'info');

  if (!_selectedFile) {
    status.hidden = false;
    status.classList.add('error');
    status.textContent = '請先選擇 JSON 檔';
    return;
  }
  if (!_selectedAnalysis?.ok) {
    status.hidden = false;
    status.classList.add('error');
    status.textContent = '檔案不符合上傳條件，請參考上方提示';
    return;
  }
  const title   = ($('gl-upload-title').value || '').trim();
  const comment = ($('gl-upload-comment').value || '').trim();
  if (!title) {
    status.hidden = false;
    status.classList.add('error');
    status.textContent = '請填公開標題';
    return;
  }

  const fd = new FormData();
  fd.append('file', _selectedFile, _selectedFile.name);
  fd.append('title', title);
  fd.append('comment', comment);
  // r28: 帶 kind 給後端（從前述偵測 + analyse 已驗證）
  fd.append('kind', _selectedAnalysis.kind || KIND_PSD);

  submit.disabled = true;
  status.hidden = false;
  status.classList.add('info');
  status.textContent = '上傳中…';

  try {
    const r = await fetch('/api/gallery/uploads', {
      method: 'POST',
      body: fd,
      credentials: 'same-origin',
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      throw new Error(data.detail || `HTTP ${r.status}`);
    }
    status.classList.remove('info');
    status.classList.add('ok');
    status.textContent = '✓ 上傳成功！';
    setTimeout(() => {
      hideUploadDialog();
      ctx.refresh && ctx.refresh();
    }, 700);
  } catch (e) {
    status.classList.remove('info');
    status.classList.add('error');
    status.textContent = '上傳失敗：' + (e.message || e);
    submit.disabled = false;
  }
}


/**
 * Wire upload dialog handlers.
 * @param {{ refresh: () => Promise<void> }} ctx
 */
export function attachUploaderHandlers(ctx) {
  $('gl-upload-file').addEventListener('change', _onFileChange);
  $('gl-upload-form').addEventListener('submit', e => _onSubmit(e, ctx));
  document.querySelector(
    '[data-action="upload-cancel"]',
  ).addEventListener('click', () => hideUploadDialog());
}
