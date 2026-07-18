// ============================================================
// WordArt (文字雲) mode
// ============================================================

// Phase 5b r1: 「規則多邊形」optgroup 整併進「多邊形 (自訂 N 邊)」。
// shape="polygon" 時 sides 從 #wa-sides-n input 讀；舊的 shorthand value
// (triangle/square/...) 後端仍支援，前端只當 backward-compat fallback
// 應對舊 query string / persisted state。
const POLYGON_SIDES = {triangle:3, square:4, pentagon:5, hexagon:6,
                       heptagon:7, octagon:8, nonagon:9, decagon:10};

function waIsPolygon() {
  const s = document.getElementById("wa-shape").value;
  return s === "polygon" || POLYGON_SIDES[s] !== undefined;
}

function waCurrentSides() {
  const s = document.getElementById("wa-shape").value;
  if (s === "polygon") {
    const el = document.getElementById("wa-sides-n");
    let n = el ? parseInt(el.value, 10) : 3;
    if (!Number.isFinite(n) || n < 3) n = 3;
    if (n > 20) n = 20;
    return n;
  }
  return POLYGON_SIDES[s] || 0;
}

function waRebuildEdgeInputs() {
  const container = document.getElementById("wa-edge-inputs");
  const sides = waCurrentSides();
  const layout = document.getElementById("wa-layout").value;
  const isLinear = layout === "linear";
  if (!(isLinear && sides > 0)) return;
  // 保留現有 input 文字（rebuild 不該丟資料）
  const existing = container.querySelectorAll("input[data-edge]");
  const currentVals = [...existing].map(el => el.value);
  container.innerHTML = "";
  // Phase 5b r2: 每邊一行 = label + input + (非最後一邊) 「↓ 複製到下一個邊」按鈕。
  // 用 DOM API 而非 innerHTML 字串拼接，避免 user 輸入含 quote / `<` 時破版面。
  for (let i = 0; i < sides; i++) {
    const row = document.createElement("div");
    row.style.cssText =
      "margin:4px 0;display:flex;align-items:center;gap:6px;flex-wrap:wrap;";

    const lbl = document.createElement("label");
    lbl.textContent = `邊 ${i + 1}`;
    lbl.style.minWidth = "60px";
    row.appendChild(lbl);

    const inp = document.createElement("input");
    inp.type = "text";
    inp.dataset.edge = String(i);
    inp.value = currentVals[i] || "";
    inp.placeholder = "這邊的文字";
    inp.style.cssText = "flex:1;min-width:200px;max-width:300px;";
    row.appendChild(inp);

    // 最後一邊沒有「下一個」可複製，省略按鈕
    if (i < sides - 1) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = `↓ 複製到下一個邊`;
      btn.title = `複製邊 ${i + 1} 文字到邊 ${i + 2}（覆蓋）`;
      btn.style.cssText =
        "padding:3px 10px;font-size:11px;line-height:1;cursor:pointer;" +
        "border:1px solid var(--border);border-radius:3px;" +
        "background:#fcfcfc;color:#456;";
      btn.addEventListener("click", () => {
        const src = container.querySelector(`input[data-edge="${i}"]`);
        const dst = container.querySelector(`input[data-edge="${i + 1}"]`);
        if (src && dst) dst.value = src.value;
      });
      row.appendChild(btn);
    }

    container.appendChild(row);
  }
}

// Phase 5b r2: broadcast 邊 1 文字到所有其他邊
function waBroadcastEdge1() {
  const inputs = document.querySelectorAll(
    "#wa-edge-inputs input[data-edge]");
  if (inputs.length < 2) return;
  const v = inputs[0].value;
  for (let i = 1; i < inputs.length; i++) inputs[i].value = v;
}

