// W4-R2 次批：顯式跨檔邊（原全域相依 → import/export 網）
import { API_BASE } from "./core.js?v=__V__";

// W4-R2：本檔為 ES module（零被依賴、自有作用域、嚴格模式）。
// ============================================================
// Stencil (鏤空字/噴漆字模) mode — Phase 5dc
// ============================================================
// R1b：該字源有沒有可變字重軸，讀 option 的 data-weight，不在 JS 硬寫
// 字源名（那會變成第二個事實源；伺服器端的真理源是
// /api/zentangle/sources 的 supports_weight，兩者由測試鎖成同一集合）。
function scSourceHasWeight() {
  const sel = document.getElementById("sc-source");
  const opt = sel && sel.selectedOptions && sel.selectedOptions[0];
  return !!(opt && opt.dataset && opt.dataset.weight);
}

function scParams() {
  const g = (id) => document.getElementById(id).value;
  const p = {
    chars: g("sc-chars"),
    kind: g("sc-kind"),
    source: g("sc-source"),
    style: g("sc-style"),
    envelope_depth: g("sc-depth"),
    char_height_mm: g("sc-height"),
    bridge_width_mm: g("sc-bridgew"),
    bridge_count: g("sc-bridgen"),
    bold_mm: g("sc-bold"),
    spacing_mm: g("sc-spacing"),
    frame: document.getElementById("sc-frame").checked ? "true" : "false",
    frame_width_mm: g("sc-frame-w"),
  };
  // 只有可調字重的字源才送 weight——其餘字源送了會 422，而且不送就是
  // 走靜態字型（行為與記憶體與 R1b 之前完全相同）。
  if (scSourceHasWeight()) p.weight = g("sc-weight");
  return new URLSearchParams(p).toString();
}

async function renderStencil() {
  const statusEl = document.getElementById("sc-status");
  const previewEl = document.getElementById("sc-preview");
  const dlGroup = document.getElementById("sc-download-group");
  statusEl.textContent = "產生中…（幾何運算約數秒）";
  dlGroup.style.display = "none";
  const qs = scParams();
  try {
    const r = await fetch(`${API_BASE}/api/stencil?${qs}&format=svg`);
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: r.statusText}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    const svg = await r.text();
    previewEl.innerHTML = svg;
    const inner = previewEl.querySelector("svg");
    if (inner) { inner.style.maxWidth = "100%"; inner.style.height = "auto"; }
    const loops = r.headers.get("x-stencil-loops") || "?";
    const holes = r.headers.get("x-stencil-holes");
    const comps = r.headers.get("x-stencil-comps") ||
                  r.headers.get("x-stencil-components");
    const kind = document.getElementById("sc-kind").value;
    let note = kind === "stencil"
      ? `孔洞橋接 ${holes} 處` : `原始元件 ${comps} 塊已連筋`;
    statusEl.textContent =
      `OK · 切割環 ${loops} 條 · ${note} · 上機前請放大檢查`;
    document.getElementById("sc-dl-svg").href =
      `${API_BASE}/api/stencil?${qs}&format=svg&download=true`;
    document.getElementById("sc-dl-dxf").href =
      `${API_BASE}/api/stencil?${qs}&format=dxf&download=true`;
    document.getElementById("sc-dl-gcode").href =
      `${API_BASE}/api/stencil?${qs}&format=gcode&download=true`;
    dlGroup.style.display = "";
  } catch (e) {
    statusEl.textContent = "失敗：" + e.message;
  }
}
document.getElementById("sc-render")
  .addEventListener("click", renderStencil);

// 切割風格＝方正簡潔（envelope）時，顯示免責提示＋連筋深度輸入。
(function () {
  const sel = document.getElementById("sc-style");
  const note = document.getElementById("sc-style-note");
  const depth = document.getElementById("sc-depth-wrap");
  if (sel && note) {
    const sync = () => {
      const isEnv = sel.value === "envelope";
      note.style.display = isEnv ? "" : "none";
      if (depth) depth.style.display = isEnv ? "" : "none";
    };
    sel.addEventListener("change", sync);
    sync();
  }
})();

// R1b：字型風格有可變字重軸時才顯示字重滑桿（同上，由 data-weight 驅動）。
(function () {
  const sel = document.getElementById("sc-source");
  const wrap = document.getElementById("sc-weight-wrap");
  const slider = document.getElementById("sc-weight");
  const val = document.getElementById("sc-weight-val");
  if (!sel || !wrap) return;
  const sync = () => { wrap.style.display = scSourceHasWeight() ? "" : "none"; };
  sel.addEventListener("change", sync);
  if (slider && val) {
    const show = () => { val.textContent = slider.value; };
    slider.addEventListener("input", show);
    show();
  }
  sync();
})();

