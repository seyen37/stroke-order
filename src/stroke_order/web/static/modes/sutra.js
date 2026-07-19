// W4-R2 次批：顯式跨檔邊（原全域相依 → import/export 網）
import { API_BASE } from "./core.js?v=__V__";
import { swAttachPreviewClicks } from "./handwrite.js?v=__V__";
import { escapeHtml } from "./userdict.js?v=__V__";

// ============================================================
// 抄經模式 (Phase 5az) — A4 landscape trace SVG for plotter use
// ============================================================
const SUTRA = {
  presets: [],         // /api/sutra/presets payload (array of preset dicts)
  current_index: 0,    // 0-based body page index
  total_pages: 0,      // cover + body_pages + dedication
  layout: [],          // ordered list of {type:"cover|body|dedication", body_index?:N}
};

function sutraInit() {
  const $ = id => document.getElementById(id);
  if (!$("su-render")) return;
  $("su-render").onclick = () => sutraRender();
  $("su-prev").onclick = () => sutraStep(-1);
  $("su-next").onclick = () => sutraStep(+1);
  $("su-dl-current").onclick = () => sutraDownloadCurrent();
  $("su-dl-all").onclick = () => sutraDownloadAll();
  $("su-dl-pdf").onclick = () => sutraDownloadPdf();   // 5bi
  // Re-fetch presets + reset layout when relevant inputs change
  ["su-preset", "su-include-cover", "su-include-dedication",
   "su-text-mode",
   "su-paper-orientation", "su-text-direction"   // 5bj
  ].forEach(id => {
    $(id).addEventListener("change", () => {
      SUTRA.current_index = 0;
      sutraRebuildLayout();
      // 5bg: apply closing meta + sync labels when preset changes
      if (id === "su-preset") sutraApplyClosingMeta(sutraCurrentPreset());
    });
  });
  // 5bg: category + search wire — rebuild preset dropdown on change
  $("su-category").addEventListener("change", () => {
    sutraRebuildPresetDropdown();
    SUTRA.current_index = 0;
    sutraRebuildLayout();
  });
  $("su-search").addEventListener("input", () => {
    sutraRebuildPresetDropdown();
    SUTRA.current_index = 0;
    sutraRebuildLayout();
  });
  // 5bg: track if user manually edits the verse so we don't clobber it
  $("su-dedication-verse").addEventListener("input", (e) => {
    e.target.dataset.userEdited = "1";
  });
  // 5cc: warn the user that lishu / seal_script SVGs are skeleton-only
  // outputs and may have incomplete glyphs. The check runs on initial
  // load (in case a previous session left those styles selected) and
  // every time the dropdown changes.
  const updateStyleWarning = () => {
    const v = $("su-style").value;
    $("su-style-warning").style.display =
      (v === "lishu" || v === "seal_script") ? "" : "none";
  };
  $("su-style").addEventListener("change", updateStyleWarning);
  updateStyleWarning();
  // 5bb: management modal
  sutraMgmtInit();
  sutraLoadPresets();
}

// ============================================================
// 經文管理 (Phase 5bb) — modal CRUD for user/ presets
// ============================================================
const SUMGMT = {
  editingKey: null,    // null = add mode; string = edit existing key
};

function sutraMgmtInit() {
  const $ = id => document.getElementById(id);
  if (!$("su-mgmt-open")) return;
  $("su-mgmt-open").onclick  = sutraMgmtOpen;
  $("su-mgmt-close").onclick = sutraMgmtClose;
  $("su-mgmt-cancel").onclick = sutraMgmtResetForm;
  $("su-mgmt-save").onclick  = sutraMgmtSave;
  $("su-mgmt-file").addEventListener("change", sutraMgmtPickFile);
  document.getElementById("su-mgmt-overlay").addEventListener("click", e => {
    if (e.target.id === "su-mgmt-overlay") sutraMgmtClose();
  });
}

async function sutraMgmtOpen() {
  document.getElementById("su-mgmt-overlay").style.display = "flex";
  await sutraMgmtRefreshList();
  sutraMgmtResetForm();
}

function sutraMgmtClose() {
  document.getElementById("su-mgmt-overlay").style.display = "none";
}