function waUpdatePanels() {
  const layout = document.getElementById("wa-layout").value;
  const sides = waCurrentSides();
  const rows = {
    text: document.getElementById("wa-text-row"),
    edges: document.getElementById("wa-edges-row"),
    three: document.getElementById("wa-three-row"),
    cloud: document.getElementById("wa-cloud-row"),
    ring: document.getElementById("wa-ring-row"),
    grad: document.getElementById("wa-grad-row"),
    split: document.getElementById("wa-split-row"),
    // Phase 5an
    gradH: document.getElementById("wa-grad-h-row"),
    wave:  document.getElementById("wa-wave-row"),
    radial:document.getElementById("wa-radial-row"),
  };
  // Hide all
  for (const k in rows) rows[k].style.display = "none";

  // Show relevant rows per layout
  if (layout === "ring" || layout === "fill") {
    rows.text.style.display = "";
  } else if (layout === "linear") {
    if (sides > 0) {
      rows.edges.style.display = "";
    } else {
      rows.text.style.display = "";  // fallback
    }
  } else if (layout === "three_band") {
    rows.three.style.display = "";
  } else if (layout === "wordcloud") {
    rows.cloud.style.display = "";
  } else if (layout === "concentric") {
    rows.ring.style.display = "";
  } else if (layout === "gradient_v") {
    rows.text.style.display = "";
    rows.grad.style.display = "";
    rows.cloud.style.display = "";  // reuse min/max/padding inputs
  } else if (layout === "split_lr") {
    rows.split.style.display = "";
  // Phase 5an
  } else if (layout === "gradient_h") {
    rows.text.style.display = "";
    rows.gradH.style.display = "";
    rows.cloud.style.display = "";   // reuse min/max
  } else if (layout === "wave") {
    rows.text.style.display = "";
    rows.wave.style.display = "";
  } else if (layout === "radial_convex" || layout === "radial_concave") {
    rows.text.style.display = "";
    rows.radial.style.display = "";
    rows.cloud.style.display = "";   // reuse min/max
  }
  waRebuildEdgeInputs();
  // Phase 5b r1: 同步邊數 counter（hidden input → visible label + button states）
  if (typeof waSyncSidesCounter === "function") waSyncSidesCounter();
}

function waBuildParams(forCapacity = false) {
  const g = (id) => document.getElementById(id).value;
  const layout = g("wa-layout");
  const params = new URLSearchParams({
    shape: g("wa-shape"),
    shape_size_mm: g("wa-size"),
    aspect: g("wa-aspect"),
    sides: String(waCurrentSides() || 6),
    char_size_mm: g("wa-charsize"),
    layout: layout,
    page_width_mm: g("wa-pw"),
    page_height_mm: g("wa-ph"),
  });
  // capacity-relevant params
  if (layout === "three_band") params.set("mid_ratio", g("wa-mid-ratio"));
  if (layout === "wordcloud" || layout === "gradient_v"
      // Phase 5an: gradient_h + radial both consume min/max size
      || layout === "gradient_h"
      || layout === "radial_convex" || layout === "radial_concave") {
    params.set("min_size_mm", g("wa-min-size"));
    params.set("max_size_mm", g("wa-max-size"));
  }
  if (forCapacity) return params;

  params.set("orientation", g("wa-orient"));
  params.set("source", g("wa-source"));
  params.set("style", g("wa-style"));
  params.set("cns_outline_mode", g("wa-cns-mode"));
  params.set("show_shape_outline",
             document.getElementById("wa-outline").checked ? "true" : "false");
  params.set("auto_cycle",
             document.getElementById("wa-auto-cycle").checked ? "true" : "false");
  params.set("auto_fit",
             document.getElementById("wa-auto-fit").checked ? "true" : "false");
  params.set("min_char_size_mm", g("wa-min-char"));
  params.set("align", g("wa-align"));
  params.set("direction", g("wa-direction"));

  if (layout === "linear" && waIsPolygon()) {
    const edgeInputs = document.querySelectorAll("#wa-edge-inputs [data-edge]");
    const texts = [...edgeInputs].map(el => el.value);
    params.set("texts_per_edge", texts.join("|"));
    const eg = g("wa-edge-groups").trim();
    if (eg) params.set("edge_groups", eg);
    params.set("edge_start", g("wa-edge-start"));
    params.set("edge_direction", g("wa-edge-direction"));
  } else if (layout === "three_band") {
    params.set("text_top", g("wa-top"));
    params.set("text_mid", g("wa-mid"));
    params.set("text_bot", g("wa-bot"));
    params.set("orient_top", g("wa-orient-top"));
    params.set("orient_mid", g("wa-orient-mid"));
    params.set("orient_bot", g("wa-orient-bot"));
  } else if (layout === "wordcloud") {
    params.set("tokens", g("wa-tokens"));
    params.set("weight_mode", g("wa-weight-mode"));
    params.set("padding_mm", g("wa-padding"));
  } else if (layout === "concentric") {
    params.set("texts_per_ring", g("wa-rings"));
  } else if (layout === "gradient_v") {
    params.set("text", g("wa-text"));
    params.set("gradient_dir", g("wa-grad-dir"));
  } else if (layout === "split_lr") {
    params.set("text_left", g("wa-left"));
    params.set("text_right", g("wa-right"));
  // Phase 5an
  } else if (layout === "gradient_h") {
    params.set("text", g("wa-text"));
    params.set("gradient_h_dir", g("wa-grad-h-dir"));
  } else if (layout === "wave") {
    params.set("text", g("wa-text"));
    const amp = g("wa-wave-amp"), len = g("wa-wave-len");
    if (amp !== "") params.set("wave_amplitude_mm", amp);
    if (len !== "") params.set("wave_wavelength_mm", len);
    params.set("wave_lines", g("wa-wave-lines"));
    params.set("wave_tangent_rotation",
               document.getElementById("wa-wave-tangent").checked ? "true" : "false");
  } else if (layout === "radial_convex" || layout === "radial_concave") {
    params.set("text", g("wa-text"));
  } else {
    params.set("text", g("wa-text"));
  }
  return params;
}

