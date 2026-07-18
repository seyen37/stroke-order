// ============================================================
// Notebook (筆記) mode
// ============================================================
// ---- Notebook capacity (live preview, debounced) ----
function nbBuildParams(forCapacity = false) {
  const g = (id) => document.getElementById(id).value;
  const params = new URLSearchParams({
    text: g("nb-text"),
    preset: g("nb-preset"),
    grid_style: g("nb-grid"),
    direction: g("nb-direction"),
  });
  const lines = g("nb-lines");  if (lines) params.set("lines_per_page", lines);
  const lh = g("nb-lineh");    if (lh) params.set("line_height_mm", lh);
  const mg = g("nb-margin");   if (mg) params.set("margin_mm", mg);
  const fl = g("nb-first-line"); if (fl) params.set("first_line_offset_mm", fl);
  const doodleZone = document.getElementById("nb-doodle-zone").checked;
  if (doodleZone) {
    params.set("doodle_zone", "true");
    // Phase 5s: send the zones list as JSON (sans svg_content, which is
    // handled via POST when needed)
    if (nbZones.length > 0) {
      const simpleZones = nbZones.map(z => ({x: z.x, y: z.y, w: z.w, h: z.h}));
      params.set("zones_json", JSON.stringify(simpleZones));
    } else {
      params.set("doodle_zone_size_mm", g("nb-doodle-size"));
    }
  }
  if (!forCapacity) {
    params.set("cell_style", g("nb-cell-style"));
    // 5ct：userfont 為前端概念——伺服器照楷書出版面，字形整組替換
    params.set("style", g("nb-style") === "userfont"
      ? "kaishu" : g("nb-style"));
    params.set("cns_outline_mode", g("nb-cns-mode"));
    params.set("source", g("nb-source"));
    // 5cz：注音欄——前端算好映射（教育部審定音查表），參數存在即開
    if (document.getElementById("nb-zhuyin").checked) {
      params.set("zhuyin_map", gridZhuyinMap(g("nb-text")));
    }
  }
  return params;
}

let nbCapacityTimer = null;
function scheduleNbCapacity() {
  if (nbCapacityTimer) clearTimeout(nbCapacityTimer);
  nbCapacityTimer = setTimeout(fetchNbCapacity, 300);
}
async function fetchNbCapacity() {
  const el = document.getElementById("nb-capacity");
  try {
    const r = await fetch(`${API_BASE}/api/notebook/capacity?` + nbBuildParams(true));
    if (!r.ok) { el.textContent = `容量計算失敗 (${r.status})`; return; }
    const d = await r.json();
    const overflow = d.pages_estimated > 1;
    const hint = overflow
      ? `<span style="color:#a60;">ℹ 需要 <b>${d.pages_estimated}</b> 頁，按「產生筆記」會自動分頁</span>`
      : `<span style="color:#260;">✓ 一頁內可放下</span>`;
    el.innerHTML =
      `一頁容納：<b>${d.chars_per_page}</b> 字 ` +
      `(${d.cols_per_line} 欄 × ${d.lines_per_page} 行)  ·  ` +
      `您輸入：<b>${d.total_chars}</b> 字  ·  ${hint}`;
    // Phase 5p: update the first_line_offset input min/placeholder from
    // the server-computed auto default (= minimum).
    nbUpdateFirstLineDefault(d.default_first_line_offset_mm);
  } catch (e) {
    el.textContent = "容量計算失敗：" + e.message;
  }
}

// Phase 5p: reflect the auto default of first_line_offset_mm in the UI.
// Sets input's min + placeholder + a visible hint line.
function nbUpdateFirstLineDefault(defaultMm) {
  if (defaultMm == null) return;
  const input = document.getElementById("nb-first-line");
  const hint = document.getElementById("nb-first-line-hint");
  const dir = document.getElementById("nb-direction").value;
  const rounded = Math.round(defaultMm * 10) / 10;
  input.min = String(rounded);
  input.placeholder = `auto = ${rounded}`;
  if (hint) {
    const edge = (dir === "vertical") ? "右邊緣" : "頁頂";
    hint.innerHTML =
      `最小值 <b>${rounded}</b> mm (auto 預設；` +
      `數字 = 第一${dir === "vertical" ? "欄左緣距" + edge : "行下緣距" + edge})`;
  }
  // Enforce min on current value (if user typed below, bump it up)
  const cur = parseFloat(input.value);
  if (!isNaN(cur) && cur < rounded - 0.001) {
    input.value = String(rounded);
  }
}
// wire up: live update on any setting change
for (const id of ["nb-text", "nb-preset", "nb-grid", "nb-lineh", "nb-lines", "nb-direction",
                  "nb-margin", "nb-doodle-zone", "nb-doodle-size",
                  "nb-doodle-x", "nb-doodle-y", "nb-doodle-w", "nb-doodle-h"]) {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener("input", scheduleNbCapacity);
    el.addEventListener("change", scheduleNbCapacity);
  }
}

// Phase 5s: build POST /api/notebook body (full zones with svg_content)
function nbBuildPostBody(pageN) {
  const g = (id) => document.getElementById(id).value;
  const body = {
    text: g("nb-text"),
    preset: g("nb-preset"),
    grid_style: g("nb-grid"),
    direction: g("nb-direction"),
    cell_style: g("nb-cell-style"),
    style: g("nb-style") === "userfont" ? "kaishu" : g("nb-style"),  // 5ct
    cns_outline_mode: g("nb-cns-mode"),
    source: g("nb-source"),
    zones: nbZones.map(z => ({
      x: z.x, y: z.y, w: z.w, h: z.h,
      label: `塗鴉區`,
      svg_content: z.svg_content || null,
      content_viewbox: z.content_viewbox || null,
      stretch: document.getElementById("nb-doodle-stretch").checked,
    })),
  };
  const lh = g("nb-lineh");    if (lh) body.line_height_mm = parseFloat(lh);
  const mg = g("nb-margin");   if (mg) body.margin_mm = parseFloat(mg);
  const lines = g("nb-lines"); if (lines) body.lines_per_page = parseInt(lines, 10);
  const fl = g("nb-first-line"); if (fl) body.first_line_offset_mm = parseFloat(fl);
  if (pageN !== null) body.page = pageN;
  return body;
}

