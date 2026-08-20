// W4-R2 次批：顯式跨檔邊（原全域相依 → import/export 網）
import { API_BASE } from "./core.js?v=__V__";
// 5ew-R4：點格手寫（循環邊 grid↔handwrite——函式宣告＋事件時呼叫，§44 安全）
import { swAttachCells } from "./handwrite.js?v=__V__";

// ============================================================
// Grid (字帖) mode
// ============================================================
// ------------------------------------------------------------------
// Phase 5cu：拼音 → 注音（確定性規則轉換）
// pinyin-pro（已全域載入）出「拼音＋調號」，這裡查表轉注音——
// 語言知識留在前端，伺服器零字典依賴（同 5cn 架構哲學）。
// ------------------------------------------------------------------
const ZY_WHOLE = {zhi:"ㄓ",chi:"ㄔ",shi:"ㄕ",ri:"ㄖ",zi:"ㄗ",ci:"ㄘ",si:"ㄙ",
  yi:"ㄧ",ya:"ㄧㄚ",yo:"ㄧㄛ",ye:"ㄧㄝ",yao:"ㄧㄠ",you:"ㄧㄡ",yan:"ㄧㄢ",
  yin:"ㄧㄣ",yang:"ㄧㄤ",ying:"ㄧㄥ",yong:"ㄩㄥ",
  wu:"ㄨ",wa:"ㄨㄚ",wo:"ㄨㄛ",wai:"ㄨㄞ",wei:"ㄨㄟ",wan:"ㄨㄢ",wen:"ㄨㄣ",
  wang:"ㄨㄤ",weng:"ㄨㄥ",
  yu:"ㄩ",yue:"ㄩㄝ",yuan:"ㄩㄢ",yun:"ㄩㄣ"};
const ZY_INIT = {b:"ㄅ",p:"ㄆ",m:"ㄇ",f:"ㄈ",d:"ㄉ",t:"ㄊ",n:"ㄋ",l:"ㄌ",
  g:"ㄍ",k:"ㄎ",h:"ㄏ",j:"ㄐ",q:"ㄑ",x:"ㄒ",zh:"ㄓ",ch:"ㄔ",sh:"ㄕ",
  r:"ㄖ",z:"ㄗ",c:"ㄘ",s:"ㄙ"};
const ZY_FIN = {a:"ㄚ",o:"ㄛ",e:"ㄜ",ai:"ㄞ",ei:"ㄟ",ao:"ㄠ",ou:"ㄡ",
  an:"ㄢ",en:"ㄣ",ang:"ㄤ",eng:"ㄥ",er:"ㄦ",
  i:"ㄧ",ia:"ㄧㄚ",ie:"ㄧㄝ",iao:"ㄧㄠ",iu:"ㄧㄡ",ian:"ㄧㄢ",in:"ㄧㄣ",
  iang:"ㄧㄤ",ing:"ㄧㄥ",iong:"ㄩㄥ",
  u:"ㄨ",ua:"ㄨㄚ",uo:"ㄨㄛ",uai:"ㄨㄞ",ui:"ㄨㄟ",uan:"ㄨㄢ",un:"ㄨㄣ",
  uang:"ㄨㄤ",ong:"ㄨㄥ",
  v:"ㄩ",ve:"ㄩㄝ",van:"ㄩㄢ",vn:"ㄩㄣ"};
const ZY_TONE = {"1": "", "2": "ˊ", "3": "ˇ", "4": "ˋ", "0": "˙", "5": "˙"};

function pinyinToZhuyin(pyNum) {
  const m = /^([a-zv]+)([0-9])?$/.exec(
    String(pyNum).toLowerCase().replace(/ü/g, "v").trim());
  if (!m) return "";
  const syl = m[1];
  const tone = ZY_TONE[m[2] || "1"] ?? "";
  if (ZY_WHOLE[syl]) return ZY_WHOLE[syl] + tone;
  let init = "", rest = syl;
  if (syl.length >= 2 && ZY_INIT[syl.slice(0, 2)]) {   // zh/ch/sh
    init = syl.slice(0, 2); rest = syl.slice(2);
  } else if (ZY_INIT[syl[0]]) {
    init = syl[0]; rest = syl.slice(1);
  }
  if ("jqx".includes(init) && rest[0] === "u") {       // jqx 後 u = ü
    rest = "v" + rest.slice(1);
  }
  const fin = rest === "" ? "" : ZY_FIN[rest];
  if (fin === undefined) return "";
  return (ZY_INIT[init] || "") + fin + tone;
}