async function sutraMgmtRefreshList() {
  const list = document.getElementById("su-mgmt-list");
  try {
    const r = await fetch(`${API_BASE}/api/sutra/presets?grouped=true`);
    if (!r.ok) throw new Error(r.statusText);
    const data = await r.json();
    const userPresets = [];
    for (const g of data.categories) {
      for (const p of g.presets) {
        if (!p.is_builtin) userPresets.push(p);
      }
    }
    if (userPresets.length === 0) {
      list.innerHTML = `<span style="color:var(--muted);font-size:12px;">
        （尚無自用經文，使用下方表單新增）</span>`;
      return;
    }
    list.innerHTML = userPresets.map(p => `
      <div style="display:flex;align-items:center;gap:8px;font-size:12px;
                  background:white;padding:6px 10px;border-radius:3px;
                  border:1px solid var(--border);">
        <span style="flex:1;">
          <b>${escapeHtml(p.title)}</b>
          <span style="color:var(--muted);">
            · ${escapeHtml(p.category_label)} · ${p.actual_chars} 字
          </span>
        </span>
        <button data-key="${escapeHtml(p.key)}" class="su-mgmt-edit-btn"
                style="font-size:11px;padding:2px 8px;background:#fafaf8;
                       border:1px solid var(--border);border-radius:3px;
                       cursor:pointer;">編輯</button>
        <button data-key="${escapeHtml(p.key)}" class="su-mgmt-del-btn"
                style="font-size:11px;padding:2px 8px;background:#fff;
                       border:1px solid var(--accent);color:var(--accent);
                       border-radius:3px;cursor:pointer;">刪除</button>
      </div>
    `).join("");
    list.querySelectorAll(".su-mgmt-edit-btn").forEach(b =>
      b.addEventListener("click", () => sutraMgmtEdit(b.dataset.key)));
    list.querySelectorAll(".su-mgmt-del-btn").forEach(b =>
      b.addEventListener("click", () => sutraMgmtDelete(b.dataset.key)));
  } catch (e) {
    list.innerHTML = `<span style="color:var(--accent);font-size:12px;">
      讀取失敗：${escapeHtml(e.message)}</span>`;
  }
}

function sutraMgmtResetForm() {
  SUMGMT.editingKey = null;
  document.getElementById("su-mgmt-form-title").textContent = "新增自用經文";
  document.getElementById("su-mgmt-title").value = "";
  document.getElementById("su-mgmt-source").value = "";
  document.getElementById("su-mgmt-tags").value = "";
  document.getElementById("su-mgmt-subtitle").value = "手抄本";
  document.getElementById("su-mgmt-category").value = "user_custom";
  document.getElementById("su-mgmt-repeat").checked = false;
  document.getElementById("su-mgmt-repeat-count").value = "108";
  document.getElementById("su-mgmt-text").value = "";
  document.getElementById("su-mgmt-file").value = "";
  document.getElementById("su-mgmt-status").textContent = "";
}

async function sutraMgmtPickFile() {
  const f = document.getElementById("su-mgmt-file").files[0];
  if (!f) return;
  const text = await f.text();
  document.getElementById("su-mgmt-text").value = text;
  // Auto-fill title from filename if empty
  const titleField = document.getElementById("su-mgmt-title");
  if (!titleField.value.trim()) {
    titleField.value = f.name.replace(/\.txt$/i, "");
  }
}

async function sutraMgmtEdit(key) {
  try {
    const r = await fetch(`${API_BASE}/api/sutra/user/${encodeURIComponent(key)}`);
    if (!r.ok) throw new Error(r.statusText);
    const d = await r.json();
    SUMGMT.editingKey = key;
    document.getElementById("su-mgmt-form-title").textContent = "編輯：" + d.title;
    document.getElementById("su-mgmt-title").value = d.title;
    document.getElementById("su-mgmt-source").value = d.source || "";
    document.getElementById("su-mgmt-tags").value = (d.tags || []).join(",");
    document.getElementById("su-mgmt-subtitle").value = d.subtitle || "手抄本";
    document.getElementById("su-mgmt-category").value = d.category || "user_custom";
    document.getElementById("su-mgmt-repeat").checked = !!d.is_mantra_repeat;
    document.getElementById("su-mgmt-repeat-count").value = d.repeat_count || 1;
    document.getElementById("su-mgmt-text").value = d.raw_text || "";
    document.getElementById("su-mgmt-status").textContent = "";
  } catch (e) {
    document.getElementById("su-mgmt-status").textContent = "讀取失敗：" + e.message;
    document.getElementById("su-mgmt-status").style.color = "var(--accent)";
  }
}