// Phase 5s: multi-zone state + CRUD
// -----------------------------------------------------------
// Each zone: {id, x, y, w, h, svg_content?, content_viewbox?}
// Stored in JS state (not in URL) so SVG content can be large.
let nbZones = [];
let nbSelectedZoneId = null;  // currently selected for drag
let lastDoodleSvg = null;     // cached from 塗鴉 mode rendering

function nbGenZoneId() {
  return "z" + Math.random().toString(36).slice(2, 9);
}
function nbDefaultZone() {
  return {id: nbGenZoneId(), x: 145, y: 232, w: 50, h: 50,
          svg_content: null, content_viewbox: null};
}

function nbRenderZonesList() {
  const wrap = document.getElementById("nb-zones-list");
  const on = document.getElementById("nb-doodle-zone").checked;
  wrap.style.display = on ? "" : "none";
  if (!on) return;
  if (nbZones.length === 0) {
    // Seed with a default zone when first enabling
    nbZones.push(nbDefaultZone());
    nbSelectedZoneId = nbZones[0].id;
  }
  wrap.innerHTML = "";
  nbZones.forEach((z, i) => {
    const row = document.createElement("div");
    row.style.cssText = (
      "display:flex; align-items:center; gap:6px; padding:3px 4px; " +
      "border-radius:3px; font-size:12px; margin-bottom:2px;" +
      (z.id === nbSelectedZoneId ? "background:#fff3d0;" : "")
    );
    row.innerHTML =
      `<label title="選擇此區以在預覽拖曳">
         <input type="radio" name="nb-zone-sel" value="${z.id}"
                ${z.id === nbSelectedZoneId ? "checked" : ""}>
         Zone ${i + 1}
       </label>
       <span style="color:#666;">
         X=${Math.round(z.x)} Y=${Math.round(z.y)} W=${Math.round(z.w)} H=${Math.round(z.h)}
       </span>
       <span style="color:${z.svg_content ? '#060' : '#999'};">
         ${z.svg_content ? "✓ 有向量" : "✗ 空白"}
       </span>
       <button data-act="doodle-import" data-id="${z.id}"
               title="匯入剛剛產生的塗鴉向量">⬅ 匯入塗鴉</button>
       <button data-act="upload" data-id="${z.id}"
               title="從本機選一張 SVG 檔匯入">📁 上傳</button>
       <button data-act="paste" data-id="${z.id}"
               title="從剪貼簿貼上 SVG 內容">📋 貼上</button>
       <button data-act="clear" data-id="${z.id}"
               title="清除此區的向量">🧹 清空</button>
       <button data-act="copy" data-id="${z.id}"
               title="複製本區（位置向右下偏移 10mm）">🗂 複製</button>
       <button data-act="delete" data-id="${z.id}"
               ${nbZones.length === 1 ? "disabled" : ""}
               title="刪除本區">🗑 刪除</button>`;
    wrap.appendChild(row);
  });
  // Event delegation for buttons
  wrap.querySelectorAll("input[type=radio]").forEach(r => {
    r.onchange = () => { nbSelectedZoneId = r.value; nbRenderZonesList(); };
  });
  wrap.querySelectorAll("button[data-act]").forEach(b => {
    b.onclick = () => nbZoneAction(b.dataset.act, b.dataset.id);
  });
}

function nbZoneAction(act, id) {
  const idx = nbZones.findIndex(z => z.id === id);
  if (idx < 0) return;
  if (act === "delete") {
    if (nbZones.length <= 1) return;
    nbZones.splice(idx, 1);
    if (nbSelectedZoneId === id) nbSelectedZoneId = nbZones[0].id;
  } else if (act === "copy") {
    const orig = nbZones[idx];
    const copy = {
      id: nbGenZoneId(), x: orig.x + 10, y: orig.y + 10,
      w: orig.w, h: orig.h,
      svg_content: orig.svg_content, content_viewbox: orig.content_viewbox,
    };
    nbZones.splice(idx + 1, 0, copy);
    nbSelectedZoneId = copy.id;
  } else if (act === "clear") {
    nbZones[idx].svg_content = null;
    nbZones[idx].content_viewbox = null;
  } else if (act === "doodle-import") {
    if (!lastDoodleSvg) {
      alert("請先在「塗鴉模式」產生一張向量圖，再回來匯入。");
      return;
    }
    const parsed = nbParseSvg(lastDoodleSvg);
    if (!parsed) { alert("向量圖解析失敗"); return; }
    nbZones[idx].svg_content = parsed.inner;
    nbZones[idx].content_viewbox = parsed.viewBox;
  } else if (act === "upload") {
    nbZoneUploadSvg(idx);   // async — re-renders itself
    return;
  } else if (act === "paste") {
    nbZonePasteSvg(idx);    // async — re-renders itself
    return;
  }
  nbRenderZonesList();
  renderNotebook(null);
}

