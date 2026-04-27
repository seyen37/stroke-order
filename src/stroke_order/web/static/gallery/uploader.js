// ======================================================================
// gallery/uploader.js — upload dialog with client-side schema preview.
//
// Selecting a JSON file pre-validates the schema and shows a tiny
// summary card (trace_count / unique chars / styles / SHA-256 prefix)
// so the user can confirm what they're about to publish before
// committing.
//
// On submit, posts multipart to POST /api/gallery/uploads.
// ======================================================================

const $ = id => document.getElementById(id);

let _selectedFile = null;        // File object once user picks
let _selectedAnalysis = null;    // { ok, schema, trace_count, … } or null


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

function _analyseLocal(json) {
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


// ----------------------------------------------------------- preview

async function _renderPreview(file) {
  const box = $('gl-upload-preview');
  box.hidden = false;
  box.textContent = '分析中…';

  let json;
  try {
    const text = await _readFileAsText(file);
    json = JSON.parse(text);
  } catch (e) {
    box.classList.add('error');
    box.innerHTML = '<b>⚠ 無法解析檔案</b>：' +
      (e?.message || '請確認是有效的 JSON');
    _selectedAnalysis = { ok: false };
    return;
  }
  if (json?.schema !== 'stroke-order-psd-v1') {
    box.classList.add('error');
    box.innerHTML = (
      `<b>⚠ schema 不符</b>：${json?.schema || '（未指定）'}；` +
      `本系統僅接受 <code>stroke-order-psd-v1</code>（請從筆順練習頁匯出）。`
    );
    _selectedAnalysis = { ok: false };
    return;
  }
  const stats = _analyseLocal(json);
  if (stats.trace_count === 0) {
    box.classList.add('error');
    box.innerHTML = '<b>⚠ traces 是空的</b>，無法上傳。';
    _selectedAnalysis = { ok: false };
    return;
  }

  let hashPrefix = '';
  try { hashPrefix = await _sha256HexPrefix(file); }
  catch (_) { /* non-fatal */ }

  box.classList.remove('error');
  box.innerHTML = (
    `<b>✓ schema OK</b><br>` +
    `<b>${stats.trace_count}</b> 筆軌跡 · 涵蓋 <b>${stats.unique_chars}</b> 個不重複字<br>` +
    `字型：${stats.styles_used.length
      ? stats.styles_used.map(s => `<span class="pill">${s}</span>`).join(' ')
      : '<i>（未標註）</i>'}<br>` +
    (hashPrefix
      ? `<small>SHA-256 前 12 碼：<span class="pill">${hashPrefix}</span></small>`
      : '')
  );
  _selectedAnalysis = { ok: true, ...stats };
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
