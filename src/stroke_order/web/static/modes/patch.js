// ============================================================
// 預覽用：把字 outline 改成灰階填充 (Phase 5ba-5)
// ------------------------------------------------------------
// 原 SVG 是「無 fill 細線」(給寫字機/雷射用)；放大預覽時細線
// 看不清楚。改填灰色後字看起來像實體印刷字型，視覺更厚實。
// 規則：
//   1. 父 group (patch-cut / stamp-engrave) fill="#444"（深灰）
//   2. .patch-outline / .stamp-border 顯式 fill="none"
//      （否則整個外框會被填成灰色方塊）
//   3. patch-write 紅色骨架線保留 stroke 不變（raw_track 不封閉，不能 fill）
// 不影響下載 SVG（只動 DOM 中的預覽元素）。
// ============================================================
function tintPreviewFill(svg) {
  if (!svg) return;
  // 1. 字 outline → 淡灰 fill。
  //    **不對父 group 設 stroke** — 這會被子元素繼承，抹掉：
  //    (a) .stamp-border / .patch-outline 邊框
  //    (b) 隸書 / 篆書筆畫骨架線（5aj 濾鏡產生的 stroke-based polyline）
  //        ←  這個若被抹掉，預覽就會空白！
  //    改用「個別 path 是否有 stroke 屬性」判斷：
  //    - outline path（無 stroke 屬性）→ 顯式 stroke="none"（避免線框感）
  //    - 骨架線 polyline / polygon（有 stroke 屬性）→ 不動，保留自己的 stroke
  ["patch-cut", "stamp-engrave"].forEach(id => {
    const g = svg.querySelector("#" + id);
    if (!g) return;
    g.setAttribute("fill", "#888");
    // 對「沒設 stroke 屬性的」子 path/polyline/polygon 顯式 stroke="none"。
    // 這樣 outline 字無線框感，但骨架線保留原 stroke。
    g.querySelectorAll("path, polyline, polygon").forEach(elem => {
      if (!elem.hasAttribute("stroke")) {
        elem.setAttribute("stroke", "none");
      }
    });
  });
  // 2. border 顯式 fill=none — 否則整個邊框會被父 group 的灰色塗滿。
  //    顯式 stroke=black 保證可見（無條件 override）。
  svg.querySelectorAll(".patch-outline, .stamp-border").forEach(p => {
    p.setAttribute("fill", "none");
    p.setAttribute("stroke", "black");
  });
  // 3. patch-write 紅色骨架線：不動，保留 SVG 原 stroke=#c33 / 0.3mm。
}

// ============================================================
// 布章模式 (Phase 5ax)
// ============================================================
const PATCH = {
  decorations: [],   // [{svg_content, x_mm, y_mm, w_mm, h_mm}, ...]
};

function patchInit() {
  const $ = id => document.getElementById(id);
  if (!$("pt-render")) return;
  $("pt-render").onclick   = () => patchRender();
  $("pt-dl-svg").onclick   = () => patchDownload("svg");
  $("pt-dl-cut").onclick   = () => patchDownload("gcode_cut");
  $("pt-dl-write").onclick = () => patchDownload("gcode_write");
  $("pt-dl-dxf").onclick   = () => patchDownload("dxf");   // 5bq
  $("pt-deco-add").onclick = patchAddDecoration;
  // Capacity hint live-updates
  ["pt-preset", "pt-w", "pt-h", "pt-charsize",
   "pt-rows", "pt-cols", "pt-gap"].forEach(id => {
    $(id).addEventListener("change", patchUpdateCapacity);
    $(id).addEventListener("input", patchUpdateCapacity);
  });
  patchUpdateCapacity();
  patchRefreshDecoList();
}

async function patchUpdateCapacity() {
  const $ = id => document.getElementById(id).value;
  const params = new URLSearchParams({
    preset: $("pt-preset"),
    patch_width_mm: $("pt-w"), patch_height_mm: $("pt-h"),
    char_size_mm: $("pt-charsize"),
    tile_rows: $("pt-rows"), tile_cols: $("pt-cols"), tile_gap_mm: $("pt-gap"),
  });
  try {
    const r = await fetch(`${API_BASE}/api/patch/capacity?${params}`);
    if (!r.ok) return;
    const d = await r.json();
    document.getElementById("pt-capacity").innerHTML =
      `每 patch 約可放 <b>${d.chars_per_patch}</b> 字 ｜ 平鋪 ${d.tiles_used} 個 = ${d.used_size_mm[0]}×${d.used_size_mm[1]} mm `
      + (d.fits_page ? `<span style="color:#080;">✓ A4 內</span>`
                     : `<span style="color:var(--accent);">✗ 超過 A4</span>`)
      + ` ｜ A4 最多 ${d.max_grid[0]}×${d.max_grid[1]} = ${d.max_tiles_per_page} 個`;
  } catch (_) {}
}

