// W4-R2 次批：顯式跨檔邊（原全域相依 → import/export 網）
import { API_BASE } from "./core.js?v=__V__";
import { swAttachCells } from "./handwrite.js?v=__V__";   // 5ew-R4：點格手寫

// ============================================================
// Manuscript (稿紙) mode — Phase 5ad
// ============================================================
function msBuildParams() {
  const g = (id) => document.getElementById(id).value;
  const params = new URLSearchParams({
    text: g("ms-text"),
    preset: g("ms-preset"),
    margin_top_mm: g("ms-margin-top"),
    margin_bottom_mm: g("ms-margin-bottom"),
    margin_left_mm: g("ms-margin-left"),
    margin_right_mm: g("ms-margin-right"),
  });
  const zw = g("ms-zhuyin-width");
  if (zw) params.set("zhuyin_width_mm", zw);
  params.set("cell_style", g("ms-cell-style"));
  params.set("style", g("ms-style"));
  params.set("cns_outline_mode", g("ms-cns-mode"));
  params.set("show_grid",
             document.getElementById("ms-hide-grid").checked ? "false" : "true");
  params.set("source", g("ms-source"));
  return params;
}

let msCapacityTimer = null;
function scheduleMsCapacity() {
  if (msCapacityTimer) clearTimeout(msCapacityTimer);
  msCapacityTimer = setTimeout(fetchMsCapacity, 300);
}
async function fetchMsCapacity() {
  const el = document.getElementById("ms-capacity");
  const p = new URLSearchParams({
    text: document.getElementById("ms-text").value,
    preset: document.getElementById("ms-preset").value,
    margin_top_mm: document.getElementById("ms-margin-top").value,
    margin_bottom_mm: document.getElementById("ms-margin-bottom").value,
    margin_left_mm: document.getElementById("ms-margin-left").value,
    margin_right_mm: document.getElementById("ms-margin-right").value,
  });
  const zw = document.getElementById("ms-zhuyin-width").value;
  if (zw) p.set("zhuyin_width_mm", zw);
  try {
    const r = await fetch(`${API_BASE}/api/manuscript/capacity?${p}`);
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: r.statusText}));
      el.textContent = `容量計算失敗：${err.detail || r.status}`;
      return;
    }
    const d = await r.json();
    const overflow = d.pages_estimated > 1;
    const hint = overflow
      ? `<span style="color:#a60;">ℹ 需要 <b>${d.pages_estimated}</b> 頁，按「產生稿紙」會自動分頁</span>`
      : `<span style="color:#260;">✓ 一頁內可放下</span>`;
    el.innerHTML =
      `一頁容納：<b>${d.chars_per_page}</b> 字 ` +
      `(${d.rows} 列 × ${d.cols} 欄)  ·  ` +
      `字格：<b>${d.char_width_mm.toFixed(1)} × ${d.cell_height_mm.toFixed(1)}</b> mm ` +
      `· 注音格寬：<b>${d.zhuyin_width_mm.toFixed(1)}</b> mm  ·  ` +
      `您輸入：<b>${d.total_chars}</b> 字  ·  ${hint}`;
  } catch (e) {
    el.textContent = "容量計算失敗：" + e.message;
  }
}
for (const id of ["ms-text", "ms-preset", "ms-margin-top", "ms-margin-bottom",
                  "ms-margin-left", "ms-margin-right", "ms-zhuyin-width"]) {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener("input", scheduleMsCapacity);
    el.addEventListener("change", scheduleMsCapacity);
  }
}

function msSetDownloadLinks(svgUrl, gcodeUrl, jsonUrl) {
  const g = document.getElementById("ms-download-group");
  document.getElementById("ms-download-svg").href = svgUrl;
  document.getElementById("ms-download-gcode").href = gcodeUrl;
  document.getElementById("ms-download-json").href = jsonUrl;
  g.style.display = "inline";
}

async function renderManuscript(pageN = null) {
  const statusEl = document.getElementById("ms-status");
  const previewEl = document.getElementById("ms-preview");
  const navEl = document.getElementById("ms-page-nav");
  statusEl.textContent = "產生中…";
  document.getElementById("ms-download-group").style.display = "none";

  const params = msBuildParams();
  if (pageN !== null) params.set("page", String(pageN));

  try {
    const r = await fetch(`${API_BASE}/api/manuscript?${params}`);
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
      statusEl.textContent = `OK · ${total} 頁`;
      if (total > 1) {
        const buttons = [];
        for (let i = 1; i <= total; i++)
          buttons.push(`<button data-page="${i}" style="margin:0 2px;" ${i===(pageN||1)?'class="primary"':''}>${i}</button>`);
        navEl.innerHTML = buttons.join("");
        navEl.querySelectorAll("button").forEach(b =>
          b.onclick = () => renderManuscript(parseInt(b.dataset.page, 10))
        );
      } else navEl.innerHTML = "";
      // 5ew-R4：點格手寫——refresh 重繪目前頁
      swAttachCells(previewEl, {
        key: "manuscript", styleId: "ms-style", sourceId: "ms-source",
        refresh: () => renderManuscript(pageN) });
    } else {
      previewEl.innerHTML = `<p>共 ${total} 頁，點擊頁碼預覽：</p>`;
      const buttons = [];
      for (let i = 1; i <= total; i++)
        buttons.push(`<button data-page="${i}" style="margin:0 2px;">${i}</button>`);
      navEl.innerHTML = buttons.join("");
      navEl.querySelectorAll("button").forEach(b =>
        b.onclick = () => renderManuscript(parseInt(b.dataset.page, 10))
      );
      statusEl.textContent = `${total} 頁（ZIP）`;
    }
    msSetDownloadLinks(
      `${API_BASE}/api/manuscript?${params}&download=true&format=svg`,
      `${API_BASE}/api/manuscript?${params}&download=true&format=gcode`,
      `${API_BASE}/api/manuscript?${params}&download=true&format=json`,
    );
  } catch (e) {
    statusEl.textContent = "";
    previewEl.innerHTML =
      `<span style="color:var(--accent);">錯誤：${e.message}</span>`;
  }
}
document.getElementById("ms-render").onclick = () => renderManuscript(null);
// Initial capacity probe when user first switches into manuscript mode
scheduleMsCapacity();

