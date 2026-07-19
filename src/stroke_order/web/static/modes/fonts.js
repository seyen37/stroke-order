// W4-R2 次批：顯式跨檔邊（原全域相依 → import/export 網）
import { API_BASE } from "./core.js?v=__V__";
import { escapeHtml, udOpen } from "./userdict.js?v=__V__";

// ============================================================
// Tier 1 (Phase 5ak): text-fallback warning banner
// ============================================================
// Scans an inline-rendered SVG inside `previewEl`. If any character had
// to fall back to <text> (no stroke data anywhere — not in g0v / MMH /
// punctuation / user dict), show a yellow warning telling the user
// G-code will skip those cells.
function _showTextFallbackWarning(previewEl, statusEl) {
  const fallbackTexts = previewEl.querySelectorAll(
    'g.text-fallback text, g[class*="text-fallback"] text'
  );
  if (!fallbackTexts.length) return;
  const chars = new Set();
  fallbackTexts.forEach(t => chars.add(t.textContent));
  const list = [...chars].join("");
  const banner = document.createElement("div");
  banner.style.cssText =
    "background:#fff8e0;border-left:3px solid #d8a000;color:#704000;" +
    "padding:6px 10px;font-size:12px;border-radius:3px;margin:6px 0;";
  banner.innerHTML =
    `⚠ 這些字無筆跡資料：<b style="font-family:'Noto Sans TC',sans-serif;">${escapeHtml(list)}</b>` +
    `（共 ${chars.size} 字）。預覽以系統字型呈現，但 G-code / 機器人輸出會跳過。` +
    ` <a href="#" id="ud-jump" style="color:#704000;text-decoration:underline;">` +
    `→ 開啟罕用字管理補上筆跡</a>`;
  // Insert above the preview content
  previewEl.parentNode.insertBefore(banner, previewEl);
  banner.querySelector("#ud-jump").onclick = (e) => {
    e.preventDefault();
    udOpen();
  };
}

// Helper: clear any prior fallback banner under a preview (called BEFORE
// inserting a new one so we don't stack them on re-renders).
function _clearTextFallbackWarning(previewEl) {
  const prev = previewEl.parentNode.querySelector(
    "div[data-fallback-banner]"
  );
  if (prev) prev.remove();
  // Old format from older versions of this function
  Array.from(previewEl.parentNode.children).forEach(el => {
    if (el.style && el.style.borderLeft === "3px solid #d8a000") {
      // Defensive cleanup if style was set via CSS string
      // (matches the banner inserted above)
      if (el.tagName === "DIV" && el.textContent.includes("無筆跡資料"))
        el.remove();
    }
  });
}

// Wrap the three multi-mode render functions to also show the warning
// after a successful render. We monkey-patch by saving the originals
// and overriding. (The preview elements are: nb-preview, lt-preview,
// ms-preview.)
(function _wireTextFallbackWarnings() {
  const wrap = (origName, previewId, statusId) => {
    const orig = window[origName];
    if (typeof orig !== "function") return;
    window[origName] = async function (...args) {
      // Clear any previous banner for this preview before running.
      const previewEl = document.getElementById(previewId);
      if (previewEl) _clearTextFallbackWarning(previewEl);
      const result = await orig.apply(this, args);
      // After render completes, scan for text-fallback and show banner.
      if (previewEl) {
        const statusEl = document.getElementById(statusId);
        _showTextFallbackWarning(previewEl, statusEl);
      }
      return result;
    };
  };
  wrap("renderNotebook",   "nb-preview", "nb-status");
  wrap("renderLetter",     "lt-preview", "lt-status");
  wrap("renderManuscript", "ms-preview", "ms-status");
})();

// ============================================================
// CNS 全字庫 UI hooks (Phase 5al-UI)
// ============================================================