async function patchAddDecoration() {
  const $ = id => document.getElementById(id);
  const file = $("pt-deco-file").files[0];
  let svg_content = $("pt-deco-paste").value.trim();
  if (file) {
    svg_content = await file.text();
  }
  if (!svg_content) {
    alert("請選擇 SVG 檔或貼上 SVG 內容");
    return;
  }
  PATCH.decorations.push({
    svg_content,
    x_mm: parseFloat($("pt-deco-x").value),
    y_mm: parseFloat($("pt-deco-y").value),
    w_mm: parseFloat($("pt-deco-w").value),
    h_mm: parseFloat($("pt-deco-h").value),
  });
  $("pt-deco-file").value = "";
  $("pt-deco-paste").value = "";
  patchRefreshDecoList();
}

function patchRefreshDecoList() {
  const list = document.getElementById("pt-deco-list");
  if (!list) return;
  if (PATCH.decorations.length === 0) {
    list.innerHTML = "（尚未加入裝飾。可選 SVG 檔或貼上後按「+ 加入」）";
    return;
  }
  list.innerHTML = PATCH.decorations.map((d, i) =>
    `<div style="margin:2px 0;">
       #${i + 1} 位置(${d.x_mm},${d.y_mm}) 大小 ${d.w_mm}×${d.h_mm} mm
       (${d.svg_content.length} 字元)
       <button data-idx="${i}" class="pt-deco-del"
               style="background:none;border:none;color:var(--accent);cursor:pointer;">✕</button>
     </div>`
  ).join("");
  list.querySelectorAll(".pt-deco-del").forEach(b =>
    b.addEventListener("click", () => {
      PATCH.decorations.splice(parseInt(b.dataset.idx), 1);
      patchRefreshDecoList();
    }));
}

function patchBuildBody(format) {
  const $ = id => document.getElementById(id).value;
  const $$ = id => document.getElementById(id);
  return {
    text: $("pt-text"),
    preset: $("pt-preset"),
    patch_width_mm: parseFloat($("pt-w")),
    patch_height_mm: parseFloat($("pt-h")),
    char_size_mm: parseFloat($("pt-charsize")),
    text_position: $("pt-textpos"),
    style: $("pt-style"),
    source: $("pt-source"),
    tile_rows: parseInt($("pt-rows")),
    tile_cols: parseInt($("pt-cols")),
    tile_gap_mm: parseFloat($("pt-gap")),
    show_border: $$("pt-show-border")?.checked !== false,
    // 5de：auto 字級——字少自動放大、字多自動縮小（造型感知）
    auto_size: $$("pt-auto-size")?.checked === true,
    decorations: PATCH.decorations,
    format,
  };
}

async function patchRender() {
  const status = document.getElementById("pt-status");
  const preview = document.getElementById("pt-preview");
  status.textContent = "產生中…";
  try {
    const r = await fetch(`${API_BASE}/api/patch`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(patchBuildBody("svg")),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: r.statusText}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    preview.innerHTML = await r.text();
    const inner = preview.querySelector("svg");
    if (inner) {
      // 5ba-2: patch SVG 實際尺寸只有 ~80mm；不放大會看不見。
      inner.removeAttribute("width");
      inner.removeAttribute("height");
      inner.style.width = "100%";
      inner.style.maxHeight = "600px";
      inner.style.height = "auto";
      inner.style.display = "block";
      inner.style.background = "white";
      tintPreviewFill(inner);   // 5ba-5: grey fill instead of thick stroke
    }
    status.textContent = "✓ 完成";
    status.style.color = "#080";
  } catch (e) {
    status.textContent = "失敗：" + e.message;
    status.style.color = "var(--accent)";
  }
}

async function patchDownload(format) {
  const status = document.getElementById("pt-status");
  status.textContent = "下載中…";
  try {
    const r = await fetch(`${API_BASE}/api/patch`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(patchBuildBody(format)),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const ext = format === "svg" ? "svg"
              : format === "dxf" ? "dxf"
              : format === "gcode_cut" ? "cut.gcode" : "write.gcode";
    a.download = `patch.${ext}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    status.textContent = `✓ 已下載 patch.${ext}`;
    status.style.color = "#080";
  } catch (e) {
    status.textContent = "下載失敗：" + e.message;
    status.style.color = "var(--accent)";
  }
}

