// ============================================================
// User-dict manager (Phase 5ak) — modal + handwriting + SVG + JSON
// ============================================================

const UD = {
  hwStrokes: [],          // array of [{x,y}, ...]
  hwActive: null,         // currently-drawing stroke (or null)
  svgContent: null,       // raw SVG text from upload
  activeTab: "hw",
  editingChar: null,      // Phase 5ar: which existing char is loaded for edit
};

function udInit() {
  document.getElementById("ud-open").onclick = udOpen;
  document.getElementById("ud-close").onclick = udClose;
  document.getElementById("ud-overlay").addEventListener("click", (e) => {
    if (e.target.id === "ud-overlay") udClose();
  });
  // Tab switching
  document.querySelectorAll(".ud-tab-btn").forEach(b => {
    b.addEventListener("click", () => udSwitchTab(b.dataset.tab));
  });
  document.getElementById("ud-canvas-undo").onclick = udHwUndo;
  document.getElementById("ud-canvas-clear").onclick = udHwClear;
  document.getElementById("ud-svg-file").addEventListener("change", udSvgPick);
  document.getElementById("ud-save").onclick = udSave;
  // Phase 5ar
  document.getElementById("ud-export").onclick = udExport;
  document.getElementById("ud-import").onclick = udImport;
  udBindCanvas();
}

async function udOpen() {
  document.getElementById("ud-overlay").style.display = "flex";
  await udRefreshList();
}
function udClose() {
  document.getElementById("ud-overlay").style.display = "none";
}

function udSwitchTab(tab) {
  UD.activeTab = tab;
  document.querySelectorAll(".ud-tab-btn").forEach(b => {
    const active = b.dataset.tab === tab;
    b.style.borderBottomColor = active ? "var(--accent)" : "transparent";
    b.style.fontWeight = active ? "600" : "normal";
  });
  document.getElementById("ud-tab-hw").style.display   = (tab === "hw")   ? "" : "none";
  document.getElementById("ud-tab-svg").style.display  = (tab === "svg")  ? "" : "none";
  document.getElementById("ud-tab-json").style.display = (tab === "json") ? "" : "none";
}