// ------------------------------------------------------------------
// Phase 5cw：台灣讀音（教育部體系）查表優先
// 資料：McBopomofo（openvanilla，MIT）字級注音庫 21,786 字衍生檔
// static/zhuyin_tw.json（{"字":"主音|次音|…"}，heterophony 排序決定
// 破音字預設讀音）；衍生檔入 repo、同源載入＝執行期零外網。
// pinyin-pro（大陸讀音體系）降級為「表缺字」fallback。
// ------------------------------------------------------------------
let zyTwDict = null;      // {字: "主音|次音|…"}（載妥後常駐）
let zyTwLoading = null;
function ensureZhuyinTw() {
  if (zyTwDict) return Promise.resolve(zyTwDict);
  if (!zyTwLoading) {
    zyTwLoading = fetch("/static/zhuyin_tw.json?v=__V__")
      .then(r => {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(d => (zyTwDict = d))
      .catch(() => { zyTwLoading = null; return null; });  // 可重試；走 fallback
  }
  return zyTwLoading;
}

/** 逐字出注音（台灣審定音查表優先、pinyin-pro 近似墊底）→ "字:注音,…" */
function gridZhuyinMap(chars) {
  const cs = [...chars];
  const hasPy = typeof window.pinyinPro !== "undefined";
  let arr = [];
  if (hasPy) {
    try {
      arr = pinyinPro.pinyin(chars, {toneType: "num", type: "array", v: true});
    } catch (e) { arr = []; }
  }
  const aligned = arr.length === cs.length;
  const out = [];
  const seen = new Set();
  for (let i = 0; i < cs.length; i++) {
    const ch = cs[i];
    if (seen.has(ch) || !/[㐀-鿿]/.test(ch)) continue;
    seen.add(ch);
    let zy = "";
    const rs = (zyTwDict && zyTwDict[ch]) ? zyTwDict[ch].split("|") : null;
    if (rs && gridZhuyinChoice[ch] && rs.includes(gridZhuyinChoice[ch])) {
      zy = gridZhuyinChoice[ch];            // 5cx：使用者改選的破音字讀音
    } else if (rs) {
      zy = rs[0];                           // 5cw：教育部體系預設讀音
    } else if (hasPy) {
      const py = aligned ? arr[i]
        : pinyinPro.pinyin(ch, {toneType: "num", v: true});
      zy = pinyinToZhuyin(py);              // fallback：大陸體系近似
    }
    if (zy) out.push(ch + ":" + zy);
  }
  return out.join(",");
}

// ------------------------------------------------------------------
// Phase 5cx：破音字下拉修正
// 表值含 "|" 的字＝多音字，逐字生成下拉（選項＝全部審定讀音、
// 預設＝主音）；改選記在 gridZhuyinChoice（跨重繪保留），
// gridZhuyinMap 以「改選 > 主音 > pinyin 近似」優先序取讀音。
// ------------------------------------------------------------------
const gridZhuyinChoice = {};   // 字 → 使用者改選的讀音
async function refreshZhuyinPoly() {
  const row = document.getElementById("grid-zhuyin-poly-row");
  const box = document.getElementById("grid-zhuyin-poly");
  if (!document.getElementById("grid-zhuyin").checked) {
    row.style.display = "none";
    return;
  }
  const dict = await ensureZhuyinTw();
  if (!dict) { row.style.display = "none"; return; }
  box.innerHTML = "";
  const seen = new Set();
  for (const ch of document.getElementById("grid-chars").value) {
    if (seen.has(ch) || !/[㐀-鿿]/.test(ch)) continue;
    seen.add(ch);
    const rs = (dict[ch] || "").split("|");
    if (rs.length < 2) continue;
    const label = document.createElement("label");
    label.style.marginLeft = "8px";
    label.textContent = ch + " ";
    const sel = document.createElement("select");
    for (const r of rs) {
      const o = document.createElement("option");
      o.value = r;
      o.textContent = r;
      sel.appendChild(o);
    }
    if (gridZhuyinChoice[ch] && rs.includes(gridZhuyinChoice[ch])) {
      sel.value = gridZhuyinChoice[ch];
    }
    sel.addEventListener("change", () => {
      gridZhuyinChoice[ch] = sel.value;
    });
    label.appendChild(sel);
    box.appendChild(label);
  }
  row.style.display = box.children.length ? "" : "none";
}
document.getElementById("grid-zhuyin")
  .addEventListener("change", refreshZhuyinPoly);
document.getElementById("grid-chars")
  .addEventListener("input", refreshZhuyinPoly);

function gridParams() {
  const g = (id) => document.getElementById(id).value;
  const p = new URLSearchParams({
    chars: g("grid-chars"),
    source: g("grid-source"),
    hook_policy: g("grid-hook"),
    cols: g("grid-cols"),
    guide: g("grid-guide"),
    cell_style: g("grid-cell-style"),
    cell_size: g("grid-cell-size"),
    repeat: g("grid-repeat"),
    ghost_copies: g("grid-ghost"),
    blank_copies: g("grid-blank"),
    direction: g("grid-direction"),
    // 5cn：自訂字型是純前端概念——伺服器照楷書出版面（字形會被
    // 前端整格替換），API 不需要認識 userfont
    style: g("grid-font-style") === "userfont"
      ? "kaishu" : g("grid-font-style"),
    cns_outline_mode: g("grid-cns-mode"),
  });
  // 5cu：注音欄——前端算好映射傳給伺服器（參數存在即開欄）
  if (document.getElementById("grid-zhuyin").checked) {
    p.set("zhuyin_map", gridZhuyinMap(g("grid-chars")));
  }
  // W2：頁尾生字資訊區——教育部原文由伺服器查（bundle 隨 repo 部署，
  // 零外部服務），前端只送開關
  if (document.getElementById("grid-info-footer").checked) {
    p.set("info_footer", "true");
  }
  return p.toString();
}

async function renderGrid() {
  const statusEl = document.getElementById("grid-status");
  const previewEl = document.getElementById("grid-preview");
  const dlGroup = document.getElementById("grid-download-group");
  statusEl.textContent = "產生中…";
  dlGroup.style.display = "none";
  // 5cw：注音開啟時先確保台灣讀音表載妥（首次約 450KB，之後快取）
  // 5cx：並同步破音字下拉列（帶入／程式改字後 input 事件不會觸發）
  if (document.getElementById("grid-zhuyin").checked) {
    await ensureZhuyinTw();
    await refreshZhuyinPoly();
  }
  const qs = gridParams();
  try {
    const r = await fetch(`${API_BASE}/api/grid?${qs}&format=svg`);
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: r.statusText}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    const svg = await r.text();
    previewEl.innerHTML = svg;
    const innerSvg = previewEl.querySelector("svg");
    if (innerSvg) {
      innerSvg.style.maxWidth = "100%";
      innerSvg.style.height = "auto";
    }
    statusEl.textContent = `OK · SVG ${(svg.length / 1024).toFixed(1)} KB`;
    if (document.getElementById("grid-zhuyin").checked) {
      // 5cw：標明讀音體系（查表命中＝教育部；表未載入＝拼音近似）
      // 5cy：伺服器 G-code 含注音（自訂字型模式的前端 G-code 除外）；
      //      JSON 仍為主字版面
      const zySrc = zyTwDict ? "教育部審定體系" : "拼音近似（讀音表未載入）";
      statusEl.textContent +=
        `（含注音欄描紅・${zySrc}；G-code 含注音、JSON 為主字版面）`;
    }
    // Wire up the 3 download links
    const dlSvg = document.getElementById("grid-download-svg");
    const dlGcode = document.getElementById("grid-download-gcode");
    const dlJson = document.getElementById("grid-download-json");
    dlSvg.href = `${API_BASE}/api/grid?${qs}&format=svg&download=true`;
    // W1：多頁/單張都出可列印 PDF（grid 貼合紙張，見 paper 參數）
    const dlPdf = document.getElementById("grid-download-pdf");
    if (dlPdf) dlPdf.href = `${API_BASE}/api/grid?${qs}&format=pdf&download=true`;
    dlSvg.removeAttribute("download");
    dlGcode.href = `${API_BASE}/api/grid?${qs}&format=gcode&download=true`;
    dlGcode.removeAttribute("download");   // 5cs：清 userfont blob 殘留
    dlJson.href = `${API_BASE}/api/grid?${qs}&format=json&download=true`;
    dlGcode.style.display = "";
    dlJson.style.display = "";

    // Phase 5cn：自訂字型——前端逐格注入（字型檔不上傳；伺服器只出
    // 版面與格線，字形整格替換成使用者字型的外框 path）
    if (document.getElementById("grid-font-style").value === "userfont") {
      if (!gridUserFont) {
        statusEl.textContent =
          "請先按「選字型檔…」載入本機 TTF/OTF，再產生字帖";
      } else {
        const inner = previewEl.querySelector("svg");
        const n = injectUserFontIntoGrid(inner);
        const clone = inner.cloneNode(true);
        clone.removeAttribute("style");
        const blob = new Blob(
          [new XMLSerializer().serializeToString(clone)],
          {type: "image/svg+xml"});
        dlSvg.href = URL.createObjectURL(blob);
        dlSvg.setAttribute("download", "grid_userfont.svg");
        // 5cs：G-code 復活——骨架化中心線機器軌跡（前端生成、
        // 字型不上傳）；JSON（筆順結構）仍不適用、維持隱藏
        let gcodeNote = "";
        try {
          const gc = gridUserFontGcode(inner);
          dlGcode.href = URL.createObjectURL(
            new Blob([gc], {type: "text/plain"}));
          dlGcode.setAttribute("download", "grid_userfont.gcode");
          dlGcode.style.display = "";
          gcodeNote = "；G-code 為骨架化中心線（幾何近似，非筆順）";
        } catch (e2) {
          console.warn("userfont gcode failed:", e2);
          dlGcode.style.display = "none";
        }
        dlJson.style.display = "none";
        statusEl.textContent =
          `OK · 自訂字型「${gridUserFontName}」已套用 ${n} 格` +
          "（字型檔僅在瀏覽器處理、未上傳；輸出請依字型授權自用列印" +
          gcodeNote + "）";
      }
    }
    dlGroup.style.display = "inline";
    // 5ew-R4：點格手寫——自訂字型注入「之後」才掛（範字複製即時格內容）
    swAttachCells(previewEl, {
      key: "grid", styleId: "grid-font-style", refresh: renderGrid });
  } catch (e) {
    statusEl.textContent = "";
    previewEl.innerHTML =
      `<span style="color:var(--accent);">錯誤：${e.message}</span>`;
  }
}
document.getElementById("grid-render").onclick = renderGrid;

// ------------------------------------------------------------------
// Phase 5cn：自訂字型（瀏覽器端）——TTF/OTF 檔案僅在本機解析，
// 伺服器零版權風險。opentype.js 走 /vendor 同源代理（校網免疫）。
// ------------------------------------------------------------------
let gridUserFont = null;
let gridUserFontName = "";
let _opentypeP = null;

function loadOpentype() {
  if (window.opentype) return Promise.resolve(window.opentype);
  if (_opentypeP) return _opentypeP;
  _opentypeP = new Promise((res, rej) => {
    const tag = document.createElement("script");
    const timer = setTimeout(() => {          // silent-drop 防火牆保險
      tag.onload = tag.onerror = null;
      _opentypeP = null;
      rej(new Error("opentype.js 載入逾時（20s）"));
    }, 20000);
    // 5db：帶版本 query——vendor 端點 max-age=7 天，pin 升級時
    // 瀏覽器 HTTP 快取要隨 query 失效（opencv 同源 URL 同規則）
    tag.src = "/vendor/opentype.min.js?v=1.3.4";
    tag.onload = () => { clearTimeout(timer); res(window.opentype); };
    tag.onerror = () => {
      clearTimeout(timer);
      _opentypeP = null;
      rej(new Error("opentype.js 載入失敗"));
    };
    document.head.appendChild(tag);
  });
  return _opentypeP;
}

async function gridLoadUserFontFile(file) {
  const statusEl = document.getElementById("grid-status");
  try {
    statusEl.textContent = "解析字型檔…";
    const ot = await loadOpentype();
    gridUserFont = ot.parse(await file.arrayBuffer());
    gridUserFontName = file.name;
    _fontTrackCache.clear();               // 5cs：換字型清軌跡快取
    document.getElementById("grid-font-name").textContent =
      `已載入：${file.name}`;
    statusEl.textContent =
      "字型已載入（僅在瀏覽器處理，未上傳）。按「產生字帖」套用。";
  } catch (e) {
    gridUserFont = null;
    gridUserFontName = "";
    document.getElementById("grid-font-name").textContent = "";
    statusEl.textContent = `字型解析失敗：${e.message}`;
  }
}

/** 把使用者字型逐格注入字帖 SVG。回傳注入格數。
 *  cell 定位靠 grid.py 的 data-char / data-cell-style 標記；
 *  格線（.guides）保留、伺服器字形整組移除後放字型外框 path。 */
function injectUserFontIntoGrid(svgRoot) {
  if (!svgRoot || !gridUserFont) return 0;
  const upem = gridUserFont.unitsPerEm || 1000;
  const scale = 2048 / upem;
  const baseY = (gridUserFont.ascender || upem * 0.88) * scale;
  const NS = "http://www.w3.org/2000/svg";
  let n = 0;
  svgRoot.querySelectorAll("g[data-char]").forEach((cell) => {
    const ch = cell.getAttribute("data-char");
    const style = cell.getAttribute("data-cell-style") || "outline";
    cell.querySelectorAll(":scope > g:not(.guides)")
        .forEach((g) => g.remove());
    if (style === "blank" || !ch) return;
    // 全形字 advance ≈ em；半形字置中補位
    const adv = gridUserFont.getAdvanceWidth(ch, 2048);
    const x = Math.max(0, (2048 - adv) / 2);
    const d = gridUserFont.getPath(ch, x, baseY, 2048).toPathData(1);
    if (!d) return;
    const g = document.createElementNS(NS, "g");
    g.setAttribute("class", "userfont");
    if (style === "ghost") {
      g.setAttribute("fill", "#e0e0e0");
    } else if (style === "trace") {
      g.setAttribute("fill", "none");
      g.setAttribute("stroke", "#c22");
      g.setAttribute("stroke-width", "14");
    } else {                       // outline / filled → 墨跡
      g.setAttribute("fill", "#222");
    }
    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", d);
    g.appendChild(path);
    cell.appendChild(g);
    n++;
  });
  return n;
}

// ------------------------------------------------------------------
// Phase 5cs：自訂字型 → 機器軌跡（骨架化中心線 → G-code）
// 字型檔不出本機：glyph 光柵化＋Zhang-Suen＋圖論追蹤＋RDP 全在
// 瀏覽器（復用 doodle_engine 5cg 純函式三件組），G-code 前端組裝。
// 注意：字型只有外框、無真筆順——骨架化中心線的分段與順序是
// 幾何近似，適合單線筆/雷雕，不等於教育部筆順。
// ------------------------------------------------------------------
const _fontTrackCache = new Map();   // `${fontName}:${ch}` → EM 2048 折線集

function fontCharTracks(ch) {
  // 5el：平滑度可調——Chaikin 迭代從 UI 讀（預設 2）。5em：RDP 簡化 eps 亦
  // 可調（預設 1.5）。cache key 納入兩者，調值後不回舊軌跡（否則出舊快取＝bug）。
  const smEl = document.getElementById("gf-smooth");
  const ckIters = smEl ? Math.max(0, parseInt(smEl.value, 10) || 0) : 2;
  const spEl = document.getElementById("gf-simplify");
  const rdpEps = spEl ? Math.max(0, parseFloat(spEl.value) || 0) : 1.5;
  const key = gridUserFontName + ":" + ch + ":" + ckIters + ":" + rdpEps;
  if (_fontTrackCache.has(key)) return _fontTrackCache.get(key);
  const eng = window.DoodleEngine;
  const P = 384;                             // 光柵解析度（5cg 800² 0.4s → 384² 快）
  const upem = gridUserFont.unitsPerEm || 1000;
  const scale = P / upem;
  const baseY = (gridUserFont.ascender || upem * 0.88) * scale;
  const adv = gridUserFont.getAdvanceWidth(ch, P);
  const cx = document.createElement("canvas");
  cx.width = cx.height = P;
  const c2 = cx.getContext("2d", {willReadFrequently: true});
  c2.fillStyle = "#fff";
  c2.fillRect(0, 0, P, P);
  const gp = gridUserFont.getPath(ch, Math.max(0, (P - adv) / 2), baseY, P);
  gp.fill = "#000";
  gp.stroke = null;
  gp.draw(c2);
  const img = c2.getImageData(0, 0, P, P).data;
  const bin = new Uint8Array(P * P);
  for (let i = 0, q = 0; i < bin.length; i++, q += 4) {
    bin[i] = img[q] < 128 ? 1 : 0;           // 黑 = 筆畫
  }
  const skel = eng.zhangSuenThin(bin, P, P);
  const traced = eng.traceCenterlines(skel, P, P);
  const emScale = 2048 / P;
  const tracks = [];
  for (const tr of traced) {
    if (tr.length < 4) continue;             // 去雜點
    // 5eh：RDP 後套 Chaikin 削角（同塗鴉 centerline），細線化階梯的殘餘
    // 尖角讀成平滑中心線；端點保留。5el：Chaikin 迭代由 UI 可調（gf-smooth）；
    // 5em：RDP eps 亦由 UI 可調（gf-simplify）。
    const simp = eng.chaikinSmooth(eng.rdpSimplify(tr, rdpEps), ckIters);
    tracks.push(simp.map((pt) => [pt[0] * emScale, pt[1] * emScale]));
  }
  _fontTrackCache.set(key, tracks);
  return tracks;
}

/** 復刻 exporters/grid.render_grid_gcode 的輸出慣例（G21/G90、
 *  M5/M3 S90、G0 F6000/G1 F3000、G4 P150、flip_y、origin 10,10、
 *  只寫主字層、tier 順序），字形軌跡換成骨架化中心線。 */
function gridUserFontGcode(svgRoot) {
  const EM = 2048;
  const cellMm = 20.0, feed = 3000, travel = 6000;
  const penUp = "M5", penDown = "M3 S90", dwellMs = 150;
  const ox = 10.0, oy = 10.0;
  const scaleMm = cellMm / EM;
  // 5cu：注音欄開啟時格距變寬（data-pair-em），X 向距同步縮放
  const pairEm = parseFloat(svgRoot.getAttribute("data-pair-em") || "") || EM;
  const xPitchMm = cellMm * pairEm / EM;
  const direction = document.getElementById("grid-direction").value;
  const cells = [];
  svgRoot.querySelectorAll("g[data-char]").forEach((cell) => {
    const style = cell.getAttribute("data-cell-style") || "";
    if (style === "ghost" || style === "blank") return;   // 只寫主字層
    const m = /translate\((-?[\d.]+),(-?[\d.]+)\)/
      .exec(cell.getAttribute("transform") || "");
    if (!m) return;
    cells.push({ch: cell.getAttribute("data-char"),
                col: Math.round(parseFloat(m[1]) / pairEm),
                row: Math.round(parseFloat(m[2]) / EM)});
  });
  cells.sort((a, b) => direction === "vertical"
    ? a.row - b.row : a.col - b.col);

  const out = [];
  out.push("; --- stroke-order 字帖 G-code (custom font / skeletonized) ---");
  out.push("; font: " + gridUserFontName + " (瀏覽器骨架化，未上傳)");
  out.push("; NOTE: 字型無筆順資料——中心線分段/順序為幾何近似，非教育部筆順");
  out.push(`; cell_size=${cellMm}mm feed=${feed} direction=${direction}`);
  out.push("G21 ; mm");
  out.push("G90 ; absolute");
  out.push(`${penUp} ; pen up (start)`);
  out.push(`G4 P${dwellMs}`);
  out.push(`G0 X${ox.toFixed(3)} Y${oy.toFixed(3)} F${travel} ; home`);
  for (const cell of cells) {
    const cxMm = ox + cell.col * xPitchMm;   // 5cu：X 向用 pair 距
    const cyMm = oy + cell.row * cellMm;
    out.push("");
    out.push(`; --- cell (${cell.row},${cell.col}): ${cell.ch} ---`);
    const tracks = fontCharTracks(cell.ch);
    tracks.forEach((pts, ti) => {
      if (!pts.length) return;
      out.push(`; segment ${ti + 1}/${tracks.length}`);
      const xf = (p) => [cxMm + p[0] * scaleMm,
                         cyMm + (EM - p[1]) * scaleMm];   // flip_y
      let [x, y] = xf(pts[0]);
      out.push(`G0 X${x.toFixed(3)} Y${y.toFixed(3)} F${travel}`);
      out.push(penDown);
      out.push(`G4 P${dwellMs}`);
      for (let i = 1; i < pts.length; i++) {
        [x, y] = xf(pts[i]);
        out.push(`G1 X${x.toFixed(3)} Y${y.toFixed(3)} F${feed}`);
      }
      out.push(`G4 P${dwellMs}`);
      out.push(penUp);
    });
  }
  out.push("");
  out.push("; --- epilogue ---");
  out.push(`${penUp} ; ensure pen up`);
  out.push(`G0 X${ox.toFixed(3)} Y${oy.toFixed(3)} F${travel} ; return home`);
  out.push("; done");
  return out.join("\n") + "\n";
}

document.getElementById("grid-font-style").addEventListener("change", (ev) => {
  const wrap = document.getElementById("grid-font-file-wrap");
  if (ev.target.value === "userfont") {
    wrap.style.display = "inline";
    if (!gridUserFont) {
      document.getElementById("grid-font-file").click();
    }
  } else {
    wrap.style.display = "none";
  }
});
document.getElementById("grid-font-file").addEventListener("change", (ev) => {
  if (ev.target.files && ev.target.files[0]) {
    gridLoadUserFontFile(ev.target.files[0]);
  }
});
// 5ct：筆記/信紙的字型選單選到自訂字型且尚未載入 → 直接開選檔
// （共用 grid-font-file 隱藏輸入框與全域 gridUserFont）
for (const selId of ["nb-style", "lt-style"]) {
  document.getElementById(selId).addEventListener("change", (ev) => {
    if (ev.target.value === "userfont" && !gridUserFont) {
      document.getElementById("grid-font-file").click();
    }
  });
}

// Phase 5j: auto-derive ghost/blank from cols (user can still manually override)
// Rule: cols=1 → (0,0); cols=2 → (1,0); cols≥3 → (1, cols-2).
function gridAutoTiers() {
  const cols = parseInt(document.getElementById("grid-cols").value, 10) || 1;
  const ghostEl = document.getElementById("grid-ghost");
  const blankEl = document.getElementById("grid-blank");
  let ghost, blank;
  if (cols <= 1)      { ghost = 0; blank = 0; }
  else if (cols === 2) { ghost = 1; blank = 0; }
  else                 { ghost = 1; blank = cols - 2; }
  ghostEl.value = ghost;
  blankEl.value = blank;
  const hint = document.getElementById("grid-tier-hint");
  if (hint) hint.textContent =
    `總 ${cols} 層 = 1 主字 + ${ghost} ghost + ${blank} blank`;
}
document.getElementById("grid-cols").addEventListener("input", gridAutoTiers);
document.getElementById("grid-cols").addEventListener("change", gridAutoTiers);

// Fire once on load to sync the hint text
document.addEventListener("DOMContentLoaded", gridAutoTiers);

document.getElementById("grid-chars").addEventListener("keydown", e => {
  if (e.key === "Enter") renderGrid();
});

// W4-R2：跨檔邊匯出（消費端見 import 網）
export { ensureZhuyinTw, gridUserFont, gridUserFontName, gridZhuyinMap, injectUserFontIntoGrid };