async function sutraMgmtDelete(key) {
  if (!confirm(`確定刪除自用經文「${key}」？此動作無法復原。`)) return;
  try {
    const r = await fetch(`${API_BASE}/api/sutra/user/${encodeURIComponent(key)}`,
                          {method: "DELETE"});
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    await sutraMgmtRefreshList();
    if (SUMGMT.editingKey === key) sutraMgmtResetForm();
    sutraLoadPresets();   // refresh main panel dropdown
  } catch (e) {
    document.getElementById("su-mgmt-status").textContent = "刪除失敗：" + e.message;
    document.getElementById("su-mgmt-status").style.color = "var(--accent)";
  }
}

async function sutraMgmtSave() {
  const $ = id => document.getElementById(id).value;
  const status = document.getElementById("su-mgmt-status");
  const text = $("su-mgmt-text").trim();
  if (!text) {
    status.textContent = "內文不能為空";
    status.style.color = "var(--accent)";
    return;
  }
  const tags = $("su-mgmt-tags").split(",")
    .map(t => t.trim()).filter(Boolean);
  const meta = {
    title: $("su-mgmt-title") || "未命名",
    subtitle: $("su-mgmt-subtitle") || "手抄本",
    category: $("su-mgmt-category"),
    source: $("su-mgmt-source"),
    is_mantra_repeat: document.getElementById("su-mgmt-repeat").checked,
    repeat_count: parseInt($("su-mgmt-repeat-count")) || 1,
    tags,
  };
  status.textContent = "儲存中…";
  status.style.color = "var(--muted)";
  try {
    if (SUMGMT.editingKey) {
      // Update existing — but content changes need delete + re-upload since
      // we don't have a "PUT raw text" endpoint. For metadata-only changes
      // PUT is cheaper.
      const original = await (await fetch(
        `${API_BASE}/api/sutra/user/${encodeURIComponent(SUMGMT.editingKey)}`)).json();
      if (original.raw_text === text) {
        // Metadata-only update
        const r = await fetch(
          `${API_BASE}/api/sutra/user/${encodeURIComponent(SUMGMT.editingKey)}`,
          {method: "PUT", headers: {"Content-Type": "application/json"},
           body: JSON.stringify(meta)});
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
      } else {
        // Content changed — delete + re-upload
        await fetch(`${API_BASE}/api/sutra/user/${encodeURIComponent(SUMGMT.editingKey)}`,
                    {method: "DELETE"});
        const r = await fetch(`${API_BASE}/api/sutra/upload`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({...meta, text, desired_key: SUMGMT.editingKey}),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
      }
    } else {
      // Add new
      const r = await fetch(`${API_BASE}/api/sutra/upload`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({...meta, text}),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({detail: r.statusText}));
        throw new Error(err.detail || `HTTP ${r.status}`);
      }
    }
    status.textContent = "✓ 已儲存";
    status.style.color = "#080";
    await sutraMgmtRefreshList();
    sutraMgmtResetForm();
    sutraLoadPresets();   // refresh dropdown in main panel
  } catch (e) {
    status.textContent = "儲存失敗：" + e.message;
    status.style.color = "var(--accent)";
  }
}