async function cnsInit() {
  const banner = document.getElementById("cns-status-row");
  if (!banner) return;
  try {
    const r = await fetch(`${API_BASE}/api/cns-status`);
    if (!r.ok) throw new Error(r.statusText);
    const d = await r.json();
    if (d.fonts_ready) {
      const kaiPlanes  = (d.kai_planes  || []).map(p => `Plane ${p}`).join("、");
      const sungPlanes = (d.sung_planes || []).map(p => `Plane ${p}`).join("、");
      const parts = [];
      if (kaiPlanes)  parts.push(`楷體：${kaiPlanes}`);
      if (sungPlanes) parts.push(`宋體：${sungPlanes}（風格切換已啟用）`);
      const planeInfo = parts.join(" / ");
      const info = FONT_AUTH_INFO.cns;
      const authed = fontAuthGet("cns");
      if (authed) {
        // 綠燈 + attribution + 取消授權
        banner.style.background = "#e0f5e0";
        banner.style.color = "#260";
        banner.innerHTML =
          fontAuthButtonHtml("cns")
          + `✓ <b>CNS 全字庫</b> 已載入（${planeInfo}）`
          + (d.properties_ready ? "・部件 metadata 可查" : "")
          + ` — <a href="${info.licenseUrl}" target="_blank"`
          + `   style="color:#260;text-decoration:underline;">${escapeHtml(info.attribution)}</a>`;
        banner.title = `授權：${info.license}`;
      } else {
        // 紅燈 + 「未授權」+ 授權按鈕
        banner.style.background = "#fde0e0";
        banner.style.color = "#700";
        banner.innerHTML =
          fontAuthButtonHtml("cns")
          + `✕ <b>CNS 全字庫</b> 尚未授權 — 字型來源就緒（${planeInfo}），需您授權代為下載與使用後才會啟用（${info.license}）。`
          + ` <a href="${info.licenseUrl}" target="_blank"`
          + `   style="color:#700;text-decoration:underline;">${escapeHtml(info.attribution)}</a>`;
      }
      bindFontAuthButton(banner, "cns", cnsInit);
      fontStatusMark("cns", authed);
    } else {
      banner.style.background = "#fff8e0";
      banner.style.color = "#704000";
      banner.innerHTML =
        `ⓘ <b>CNS 全字庫</b> 未載入 — 罕用字 fallback 不可用。`
        + ` <a href="https://www.cns11643.gov.tw/downloadList.jsp?ID=2" target="_blank"`
        + `   style="color:#704000;">下載全字庫</a>`
        + ` 解壓至 <code>${escapeHtml(d.font_dir)}</code> 即啟用。`;
      fontStatusMark("cns", false);
    }
  } catch (e) {
    banner.textContent = `CNS 字型：狀態檢查失敗 (${e.message})`;
    fontStatusMark("cns", false);
  }
}

// ============================================================
// 崇羲篆體 UI hook (Phase 5at) — banner with mandatory CC BY-ND
// attribution shown whenever the seal-script font is loaded.
// ============================================================
async function sealInit() {
  const banner = document.getElementById("seal-status-row");
  if (!banner) return;
  try {
    const r = await fetch(`${API_BASE}/api/seal-status`);
    if (!r.ok) throw new Error(r.statusText);
    const d = await r.json();
    if (d.ready) {
      const authed = fontAuthGet("seal");
      if (authed) {
        // 綠燈 + attribution + 取消授權
        banner.style.background = "#e0e8f5";
        banner.style.color = "#234";
        banner.innerHTML =
          fontAuthButtonHtml("seal")
          + `✓ <b>篆書字型</b> (${d.glyph_count} 字) — `
          + `<a href="${d.license_url}" target="_blank" `
          + `style="color:#234;text-decoration:underline;">`
          + `${escapeHtml(d.attribution)}</a>`;
        banner.title = `授權：${d.license}（必須標示原作者）`;
      } else {
        // 紅燈 + 授權按鈕
        banner.style.background = "#fde0e0";
        banner.style.color = "#700";
        banner.innerHTML =
          fontAuthButtonHtml("seal")
          + `✕ <b>篆書字型</b> 尚未授權 (${d.glyph_count} 字) — 字型來源就緒，需您授權代為下載與使用後才會啟用（${d.license}）。`
          + ` <a href="${d.license_url}" target="_blank" `
          + `style="color:#700;text-decoration:underline;">`
          + `${escapeHtml(d.attribution)}</a>`;
      }
      bindFontAuthButton(banner, "seal", sealInit);
      fontStatusMark("seal", authed);
    } else {
      banner.style.background = "#fff8e0";
      banner.style.color = "#704000";
      banner.innerHTML =
        `ⓘ <b>篆書字型</b> 未載入 — style="seal_script" 不可用。`
        + ` <a href="https://xiaoxue.iis.sinica.edu.tw/chongxi/download.htm" `
        + `   target="_blank" style="color:#704000;">下載崇羲篆體</a>`
        + ` 放到 <code>${escapeHtml(d.font_file)}</code>。`;
      fontStatusMark("seal", false);
    }
  } catch (e) {
    banner.textContent = `篆書字型：狀態檢查失敗 (${e.message})`;
    fontStatusMark("seal", false);
  }
}

