// W4-R2 次批：顯式跨檔邊（原全域相依 → import/export 網）
import { API_BASE } from "./core.js?v=__V__";
import { ensureZhuyinTw, gridUserFont, gridUserFontName, gridZhuyinMap, injectUserFontIntoGrid } from "./grid.js?v=__V__";
import { swAttachCells } from "./handwrite.js?v=__V__";   // 5ew-R4：點格手寫
import { _attachRulerToPreview, ufPageDownloads } from "./notebook.js?v=__V__";

// ============================================================
// Letter (信紙) mode — very similar to notebook
// ============================================================
// ---- Letter capacity (live preview, debounced) ----
function ltBuildParams(forCapacity = false) {
  const g = (id) => document.getElementById(id).value;
  const params = new URLSearchParams({
    text: g("lt-text"),
    preset: g("lt-preset"),
    title_space_mm: g("lt-title-space"),
    signature_space_mm: g("lt-sign-space"),
    direction: g("lt-direction"),
  });
  const lines = g("lt-lines"); if (lines) params.set("lines_per_page", lines);
  const lh = g("lt-lineh");   if (lh) params.set("line_height_mm", lh);
  const mg = g("lt-margin");  if (mg) params.set("margin_mm", mg);
  const fl = g("lt-first-line"); if (fl && !forCapacity) params.set("first_line_offset_mm", fl);
  if (!forCapacity) {
    params.set("title_text", g("lt-title"));
    params.set("signature_text", g("lt-sign"));
    params.set("date_text", g("lt-date"));
    const ts = g("lt-title-size");   if (ts) params.set("title_size_mm", ts);
    const ss = g("lt-sign-size");    if (ss) params.set("signature_size_mm", ss);
    const ds = g("lt-date-size");    if (ds) params.set("date_size_mm", ds);
    params.set("signature_lines_after_body", g("lt-sig-lines"));
    params.set("signature_align", g("lt-sig-align"));
    params.set("cell_style", g("lt-cell-style"));
    // 5ct：userfont 為前端概念——伺服器照楷書出版面，字形整組替換
    params.set("style", g("lt-style") === "userfont"
      ? "kaishu" : g("lt-style"));
    params.set("cns_outline_mode", g("lt-cns-mode"));
    params.set("decorative_border",
               document.getElementById("lt-border").checked ? "true" : "false");
    params.set("show_grid",
               document.getElementById("lt-hide-grid").checked ? "false" : "true");
    params.set("source", g("lt-source"));
    // 5cz：注音欄（同 notebook）
    if (document.getElementById("lt-zhuyin").checked) {
      params.set("zhuyin_map", gridZhuyinMap(g("lt-text")));
    }
  }
  return params;
}

let ltCapacityTimer = null;
function scheduleLtCapacity() {
  if (ltCapacityTimer) clearTimeout(ltCapacityTimer);
  ltCapacityTimer = setTimeout(fetchLtCapacity, 300);
}
async function fetchLtCapacity() {
  const el = document.getElementById("lt-capacity");
  try {
    const r = await fetch(`${API_BASE}/api/letter/capacity?` + ltBuildParams(true));
    if (!r.ok) { el.textContent = `容量計算失敗 (${r.status})`; return; }
    const d = await r.json();
    const overflow = d.pages_estimated > 1;
    const hint = overflow
      ? `<span style="color:#a60;">ℹ 需要 <b>${d.pages_estimated}</b> 頁，按「產生信紙」會自動分頁</span>`
      : `<span style="color:#260;">✓ 一頁內可放下</span>`;
    el.innerHTML =
      `一頁容納：<b>${d.chars_per_page}</b> 字 ` +
      `(${d.cols_per_line} 欄 × ${d.lines_per_page} 行)  ·  ` +
      `您輸入：<b>${d.total_chars}</b> 字  ·  ${hint}`;
    // Phase 5aa: reflect the auto default of first_line_offset_mm in the UI.
    ltUpdateFirstLineDefault(d.default_first_line_offset_mm);
  } catch (e) {
    el.textContent = "容量計算失敗：" + e.message;
  }
}