async function sutraLoadPresets() {
  try {
    const r = await fetch(`${API_BASE}/api/sutra/presets?grouped=true`);
    if (!r.ok) throw new Error(r.statusText);
    const data = await r.json();
    SUTRA.categories = data.categories;        // 5bg: cache full grouped data
    // Flatten for quick lookup
    SUTRA.presets = [];
    for (const g of data.categories) {
      for (const p of g.presets) SUTRA.presets.push(p);
    }
    document.getElementById("su-dir-hint").textContent = data.sutra_dir;
    document.getElementById("su-mgmt-path").textContent =
      data.sutra_dir + "/user/";

    // 5bg: populate category dropdown — non-empty cats + "全部" first
    const catSel = document.getElementById("su-category");
    const prevCat = catSel.value || "__all__";
    const opts = ['<option value="__all__">全部分類</option>'];
    for (const g of data.categories) {
      if (g.presets.length === 0) continue;
      opts.push(`<option value="${g.key}">${escapeHtml(g.label)} (${g.presets.length})</option>`);
    }
    catSel.innerHTML = opts.join("");
    if ([...catSel.options].some(o => o.value === prevCat)) catSel.value = prevCat;

    sutraRebuildPresetDropdown();

    // Banner: only when NO builtin text is loaded at all (a truly empty
    // sutra install). 5bp ships packaged texts, so a healthy deployment
    // always has most builtins ready; individually-missing presets
    // (e.g. copyright-excluded macarthur_prayer) are already marked
    // ✗ in the preset dropdown and must not trigger the banner.
    const noBuiltinReady = !SUTRA.presets.some(p => p.is_builtin && p.ready);
    document.getElementById("su-not-loaded-banner").style.display =
      noBuiltinReady ? "block" : "none";
    sutraRebuildLayout();
  } catch (e) {
    document.getElementById("su-status").textContent = "載入經文清單失敗：" + e.message;
  }
}

// 5bg: rebuild preset dropdown based on current category + search filter
function sutraRebuildPresetDropdown() {
  const catSel    = document.getElementById("su-category");
  const presetSel = document.getElementById("su-preset");
  const search    = (document.getElementById("su-search").value || "")
                    .trim().toLowerCase();
  const cat = catSel.value || "__all__";
  const prev = presetSel.value;

  const matches = (p) => {
    // 5dr：目錄不列「內建但正文未打包」的 preset。唯一案例為著作權排除的
    // macarthur_prayer——線上部署（repo 不含正文）→ ready=false → 隱藏；
    // 使用者在本機 ~/.stroke-order/sutras/builtin/ 放入正文後 → ready=true
    // → 自動出現。使用者自訂 preset 只在檔案存在時才列出，天生 ready，
    // 不受此條影響。
    if (p.is_builtin && !p.ready) return false;
    if (cat !== "__all__" && p.category !== cat) return false;
    if (!search) return true;
    const hay = [
      p.title, p.author, p.editor, p.source, p.key,
      ...(p.tags || []),
    ].join(" ").toLowerCase();
    return hay.includes(search);
  };

  const filtered = SUTRA.presets.filter(matches);
  if (filtered.length === 0) {
    presetSel.innerHTML = `<option value="">（無符合條件的經典）</option>`;
    sutraApplyClosingMeta(null);
    return;
  }

  // Build options grouped by category for clarity
  const byCat = new Map();
  for (const p of filtered) {
    if (!byCat.has(p.category)) byCat.set(p.category, []);
    byCat.get(p.category).push(p);
  }
  const html = [];
  for (const [k, items] of byCat) {
    const label = items[0].category_label;
    const inner = items.map(p => {
      const marker = p.ready ? "✓" : "ⓘ";
      const tail = p.ready ? `(${p.actual_chars} 字 / ${p.body_pages} 頁)`
                           : "（未載入）";
      return `<option value="${escapeHtml(p.key)}">${marker} ${escapeHtml(p.title)} ${tail}</option>`;
    }).join("");
    html.push(`<optgroup label="${escapeHtml(label)}">${inner}</optgroup>`);
  }
  presetSel.innerHTML = html.join("");
  if ([...presetSel.options].some(o => o.value === prev)) {
    presetSel.value = prev;
  }
  // Apply closing metadata for the (possibly new) selected preset
  const cur = sutraCurrentPreset();
  sutraApplyClosingMeta(cur);
}