// ============================================================
// 教育部隸書 UI hook (Phase 5au) — banner with mandatory CC BY-ND
// attribution shown whenever the lishu font is loaded.
// ============================================================
async function lishuInit() {
  const banner = document.getElementById("lishu-status-row");
  if (!banner) return;
  try {
    const r = await fetch(`${API_BASE}/api/lishu-status`);
    if (!r.ok) throw new Error(r.statusText);
    const d = await r.json();
    if (d.ready) {
      const authed = fontAuthGet("lishu");
      if (authed) {
        banner.style.background = "#f0e8d8";
        banner.style.color = "#532";
        banner.innerHTML =
          fontAuthButtonHtml("lishu")
          + `✓ <b>隸書字型</b> (${d.glyph_count} 字) — `
          + `<a href="${d.license_url}" target="_blank" `
          + `style="color:#532;text-decoration:underline;">`
          + `${escapeHtml(d.attribution)}</a>`;
        banner.title = `授權：${d.license}（必須標示「中華民國教育部」）`;
      } else {
        banner.style.background = "#fde0e0";
        banner.style.color = "#700";
        banner.innerHTML =
          fontAuthButtonHtml("lishu")
          + `✕ <b>隸書字型</b> 尚未授權 (${d.glyph_count} 字) — 字型來源就緒，需您授權代為下載與使用後才會啟用（${d.license}）。`
          + ` <a href="${d.license_url}" target="_blank" `
          + `style="color:#700;text-decoration:underline;">`
          + `${escapeHtml(d.attribution)}</a>`;
      }
      bindFontAuthButton(banner, "lishu", lishuInit);
      fontStatusMark("lishu", authed);
    } else {
      banner.style.background = "#fff8e0";
      banner.style.color = "#704000";
      banner.innerHTML =
        `ⓘ <b>隸書字型</b> 未載入 — style="lishu" 用 5aj 假隸書濾鏡。`
        + ` <a href="https://language.moe.gov.tw/result.aspx?classify_sn=23" `
        + `   target="_blank" style="color:#704000;">下載教育部隸書</a>`
        + ` 放到 <code>${escapeHtml(d.font_file)}</code>。`;
      fontStatusMark("lishu", false);
    }
  } catch (e) {
    banner.textContent = `隸書字型：狀態檢查失敗 (${e.message})`;
    fontStatusMark("lishu", false);
  }
}

// ============================================================
// 教育部標準宋體 UI hook (Phase 5av) — banner + mandatory CC BY-ND
// attribution. When ready, takes priority over CNS Sung as the
// `style="mingti"` swap target.
// ============================================================
async function songInit() {
  const banner = document.getElementById("song-status-row");
  if (!banner) return;
  try {
    const r = await fetch(`${API_BASE}/api/song-status`);
    if (!r.ok) throw new Error(r.statusText);
    const d = await r.json();
    if (d.ready) {
      const authed = fontAuthGet("song");
      if (authed) {
        banner.style.background = "#e8e0f0";
        banner.style.color = "#332";
        banner.innerHTML =
          fontAuthButtonHtml("song")
          + `✓ <b>宋體字型</b> (${d.glyph_count} 字) — `
          + `<a href="${d.license_url}" target="_blank" `
          + `style="color:#332;text-decoration:underline;">`
          + `${escapeHtml(d.attribution)}</a>`;
        banner.title = `授權：${d.license}（必須標示「中華民國教育部」）`;
      } else {
        banner.style.background = "#fde0e0";
        banner.style.color = "#700";
        banner.innerHTML =
          fontAuthButtonHtml("song")
          + `✕ <b>宋體字型</b> 尚未授權 (${d.glyph_count} 字) — 字型來源就緒，需您授權代為下載與使用後才會啟用（${d.license}）。`
          + ` <a href="${d.license_url}" target="_blank" `
          + `style="color:#700;text-decoration:underline;">`
          + `${escapeHtml(d.attribution)}</a>`;
      }
      bindFontAuthButton(banner, "song", songInit);
      fontStatusMark("song", authed);
    } else {
      banner.style.background = "#fff8e0";
      banner.style.color = "#704000";
      banner.innerHTML =
        `ⓘ <b>宋體字型</b> 未載入 — style="mingti" 用 CNS Sung (5am) 或 5aj 假宋體濾鏡。`
        + ` <a href="https://language.moe.gov.tw/result.aspx?classify_sn=23" `
        + `   target="_blank" style="color:#704000;">下載教育部標準宋體</a>`
        + ` 放到 <code>${escapeHtml(d.font_file)}</code>。`;
      fontStatusMark("song", false);
    }
  } catch (e) {
    banner.textContent = `宋體字型：狀態檢查失敗 (${e.message})`;
    fontStatusMark("song", false);
  }
}