// Phase 5x: upload a local SVG file into the zone
function nbZoneUploadSvg(zoneIdx) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".svg,image/svg+xml";
  input.style.display = "none";
  input.onchange = () => {
    const file = input.files && input.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const svgText = reader.result;
      if (typeof svgText !== "string") {
        alert("檔案讀取失敗"); return;
      }
      const parsed = nbParseSvg(svgText);
      if (!parsed) { alert("SVG 解析失敗，請確認檔案格式"); return; }
      nbZones[zoneIdx].svg_content = parsed.inner;
      nbZones[zoneIdx].content_viewbox = parsed.viewBox;
      nbRenderZonesList();
      renderNotebook(null);
    };
    reader.onerror = () => alert("讀取失敗：" + reader.error);
    reader.readAsText(file, "utf-8");
  };
  document.body.appendChild(input);
  input.click();
  // cleanup
  setTimeout(() => { if (input.parentNode) input.parentNode.removeChild(input); }, 5000);
}

// Phase 5x: paste SVG text from clipboard
async function nbZonePasteSvg(zoneIdx) {
  let svgText = null;
  // Try native clipboard API first (requires secure context + permission)
  if (navigator.clipboard && navigator.clipboard.readText) {
    try {
      svgText = await navigator.clipboard.readText();
    } catch (e) {
      // permission denied or not available — fallback below
    }
  }
  // Fallback: prompt the user to paste manually
  if (!svgText || !svgText.trim()) {
    svgText = prompt(
      "在這裡貼上 SVG 原始內容（Ctrl+V，可以是 <?xml...?> 開頭或 <svg...>）：",
      ""
    );
  }
  if (!svgText || !svgText.trim()) return;
  // Quick sanity check: must contain <svg
  if (!svgText.includes("<svg")) {
    alert("貼上的內容不像 SVG（找不到 <svg> 標籤）");
    return;
  }
  const parsed = nbParseSvg(svgText);
  if (!parsed) { alert("SVG 解析失敗"); return; }
  nbZones[zoneIdx].svg_content = parsed.inner;
  nbZones[zoneIdx].content_viewbox = parsed.viewBox;
  nbRenderZonesList();
  renderNotebook(null);
}

function nbParseSvg(svgText) {
  const xmlDoc = new DOMParser().parseFromString(svgText, "image/svg+xml");
  const srcSvg = xmlDoc.querySelector("svg");
  if (!srcSvg) return null;
  const svg = document.importNode(srcSvg, true);

  const temp = document.createElement("div");
  temp.style.cssText =
    "position:absolute; left:-99999px; top:-99999px; " +
    "width:1000px; height:1000px; overflow:hidden;";
  if (!svg.getAttribute("width"))  svg.setAttribute("width",  "500");
  if (!svg.getAttribute("height")) svg.setAttribute("height", "500");
  temp.appendChild(svg);
  document.body.appendChild(temp);

  // Phase 5s-fix v3: DESTRUCTIVELY remove background <rect>s at ANY depth
  // (v2 only scanned direct children, missing rects nested inside <g>).
  // Rule: a whitish rect that spans ≥90% of the viewBox is a background.
  const vbAttr = svg.getAttribute("viewBox");
  const declVb = vbAttr ? vbAttr.split(/\s+/).map(parseFloat) : null;

  if (declVb && declVb.length === 4) {
    const [vbX, vbY, vbW, vbH] = declVb;
    const area = vbW * vbH;
    const rects = Array.from(svg.querySelectorAll("rect"));
    for (const rect of rects) {
      const rawFill = (rect.getAttribute("fill")
                       || rect.style?.fill || "").toLowerCase().trim();
      const isWhitish = ["white", "#fff", "#ffffff", "none", "",
                          "transparent"].includes(rawFill);
      if (!isWhitish) continue;
      // Compute rect's position/size, accounting for any transform in ancestors
      let x, y, w, h;
      try {
        const bb = rect.getBBox();
        if (!bb) continue;
        x = bb.x; y = bb.y; w = bb.width; h = bb.height;
      } catch (e) { continue; }
      // Is this rect covering ≥90% of the viewBox (with some tolerance)?
      const rectArea = w * h;
      if (rectArea >= 0.9 * area
          && x <= vbX + 1 && y <= vbY + 1
          && x + w >= vbX + vbW - 1 && y + h >= vbY + vbH - 1) {
        rect.remove();
      }
    }
  }

  // Now compute the tight bbox of what's left
  let bb = null;
  try {
    const cb = svg.getBBox();
    if (cb && cb.width > 0 && cb.height > 0) {
      bb = {x: cb.x, y: cb.y, right: cb.x + cb.width,
            bottom: cb.y + cb.height};
    }
  } catch (e) { /* ignore */ }

  let viewBox = null;
  if (bb) {
    viewBox = [bb.x, bb.y, bb.right - bb.x, bb.bottom - bb.y];
  } else if (declVb && declVb.length === 4) {
    viewBox = declVb;
  } else {
    const w = parseFloat(svg.getAttribute("width")  || "100");
    const h = parseFloat(svg.getAttribute("height") || "100");
    viewBox = [0, 0, w, h];
  }

  // Debug output — user can share if the fix still doesn't work
  console.log("[nbParseSvg] declaredViewBox =", declVb,
              "| tight viewBox =", viewBox,
              "| bg rects removed =",
              svg.querySelectorAll("rect").length !==
              (xmlDoc.querySelectorAll("rect").length));

  const inner = svg.innerHTML;
  document.body.removeChild(temp);
  return {inner, viewBox};
}

document.getElementById("nb-doodle-zone").addEventListener(
  "change", () => { nbRenderZonesList(); renderNotebook(null); });

document.getElementById("nb-doodle-stretch").addEventListener(
  "change", () => renderNotebook(null));