// 5bg: when preset changes, sync closing-page UI labels + default verse
function sutraApplyClosingMeta(preset) {
  const verse = document.getElementById("su-dedication-verse");
  const closingLabel = document.getElementById("su-closing-label");
  const verseLabel = document.getElementById("su-verse-label");
  const blank1 = document.getElementById("su-blank1-label");
  const blank2 = document.getElementById("su-blank2-label");

  if (!preset || !preset.closing_effective) {
    closingLabel.textContent = "結語頁";
    verseLabel.textContent = "結語主文";
    blank1.textContent = "填空 1";
    blank2.textContent = "填空 2";
    if (!verse.dataset.userEdited) verse.value = "";
    return;
  }
  const c = preset.closing_effective;
  closingLabel.textContent = c.title || "結語頁";
  verseLabel.textContent = (c.title || "結語") + "主文";
  blank1.textContent = c.blank1_label || "填空 1";
  blank2.textContent = c.blank2_label || "填空 2";
  // Auto-fill verse only if user hasn't manually edited it
  if (!verse.dataset.userEdited) verse.value = c.verse || "";
}

function sutraCurrentPreset() {
  const key = document.getElementById("su-preset").value;
  return SUTRA.presets.find(p => p.key === key);
}

async function sutraRebuildLayout() {
  const p = sutraCurrentPreset();
  const includeCover = document.getElementById("su-include-cover").checked;
  const includeDedication = document.getElementById("su-include-dedication").checked;
  const textMode = document.getElementById("su-text-mode").value;
  const paperOrient = document.getElementById("su-paper-orientation").value;
  const layout = [];
  if (!p) {
    SUTRA.layout = []; SUTRA.total_pages = 0;
    sutraUpdatePageLabel(); return;
  }
  // 5bh / 5bj: capacity depends on text_mode + orientation (geom).
  let bodyPages = p.body_pages;
  if (p.ready) {
    try {
      const params = new URLSearchParams({
        preset: p.key, text_mode: textMode,
        paper_orientation: paperOrient,
        include_cover: includeCover, include_dedication: includeDedication,
      });
      const r = await fetch(`${API_BASE}/api/sutra/capacity?${params}`);
      if (r.ok) {
        const d = await r.json();
        bodyPages = d.body_pages || 0;
      }
    } catch (_) { /* fall back to cached value */ }
  }
  if (includeCover) layout.push({type: "cover"});
  // 5dq：元素週期表只用「週期表形狀描紅頁」——它的意義在結構位置
  // （族/週期 + 鑭系/錒系），平鋪格子描紅反而破壞可讀性。其餘表格類
  // preset 維持「平鋪描紅頁 + 表格頁」兩段。
  const tableOnly = (p.key === "periodic_table" && p.ready);
  if (!tableOnly) {
    for (let i = 0; i < bodyPages; i++) {
      layout.push({type: "body", body_index: i});
    }
  }
  // 5bo: presets with a table layout get that page after the body
  // pages (A4 landscape fixed geometry).
  if (["periodic_table", "multiplication_table", "solar_terms",
       "kangxi_radicals", "cangjie_roots", "zhuyin_symbols"]
      .includes(p.key) && p.ready) {
    layout.push({type: "table"});
  }
  if (includeDedication) layout.push({type: "dedication"});
  SUTRA.layout = layout;
  SUTRA.total_pages = layout.length;
  if (SUTRA.current_index >= SUTRA.total_pages) {
    SUTRA.current_index = Math.max(0, SUTRA.total_pages - 1);
  }
  // Preset info hint
  const info = document.getElementById("su-preset-info");
  if (p.ready) {
    info.innerHTML = `${p.actual_chars} 字 ／ ${bodyPages} 描紅頁 ／ 共 <b>${SUTRA.total_pages}</b> 頁`;
    info.style.color = "var(--muted)";
  } else {
    info.innerHTML = `<b>未載入</b> — 請放 <code>${p.filename}</code> 至經文資料夾`;
    info.style.color = "var(--accent)";
  }
  sutraUpdatePageLabel();
}

function sutraUpdatePageLabel() {
  const lbl = document.getElementById("su-page-label");
  if (SUTRA.total_pages === 0) { lbl.textContent = "－"; return; }
  const idx = SUTRA.current_index;
  const slot = SUTRA.layout[idx];
  let typeLabel;
  if (slot.type === "cover") typeLabel = "封面";
  else if (slot.type === "dedication") typeLabel = "迴向頁";
  else if (slot.type === "table") typeLabel = "週期表";
  else typeLabel = `描紅 ${slot.body_index + 1}`;
  lbl.textContent = `${idx + 1} / ${SUTRA.total_pages} (${typeLabel})`;
}