// ============================================================
// 教育部標準楷書 UI hook (Phase 5aw) — banner + mandatory CC BY-ND
// attribution. When ready, AutoSource silently uses it as a Tier-3
// outline fallback for chars g0v/MMH don't carry.
// ============================================================
async function kaishuInit() {
  const banner = document.getElementById("kaishu-status-row");
  if (!banner) return;
  try {
    const r = await fetch(`${API_BASE}/api/kaishu-status`);
    if (!r.ok) throw new Error(r.statusText);
    const d = await r.json();
    if (d.ready) {
      const authed = fontAuthGet("kaishu");
      if (authed) {
        banner.style.background = "#e0f0e8";
        banner.style.color = "#143";
        banner.innerHTML =
          fontAuthButtonHtml("kaishu")
          + `✓ <b>楷書字型</b> (${d.glyph_count} 字 fallback) — `
          + `<a href="${d.license_url}" target="_blank" `
          + `style="color:#143;text-decoration:underline;">`
          + `${escapeHtml(d.attribution)}</a>`;
        banner.title = `授權：${d.license}（必須標示「中華民國教育部」）。`
          + `預設用 g0v/MMH 筆順資料；MoE Kaishu 在它們缺字時補上 outline。`;
      } else {
        banner.style.background = "#fde0e0";
        banner.style.color = "#700";
        banner.innerHTML =
          fontAuthButtonHtml("kaishu")
          + `✕ <b>楷書字型</b> 尚未授權 (${d.glyph_count} 字 fallback) — 字型來源就緒，需您授權代為下載與使用後才會啟用（${d.license}）。`
          + ` <a href="${d.license_url}" target="_blank" `
          + `style="color:#700;text-decoration:underline;">`
          + `${escapeHtml(d.attribution)}</a>`;
      }
      bindFontAuthButton(banner, "kaishu", kaishuInit);
      fontStatusMark("kaishu", authed);
    } else {
      banner.style.background = "#fff8e0";
      banner.style.color = "#704000";
      banner.innerHTML =
        `ⓘ <b>楷書字型</b> 未載入 — 罕用字 fallback 仍用 CNS Kai (5al)。`
        + ` <a href="https://language.moe.gov.tw/result.aspx?classify_sn=23" `
        + `   target="_blank" style="color:#704000;">下載教育部標準楷書</a>`
        + ` 放到 <code>${escapeHtml(d.font_file)}</code>。`;
      fontStatusMark("kaishu", false);
    }
  } catch (e) {
    banner.textContent = `楷書字型：狀態檢查失敗 (${e.message})`;
    fontStatusMark("kaishu", false);
  }
}

// ============================================================
// 字型授權（主動同意 gate）— Phase 5ba+
//
// 預設**未授權**：即使後端字型已載入，前端 UI 顯示紅燈 + 「授權」按鈕。
// 使用者讀過 license 說明、點「授權」確認同意後，才切到綠燈可用狀態。
// 授權狀態存 localStorage（per-browser），重整網頁後保留。
// 點「取消授權」直接生效（無二次確認）。
//
// 設計動機：CC BY-ND 3.0 TW 等授權要求 attribution 顯示 + 使用者明確同意。
// 自動載入綠燈無法達成「明確同意」這層；要求主動點按更貼合授權精神。
// ============================================================

const FONT_AUTH_KEY_PREFIX = "stroke-order:font-authorized:";

const FONT_AUTH_INFO = {
  cns: {
    label: "CNS 全字庫",
    license: "政府資料開放授權條款 1.0",
    licenseUrl: "https://www.cns11643.gov.tw/",
    attribution: "中華民國數位發展部 · CNS 11643 全字庫",
  },
  seal: {
    label: "崇羲篆體",
    license: "CC BY-ND 3.0 TW",
    licenseUrl: "https://xiaoxue.iis.sinica.edu.tw/chongxi/copyright.htm",
    attribution: "崇羲篆體 by 季旭昇 / 中央研究院資訊科學研究所",
  },
  lishu: {
    label: "教育部標準隸書",
    license: "CC BY-ND 3.0 TW",
    licenseUrl: "https://language.moe.gov.tw/result.aspx?classify_sn=23",
    attribution: "教育部標準隸書 by 中華民國教育部",
  },
  song: {
    label: "教育部標準宋體",
    license: "CC BY-ND 3.0 TW",
    licenseUrl: "https://language.moe.gov.tw/result.aspx?classify_sn=23",
    attribution: "教育部標準宋體 by 中華民國教育部",
  },
  kaishu: {
    label: "教育部標準楷書",
    license: "CC BY-ND 3.0 TW",
    licenseUrl: "https://language.moe.gov.tw/result.aspx?classify_sn=23",
    attribution: "教育部標準楷書 by 中華民國教育部",
  },
};