document.getElementById("nb-zone-add").onclick = () => {
  const newZone = nbDefaultZone();
  // Stagger new zone from the last one
  if (nbZones.length > 0) {
    const last = nbZones[nbZones.length - 1];
    newZone.x = Math.min(last.x + 15, 200);
    newZone.y = Math.min(last.y + 15, 280);
  }
  nbZones.push(newZone);
  nbSelectedZoneId = newZone.id;
  document.getElementById("nb-doodle-zone").checked = true;
  nbRenderZonesList();
  renderNotebook(null);
};

function nbSetDownloadLinks(svgUrl, gcodeUrl, jsonUrl) {
  // Phase 5v: 3 download buttons next to nb-render
  const g = document.getElementById("nb-download-group");
  const s = document.getElementById("nb-download-svg");
  const c = document.getElementById("nb-download-gcode");
  const j = document.getElementById("nb-download-json");
  if (svgUrl) s.href = svgUrl;
  if (gcodeUrl) c.href = gcodeUrl;
  if (jsonUrl) j.href = jsonUrl;
  s.removeAttribute("download");   // 5ct：清 userfont blob 殘留
  s.onclick = null;
  c.style.display = "";
  j.style.display = "";
  g.style.display = "inline";
}

/** 5ct：頁面型模式（筆記/信紙）自訂字型下載接線——本頁注入後
 *  的 SVG 走前端 blob；G-code/JSON（筆順輸出）不適用先隱藏。 */
function ufPageDownloads(prefix, innerSvg, pageN, baseName) {
  const sA = document.getElementById(prefix + "-download-svg");
  const clone = innerSvg.cloneNode(true);
  clone.removeAttribute("style");
  sA.href = URL.createObjectURL(new Blob(
    [new XMLSerializer().serializeToString(clone)],
    {type: "image/svg+xml"}));
  sA.setAttribute("download", `${baseName}_userfont_p${pageN || 1}.svg`);
  sA.onclick = null;
  document.getElementById(prefix + "-download-gcode").style.display = "none";
  document.getElementById(prefix + "-download-json").style.display = "none";
  document.getElementById(prefix + "-download-group").style.display = "inline";
}

// Phase 5v: for the POST path, we can't use <a href> because body isn't in URL.
// Wrap the GET-equivalent fetch into a blob download.
async function nbDownloadViaPost(format) {
  const body = nbBuildPostBody(null);
  body.format = format;
  const r = await fetch(`${API_BASE}/api/notebook`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
  if (!r.ok) { alert("下載失敗: " + r.status); return; }
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `notebook.${format === "gcode" ? "gcode" : format}`;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
}

async function renderNotebook(pageN = null) {
  const statusEl = document.getElementById("nb-status");
  const previewEl = document.getElementById("nb-preview");
  const downloadEl = document.getElementById("nb-download");
  const navEl = document.getElementById("nb-page-nav");
  statusEl.textContent = "產生中…";
  downloadEl.style.display = "none";
  document.getElementById("nb-download-group").style.display = "none";

  // 5cz：注音開啟時先確保台灣讀音表載妥（同 5cw 字帖）
  if (document.getElementById("nb-zhuyin").checked) await ensureZhuyinTw();
  const params = nbBuildParams(false);
  if (pageN !== null) params.set("page", String(pageN));

  // Phase 5s: if any zone has svg_content, route through POST (GET URL too small)
  const doodleOn = document.getElementById("nb-doodle-zone").checked;
  const hasSvgContent = doodleOn && nbZones.some(z => z.svg_content);

  try {
    let r;
    if (hasSvgContent) {
      const body = nbBuildPostBody(pageN);
      r = await fetch(`${API_BASE}/api/notebook`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body),
      });
    } else {
      r = await fetch(`${API_BASE}/api/notebook?${params}`);
    }
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: r.statusText}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    const total = parseInt(r.headers.get("x-stroke-order-pages") || "1", 10);
    const ct = r.headers.get("content-type") || "";
    if (ct.startsWith("image/svg+xml") || pageN !== null) {
      // render inline
      const svg = await r.text();
      previewEl.innerHTML = svg;
      const innerSvg = previewEl.querySelector("svg");
      if (innerSvg) { innerSvg.style.maxWidth = "100%"; innerSvg.style.height = "auto"; }
      // Attach ruler overlay if checkbox is checked
      nbAttachRuler();
      // Phase 5r: attach drag/resize for the doodle zone if present
      nbAttachDoodleZoneInteraction();
      statusEl.textContent = `OK · ${total} 頁 · 當前 page ${pageN || 1}`;
      // page nav
      if (total > 1) {
        const buttons = [];
        for (let i = 1; i <= total; i++) {
          buttons.push(`<button data-page="${i}" style="margin:0 2px;" ${i===(pageN||1)?'class="primary"':''}>${i}</button>`);
        }
        navEl.innerHTML = buttons.join("");
        navEl.querySelectorAll("button").forEach(b =>
          b.onclick = () => renderNotebook(parseInt(b.dataset.page, 10))
        );
      } else {
        navEl.innerHTML = "";
      }
      // Phase 5v: 3 download links (SVG / G-code / JSON)
      if (hasSvgContent) {
        // POST path — wire buttons to call nbDownloadViaPost
        const svgA = document.getElementById("nb-download-svg");
        const gcA  = document.getElementById("nb-download-gcode");
        const jsA  = document.getElementById("nb-download-json");
        svgA.href = "#"; svgA.onclick = (e) => { e.preventDefault(); nbDownloadViaPost("svg"); };
        gcA.href  = "#"; gcA.onclick  = (e) => { e.preventDefault(); nbDownloadViaPost("gcode"); };
        jsA.href  = "#"; jsA.onclick  = (e) => { e.preventDefault(); nbDownloadViaPost("json"); };
        document.getElementById("nb-download-group").style.display = "inline";
      } else {
        // GET path — direct URLs with ?format=
        nbSetDownloadLinks(
          `${API_BASE}/api/notebook?${params}&download=true&format=svg`,
          `${API_BASE}/api/notebook?${params}&download=true&format=gcode`,
          `${API_BASE}/api/notebook?${params}&download=true&format=json`,
        );
      }
      // 5ct：自訂字型——本頁逐字注入（page.py data-* 錨點；EM 座標
      // 直入，transform 自帶 mm 縮放）＋本頁 SVG 前端下載
      if (document.getElementById("nb-style").value === "userfont") {
        if (gridUserFont && innerSvg) {
          const nUf = injectUserFontIntoGrid(innerSvg);
          ufPageDownloads("nb", innerSvg, pageN, "notebook");
          statusEl.textContent += ` · 自訂字型「${gridUserFontName}」` +
            `${nUf} 字（前端組裝、未上傳；多頁請逐頁切換下載）`;
        } else {
          statusEl.textContent += " · 尚未載入字型檔——請先選 TTF/OTF";
          if (!gridUserFont) {
            document.getElementById("grid-font-file").click();
          }
        }
      }
    } else if (ct.startsWith("application/zip")) {
      // Multi-page: can't preview ZIP inline, but provide per-page preview links
      previewEl.innerHTML =
        `<p>共 ${total} 頁，點擊下方頁碼可預覽/下載：</p>`;
      const buttons = [];
      for (let i = 1; i <= total; i++) {
        buttons.push(`<button data-page="${i}" style="margin:0 2px;">${i}</button>`);
      }
      navEl.innerHTML = buttons.join("");
      navEl.querySelectorAll("button").forEach(b =>
        b.onclick = () => renderNotebook(parseInt(b.dataset.page, 10))
      );
      statusEl.textContent = `${total} 頁（ZIP, ${(r.headers.get("content-length")/1024).toFixed(1)} KB）`;
      // Phase 5v: 3 download buttons for multi-page too
      nbSetDownloadLinks(
        `${API_BASE}/api/notebook?${params}&download=true&format=svg`,
        `${API_BASE}/api/notebook?${params}&download=true&format=gcode`,
        `${API_BASE}/api/notebook?${params}&download=true&format=json`,
      );
    }
  } catch (e) {
    statusEl.textContent = "";
    previewEl.innerHTML =
      `<span style="color:var(--accent);">錯誤：${e.message}</span>`;
  }
}
document.getElementById("nb-render").onclick = () => renderNotebook(null);