let waCapacityTimer = null;
function scheduleWaCapacity() {
  if (waCapacityTimer) clearTimeout(waCapacityTimer);
  waCapacityTimer = setTimeout(fetchWaCapacity, 300);
}

async function fetchWaCapacity() {
  const el = document.getElementById("wa-capacity");
  try {
    const r = await fetch(`${API_BASE}/api/wordart/capacity?` + waBuildParams(true));
    if (!r.ok) { el.textContent = "計算失敗 (" + r.status + ")"; return; }
    const d = await r.json();
    const layout = d.layout;
    let hint = "";
    if (layout === "ring") {
      hint = `一整圈需要 <b>${d.min_chars_for_full_ring}</b> 字<br/>`
           + `（周長 ${d.shape_perimeter_mm.toFixed(0)} mm，字大小 ${d.char_size_mm} mm）`
           + (d.min_chars_for_full_ring < 4
              ? ` <span style="color:#a60;">⚠ 字太大，圈太小</span>` : "");
    } else if (layout === "fill") {
      hint = `填滿需要 <b>${d.min_chars_for_full_fill}</b> 字<br/>`
           + `（字太大則填不滿；字太小可容納更多）`;
    } else if (layout === "linear") {
      const per = (d.min_chars_per_edge || []).join(", ");
      hint = `每邊各需：[${per}] 字<br/>`
           + `全部邊加總需要 <b>${d.min_chars_for_all_edges}</b> 字`;
    } else if (layout === "three_band") {
      hint = `上弧 <b>${d.top}</b> 字 · 中線 <b>${d.mid}</b> 字 · 下弧 <b>${d.bot}</b> 字`
           + `<br/>三段合計最多 <b>${d.top + d.mid + d.bot}</b> 字`;
    } else if (layout === "concentric") {
      hint = `最多 <b>${d.max_rings}</b> 環；最外環容納 <b>${d.outer_ring_chars}</b> 字`
           + `<br/>（每環字數隨半徑遞減）`;
    } else if (layout === "gradient_v") {
      hint = `約可容納 <b>${d.approx_chars}</b> 字（依字大小漸變而異）`;
    } else if (layout === "split_lr") {
      hint = `左右合計約 <b>${d.approx_chars}</b> 字（各半約 ${Math.floor(d.approx_chars/2)} 字）`;
    } else if (layout === "wordcloud") {
      hint = `約可放置 <b>${d.approx_max_tokens}</b> 個 token`
           + `<br/>（字大小 ${d.min_size_mm}–${d.max_size_mm} mm，按 7 級分配）`;
    // Phase 5an
    } else if (layout === "gradient_h") {
      hint = `約可容納 <b>${d.approx_chars}</b> 字（依字大小漸變而異）`;
    } else if (layout === "wave") {
      hint = `沿曲線約可放 <b>${d.approx_chars}</b> 字（與波線數、形狀相關）`;
    } else if (layout === "radial_convex" || layout === "radial_concave") {
      const where = layout === "radial_convex" ? "中央大邊緣小（凸）" : "中央小邊緣大（凹）";
      hint = `約可容納 <b>${d.approx_chars}</b> 字 — ${where}`;
    }
    if (d.clamped) {
      hint += `<br/><span style="color:#a60;">⚠ 形狀被限縮至頁面範圍內</span>`;
    }
    el.innerHTML = hint;
  } catch (e) {
    el.textContent = "計算失敗：" + e.message;
  }
}