function fontAuthGet(key) {
  return localStorage.getItem(FONT_AUTH_KEY_PREFIX + key) === "1";
}
function fontAuthSet(key, val) {
  if (val) localStorage.setItem(FONT_AUTH_KEY_PREFIX + key, "1");
  else localStorage.removeItem(FONT_AUTH_KEY_PREFIX + key);
}

// 簡潔模式 confirm dialog — 顯示 license 摘要 + attribution + license URL。
// 文案精確區分「授權下載/使用代理」與「字型本身著作權」兩件事。
function fontAuthPromptAndSet(key) {
  const info = FONT_AUTH_INFO[key];
  if (!info) return false;
  const msg =
    `您即將授權本網站從字型來源網站下載並使用「${info.label}」。\n\n` +
    `字型授權條款：${info.license}\n` +
    `字型著作權人：${info.attribution}\n\n` +
    `※ 字型本身的著作權仍歸原作者所有，本網站僅作為下載與使用的代理。\n\n` +
    `按下「確定」即表示您已知悉此委託關係，並同意該字型的授權條款。\n` +
    `授權條款 / 下載來源詳見：\n${info.licenseUrl}`;
  return confirm(msg);
}

// 產生授權／取消授權按鈕 HTML（放在 banner 最前面，故用 margin-right 推開後續文字）
function fontAuthButtonHtml(key) {
  const authed = fontAuthGet(key);
  const label = authed ? "取消授權" : "授權";
  const bg = authed ? "#888" : "#3a8";
  return (
    `<button data-fontkey="${key}" class="font-auth-btn"` +
    ` style="margin-right:10px;padding:3px 12px;font-size:13px;` +
    `background:${bg};color:#fff;border:none;border-radius:3px;cursor:pointer;` +
    `vertical-align:middle;">` +
    label +
    `</button>`
  );
}

// 在 banner 內找到 .font-auth-btn 並綁 click — 點下後寫 localStorage 並重 init UI
function bindFontAuthButton(banner, key, reinitFn) {
  const btn = banner.querySelector(".font-auth-btn");
  if (!btn) return;
  btn.onclick = () => {
    const wasAuthed = fontAuthGet(key);
    if (wasAuthed) {
      // 取消授權直接生效（無二次確認）
      fontAuthSet(key, false);
    } else {
      // 授權前 confirm dialog（簡潔模式）
      if (!fontAuthPromptAndSet(key)) return;
      fontAuthSet(key, true);
    }
    reinitFn();
  };
}

// ============================================================
// 字型風格 select 的授權 gate — Phase 5ba+
// 切到未授權的 style → 自動跳授權 dialog；確認 → 啟用；取消 → rollback
// ============================================================

// style → 對應的字型授權 key（用 license 對應）
const STYLE_TO_AUTH_KEY = {
  mingti: "song",          // 宋體 → 教育部宋體
  lishu: "lishu",          // 隸書 → 教育部隸書
  seal_script: "seal",     // 篆書 → 崇羲篆體
  // kaishu / bold 不需授權（kaishu = 預設 g0v；bold = 純濾鏡）
};

const STYLE_REINIT_MAP = {
  song: () => songInit(),
  lishu: () => lishuInit(),
  seal: () => sealInit(),
  cns: () => cnsInit(),
  kaishu: () => kaishuInit(),
};

// 當 select 切到需授權的 style 但尚未授權，跳 dialog；取消則 rollback 到 kaishu。
// 已授權的 style 透明通過。
function fontStyleAuthGate(selectEl) {
  const newVal = selectEl.value;
  const authKey = STYLE_TO_AUTH_KEY[newVal];
  if (!authKey) return;                  // kaishu / bold — 不需授權
  if (fontAuthGet(authKey)) return;      // 已授權 — 透明通過
  // 未授權 → prompt
  if (fontAuthPromptAndSet(authKey)) {
    fontAuthSet(authKey, true);
    // 重 init 對應 banner 讓字型狀態彈窗的綠燈狀態同步
    const reinit = STYLE_REINIT_MAP[authKey];
    if (reinit) reinit();
  } else {
    // 使用者取消 → rollback 到楷書
    selectEl.value = "kaishu";
  }
}