// ----- Phase 5n: direction-aware label (行高 ↔ 字寬) -------------------
function nbUpdateDirectionalLabel() {
  const dir = document.getElementById("nb-direction").value;
  const lbl = document.getElementById("nb-lineh-label");
  if (lbl) lbl.textContent = (dir === "vertical") ? "字寬 (mm)" : "行高 (mm)";
  // Hint text on first-line-offset
  const flTip = document.getElementById("nb-first-line-label");
  if (flTip) {
    flTip.title = (dir === "vertical")
      ? "直書: 第一欄左緣距頁面右邊緣 mm；留空用 [邊緣留白+字寬]"
      : "橫書: 第一行下緣距頁面頂端 mm；留空用 [邊緣留白+行高]";
  }
}
document.getElementById("nb-direction").addEventListener(
  "change", nbUpdateDirectionalLabel);
nbUpdateDirectionalLabel();

// ----- Phase 5n: ruler overlay + hover/click guide lines ---------------
function nbAttachRuler() {
  _attachRulerToPreview({
    previewEl: document.getElementById("nb-preview"),
    showRuler: document.getElementById("nb-show-ruler").checked,
    direction: document.getElementById("nb-direction").value,
  });
}

// Phase 5y: shared ruler implementation used by notebook + letter modes
function _attachRulerToPreview({previewEl, showRuler, direction}) {
  const wrap = previewEl;
  // Remove any existing ruler wrapper to prevent duplication
  const existing = wrap.querySelector(".nb-ruler-wrap");
  if (existing) existing.remove();
  if (!showRuler) return;
  const svg = wrap.querySelector("svg");
  if (!svg) return;

  // Get page dimensions from viewBox
  const vb = svg.getAttribute("viewBox");
  if (!vb) return;
  const parts = vb.split(/\s+/).map(parseFloat);
  const pageW = parts[2];
  const pageH = parts[3];
  const dir = direction;

  // Move the SVG into a positioned container with ruler overlays
  const container = document.createElement("div");
  container.className = "nb-ruler-wrap";
  container.style.cssText = "position:relative; display:inline-block;";
  svg.parentNode.insertBefore(container, svg);
  container.appendChild(svg);

  // Helper to build a ruler SVG
  function buildRuler(orientation, reverseFromRight = false) {
    // orientation: "horizontal" (top) or "vertical" (side)
    const size = 12;  // px thickness of ruler bar
    const overlayWidth = orientation === "horizontal" ? pageW : size;
    const overlayHeight = orientation === "horizontal" ? size : pageH;
    const rulerSvg = document.createElementNS(
      "http://www.w3.org/2000/svg", "svg");
    rulerSvg.setAttribute("viewBox",
      `0 0 ${overlayWidth} ${overlayHeight}`);
    rulerSvg.classList.add(
      orientation === "horizontal" ? "nb-ruler-top" : "nb-ruler-side");
    rulerSvg.setAttribute("preserveAspectRatio", "none");
    // Background
    const bg = document.createElementNS(
      "http://www.w3.org/2000/svg", "rect");
    bg.setAttribute("x", "0");
    bg.setAttribute("y", "0");
    bg.setAttribute("width", overlayWidth);
    bg.setAttribute("height", overlayHeight);
    bg.setAttribute("fill", "#f8f8f8");
    bg.setAttribute("stroke", "#ccc");
    bg.setAttribute("stroke-width", "0.15");
    rulerSvg.appendChild(bg);

    // Ticks: major=10mm, medium=5mm, minor=1mm
    const maxVal = (orientation === "horizontal") ? pageW : pageH;
    for (let v = 0; v <= maxVal + 0.01; v += 1) {
      const isMajor = (Math.round(v) % 10) === 0;
      const isMedium = (Math.round(v) % 5) === 0 && !isMajor;
      let tickLen;
      if (isMajor) tickLen = size * 0.65;
      else if (isMedium) tickLen = size * 0.4;
      else tickLen = size * 0.18;
      const tick = document.createElementNS(
        "http://www.w3.org/2000/svg", "line");
      if (orientation === "horizontal") {
        // displayed value: reverseFromRight ? pageW - v : v
        const displayV = reverseFromRight ? (pageW - v) : v;
        tick.setAttribute("x1", v);
        tick.setAttribute("y1", overlayHeight - tickLen);
        tick.setAttribute("x2", v);
        tick.setAttribute("y2", overlayHeight);
        // skip label (handle separately)
      } else {
        tick.setAttribute("x1", overlayWidth - tickLen);
        tick.setAttribute("y1", v);
        tick.setAttribute("x2", overlayWidth);
        tick.setAttribute("y2", v);
      }
      tick.setAttribute("stroke", isMajor ? "#444" : "#888");
      tick.setAttribute("stroke-width", isMajor ? "0.25" : "0.15");
      rulerSvg.appendChild(tick);

      // Label (only on major ticks, skipping 0)
      if (isMajor && v > 0 && v < maxVal - 1) {
        const label = document.createElementNS(
          "http://www.w3.org/2000/svg", "text");
        label.textContent = reverseFromRight ? String(pageW - v) : String(v);
        label.setAttribute("font-size", "2");
        label.setAttribute("font-family", "sans-serif");
        label.setAttribute("fill", "#666");
        if (orientation === "horizontal") {
          label.setAttribute("x", v);
          label.setAttribute("y", overlayHeight * 0.45);
          label.setAttribute("text-anchor", "middle");
        } else {
          label.setAttribute("x", overlayWidth * 0.35);
          label.setAttribute("y", v + 0.7);
          label.setAttribute("text-anchor", "end");
        }
        rulerSvg.appendChild(label);
      }
    }
    return {svg: rulerSvg, size};
  }

  // Top ruler
  const topR = buildRuler("horizontal");
  topR.svg.style.cssText = (
    "position:absolute; left:0; top:-14px; " +
    "width:100%; height:12px; pointer-events:auto; z-index:2;");
  container.appendChild(topR.svg);

  // Side ruler (left for horizontal, right for vertical)
  const sideOrientation = "vertical";
  const sideR = buildRuler(sideOrientation);
  if (dir === "horizontal") {
    sideR.svg.style.cssText = (
      "position:absolute; top:0; left:-14px; " +
      "width:12px; height:100%; pointer-events:auto; z-index:2;");
  } else {
    sideR.svg.style.cssText = (
      "position:absolute; top:0; right:-14px; " +
      "width:12px; height:100%; pointer-events:auto; z-index:2;");
  }
  container.appendChild(sideR.svg);

  // Hover guide lines + click pin logic
  const guide = document.createElementNS(
    "http://www.w3.org/2000/svg", "svg");
  guide.setAttribute("viewBox", `0 0 ${pageW} ${pageH}`);
  guide.setAttribute("preserveAspectRatio", "none");
  guide.style.cssText = (
    "position:absolute; top:0; left:0; " +
    "width:100%; height:100%; pointer-events:none; z-index:3;");
  container.appendChild(guide);

  // Tooltip
  const tip = document.createElement("div");
  tip.style.cssText = (
    "position:absolute; background:#333; color:white; " +
    "padding:2px 6px; border-radius:3px; font-size:11px; " +
    "pointer-events:none; z-index:4; display:none; " +
    "font-family:sans-serif;");
  container.appendChild(tip);

  let pinned = null;  // {x_mm, y_mm} or null

  function drawGuides(x_mm, y_mm, kind) {
    // kind: "hover" (grey dashed, faint) or "pinned" (blue solid)
    // Redraw all guides: first pinned (if any), then hover current
    guide.innerHTML = "";
    function addLines(xmm, ymm, stroke, dash, width) {
      const vline = document.createElementNS(
        "http://www.w3.org/2000/svg", "line");
      vline.setAttribute("x1", xmm); vline.setAttribute("x2", xmm);
      vline.setAttribute("y1", 0);   vline.setAttribute("y2", pageH);
      vline.setAttribute("stroke", stroke);
      vline.setAttribute("stroke-width", width);
      if (dash) vline.setAttribute("stroke-dasharray", dash);
      guide.appendChild(vline);
      const hline = document.createElementNS(
        "http://www.w3.org/2000/svg", "line");
      hline.setAttribute("x1", 0);     hline.setAttribute("x2", pageW);
      hline.setAttribute("y1", ymm);   hline.setAttribute("y2", ymm);
      hline.setAttribute("stroke", stroke);
      hline.setAttribute("stroke-width", width);
      if (dash) hline.setAttribute("stroke-dasharray", dash);
      guide.appendChild(hline);
    }
    if (pinned) addLines(pinned.x_mm, pinned.y_mm, "#0066cc", null, 0.25);
    if (kind === "hover" && x_mm != null)
      addLines(x_mm, y_mm, "#888", "1 1", 0.15);
  }

  function updateTooltip(x_mm, y_mm, ev) {
    if (x_mm == null) { tip.style.display = "none"; return; }
    const rightDist = pageW - x_mm;
    const bottomDist = pageH - y_mm;
    tip.innerHTML = (dir === "vertical")
      ? `右 ${rightDist.toFixed(1)} · 頂 ${y_mm.toFixed(1)} mm`
      : `左 ${x_mm.toFixed(1)} · 頂 ${y_mm.toFixed(1)} mm`;
    const rect = container.getBoundingClientRect();
    const offsetX = ev.clientX - rect.left + 14;
    const offsetY = ev.clientY - rect.top + 10;
    tip.style.left = `${offsetX}px`;
    tip.style.top = `${offsetY}px`;
    tip.style.display = "block";
  }

  function pointToMm(ev) {
    const rect = svg.getBoundingClientRect();
    const mm_x = (ev.clientX - rect.left) / rect.width * pageW;
    const mm_y = (ev.clientY - rect.top) / rect.height * pageH;
    return {x_mm: mm_x, y_mm: mm_y};
  }

  // Hover on SVG → guide lines track cursor
  svg.style.cursor = "crosshair";
  svg.addEventListener("mousemove", ev => {
    const {x_mm, y_mm} = pointToMm(ev);
    if (x_mm < 0 || x_mm > pageW || y_mm < 0 || y_mm > pageH) {
      drawGuides(null, null, "hover");
      tip.style.display = "none";
      return;
    }
    drawGuides(x_mm, y_mm, "hover");
    updateTooltip(x_mm, y_mm, ev);
  });
  svg.addEventListener("mouseleave", () => {
    drawGuides(null, null, "hover");
    tip.style.display = "none";
  });

  // Click on SVG or on ruler → pin guide at clicked position
  function pinAt(ev) {
    const {x_mm, y_mm} = pointToMm(ev);
    if (x_mm >= 0 && x_mm <= pageW && y_mm >= 0 && y_mm <= pageH) {
      pinned = {x_mm, y_mm};
      drawGuides(x_mm, y_mm, "hover");
    }
  }
  svg.addEventListener("click", pinAt);
  topR.svg.addEventListener("click", pinAt);
  sideR.svg.addEventListener("click", pinAt);
}
document.getElementById("nb-show-ruler").addEventListener(
  "change", nbAttachRuler);