// ---- existing-chars list -----------------------------------
async function udRefreshList() {
  const el = document.getElementById("ud-list");
  try {
    const r = await fetch(`${API_BASE}/api/user-dict`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    document.getElementById("ud-path").textContent = d.dict_dir;
    if (d.count === 0) {
      el.innerHTML = `<span style="color:var(--muted);font-size:12px;">
        （尚未自訂任何字。在下方畫一個或上傳 SVG 試試）</span>`;
      return;
    }
    // Phase 5ar: chip with mini SVG preview, click body to edit, X to delete.
    el.innerHTML = d.chars.map(c => {
      const editing = (UD.editingChar === c.char);
      const border = editing ? "var(--accent)" : "var(--border)";
      const bg = editing ? "#fff8e0" : "white";
      return `
      <span data-char="${escapeAttr(c.char)}" class="ud-chip"
            style="display:inline-flex;align-items:center;gap:4px;
                   padding:4px 6px;background:${bg};border:1.5px solid ${border};
                   border-radius:4px;font-size:14px;">
        <span class="ud-chip-preview" data-preview="${escapeAttr(c.char)}"
              style="display:inline-block;width:32px;height:32px;
                     background:#fafafa;border:1px solid #eee;border-radius:2px;
                     vertical-align:middle;"></span>
        <button class="ud-chip-load" data-char="${escapeAttr(c.char)}"
                title="載入編輯"
                style="background:none;border:none;cursor:pointer;
                       padding:2px 4px;font:inherit;text-align:left;">
          <span style="font-size:18px;font-family:'Noto Sans TC',sans-serif;">${escapeHtml(c.char)}</span>
          <span style="color:var(--muted);font-size:10px;">U+${c.unicode_hex.toUpperCase()} · ${c.stroke_count} 筆</span>
        </button>
        <button data-char="${escapeAttr(c.char)}" class="ud-del"
                style="background:none;border:none;cursor:pointer;color:var(--accent);"
                title="刪除">✕</button>
      </span>
      `;
    }).join("");
    el.querySelectorAll(".ud-del").forEach(b => {
      b.addEventListener("click", (e) => { e.stopPropagation(); udDelete(b.dataset.char); });
    });
    el.querySelectorAll(".ud-chip-load").forEach(b => {
      b.addEventListener("click", () => udLoadIntoEditor(b.dataset.char));
    });
    // Async fetch each char and inject mini preview SVG. Browser handles
    // parallelism; for typical user-dict sizes (5-50 chars) this is fast.
    el.querySelectorAll(".ud-chip-preview").forEach(span => {
      udRenderChipPreview(span.dataset.preview, span);
    });
  } catch (e) {
    el.innerHTML = `<span style="color:var(--accent);font-size:12px;">讀取失敗：${e.message}</span>`;
  }
}

async function udRenderChipPreview(ch, container) {
  try {
    const r = await fetch(`${API_BASE}/api/user-dict/${encodeURIComponent(ch)}`);
    if (!r.ok) return;
    const d = await r.json();
    // Build mini SVG from raw_track in 2048 em frame, scaled to 32×32.
    const polylines = d.strokes.map(s =>
      `<polyline points="${s.track.map(p => `${p[0]},${p[1]}`).join(' ')}"
                 fill="none" stroke="#222" stroke-width="60"
                 stroke-linecap="round" stroke-linejoin="round"/>`
    ).join("");
    container.innerHTML = `<svg viewBox="0 0 2048 2048" width="32" height="32">${polylines}</svg>`;
  } catch (_) { /* leave empty box on error */ }
}

async function udDelete(ch) {
  if (!confirm(`刪除 "${ch}"？`)) return;
  await fetch(`${API_BASE}/api/user-dict/${encodeURIComponent(ch)}`, {method: "DELETE"});
  if (UD.editingChar === ch) UD.editingChar = null;   // exit edit mode
  await udRefreshList();
}

// ---- Phase 5ar: edit-existing flow -------------------------------------
async function udLoadIntoEditor(ch) {
  try {
    const r = await fetch(`${API_BASE}/api/user-dict/${encodeURIComponent(ch)}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    // Drop existing strokes into the handwriting canvas — em coords
    // (0..2048) scale linearly to canvas pixels (0..W/H, since canvas
    // is square and udSave rescales back to em for the round-trip).
    const canvas = document.getElementById("ud-canvas");
    const W = canvas.width, H = canvas.height;
    UD.hwStrokes = d.strokes.map(s =>
      s.track.map(p => [p[0] / 2048 * W, p[1] / 2048 * H])
    );
    UD.editingChar = ch;
    document.getElementById("ud-char").value = ch;
    udSwitchTab("hw");
    udHwRedraw();
    udHwUpdateInfo();
    await udRefreshList();   // re-paint to highlight the active chip
    document.getElementById("ud-save-status").textContent =
      `編輯中：${ch}（修改後按存檔會覆蓋既有）`;
    document.getElementById("ud-save-status").style.color = "var(--accent)";
  } catch (e) {
    document.getElementById("ud-save-status").textContent = "載入失敗：" + e.message;
    document.getElementById("ud-save-status").style.color = "var(--accent)";
  }
}

// ---- Phase 5ar: bulk export -----------------------------------
function udExport() {
  // Browser handles the download via Content-Disposition header.
  window.location.href = `${API_BASE}/api/user-dict/export`;
}

// ---- Phase 5ar: bulk import -----------------------------------
async function udImport() {
  const file = document.getElementById("ud-import-file").files[0];
  const status = document.getElementById("ud-bulk-status");
  if (!file) {
    status.textContent = "請先選擇 ZIP 檔";
    status.style.color = "var(--accent)";
    return;
  }
  const policyEl = document.querySelector("input[name='ud-import-policy']:checked");
  const policy = policyEl ? policyEl.value : "skip";
  const fd = new FormData();
  fd.append("file", file);
  fd.append("policy", policy);
  status.textContent = "匯入中…";
  status.style.color = "var(--muted)";
  try {
    const r = await fetch(`${API_BASE}/api/user-dict/import`,
                          {method: "POST", body: fd});
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: r.statusText}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    const s = await r.json();
    const errs = (s.errors || []).length;
    status.textContent =
      `✓ 新增 ${s.added}・覆蓋 ${s.replaced}・跳過 ${s.skipped}` +
      (errs ? `・${errs} 個錯誤項` : "");
    status.style.color = "#260";
    document.getElementById("ud-import-file").value = "";
    await udRefreshList();
  } catch (e) {
    status.textContent = "匯入失敗：" + e.message;
    status.style.color = "var(--accent)";
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, m => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[m]));
}
function escapeAttr(s) { return escapeHtml(s); }

// ---- handwriting canvas -------------------------------------
function udBindCanvas() {
  const canvas = document.getElementById("ud-canvas");
  canvas.addEventListener("pointerdown", e => {
    canvas.setPointerCapture(e.pointerId);
    const p = udCanvasPt(e);
    UD.hwActive = [p];
    UD.hwStrokes.push(UD.hwActive);
    udHwRedraw();
  });
  canvas.addEventListener("pointermove", e => {
    if (UD.hwActive == null) return;
    UD.hwActive.push(udCanvasPt(e));
    udHwRedraw();
  });
  const finish = (e) => {
    if (UD.hwActive == null) return;
    UD.hwActive = null;
    udHwUpdateInfo();
  };
  canvas.addEventListener("pointerup", finish);
  canvas.addEventListener("pointercancel", finish);
  canvas.addEventListener("pointerleave", finish);
  udHwRedraw();
}

function udCanvasPt(e) {
  const r = e.target.getBoundingClientRect();
  return [e.clientX - r.left, e.clientY - r.top];
}

function udHwRedraw() {
  const canvas = document.getElementById("ud-canvas");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  // 米字格 reference
  ctx.strokeStyle = "#e8e8e8";
  ctx.lineWidth = 1;
  ctx.beginPath();
  // outer box
  ctx.strokeRect(0.5, 0.5, W - 1, H - 1);
  // diagonals + cross
  ctx.beginPath();
  ctx.moveTo(0, 0); ctx.lineTo(W, H);
  ctx.moveTo(W, 0); ctx.lineTo(0, H);
  ctx.moveTo(W / 2, 0); ctx.lineTo(W / 2, H);
  ctx.moveTo(0, H / 2); ctx.lineTo(W, H / 2);
  ctx.stroke();
  // strokes
  ctx.strokeStyle = "#222";
  ctx.lineWidth = 3;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (const s of UD.hwStrokes) {
    if (s.length < 2) continue;
    ctx.beginPath();
    ctx.moveTo(s[0][0], s[0][1]);
    for (let i = 1; i < s.length; i++) ctx.lineTo(s[i][0], s[i][1]);
    ctx.stroke();
  }
}
function udHwUpdateInfo() {
  document.getElementById("ud-canvas-info").textContent =
    `${UD.hwStrokes.filter(s => s.length >= 2).length} 筆畫`;
}
function udHwUndo() { UD.hwStrokes.pop(); udHwRedraw(); udHwUpdateInfo(); }
function udHwClear() { UD.hwStrokes = []; udHwRedraw(); udHwUpdateInfo(); }

// ---- SVG upload --------------------------------------------
async function udSvgPick(e) {
  const f = e.target.files[0];
  const preview = document.getElementById("ud-svg-preview");
  if (!f) {
    UD.svgContent = null;
    preview.innerHTML = "(選擇 SVG 後預覽)";
    return;
  }
  UD.svgContent = await f.text();
  preview.innerHTML = UD.svgContent;
  const inner = preview.querySelector("svg");
  if (inner) {
    inner.style.maxWidth = "100%"; inner.style.maxHeight = "180px";
  }
}

// ---- save --------------------------------------------------
async function udSave() {
  const ch = document.getElementById("ud-char").value.trim();
  const status = document.getElementById("ud-save-status");
  if (ch.length !== 1) {
    status.textContent = "請輸入恰好一個字"; status.style.color = "var(--accent)";
    return;
  }
  let body = {char: ch};
  if (UD.activeTab === "hw") {
    const valid = UD.hwStrokes.filter(s => s.length >= 2);
    if (valid.length === 0) {
      status.textContent = "畫布上至少要有一筆畫"; status.style.color = "var(--accent)";
      return;
    }
    const canvas = document.getElementById("ud-canvas");
    body.format = "handwriting";
    body.handwriting = {
      strokes: valid,
      canvas_width: canvas.width,
      canvas_height: canvas.height,
    };
  } else if (UD.activeTab === "svg") {
    if (!UD.svgContent) {
      status.textContent = "請先選擇 SVG 檔"; status.style.color = "var(--accent)";
      return;
    }
    body.format = "svg";
    body.svg_content = UD.svgContent;
  } else {  // json
    const txt = document.getElementById("ud-json").value.trim();
    if (!txt) {
      status.textContent = "請貼入 JSON"; status.style.color = "var(--accent)";
      return;
    }
    let parsed;
    try { parsed = JSON.parse(txt); }
    catch (e) {
      status.textContent = "JSON 格式錯誤：" + e.message;
      status.style.color = "var(--accent)";
      return;
    }
    if (!Array.isArray(parsed.strokes)) {
      status.textContent = "JSON 缺 strokes 陣列";
      status.style.color = "var(--accent)";
      return;
    }
    body.format = "json";
    body.strokes = parsed.strokes;
  }
  status.textContent = "儲存中…"; status.style.color = "var(--muted)";
  try {
    const r = await fetch(`${API_BASE}/api/user-dict`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: r.statusText}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    const d = await r.json();
    const wasEdit = (UD.editingChar === d.char);
    status.textContent = wasEdit
      ? `✓ 已更新「${d.char}」(${d.stroke_count} 筆)`
      : `✓ 已存「${d.char}」(${d.stroke_count} 筆)`;
    status.style.color = "#260";
    udHwClear();
    document.getElementById("ud-svg-file").value = "";
    document.getElementById("ud-json").value = "";
    UD.svgContent = null;
    UD.editingChar = null;   // Phase 5ar: leave edit mode after save
    document.getElementById("ud-svg-preview").innerHTML = "(選擇 SVG 後預覽)";
    document.getElementById("ud-char").value = "";
    await udRefreshList();
  } catch (e) {
    status.textContent = "失敗：" + e.message;
    status.style.color = "var(--accent)";
  }
}

