// W4-R2：本檔為 ES module。lastDoodleSvg 為 notebook.js 宣告的全域
// binding（module 可見可賦值）——塗鴉→筆記引用鏈不變。
// ============================================================
// Doodle (塗鴉) mode
// ============================================================
let ddAnnRowCount = 0;
function addDoodleAnnRow(x = 10, y = 10, text = "", size = 3.5) {
  const wrap = document.getElementById("dd-annotations");
  const id = ++ddAnnRowCount;
  const row = document.createElement("div");
  row.className = "row";
  row.style.margin = "4px 0";
  row.dataset.annId = id;
  row.innerHTML = `
    <input type="text" placeholder="註解文字" value="${text}" data-k="text" style="width:150px;">
    <label style="color:var(--muted);">x</label>
    <input type="number" value="${x}" data-k="x" style="width:60px;" step="0.5">
    <label style="color:var(--muted);">y</label>
    <input type="number" value="${y}" data-k="y" style="width:60px;" step="0.5">
    <label style="color:var(--muted);">大小</label>
    <input type="number" value="${size}" data-k="size" style="width:60px;" step="0.5" min="1" max="20">
    <button data-del="1">✕</button>
  `;
  row.querySelector('button[data-del="1"]').onclick = () => row.remove();
  wrap.appendChild(row);
}
document.getElementById("dd-add-ann").onclick = () => addDoodleAnnRow();

function collectDoodleAnnotations() {
  const rows = document.querySelectorAll("#dd-annotations > .row");
  const anns = [];
  rows.forEach(r => {
    const text = r.querySelector('[data-k="text"]').value;
    if (!text) return;
    anns.push({
      text,
      x_mm: parseFloat(r.querySelector('[data-k="x"]').value),
      y_mm: parseFloat(r.querySelector('[data-k="y"]').value),
      size_mm: parseFloat(r.querySelector('[data-k="size"]').value),
    });
  });
  return anns;
}

// Phase 5ca: 收集塗鴉參數（瀏覽器/伺服器引擎共用同一組）
function collectDoodleOpts() {
  return {
    apiBase: API_BASE,
    canvasWidthMm: parseFloat(document.getElementById("dd-width").value),
    maxSidePx: parseInt(document.getElementById("dd-max-side").value, 10),
    threshold: parseInt(document.getElementById("dd-threshold").value, 10),
    lineColor: document.getElementById("dd-color").value,
    lineWidth: parseFloat(document.getElementById("dd-linewidth").value),
    autoCropWhitespace: document.getElementById("dd-crop-whitespace").checked,
    autoCropBorder: document.getElementById("dd-crop-border").checked,
    annotations: collectDoodleAnnotations(),
    // Phase 5ch: 伺服器取樣方式（fallback 路徑也吃這個值）
    vectorStyle: document.getElementById("dd-server-style").value,
    // Phase 5cb: OpenCV 引擎參數
    cv: {
      mode: document.getElementById("dd-cv-mode").value,
      blockSize: parseInt(document.getElementById("dd-cv-block").value, 10),
      c: parseInt(document.getElementById("dd-cv-c").value, 10),
      invert: document.getElementById("dd-cv-invert").checked,
      simplifyPx: parseFloat(document.getElementById("dd-cv-simplify").value),
      chaikinIters: parseInt(document.getElementById("dd-cv-chaikin").value, 10),
      minArea: parseFloat(document.getElementById("dd-cv-minarea").value),
      maxProcSide: parseInt(document.getElementById("dd-cv-maxside").value, 10),
    },
  };
}

// 伺服器引擎（POST /api/doodle）—— doodle_engine.js 沒載入時的保底路徑
async function renderDoodleViaServer(file, opts) {
  const t0 = performance.now();
  const fd = new FormData();
  fd.append("image", file);
  fd.append("canvas_width_mm", opts.canvasWidthMm);
  fd.append("max_side_px", opts.maxSidePx);
  fd.append("threshold", opts.threshold);
  fd.append("line_color", opts.lineColor);
  fd.append("line_width", opts.lineWidth);
  fd.append("auto_crop_whitespace", opts.autoCropWhitespace ? "true" : "false");
  fd.append("auto_crop_border", opts.autoCropBorder ? "true" : "false");
  fd.append("annotations_json", JSON.stringify(opts.annotations));
  fd.append("vector_style", opts.vectorStyle || "contour");   // 5ch
  const r = await fetch(`${API_BASE}/api/doodle`, {method: "POST", body: fd});
  if (!r.ok) {
    const err = await r.json().catch(() => ({detail: r.statusText}));
    throw new Error(err.detail || `HTTP ${r.status}`);
  }
  return {svg: await r.text(), ms: performance.now() - t0};
}