function sutraStep(delta) {
  if (SUTRA.total_pages === 0) return;
  SUTRA.current_index = Math.max(0,
    Math.min(SUTRA.total_pages - 1, SUTRA.current_index + delta));
  sutraUpdatePageLabel();
  sutraRender();
}

function sutraBuildBody(overrides) {
  const $ = id => document.getElementById(id);
  const slot = SUTRA.layout[SUTRA.current_index] || {type: "body", body_index: 0};
  const body = {
    preset: $("su-preset").value,
    page_index: slot.body_index || 0,
    page_type: slot.type,
    style: $("su-style").value,
    source: $("su-source").value,
    scribe: $("su-scribe").value,
    date_str: $("su-date").value,
    signature: $("su-signature").value,
    dedicator: $("su-dedicator").value,
    target: $("su-target").value,
    dedication_verse: $("su-dedication-verse").value,
    show_grid: $("su-show-grid").checked,
    show_helper_lines: $("su-show-helper").checked,
    include_cover: $("su-include-cover").checked,
    include_dedication: $("su-include-dedication").checked,
    // 5bh: text processing mode
    text_mode: $("su-text-mode").value,
    // 5bj: page geometry
    paper_orientation: $("su-paper-orientation").value,
    text_direction: $("su-text-direction").value,
  };
  // 5bz: callers can override individual fields. The browser preview
  // passes {show_original_glyph: true} to lay a faded reference glyph
  // beneath the skeleton tracks; SVG download buttons leave it unset
  // so the plotter receives a pure-skeleton file.
  return overrides ? Object.assign(body, overrides) : body;
}

async function sutraRender() {
  if (SUTRA.total_pages === 0) {
    document.getElementById("su-status").textContent =
      "尚無可預覽頁——請先放入經文 .txt 並重新整理頁面";
    return;
  }
  const status = document.getElementById("su-status");
  const preview = document.getElementById("su-preview");
  status.textContent = "產生中…";
  try {
    const r = await fetch(`${API_BASE}/api/sutra`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      // 5bz: preview shows the reference letterform behind the skeleton
      // (隸/篆 only). Download buttons keep the default (skeleton-only).
      // 5dt: emit_cellmap → clickable per-cell overlay for 逐字手寫.
      body: JSON.stringify(sutraBuildBody(
        {show_original_glyph: true, emit_cellmap: true})),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: r.statusText}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    preview.innerHTML = await r.text();
    const inner = preview.querySelector("svg");
    if (inner) {
      // A4 landscape SVG; 移除 mm width/height 讓它撐滿容器
      inner.removeAttribute("width");
      inner.removeAttribute("height");
      inner.style.width = "100%";
      inner.style.maxHeight = "70vh";
      inner.style.height = "auto";
      inner.style.display = "block";
      inner.style.background = "white";
    }
    // 5dt: wire each 描紅 cell to open the 逐字手寫 popup.
    swAttachPreviewClicks(preview);
    status.textContent = "✓ 完成（點格子可逐字手寫）";
    status.style.color = "#080";
  } catch (e) {
    status.textContent = "失敗：" + e.message;
    status.style.color = "var(--accent)";
  }
}

// 5dz: pull the server-provided friendly download name from Content-
// Disposition ({經典}_{字型風格}_{手寫|範例}); RFC 5987 filename* first,
// fall back to the caller's name if the header is absent/generic.
function filenameFromCD(cd, fallback) {
  if (cd) {
    const m = /filename\*=UTF-8''([^;]+)/i.exec(cd);
    if (m) { try { return decodeURIComponent(m[1]); } catch (_) { /* fall through */ } }
    const m2 = /filename="([^"]+)"/i.exec(cd);
    if (m2 && m2[1] && !/^char\.(svg|pdf|zip)$/i.test(m2[1])) return m2[1];
  }
  return fallback;
}