// Phase 5aa: same behaviour as nbUpdateFirstLineDefault — set input min,
// placeholder, and hint label from the server-computed auto default
// (which is also the minimum).
function ltUpdateFirstLineDefault(defaultMm) {
  if (defaultMm == null) return;
  const input = document.getElementById("lt-first-line");
  const hint = document.getElementById("lt-first-line-hint");
  if (!input) return;
  const dir = document.getElementById("lt-direction").value;
  const rounded = Math.round(defaultMm * 10) / 10;
  input.min = String(rounded);
  input.placeholder = `auto = ${rounded}`;
  if (hint) {
    const edge = (dir === "vertical") ? "右邊緣" : "頁頂";
    hint.innerHTML =
      `最小值 <b>${rounded}</b> mm (auto 預設；` +
      `數字 = 第一${dir === "vertical" ? "欄左緣距" + edge : "行下緣距" + edge})`;
  }
  const cur = parseFloat(input.value);
  if (!isNaN(cur) && cur < rounded - 0.001) {
    input.value = String(rounded);
  }
}

for (const id of ["lt-text", "lt-preset", "lt-lines", "lt-lineh", "lt-margin",
                  "lt-title-space", "lt-sign-space", "lt-direction"]) {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener("input", scheduleLtCapacity);
    el.addEventListener("change", scheduleLtCapacity);
  }
}

// Phase 5ac: populate 3 download links (SVG / G-code / JSON) next to lt-render.
function ltSetDownloadLinks(svgUrl, gcodeUrl, jsonUrl) {
  const g = document.getElementById("lt-download-group");
  const s = document.getElementById("lt-download-svg");
  const c = document.getElementById("lt-download-gcode");
  const j = document.getElementById("lt-download-json");
  if (svgUrl) s.href = svgUrl;
  if (gcodeUrl) c.href = gcodeUrl;
  if (jsonUrl) j.href = jsonUrl;
  s.removeAttribute("download");   // 5ct：清 userfont blob 殘留
  s.onclick = null;
  c.style.display = "";
  j.style.display = "";
  // W1：PDF 由 svg 下載網址推導（format=svg → pdf），所以呼叫點
  // 不必各自多傳一個參數——少一處會漏改的地方。
  const pdfEl = document.getElementById("lt-download-pdf");
  if (pdfEl && svgUrl) {
    pdfEl.href = svgUrl.replace("format=svg", "format=pdf");
    pdfEl.style.display = "";
  }
  g.style.display = "inline";
}