async function renderWordart() {
  const statusEl = document.getElementById("wa-status");
  const previewEl = document.getElementById("wa-preview");
  const downloadEl = document.getElementById("wa-download");
  statusEl.textContent = "產生中…";
  downloadEl.style.display = "none";

  const params = waBuildParams(false);
  try {
    const r = await fetch(`${API_BASE}/api/wordart?` + params);
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: r.statusText}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    const svg = await r.text();
    previewEl.innerHTML = svg;
    const innerSvg = previewEl.querySelector("svg");
    if (innerSvg) { innerSvg.style.maxWidth = "100%"; innerSvg.style.height = "auto"; }
    const placed = r.headers.get("x-wordart-placed") || "?";
    const cap = r.headers.get("x-wordart-capacity") || "?";
    const reqSize = parseFloat(r.headers.get("x-wordart-requested-size") || "0");
    const actualSize = parseFloat(r.headers.get("x-wordart-fitted-size") || "0");
    const dropped = r.headers.get("x-wordart-dropped");
    let msg = `已放置 ${placed} 字（容量 ${cap}）`;
    if (reqSize && actualSize && Math.abs(reqSize - actualSize) > 0.1) {
      msg += ` · 🔽 自動縮小至 ${actualSize.toFixed(1)} mm（原 ${reqSize.toFixed(1)} mm）`;
    }
    if (dropped) msg += ` · ⚠ 丟棄 ${dropped} 個 token`;
    statusEl.textContent = msg;
    // Download via blob
    const blob = new Blob([svg], {type: "image/svg+xml"});
    const url = URL.createObjectURL(blob);
    downloadEl.href = url;
    downloadEl.setAttribute("download", "wordart.svg");
    downloadEl.style.display = "inline-block";
  } catch (e) {
    statusEl.textContent = "";
    previewEl.innerHTML =
      `<span style="color:var(--accent);">錯誤：${e.message}</span>`;
  }
}

// Wire up reactivity
for (const id of ["wa-shape", "wa-size", "wa-aspect", "wa-charsize",
                  "wa-layout", "wa-pw", "wa-ph", "wa-mid-ratio",
                  "wa-min-size", "wa-max-size"]) {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener("input", scheduleWaCapacity);
    el.addEventListener("change", scheduleWaCapacity);
  }
}
// shape + layout changes → rebuild panel visibility + edge inputs
document.getElementById("wa-shape").addEventListener("change", waUpdatePanels);
document.getElementById("wa-layout").addEventListener("change", waUpdatePanels);

// Phase 5b r1: polygon 邊數 N 控制（+/− 按鈕；N 存在 hidden input）
function waSyncSidesCounter() {
  const el = document.getElementById("wa-sides-n");
  const lbl = document.getElementById("wa-sides-count");
  if (el && lbl) lbl.textContent = String(el.value || "3");
  // 邊數到上下限時 disable 對應按鈕，給視覺回饋
  const inc = document.getElementById("wa-sides-inc");
  const dec = document.getElementById("wa-sides-dec");
  const n = parseInt(el?.value || "3", 10);
  if (inc) inc.disabled = (n >= 20);
  if (dec) dec.disabled = (n <= 3);
  if (inc) inc.style.opacity = inc.disabled ? "0.4" : "1";
  if (dec) dec.style.opacity = dec.disabled ? "0.4" : "1";
}
function waBumpSides(delta) {
  const el = document.getElementById("wa-sides-n");
  if (!el) return;
  let n = parseInt(el.value, 10);
  if (!Number.isFinite(n)) n = 3;
  n = Math.max(3, Math.min(20, n + delta));
  el.value = String(n);
  waSyncSidesCounter();
  waUpdatePanels();
  scheduleWaCapacity();
}
document.getElementById("wa-sides-inc")?.addEventListener("click",
  () => waBumpSides(+1));
document.getElementById("wa-sides-dec")?.addEventListener("click",
  () => waBumpSides(-1));
document.getElementById("wa-edge-broadcast")?.addEventListener("click",
  waBroadcastEdge1);

document.getElementById("wa-render").onclick = renderWordart;