// 對所有字型風格 select 綁 onchange — 在 DOMContentLoaded 後 call 一次
function bindAllFontStyleGates() {
  ["grid-font-style", "nb-style", "lt-style", "ms-style",
   "pt-style", "st-style", "wa-style"].forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.addEventListener("change", () => fontStyleAuthGate(sel));
  });
}

// ============================================================
// 字型狀態 badge + modal (Phase 5ba) — 5 套字型整合按鈕
// ============================================================
const FONT_STATUS = {cns: null, seal: null, lishu: null, song: null, kaishu: null};

// authed = 該字型是否「已授權使用」（後端 ready + 使用者主動同意）。
// badge 統計顯示「已授權」字型數 / 總數，反映授權 gate 整體狀態。
function fontStatusMark(key, authed) {
  FONT_STATUS[key] = authed;
  const total = Object.keys(FONT_STATUS).length;
  const loaded = Object.values(FONT_STATUS).filter(v => v === true).length;
  const known  = Object.values(FONT_STATUS).filter(v => v !== null).length;
  const badge  = document.getElementById("font-status-badge");
  const count  = document.getElementById("font-status-count");
  if (!badge || !count) return;
  if (known < total) {
    badge.style.background = "#bbb";
    count.textContent = "(載入中…)";
  } else if (loaded === total) {
    badge.style.background = "#3a3";   // green: all 5 authorized
    count.textContent = `(${loaded}/${total})`;
    count.style.color = "#3a3";
  } else if (loaded === 0) {
    badge.style.background = "#c33";   // red: nothing authorized
    count.textContent = `(${loaded}/${total})`;
    count.style.color = "#c33";
  } else {
    badge.style.background = "#e80";   // orange: partial authorization
    count.textContent = `(${loaded}/${total})`;
    count.style.color = "#e80";
  }
}

(function initFontStatusModal() {
  const open  = document.getElementById("font-status-open");
  const close = document.getElementById("font-status-close");
  const overlay = document.getElementById("font-status-overlay");
  if (!open || !overlay) return;
  open.onclick  = () => { overlay.style.display = "flex"; };
  close.onclick = () => { overlay.style.display = "none"; };
  overlay.addEventListener("click", e => {
    if (e.target.id === "font-status-overlay") overlay.style.display = "none";
  });
})();

// Append CNS 部件 metadata to the single-char #decomposition panel.
// Run AFTER renderDecomposition so the 5000.TXT info appears first.
async function renderCnsDecomposition(char) {
  const elem = document.getElementById("decomposition");
  if (!elem || !char) return;
  try {
    const r = await fetch(
      `${API_BASE}/api/decompose/${encodeURIComponent(char)}`);
    if (!r.ok) return;
    const d = await r.json();
    if (!d.components || d.components.length === 0) return;
    // Render each component with hex tooltip (PUA chars don't display
    // in most fonts; show U+XXXXX so users can identify them).
    const parts = d.components.map(c => {
      const cp = c ? c.codePointAt(0) : 0;
      const hex = `U+${cp.toString(16).toUpperCase().padStart(4, "0")}`;
      return `<span title="${hex}" style="display:inline-block;
              padding:2px 6px;margin:2px;border:1px solid var(--border);
              border-radius:3px;background:white;
              font-family:'Noto Sans TC',sans-serif;font-size:18px;">${escapeHtml(c)}</span>`;
    }).join("");
    const cnsCode = d.cns_code ? `（CNS ${escapeHtml(d.cns_code)}）` : "";
    const block = document.createElement("div");
    block.style.marginTop = "10px";
    block.style.paddingTop = "8px";
    block.style.borderTop = "1px dashed var(--border)";
    block.innerHTML =
      `<div style="font-size:12px;color:var(--muted);margin-bottom:4px;">
        <b>全字庫部件分解</b>${cnsCode}
        <span style="margin-left:6px;">(${d.count} 個部件；hover 看 Unicode)</span>
       </div>
       <div>${parts}</div>`;
    elem.appendChild(block);
  } catch (e) {
    /* silent — diagnostic only */
  }
}

// W4-R2：跨檔邊匯出（消費端見 import 網）
export { bindAllFontStyleGates, cnsInit, kaishuInit, lishuInit, renderCnsDecomposition, sealInit, songInit };