// ==============================================================
// Phase 5r: interactive doodle zone — drag to move, 4 corners to resize
// ==============================================================
function nbAttachDoodleZoneInteraction() {
  const previewEl = document.getElementById("nb-preview");
  if (!document.getElementById("nb-doodle-zone").checked) return;
  const svg = previewEl.querySelector("svg");
  if (!svg) return;

  // Phase 5s: use the SELECTED zone from nbZones state (not first rect in SVG)
  const selZone = nbZones.find(z => z.id === nbSelectedZoneId);
  if (!selZone) return;

  // Read page viewBox → mm
  const vb = svg.getAttribute("viewBox");
  if (!vb) return;
  const [_, __, pageW, pageH] = vb.split(/\s+/).map(parseFloat);

  const zx0 = selZone.x, zy0 = selZone.y;
  const zw0 = selZone.w, zh0 = selZone.h;

  // Get cell size for snap-to-grid
  const lineh = parseFloat(
    document.getElementById("nb-lineh").value ||
    document.getElementById("nb-lineh").placeholder || "15");
  const snap = isFinite(lineh) && lineh > 0 ? lineh : 15;

  // Margins (approximate, from preset)
  // Use saved default from capacity response if available, else fallback
  const mgInput = document.getElementById("nb-margin");
  const mg = parseFloat(mgInput.value || mgInput.placeholder || "15") || 15;
  const contentX = mg, contentY = mg;
  const contentW = pageW - 2 * mg, contentH = pageH - 2 * mg;

  // Minimum zone = 2 cells × 2 cells (D2 rule)
  const MIN_ZONE = Math.max(10, snap * 2);

  // Mount an overlay SVG on top of the preview
  // (the preview might already be wrapped by ruler — handle both cases)
  const wrap = previewEl.querySelector(".nb-ruler-wrap") || previewEl;
  // Clean up any previous overlay
  const oldOverlay = wrap.querySelector(".nb-zone-overlay");
  if (oldOverlay) oldOverlay.remove();

  const overlay = document.createElementNS(
    "http://www.w3.org/2000/svg", "svg");
  overlay.classList.add("nb-zone-overlay");
  overlay.setAttribute("viewBox", vb);
  overlay.setAttribute("preserveAspectRatio", "none");
  overlay.style.cssText =
    "position:absolute; top:0; left:0; width:100%; height:100%; " +
    "pointer-events:none; z-index:4;";
  if (wrap !== previewEl) {
    wrap.appendChild(overlay);
  } else {
    // Ensure preview has relative positioning so absolute overlays work
    if (!svg.style.position) {
      previewEl.style.position = "relative";
      svg.style.position = "relative";
    }
    previewEl.appendChild(overlay);
  }

  // Build body (drag) + 4 corner handles, all pointer-events:auto
  function buildHandles(zx, zy, zw, zh) {
    overlay.innerHTML = "";
    // Body rect (drag)
    const body = document.createElementNS(
      "http://www.w3.org/2000/svg", "rect");
    body.setAttribute("x", zx);
    body.setAttribute("y", zy);
    body.setAttribute("width", zw);
    body.setAttribute("height", zh);
    body.setAttribute("fill", "rgba(100,150,220,0.05)");
    body.setAttribute("stroke", "#3a7bd5");
    body.setAttribute("stroke-width", "0.4");
    body.setAttribute("stroke-dasharray", "2 2");
    body.style.cursor = "move";
    body.style.pointerEvents = "auto";
    body.dataset.handle = "body";
    overlay.appendChild(body);

    // 4 corner handles (NW NE SW SE) — small squares
    const handleSize = 3;  // mm in viewBox space
    const corners = [
      {name: "nw", x: zx,          y: zy,          cur: "nwse-resize"},
      {name: "ne", x: zx + zw,     y: zy,          cur: "nesw-resize"},
      {name: "sw", x: zx,          y: zy + zh,     cur: "nesw-resize"},
      {name: "se", x: zx + zw,     y: zy + zh,     cur: "nwse-resize"},
    ];
    for (const c of corners) {
      const h = document.createElementNS(
        "http://www.w3.org/2000/svg", "rect");
      h.setAttribute("x", c.x - handleSize / 2);
      h.setAttribute("y", c.y - handleSize / 2);
      h.setAttribute("width", handleSize);
      h.setAttribute("height", handleSize);
      h.setAttribute("fill", "#3a7bd5");
      h.style.cursor = c.cur;
      h.style.pointerEvents = "auto";
      h.dataset.handle = c.name;
      overlay.appendChild(h);
    }

    // Label showing X,Y,W,H during hover/drag
    const label = document.createElementNS(
      "http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", zx + zw / 2);
    label.setAttribute("y", zy - 1.5);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("font-size", "2.5");
    label.setAttribute("font-family", "sans-serif");
    label.setAttribute("fill", "#3a7bd5");
    label.textContent =
      `${Math.round(zx)}, ${Math.round(zy)} · ${Math.round(zw)}×${Math.round(zh)} mm`;
    overlay.appendChild(label);
  }
  buildHandles(zx0, zy0, zw0, zh0);

  // Snap helper (A1: snap to cell_size)
  function snapVal(v) {
    return Math.round(v / snap) * snap;
  }

  // Event coord translate to mm
  function toMm(ev) {
    const rect = svg.getBoundingClientRect();
    const x = (ev.clientX - rect.left) / rect.width * pageW;
    const y = (ev.clientY - rect.top) / rect.height * pageH;
    return {x, y};
  }

  let dragging = null;  // {handle, startMouse, startZone}

  overlay.addEventListener("mousedown", ev => {
    const el = ev.target;
    const handle = el.dataset && el.dataset.handle;
    if (!handle) return;
    ev.preventDefault();
    const m = toMm(ev);
    // Read current zone pos from the label values
    const body = overlay.querySelector('[data-handle="body"]');
    const cur = {
      x: parseFloat(body.getAttribute("x")),
      y: parseFloat(body.getAttribute("y")),
      w: parseFloat(body.getAttribute("width")),
      h: parseFloat(body.getAttribute("height")),
    };
    dragging = {handle, startMouse: m, startZone: cur};
    document.body.style.userSelect = "none";
  });

  function onMove(ev) {
    if (!dragging) return;
    const m = toMm(ev);
    const dx = m.x - dragging.startMouse.x;
    const dy = m.y - dragging.startMouse.y;
    const s = dragging.startZone;
    let nx = s.x, ny = s.y, nw = s.w, nh = s.h;
    switch (dragging.handle) {
      case "body":
        nx = snapVal(s.x + dx);
        ny = snapVal(s.y + dy);
        break;
      case "nw":
        nx = snapVal(s.x + dx);
        ny = snapVal(s.y + dy);
        nw = s.w + (s.x - nx);
        nh = s.h + (s.y - ny);
        break;
      case "ne":
        ny = snapVal(s.y + dy);
        nw = snapVal(s.w + dx);
        nh = s.h + (s.y - ny);
        break;
      case "sw":
        nx = snapVal(s.x + dx);
        nw = s.w + (s.x - nx);
        nh = snapVal(s.h + dy);
        break;
      case "se":
        nw = snapVal(s.w + dx);
        nh = snapVal(s.h + dy);
        break;
    }
    // Enforce min size
    nw = Math.max(MIN_ZONE, nw);
    nh = Math.max(MIN_ZONE, nh);
    // Enforce boundaries (keep zone inside content area)
    nx = Math.max(contentX, Math.min(nx, contentX + contentW - nw));
    ny = Math.max(contentY, Math.min(ny, contentY + contentH - nh));
    nw = Math.min(nw, contentX + contentW - nx);
    nh = Math.min(nh, contentY + contentH - ny);
    buildHandles(nx, ny, nw, nh);
  }

  function onUp() {
    if (!dragging) return;
    document.body.style.userSelect = "";
    dragging = null;
    // Phase 5s: update the selected zone in nbZones state
    const body = overlay.querySelector('[data-handle="body"]');
    if (body) {
      const z = nbZones.find(zz => zz.id === nbSelectedZoneId);
      if (z) {
        z.x = parseFloat(body.getAttribute("x"));
        z.y = parseFloat(body.getAttribute("y"));
        z.w = parseFloat(body.getAttribute("width"));
        z.h = parseFloat(body.getAttribute("height"));
      }
      nbRenderZonesList();
      // Trigger full re-render so text flows around new zones
      renderNotebook(null);
    }
  }

  // Register global listeners (so we catch mouseup outside overlay)
  document.addEventListener("mousemove", onMove);
  document.addEventListener("mouseup", onUp);
  // Clean up on next render (handlers removed when overlay is replaced)
}