async function sutraDownloadCurrent() {
  if (SUTRA.total_pages === 0) return;
  const status = document.getElementById("su-status");
  status.textContent = "下載中…";
  try {
    const r = await fetch(`${API_BASE}/api/sutra`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(sutraBuildBody()),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const cd = r.headers.get("content-disposition");
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const slot = SUTRA.layout[SUTRA.current_index];
    const fallback = slot.type === "body"
      ? `sutra_${SUTRA.layout[SUTRA.current_index].body_index + 1}.svg`
      : `sutra_${slot.type}.svg`;
    const fname = filenameFromCD(cd, fallback);
    a.href = url;
    a.download = fname;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    status.textContent = `✓ 已下載 ${fname}`;
    status.style.color = "#080";
  } catch (e) {
    status.textContent = "下載失敗：" + e.message;
    status.style.color = "var(--accent)";
  }
}

async function sutraDownloadAll() {
  if (SUTRA.total_pages === 0) return;
  const status = document.getElementById("su-status");
  status.textContent = `下載 ${SUTRA.total_pages} 頁…`;
  // Fetch each page sequentially as a blob, store, then bundle as ZIP via JSZip.
  // 為避免再增加新依賴，這版本逐頁觸發瀏覽器下載；之後可改為 ZIP。
  const orig_index = SUTRA.current_index;
  try {
    for (let i = 0; i < SUTRA.total_pages; i++) {
      SUTRA.current_index = i;
      const slot = SUTRA.layout[i];
      const r = await fetch(`${API_BASE}/api/sutra`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(sutraBuildBody()),
      });
      if (!r.ok) throw new Error(`page ${i + 1}: HTTP ${r.status}`);
      const cd = r.headers.get("content-disposition");
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      // 5dz: server names each page {經典}_{風格}_{手寫|範例}; append the
      // page number so multiple pages don't collide on the same name.
      const serverName = filenameFromCD(cd, null);
      const pageNo = String(i + 1).padStart(2, "0");
      const fname = serverName
        ? serverName.replace(/\.svg$/i, "") + `_${pageNo}.svg`
        : (slot.type === "body"
            ? `sutra_${pageNo}.svg`
            : (slot.type === "cover" ? "sutra_00_cover.svg"
                                     : "sutra_99_dedication.svg"));
      a.href = url;
      a.download = fname;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      // Small delay so browser doesn't drop overlapping downloads
      await new Promise(res => setTimeout(res, 100));
    }
    status.textContent = `✓ 已下載 ${SUTRA.total_pages} 頁`;
    status.style.color = "#080";
  } catch (e) {
    status.textContent = "下載失敗：" + e.message;
    status.style.color = "var(--accent)";
  } finally {
    SUTRA.current_index = orig_index;
    sutraUpdatePageLabel();
  }
}

// 5bi: PDF download — single combined file (cover + body + dedication)
async function sutraDownloadPdf() {
  if (SUTRA.total_pages === 0) return;
  const status = document.getElementById("su-status");
  const $ = id => document.getElementById(id);
  status.textContent = "產生 PDF 中（可能需要 10–30 秒）…";
  status.style.color = "var(--muted)";
  const params = new URLSearchParams({
    preset: $("su-preset").value,
    style: $("su-style").value,
    source: $("su-source").value,
    scribe: $("su-scribe").value,
    date_str: $("su-date").value,
    signature: $("su-signature").value,
    dedicator: $("su-dedicator").value,
    target: $("su-target").value,
    dedication_verse: $("su-dedication-verse").value,
    show_grid: $("su-show-grid").checked,
    show_helper_lines: $("su-show-helper").checked,
    text_mode: $("su-text-mode").value,
    paper_orientation: $("su-paper-orientation").value,    // 5bj
    text_direction: $("su-text-direction").value,           // 5bj
    include_cover: $("su-include-cover").checked,
    include_dedication: $("su-include-dedication").checked,
  });
  try {
    const r = await fetch(`${API_BASE}/api/sutra/pdf?${params}`);
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: r.statusText}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    const cd = r.headers.get("content-disposition");
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filenameFromCD(cd, `sutra_${$("su-preset").value}.pdf`);
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    status.textContent = `✓ 已下載 PDF (${(blob.size / 1024).toFixed(0)} KB)`;
    status.style.color = "#080";
  } catch (e) {
    status.textContent = "PDF 下載失敗：" + e.message;
    status.style.color = "var(--accent)";
  }
}

// W4-R2：跨檔邊匯出（消費端見 import 網）
export { sutraInit, sutraRender };