let ddRenderSeq = 0;   // 即時預覽下丟棄過期回合
async function renderDoodle() {
  const statusEl = document.getElementById("dd-status");
  const previewEl = document.getElementById("dd-preview");
  const downloadEl = document.getElementById("dd-download");
  const imageInput = document.getElementById("dd-image");
  if (!imageInput.files || !imageInput.files[0]) {
    previewEl.innerHTML = `<span style="color:var(--accent);">請先選擇圖片</span>`;
    return;
  }
  const file = imageInput.files[0];
  const opts = collectDoodleOpts();
  const seq = ++ddRenderSeq;
  statusEl.textContent = "產生中…";
  downloadEl.style.display = "none";

  let engineVal = document.getElementById("dd-engine").value;
  // 5cp：opencv 本 session 失敗過 → 直接用伺服器，不再讓使用者
  // 等看門狗（受管理電腦的環境層會卡死大型腳本執行）
  let opencvSkipped = false;
  if (engineVal === "opencv" &&
      sessionStorage.getItem("dd-opencv-broken")) {
    engineVal = "server";
    opencvSkipped = true;
  }
  const mod = window.DoodleEngine;
  // Phase 5ca/5cb: 前端引擎（browser / opencv）統一路由，失敗退回伺服器
  const clientEng = (engineVal !== "server" && mod &&
                     mod.DoodleEngines[engineVal] &&
                     mod.DoodleEngines[engineVal].available())
    ? mod.DoodleEngines[engineVal] : null;
  opts.onStatus = (msg) => { statusEl.textContent = msg; };
  try {
    let res, engineNote;
    if (clientEng) {
      try {
        // Phase 5cf: renderVia 統一入口——優先 Worker（主執行緒不卡），
        // Worker 失敗自動回主執行緒直跑
        res = await mod.renderVia(engineVal, file, opts);
        engineNote = clientEng.label +
          (res.via === "worker" ? "・Worker" : "");
        if (engineVal === "opencv") {
          sessionStorage.removeItem("dd-opencv-broken");   // 5cp：成功洗白
        }
      } catch (e) {
        console.warn("client doodle engine failed, falling back:", e);
        if (engineVal === "opencv") {
          sessionStorage.setItem("dd-opencv-broken", "1"); // 5cp：記失敗
        }
        res = await renderDoodleViaServer(file, opts);
        engineNote = `${clientEng.label}失敗，已改用伺服器` +
          "（本次瀏覽期間將自動沿用伺服器引擎）";
      }
    } else {
      res = await renderDoodleViaServer(file, opts);
      engineNote = opencvSkipped
        ? "伺服器引擎（OpenCV 先前載入失敗，本次瀏覽期間自動改用）"
        : "伺服器引擎";
    }
    if (seq !== ddRenderSeq) return;   // 有更新的一輪在跑，丟棄本輪
    const svg = res.svg;
    // Phase 5ci: 預覽一律走 <img src=blob>——照片向量化可達數千條
    // path，innerHTML 直塞會建幾萬個 SVG DOM 節點、凍結主執行緒
    // 數十秒（實測 renderer frozen 40s）；<img> 由瀏覽器光柵化，
    // 不建 DOM，任何大小都順
    const blob = new Blob([svg], {type: "image/svg+xml"});
    const url = URL.createObjectURL(blob);
    previewEl.innerHTML = "";
    const im = document.createElement("img");
    im.src = url;
    im.alt = "塗鴉預覽";
    im.style.maxWidth = "100%";
    im.style.height = "auto";
    previewEl.appendChild(im);
    // Phase 5s: save the doodle SVG for import into notebook zones
    lastDoodleSvg = svg;
    const pathNote = res.paths ? `・路徑 ${res.paths} 條` : "";
    const heavyNote = (res.paths > 3000 || svg.length > 2_000_000)
      ? "（量大：雷切前建議調高「去斑」或降低解析度）" : "";
    statusEl.textContent = `OK · ${(svg.length / 1024).toFixed(1)} KB ` +
      `· ${engineNote}${pathNote} ${res.ms.toFixed(0)}ms ${heavyNote}` +
      `· 可切到「筆記模式」按「⬅ 匯入塗鴉」把向量塞進塗鴉區`;
    downloadEl.href = url;
    downloadEl.setAttribute("download", "doodle.svg");
    downloadEl.textContent = "⤓ 下載 SVG";
    downloadEl.style.display = "inline-block";
  } catch (e) {
    if (seq !== ddRenderSeq) return;
    statusEl.textContent = "";
    previewEl.innerHTML =
      `<span style="color:var(--accent);">錯誤：${e.message}</span>`;
  }
}
document.getElementById("dd-render").onclick = renderDoodle;

// Phase 5ca/5cb: 前端引擎下參數改動即時重算（debounce 150ms）
let ddLiveTimer = null;
function ddLiveRerender() {
  if (document.getElementById("dd-engine").value === "server") return;
  const f = document.getElementById("dd-image");
  if (!f.files || !f.files[0]) return;
  clearTimeout(ddLiveTimer);
  ddLiveTimer = setTimeout(renderDoodle, 150);
}
["dd-width", "dd-max-side", "dd-threshold", "dd-color", "dd-linewidth",
 "dd-cv-block", "dd-cv-c", "dd-cv-simplify", "dd-cv-chaikin",
 "dd-cv-minarea", "dd-cv-maxside"]
  .forEach(id => document.getElementById(id)
    .addEventListener("input", ddLiveRerender));
["dd-crop-whitespace", "dd-crop-border", "dd-image", "dd-engine",
 "dd-cv-mode", "dd-cv-invert", "dd-server-style"]
  .forEach(id => document.getElementById(id)
    .addEventListener("change", ddLiveRerender));
document.getElementById("dd-annotations")
  .addEventListener("input", ddLiveRerender);

// Phase 5cb/5ch: 引擎切換時同步 OpenCV／伺服器參數列顯示
function ddSyncEngineUi() {
  const v = document.getElementById("dd-engine").value;
  document.getElementById("dd-cv-params").style.display =
    v === "opencv" ? "" : "none";
  document.getElementById("dd-server-params").style.display =
    v === "server" ? "" : "none";
}
document.getElementById("dd-engine")
  .addEventListener("change", ddSyncEngineUi);
ddSyncEngineUi();