async function renderLetter(pageN = null) {
  const statusEl = document.getElementById("lt-status");
  const previewEl = document.getElementById("lt-preview");
  const downloadEl = document.getElementById("lt-download");
  const navEl = document.getElementById("lt-page-nav");
  statusEl.textContent = "產生中…";
  downloadEl.style.display = "none";
  document.getElementById("lt-download-group").style.display = "none";

  // 5cz：注音開啟時先確保台灣讀音表載妥（同 5cw 字帖）
  if (document.getElementById("lt-zhuyin").checked) await ensureZhuyinTw();
  const params = ltBuildParams(false);
  if (pageN !== null) params.set("page", String(pageN));

  try {
    const r = await fetch(`${API_BASE}/api/letter?${params}`);
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: r.statusText}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    const total = parseInt(r.headers.get("x-stroke-order-pages") || "1", 10);
    const ct = r.headers.get("content-type") || "";
    if (ct.startsWith("image/svg+xml") || pageN !== null) {
      const svg = await r.text();
      previewEl.innerHTML = svg;
      const innerSvg = previewEl.querySelector("svg");
      if (innerSvg) { innerSvg.style.maxWidth = "100%"; innerSvg.style.height = "auto"; }
      // Phase 5y: ruler overlay (same API as notebook)
      ltAttachRuler();
      statusEl.textContent = `OK · ${total} 頁`;
      if (total > 1) {
        const buttons = [];
        for (let i = 1; i <= total; i++)
          buttons.push(`<button data-page="${i}" style="margin:0 2px;" ${i===(pageN||1)?'class="primary"':''}>${i}</button>`);
        navEl.innerHTML = buttons.join("");
        navEl.querySelectorAll("button").forEach(b =>
          b.onclick = () => renderLetter(parseInt(b.dataset.page, 10))
        );
      } else navEl.innerHTML = "";
      // Phase 5ac: 3 download links (SVG / G-code / JSON)
      ltSetDownloadLinks(
        `${API_BASE}/api/letter?${params}&download=true&format=svg`,
        `${API_BASE}/api/letter?${params}&download=true&format=gcode`,
        `${API_BASE}/api/letter?${params}&download=true&format=json`,
      );
      // 5ct：自訂字型——本頁逐字注入＋本頁 SVG 前端下載
      if (document.getElementById("lt-style").value === "userfont") {
        if (gridUserFont && innerSvg) {
          const nUf = injectUserFontIntoGrid(innerSvg);
          ufPageDownloads("lt", innerSvg, pageN, "letter");
          statusEl.textContent += ` · 自訂字型「${gridUserFontName}」` +
            `${nUf} 字（前端組裝、未上傳；多頁請逐頁切換下載）`;
        } else {
          statusEl.textContent += " · 尚未載入字型檔——請先選 TTF/OTF";
          if (!gridUserFont) {
            document.getElementById("grid-font-file").click();
          }
        }
      }
      // 5ew-R4：點格手寫——refresh 重繪目前頁（自訂字型注入後才掛）
      swAttachCells(previewEl, {
        key: "letter", styleId: "lt-style", sourceId: "lt-source",
        refresh: () => renderLetter(pageN) });
    } else {
      previewEl.innerHTML = `<p>共 ${total} 頁，點擊頁碼預覽：</p>`;
      const buttons = [];
      for (let i = 1; i <= total; i++)
        buttons.push(`<button data-page="${i}" style="margin:0 2px;">${i}</button>`);
      navEl.innerHTML = buttons.join("");
      navEl.querySelectorAll("button").forEach(b =>
        b.onclick = () => renderLetter(parseInt(b.dataset.page, 10))
      );
      statusEl.textContent = `${total} 頁（ZIP）`;
      // Phase 5ac: 3 download links for multi-page (ZIP for SVG, plain for G-code/JSON)
      ltSetDownloadLinks(
        `${API_BASE}/api/letter?${params}&download=true&format=svg`,
        `${API_BASE}/api/letter?${params}&download=true&format=gcode`,
        `${API_BASE}/api/letter?${params}&download=true&format=json`,
      );
    }
  } catch (e) {
    statusEl.textContent = "";
    previewEl.innerHTML =
      `<span style="color:var(--accent);">錯誤：${e.message}</span>`;
  }
}
document.getElementById("lt-render").onclick = () => renderLetter(null);

// Phase 5y: letter ruler overlay (same UX as notebook mode)
function ltAttachRuler() {
  _attachRulerToPreview({
    previewEl: document.getElementById("lt-preview"),
    showRuler: document.getElementById("lt-show-ruler").checked,
    direction: document.getElementById("lt-direction").value,
  });
}
document.getElementById("lt-show-ruler").addEventListener(
  "change", ltAttachRuler);

// Phase 5aa: direction-aware tooltip on first-line label (mirrors notebook)
// Phase 5ab: also swap 行高/字寬 label to match direction.
function ltUpdateDirectionalLabel() {
  const dir = document.getElementById("lt-direction").value;
  const fllbl = document.getElementById("lt-first-line-label");
  if (fllbl) {
    fllbl.title = (dir === "vertical")
      ? "直書: 第一欄左緣距頁面右邊緣 mm；留空用 [邊緣留白+字寬]"
      : "橫書: 第一行下緣距頁面頂端 mm；留空用 [邊緣留白+行高]";
  }
  const lhlbl = document.getElementById("lt-lineh-label");
  if (lhlbl) lhlbl.textContent = (dir === "vertical") ? "字寬 (mm)" : "行高 (mm)";
}
document.getElementById("lt-direction").addEventListener(
  "change", ltUpdateDirectionalLabel);
ltUpdateDirectionalLabel();

// W4-R2：跨檔邊匯出（消費端見 import 網）
export { scheduleLtCapacity };
