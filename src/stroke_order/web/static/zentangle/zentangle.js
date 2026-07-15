// Phase 6z-1C/D/E — Zentangle mode DOM glue.
//
// Loaded once per index.html via:
//   <script type="module" src="/static/zentangle/zentangle.js"></script>
//
// Boots lazily on first activation of mode "zentangle" (pays no cost when
// user is in another mode). Subsequent re-activations re-use the same
// canvas/ctx.
//
// Architecture (per Phase 6z v0.3 design doc + senior review note #5):
//   - Pure geometry → outline.mjs (Node testable)
//   - DOM glue → this file (canvas init, fetch, render, status)
//   - 6z-1C: canvas + outline render
//   - 6z-1D: force-modal main menu (char + mode + tile_size, D-C 強紀律)
//   - 6z-1E: input scaffolding (鍵盤 + 滑鼠 + Web Gamepad API stubs;
//            real wiring → 6z-7)
//   - Pseudo-3D + tile rotation → 6z-2 / 6z-5

import {
  computeBbox,
  mapContourToTile,
  contoursAreClosed,
} from "./outline.mjs";
import {
  TANGLES,
  buildTangle,
  buildTangleOriented,
  renderTangleSpecs,
  listTangles,
} from "./tangle.mjs";
import {
  computeGlyphRegions,
  computeBgRegions,
  assignRandomTangles,
  pickSpacing,
  resolveRegionAt,
  splitRegionByPolyline,
} from "./regions.mjs";
import {
  applyPseudo3DToSpecs,
  isValidDepthDir,
  VALID_DEPTH_DIRS,
  applyCurveModeToSpecs,
  isValidCurveMode,
  VALID_CURVE_MODES,
} from "./pseudo3d.mjs";
import {
  ENHANCERS,
  ENHANCER_LABELS,
  applyEnhancers,
  hasAnyEnhancer,
  normalizeEnhancers,
  ENHANCER_PARAM_DEFS,
  defaultEnhancerParams,
  paramsToOpts,
  COMBOS,
} from "./enhancers.mjs";
import {
  TILE_MM,
  collectExportPaths,
  pathsToSvg,
  pathsToGcode,
  pathsToDxf,
} from "./exporters.mjs";

// 5dj-3: 全域延伸參數（per-session；一組滑桿套用到所有已勾技法的區段）。
let _enhancerParams = defaultEnhancerParams();

// 5dk: 全域匯出設定（per-session）。fillMode 填色形狀處理；scanSpacingMm
// 雷雕掃描間距；strokeMm 圖樣線寬；curveSegs 曲線攤平精細度；includeOutline
// 是否含字框。
const _exportOpts = {
  fillMode: "outline",   // outline | scan | skip
  scanSpacingMm: 1.0,
  strokeMm: 0.3,
  curveSegs: 24,
  includeOutline: true,
};

// 6z-2.1 NOTE: `rotateContours` is intentionally NOT imported here.
// Tile rotation is now applied via canvas ctx transform (so frame + outline
// rotate together — see withTileRotation). The pure helper in outline.mjs
// is preserved + Node-tested for future state-aware needs (Pseudo-3D
// pre-render in 6z-5, SVG export, .zentangle.md serialization, etc.).

// 6z-2b: tile size → canvas px attribute (real resize, Q3=A user decision).
// Bijou 5cm / 標準 9cm / 學徒磚 ~15cm — proportional 6z-1 baseline (9cm = 600px).
const TILE_SIZES = {
  bijou: 360,         // ~5cm @ ~67px/cm
  standard: 600,      // 9cm baseline (Q2)
  apprentice: 900,    // ~13.5cm — viewport-friendly cap (vs spec 15cm)
};
const TILE_MARGIN_RATIO = 0.10;  // ~10% inset; 字 outline 不貼邊
const DOT_RADIUS = 3;         // px
const DOT_COLOR = "#222";
const BORDER_COLOR = "#bbb";
const OUTLINE_COLOR = "#222";
const OUTLINE_WIDTH = 1.5;

// Helpers — derive current tile size + margin from in-memory config.
function currentTileSize() {
  return TILE_SIZES[_config?.tileSize] || TILE_SIZES.standard;
}
function currentTileMargin() {
  return Math.round(currentTileSize() * TILE_MARGIN_RATIO);
}

// localStorage key for persisted force-modal config (per session, browser-local).
const CONFIG_STORAGE_KEY = "stroke_order.zentangle.config.v1";

// 6z-1D config schema. v1 is the very first; bump to v2 when fields shift.
const CONFIG_SCHEMA_VERSION = 1;

// 6z-1.1: acquisition-first default config — show first paint immediately,
// don't block on a force-modal. User explicit thesis decision (5/7 evening):
// 「會用電腦操作來取代手繪的人，本來就已經設想要快速做出禪繞效果」 — first-
// paint friction hurts acquisition more than silent defaults hurt verification.
// D-C 強紀律弱預設 仍適用於高代價 ops 場景（NIC 名稱錯 = 斷網），但 UX
// acquisition target 不該為 strict input rigor 付 first-paint cost。Modal
// 仍 wired up，user 主動按「重新設定紙磚」可開啟調整。
const DEFAULT_CONFIG = {
  char: "心",
  mode: "hollow",      // 空心填充
  tileSize: "standard", // 標準磚 (9 cm)
};

// 6z-1D: human labels for the persisted enum values.
const MODE_LABELS = {
  pure: "純禪繞",
  hollow: "空心填充",
  bg: "背景鑲嵌",
};
const TILE_LABELS = {
  bijou: "Bijou (5 cm)",
  standard: "標準磚 (9 cm)",
  apprentice: "學徒磚 (~15 cm)",
};

// Defer-once init flag — avoids repeated DOM lookups when user toggles
// modes back and forth.
let _booted = false;
let _ctx = null;
let _statusEl = null;
let _charInput = null;
let _sourceSelect = null;
let _configDisplay = null;

// In-memory config — mirror of localStorage. null until force-modal confirmed.
let _config = null;

// 6z-2c per-session rotation state (Q5=B, NOT persisted across reload).
//   _rotationDegrees: current applied rotation (0 = upright)
//   _rotationHistory: stack of previous angles for L2「上次角度」
let _rotationDegrees = 0;
const _rotationHistory = [];
const ROTATION_HISTORY_MAX = 16;  // bounded to keep memory tame

// 6z-2.1: cache the last successfully fetched contours so rotation /
// tile-resize redraws don't re-hit the server. Cleared whenever the
// outline source changes (char / source select).
let _cachedContours = null;

// 6z-3: active tangle key (per-session state, NOT persisted).
//   "none"          → no tangle layer rendered
//   "crescent_moon" → 6z-3 MVP
//   "florz"         → 6z-3 MVP
//   (others 6z-3.X)
// △ Triangle / R 鍵 cycles through this list.
let _activeTangle = "none";

// 6z-3: tangle render style (kept module-level so 6z-3.X density UI can mutate).
const TANGLE_DENSITY = "medium";  // 6z-3 MVP fixed; future: tie to L3 cycle / radio
const TANGLE_STROKE = "#444";
const TANGLE_FILL = "#444";
const TANGLE_LINE_WIDTH = 1;

// 5df-2: 區段模型（per-session, NOT persisted）。
// regions = [{id, kind: "glyph"|"bg", band, tangle, orientation}]
// hollow（空心填充）→ glyph 區段；bg（背景鑲嵌）→ bg 區段。
// 每次「產生」（renderOutline）或切模式/紙磚尺寸時重抽（隨機填充）。
// 5df-3 互動編輯會直接改單一 region 的 tangle / orientation。
let _regions = [];

// 5df-3: 選中的區段 id（per-session；重抽即清空——區段換了一批、舊
// 選取沒有意義）。null = 未選取。方向鍵情境切換靠這個判斷：
// 有選中 → ⬆⬇⬅➡ 歸區段朝向；未選中 → 維持 6z-5a 透視（QODA 定案）。
let _selectedRegionId = null;

// 5df-3: 選中高亮樣式（canvas 不吃 CSS var，用字面色）。
const REGION_HILITE_COLOR = "#c33";
const REGION_HILITE_DASH = [6, 4];

// 5df-4/5dh: 切分狀態（per-session）。
//   _splitMode : ✂ 切分模式開關——開著時 canvas 點擊走切割線流程
//   _splitState: 三階段曲線切割狀態機（5dh 使用者規格：
//     點起點 → 移動預覽直線 → 點終點 → 滑鼠調彎曲率 → 雙擊定案）
//     null                                  = 待起點
//     {phase:1, a, regionId, hover}         = 已定起點、預覽 a→游標
//     {phase:2, a, b, ctrl, regionId}       = 已定終點、游標調 ctrl
//   _showSplitLines: 淡虛線顯示全部區段分界（可隱藏）
let _splitMode = false;
let _splitState = null;
let _showSplitLines = true;
const SPLIT_LINE_COLOR = "#bbb";
const SPLIT_LINE_DASH = [4, 4];

// 5dh: 區段每模式各存一份——空心/背景切換互不清空（使用者定案：
// 按「清除區段」才清空）。字形重載使 hollow 失效；紙磚尺寸變更
// 使兩者都失效（band 是 tile-local px）。
const _regionStash = {hollow: null, bg: null};

// 5dh: mousemove 預覽用 rAF 節流旗標。
let _redrawQueued = false;

// 6z-3.5: user-placed tangle units (per-session, per Q5=B mirror policy).
// Each entry: {tangle: "crescent_moon"|"florz", cx, cy} in TILE-LOCAL px.
// Render iterates this array via TANGLES[tangle].buildUnit; the click
// handler inverse-transforms viewport coords → tile-local before push.
let _placedUnits = [];

// 6z-3.5: last placement direction (vector from 2nd-last → last unit).
// Updated each click that produces ≥ 2 units. Used by REPEAT_3 / R 鍵.
let _lastDirection = null;  // [dx, dy] in tile-local px, or null

// 6z-3.5: per-unit visual scale (~ same as auto-fill grid spacing).
const PLACED_UNIT_SCALE = 45;

// 6z-5a: pseudo-3D sticky state — set by D-Pad / 4 button clicks / Arrow keys.
//   - All NEW placed units inherit this (sticky); old units keep their own
//   - Click a direction button → set sticky + apply to last placed unit
//   - Slider → set sticky degree + sync last unit's degree
//   - 「無透視」 button → clear sticky + clear last unit pseudo_3d
let _stickyDepthDir = null;
let _stickyDepthDegree = 0.5;

// 6z-5b: curve mode sticky state (parallel to depth_dir but independent).
// 6z-5b MVP only exposes 軸 1 (high-mid) in UI; pseudo3d.mjs supports all 4
// (high-sides / left-high / right-high) but UI 解鎖留 6z-5c 視覺評估後決定。
let _stickyCurveMode = null;
let _stickyCurveDegree = 0.5;

// 6z-5a: Arrow-key dispatcher arg → pseudo3d.mjs depth_dir name.
// (KEY_MAP in 6z-1E uses "up"/"down"/"left"/"right" args; our schema uses
// "forward"/"backward"/"left"/"right" — translate at the dispatch boundary
// to keep the input layer agnostic of perspective semantics.)
const KEY_DIR_TO_PSEUDO3D = {
  up: "forward",
  down: "backward",
  left: "left",
  right: "right",
};

// 6z-2.2: pan state — quick-peek at rotation overflow corners.
//   "center" : no pan (default; corners may exceed viewport when rotated)
//   "top"    : pan tile DOWN to reveal what was hidden at TOP
//   "bottom" : pan tile UP   to reveal what was hidden at BOTTOM
//   "left"   : pan tile RIGHT to reveal what was hidden at LEFT
//   "right"  : pan tile LEFT  to reveal what was hidden at RIGHT
// Per-session, NOT persisted (mirrors _rotationDegrees policy).
// Toggle: same side again → center; different side → switch.
let _panState = "center";

/**
 * Boot — runs once, on first activation of zentangle mode.
 */
function boot() {
  if (_booted) return;
  const canvas = document.getElementById("zentangle-canvas");
  if (!canvas) {
    // index.html missing the section — defensive guard so a typo doesn't
    // crash the rest of the page.
    console.warn("[zentangle] #zentangle-canvas not found; abort boot");
    return;
  }
  _ctx = canvas.getContext("2d");
  _statusEl = document.getElementById("zentangle-status");
  _charInput = document.getElementById("zentangle-char");
  _sourceSelect = document.getElementById("zentangle-source");
  _configDisplay = document.getElementById("zentangle-config-display");
  drawTileBackground();
  loadSources().catch((e) => setStatus(`字體清單載入失敗：${e.message}`, true));
  const renderBtn = document.getElementById("zentangle-render");
  if (renderBtn) {
    renderBtn.addEventListener("click", () => {
      renderOutline().catch((e) =>
        setStatus(`載入字框失敗：${e.message}`, true)
      );
    });
  }
  // 6z-1.2: inline controls (取代 modal) — change → 立即 persist + re-render.
  wireInlineControls();
  // 6z-1E: input scaffolding (鍵盤 + 滑鼠 + Web Gamepad API stubs).
  wireInputScaffolding();

  // 6z-1.1: acquisition-first — apply persisted config, else fall back to
  // DEFAULT_CONFIG and render immediately. No first-paint blocking.
  applyConfig(readConfig() || DEFAULT_CONFIG);
  // 6z-2b: ensure canvas attribute matches restored config (HTML default
  // is standard=600; reloading with bijou/apprentice needs explicit resize).
  resizeCanvasToConfig();
  drawTileBackground();
  renderOutline().catch((e) =>
    setStatus(`預設字框載入失敗：${e.message}（請選擇字體後手動載入）`, true)
  );
  _booted = true;
}

/**
 * Listen for mode change → boot zentangle on first activation.
 */
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll('input[name="mode"]').forEach((r) => {
    r.addEventListener("change", () => {
      const mode = document.querySelector('input[name="mode"]:checked')?.value;
      if (mode === "zentangle") boot();
    });
  });
  // If page loads with mode=zentangle already selected (e.g. via deep-link),
  // boot immediately.
  const initialMode = document.querySelector('input[name="mode"]:checked')?.value;
  if (initialMode === "zentangle") boot();
});

// ---------------------------------------------------------------------------
// Canvas drawing
// ---------------------------------------------------------------------------

// 6z-2.1: split tile rendering into 3 helpers so the frame + outline rotate
// TOGETHER under a single ctx transform (was previously: frame axis-aligned,
// outline pre-rotated via rotateContours — visual mismatch when ≠ 0°).
//
//   clearCanvas()         — clear + white bg, axis-aligned (always)
//   drawTileFrame()       — border + 4 corner dots (called inside ctx rotate)
//   withTileRotation(fn)  — ctx.save + translate/rotate + fn() + ctx.restore
//   redrawAll()           — full pipeline orchestrator (replaces dual call)

function clearCanvas() {
  if (!_ctx) return;
  const ts = currentTileSize();
  // Clear in axis-aligned space so the entire pixel area is wiped even when
  // a previous rotation left content outside the post-rotation rect.
  _ctx.clearRect(0, 0, ts, ts);
  _ctx.fillStyle = "#ffffff";
  _ctx.fillRect(0, 0, ts, ts);
}

function drawTileFrame() {
  if (!_ctx) return;
  const ts = currentTileSize();
  const tm = currentTileMargin();
  // Thin border — inset by 1px so it lives inside the canvas.
  _ctx.strokeStyle = BORDER_COLOR;
  _ctx.lineWidth = 1;
  _ctx.strokeRect(0.5, 0.5, ts - 1, ts - 1);
  // 4-corner dots — classic Zentangle tile signature.
  _ctx.fillStyle = DOT_COLOR;
  const corners = [
    [tm / 2, tm / 2],
    [ts - tm / 2, tm / 2],
    [tm / 2, ts - tm / 2],
    [ts - tm / 2, ts - tm / 2],
  ];
  for (const [cx, cy] of corners) {
    _ctx.beginPath();
    _ctx.arc(cx, cy, DOT_RADIUS, 0, Math.PI * 2);
    _ctx.fill();
  }
}

/**
 * 6z-2.2: compute how many px of the rotated bbox extend beyond the
 * canvas on each side. For a square tile rotated by θ:
 *   bboxExt = ts · (|cos θ| + |sin θ|)
 *   overflowPerSide = max(0, (bboxExt − ts) / 2)
 * At θ=0 → 0; at θ=45° → ts·(√2−1)/2 ≈ 0.207·ts.
 */
function rotationOverflow() {
  if (_rotationDegrees === 0) return 0;
  const θ = (_rotationDegrees * Math.PI) / 180;
  const ts = currentTileSize();
  const bboxExt = ts * (Math.abs(Math.cos(θ)) + Math.abs(Math.sin(θ)));
  return Math.max(0, (bboxExt - ts) / 2);
}

/**
 * 6z-2.2: derive [panX, panY] in canvas px from current _panState +
 * rotation. Pan is the displacement applied to the tile content (rotated
 * draws are shifted by this vector). The amount = rotationOverflow() so a
 * single press reveals the full hidden corner on that side.
 */
function computePanOffset() {
  if (_panState === "center") return [0, 0];
  const v = rotationOverflow();
  if (v === 0) return [0, 0];
  switch (_panState) {
    case "top":    return [0,  v];   // shift tile DOWN → top corner visible
    case "bottom": return [0, -v];
    case "left":   return [ v, 0];
    case "right":  return [-v, 0];
    default:       return [0, 0];
  }
}

function withTileRotation(fn) {
  if (!_ctx) return;
  const [px, py] = computePanOffset();
  if (_rotationDegrees === 0 && px === 0 && py === 0) {
    fn();
    return;
  }
  const ts = currentTileSize();
  const cx = ts / 2;
  const cy = ts / 2;
  _ctx.save();
  // 6z-2.2: pan applied first in concat order = displaces the rotated
  // tile after rotation (transform composes right-to-left at draw time:
  // M = T(pan) · T(c) · R(θ) · T(-c), so for any point p,
  //   x' = pan + c + R(θ)(p - c)
  // — exactly the「rotated tile slid by pan」 behaviour we want).
  _ctx.translate(px, py);
  _ctx.translate(cx, cy);
  _ctx.rotate((_rotationDegrees * Math.PI) / 180);
  _ctx.translate(-cx, -cy);
  try {
    fn();
  } finally {
    _ctx.restore();
  }
}

/**
 * Full canvas redraw orchestrator. Used after ANY change that affects what's
 * on screen: rotation, tile size, char/source fetch result.
 *
 * No fetch here — uses _cachedContours. Callers that need fresh data run
 * fetchOutline() → set _cachedContours → call redrawAll().
 */
function redrawAll() {
  if (!_ctx) return;
  clearCanvas();
  withTileRotation(() => {
    drawTileFrame();
    const mapped = currentMappedContours();
    if (mapped) {
      // 5df-2: 區段層墊在字框線之下（outline 蓋在圖樣上、輪廓保持清晰）。
      drawRegionLayer(mapped);
      drawOutline(mapped);
      // 6z-3.5: user-placed units（pure 模式主體；hollow/bg 仍可疊加）
      drawTangleLayer(mapped);
    } else {
      // 字形未載入時 bg 區段仍可渲染（band clip 不依賴字形）。
      drawRegionLayer(null);
    }
  });
}

// ---------------------------------------------------------------------------
// 5df-2 — 區段模型：重抽 + 渲染
// ---------------------------------------------------------------------------

/** 目前快取字形的 tile-local mapped contours（無快取 → null）。 */
function currentMappedContours() {
  if (!_cachedContours || !contoursAreClosed(_cachedContours)) return null;
  const ts = currentTileSize();
  const tm = currentTileMargin();
  return mapContourToTile(_cachedContours, computeBbox(_cachedContours), ts, tm);
}

/**
 * 5df-2/5dh — 取得目前模式的區段。5dh 起每模式各存一份
 * （_regionStash）：模式切換恢復暫存、互不清空；``force`` 或暫存
 * 不存在時才重新生成（隨機填充）。pure 模式無區段。
 */
function ensureRegions({force = false} = {}) {
  _regions = [];
  _selectedRegionId = null;   // 5df-3: 區段換批/換模式、選取失效
  _splitState = null;         // 5dh: 進行中的切割線也失效（模式維持）
  const mode = _config?.mode;
  if (mode !== "hollow" && mode !== "bg") return;
  if (!force && _regionStash[mode]) {
    _regions = _regionStash[mode];
    return;
  }
  const keys = listTangles().map((t) => t.key);
  if (mode === "bg") {
    // 5dh: 預設單一整區＝填滿字形以外全部（要細分用 ✂ 切分）。
    const base = computeBgRegions(currentTileSize(), currentTileMargin());
    _regions = assignRandomTangles(base, keys);
  } else {
    const mapped = currentMappedContours();
    if (!mapped || mapped.length === 0) return;
    _regions = assignRandomTangles(computeGlyphRegions(mapped), keys);
  }
  _regionStash[mode] = _regions;
}

/**
 * 5dh/5di — 清除目前模式的區段（使用者定案：按鈕才清空）。
 * 5di 改語意：清除＝**全部留白**（保留區段結構與切分線）——縮圖鈕
 * 立即可再上圖樣，不再是「刪光區段 → 點什麼都沒反應」的死路；
 * 並自動退出 ✂ 切分模式（避免清除後點擊仍被切割流程攔截）。
 */
function clearRegions() {
  const mode = _config?.mode;
  if (mode !== "hollow" && mode !== "bg") {
    setStatus("清除區段只作用於空心填充/背景鑲嵌模式", true);
    return;
  }
  if (_splitMode) setSplitMode(false);
  for (const region of _regions) {
    region.tangle = null;
    region.enhancers = {};   // 全關（normalizeEnhancers 缺欄補 false）
  }
  _selectedRegionId = null;
  _splitState = null;
  redrawAll();
  refreshEnhancerToggles();
  // bg 暫存跨字形重載保留（5dh）——「載入字框」只會重抽 hollow。
  setStatus(`${mode === "hollow" ? "空心填充" : "背景鑲嵌"}區段已全部留白` +
            "——點縮圖重新上圖樣" +
            (mode === "hollow" ? "、「載入字框」重新隨機填充" : ""));
}

/** mapped contours → Path2D（每 contour 一 sub-path、closePath）。 */
function buildGlyphPath(mappedContours) {
  const path = new Path2D();
  for (const poly of mappedContours) {
    if (!Array.isArray(poly) || poly.length < 3) continue;
    path.moveTo(poly[0][0], poly[0][1]);
    for (let i = 1; i < poly.length; i++) {
      path.lineTo(poly[i][0], poly[i][1]);
    }
    path.closePath();
  }
  return path;
}

/**
 * 5df-2 — 渲染區段層。雙重 clip（設計草稿 ②）：
 *   glyph: clip(字形 path, evenodd) ∩ clip(band rect)   ← 孔洞自動排除
 *   bg   : clip(band rect) ∩ clip(大矩形＋字形, evenodd) ← 字形當洞扣掉
 * 呼叫端保證在 withTileRotation 內（區段存 tile-local 座標、跟磚一起轉）。
 */
function drawRegionLayer(mappedContours) {
  if (_regions.length === 0 || !_ctx) return;
  const hasGlyph =
    Array.isArray(mappedContours) && mappedContours.length > 0;
  const glyphPath = hasGlyph ? buildGlyphPath(mappedContours) : null;
  // bg 用的「扣字形」path：大矩形 + 字形 contours，evenodd。
  let bgHolePath = null;
  if (hasGlyph) {
    const ts = currentTileSize();
    bgHolePath = new Path2D();
    bgHolePath.rect(-ts, -ts, ts * 3, ts * 3);
    for (const poly of mappedContours) {
      if (!Array.isArray(poly) || poly.length < 3) continue;
      bgHolePath.moveTo(poly[0][0], poly[0][1]);
      for (let i = 1; i < poly.length; i++) {
        bgHolePath.lineTo(poly[i][0], poly[i][1]);
      }
      bgHolePath.closePath();
    }
  }
  _ctx.save();
  _ctx.strokeStyle = TANGLE_STROKE;
  _ctx.fillStyle = TANGLE_FILL;
  _ctx.lineWidth = TANGLE_LINE_WIDTH;
  _ctx.lineJoin = "round";
  _ctx.lineCap = "round";
  for (const region of _regions) {
    if (!region.tangle) continue;                         // 5df-3: 留白區段
    if (region.kind === "glyph" && !glyphPath) continue;  // 字形未載入
    _ctx.save();
    // 5df-4: 切分後的區段用 poly clip；原生區段用 band 矩形。
    const shapePath = regionShapePath(region);
    if (region.kind === "glyph") {
      _ctx.clip(glyphPath, "evenodd");
      _ctx.clip(shapePath);
    } else {
      _ctx.clip(shapePath);
      if (bgHolePath) _ctx.clip(bgHolePath, "evenodd");
    }
    // 5dh: 連續 spacing——元素大小跟著區塊自動調整（筆畫窄元素小）。
    let specs = buildTangleOriented(
      region.tangle, region.band,
      pickSpacing(region.band, region.kind),
      region.orientation
    );
    // 5dj-1: 延伸技法管線（build → orient → enhance）。每區段獨立記
    // 自己勾了哪些 enhancer；有開才套（短路避免無謂複製）。
    if (hasAnyEnhancer(region.enhancers)) {
      // 5dj-2/3: dewdrop 需要區段 band；全域參數（滑桿）併入 opts。
      specs = applyEnhancers(specs, region.enhancers,
        paramsToOpts(_enhancerParams,
                     {baseLineWidth: TANGLE_LINE_WIDTH, area: region.band}));
    }
    renderTangleSpecs(_ctx, specs);
    _ctx.restore();
  }
  // 5df-4: 區段分界淡虛線（可隱藏；畫在圖樣上、高亮下）。
  if (_showSplitLines) {
    _ctx.save();
    _ctx.strokeStyle = SPLIT_LINE_COLOR;
    _ctx.lineWidth = 1;
    _ctx.setLineDash(SPLIT_LINE_DASH);
    for (const region of _regions) {
      _ctx.stroke(regionShapePath(region));
    }
    _ctx.restore();
  }
  // 5df-3: 選中區段高亮（虛線框、畫在圖樣之上、不受 clip）。
  if (_selectedRegionId !== null) {
    const sel = _regions.find((r) => r.id === _selectedRegionId);
    if (sel) {
      _ctx.save();
      _ctx.strokeStyle = REGION_HILITE_COLOR;
      _ctx.lineWidth = 1.5;
      _ctx.setLineDash(REGION_HILITE_DASH);
      _ctx.stroke(regionShapePath(sel));
      _ctx.restore();
    }
  }
  // 5dh: 虛擬切割線預覽（三階段：直線預覽 → 曲率調整）。
  if (_splitState) {
    _ctx.save();
    _ctx.strokeStyle = REGION_HILITE_COLOR;
    _ctx.fillStyle = REGION_HILITE_COLOR;
    _ctx.lineWidth = 1.5;
    _ctx.setLineDash([8, 5]);
    const st = _splitState;
    _ctx.beginPath();
    if (st.phase === 1 && st.hover) {
      _ctx.moveTo(st.a[0], st.a[1]);
      _ctx.lineTo(st.hover[0], st.hover[1]);
      _ctx.stroke();
    } else if (st.phase === 2) {
      _ctx.moveTo(st.a[0], st.a[1]);
      _ctx.quadraticCurveTo(st.ctrl[0], st.ctrl[1], st.b[0], st.b[1]);
      _ctx.stroke();
    }
    _ctx.setLineDash([]);
    for (const p of [st.a, st.b].filter(Boolean)) {
      _ctx.beginPath();
      _ctx.arc(p[0], p[1], 4, 0, Math.PI * 2);
      _ctx.fill();
    }
    _ctx.restore();
  }
  _ctx.restore();
}

/** 5df-4 — 區段形狀 Path2D：poly（切分後）或 band 矩形（原生）。 */
function regionShapePath(region) {
  const p = new Path2D();
  if (Array.isArray(region.poly) && region.poly.length >= 3) {
    p.moveTo(region.poly[0][0], region.poly[0][1]);
    for (let i = 1; i < region.poly.length; i++) {
      p.lineTo(region.poly[i][0], region.poly[i][1]);
    }
    p.closePath();
  } else {
    p.rect(region.band.x, region.band.y, region.band.w, region.band.h);
  }
  return p;
}

// ---------------------------------------------------------------------------
// 5df-3 — 區段互動編輯（點選 / 圖樣鈕列 / 留白 / 方向鍵情境切換）
// ---------------------------------------------------------------------------

function selectedRegion() {
  if (_selectedRegionId === null) return null;
  return _regions.find((r) => r.id === _selectedRegionId) || null;
}

/** click event → tile-local [x, y]（CSS 縮放＋旋轉/pan 反變換）。 */
function clickToTileLocal(e, canvas) {
  const rect = canvas.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return null;
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const viewX = (e.clientX - rect.left) * scaleX;
  const viewY = (e.clientY - rect.top) * scaleY;
  return viewportToTileLocal(viewX, viewY);
}

/** canvas 點選分流：hollow/bg → 切分或選區段；pure → 6z-3.5 手放 unit。 */
function onCanvasClick(e, canvas) {
  const mode = _config?.mode;
  if (mode === "hollow" || mode === "bg") {
    if (_splitMode) {
      const pt = clickToTileLocal(e, canvas);
      if (pt) handleSplitClick(pt);
      return;
    }
    selectRegionAtClick(e, canvas);
    return;
  }
  placeUnitAtClick(e, canvas);
}

/** rAF 節流的 redrawAll（mousemove 預覽用）。 */
function queueRedraw() {
  if (_redrawQueued) return;
  _redrawQueued = true;
  requestAnimationFrame(() => {
    _redrawQueued = false;
    redrawAll();
  });
}

/** 二次貝茲攤平成折線（含兩端沿切線延長 ext px＝保證貫穿區段）。 */
function flattenQuadExtended(a, ctrl, b, ext, segs = 32) {
  const pts = [];
  for (let i = 0; i <= segs; i++) {
    const t = i / segs;
    const u = 1 - t;
    pts.push([
      u * u * a[0] + 2 * u * t * ctrl[0] + t * t * b[0],
      u * u * a[1] + 2 * u * t * ctrl[1] + t * t * b[1],
    ]);
  }
  // 端點切線方向（t=0: a→ctrl；t=1: ctrl→b）；退化時用 a→b。
  let d0x = ctrl[0] - a[0], d0y = ctrl[1] - a[1];
  let d1x = b[0] - ctrl[0], d1y = b[1] - ctrl[1];
  if (Math.hypot(d0x, d0y) < 1e-6) { d0x = b[0] - a[0]; d0y = b[1] - a[1]; }
  if (Math.hypot(d1x, d1y) < 1e-6) { d1x = b[0] - a[0]; d1y = b[1] - a[1]; }
  const n0 = Math.hypot(d0x, d0y) || 1;
  const n1 = Math.hypot(d1x, d1y) || 1;
  pts.unshift([a[0] - (d0x / n0) * ext, a[1] - (d0y / n0) * ext]);
  pts.push([b[0] + (d1x / n1) * ext, b[1] + (d1y / n1) * ext]);
  return pts;
}

/**
 * 5dh — 曲線切割三階段（使用者規格）：
 *   click 1（區段內）→ 定起點，滑鼠移動預覽直線
 *   click 2（同區段）→ 定終點，滑鼠移動調整彎曲曲率（曲線過游標）
 *   double-click     → 固定虛擬切割線、執行剖分
 */
function handleSplitClick(pt) {
  const [x, y] = pt;
  const region = resolveRegionAt(_regions, currentMappedContours(), x, y);
  if (!_splitState) {
    if (!region) {
      setStatus("切分：請點在某個區段內定起點", true);
      return;
    }
    _splitState = {phase: 1, a: pt, regionId: region.id, hover: null};
    redrawAll();
    setStatus(`切分：起點已定（區段 ${region.id}）——移動滑鼠預覽、` +
              "同區段內點終點");
    return;
  }
  if (_splitState.phase === 1) {
    if (!region || region.id !== _splitState.regionId) {
      _splitState = null;
      redrawAll();
      setStatus("切分：終點要落在同一個區段內——已重設，請重點起點", true);
      return;
    }
    const a = _splitState.a;
    _splitState = {
      phase: 2, a, b: pt,
      ctrl: [(a[0] + x) / 2, (a[1] + y) / 2],   // 初始＝直線
      regionId: region.id,
    };
    redrawAll();
    setStatus("切分：移動滑鼠調整彎曲曲率（曲線會跟著游標）——" +
              "雙擊固定切割線");
    return;
  }
  // phase 2：單擊不動作（雙擊才定案；雙擊自帶的兩次 click 落在這裡）。
}

/** 5dh — 滑鼠移動：階段 1 預覽直線、階段 2 調整曲率（曲線過游標）。 */
function handleSplitMove(pt) {
  if (!_splitState) return;
  if (_splitState.phase === 1) {
    _splitState.hover = pt;
  } else {
    const {a, b} = _splitState;
    // 讓曲線在 t=0.5 恰通過游標：ctrl = 2M − (a+b)/2。
    _splitState.ctrl = [
      2 * pt[0] - (a[0] + b[0]) / 2,
      2 * pt[1] - (a[1] + b[1]) / 2,
    ];
  }
  queueRedraw();
}

/** 5dh — 雙擊定案：攤平曲線＋兩端延長 → 圍籬剖分。 */
function commitSplit() {
  if (!_splitState || _splitState.phase !== 2) return;
  const {a, b, ctrl, regionId} = _splitState;
  const idx = _regions.findIndex((r) => r.id === regionId);
  const region = idx >= 0 ? _regions[idx] : null;
  _splitState = null;
  if (!region) {
    redrawAll();
    setStatus("切分失敗：區段不存在", true);
    return;
  }
  const ext = Math.hypot(region.band.w, region.band.h) * 2 + 10;
  const fence = flattenQuadExtended(a, ctrl, b, ext);
  const res = splitRegionByPolyline(region, fence);
  if (!res.ok) {
    redrawAll();
    setStatus(`切分失敗：${res.reason}`, true);
    return;
  }
  // 原位替換＝保持疊序（z-order）不變。
  _regions.splice(idx, 1, ...res.parts);
  _selectedRegionId = null;
  redrawAll();
  setStatus(
    `切分完成：${region.id} → ${res.parts[0].id}＋${res.parts[1].id}` +
    "（兩半繼承原圖樣；退出切分模式後可分別點選改圖樣/朝向）"
  );
}

/** 5df-4 — 切分模式開關（開啟時清除選取，避免兩套點擊語意打架）。 */
function setSplitMode(on) {
  _splitMode = on;
  _splitState = null;
  if (on) _selectedRegionId = null;
  const btn = document.getElementById("zentangle-split-toggle");
  if (btn) {
    btn.style.background = on ? REGION_HILITE_COLOR : "#fafaf8";
    btn.style.color = on ? "#fff" : "#444";
    btn.style.borderColor = on ? REGION_HILITE_COLOR : "var(--border)";
  }
  redrawAll();
  setStatus(
    on
      ? "✂ 切分模式：點起點 → 點終點 → 移動滑鼠調彎 → 雙擊固定" +
        "（再按 ✂ 退出）"
      : "已退出切分模式（點選區段編輯）"
  );
}

/**
 * 5dj-4/5dk — 匯出目前紙磚的裝飾筆劃（含全部延伸技法）為 SVG / G-code / DXF。
 * 與 drawRegionLayer 同管線收集折線、精確裁切貼合字形/背景，換算 mm 尺寸。
 * 5dk：全域匯出設定 _exportOpts（填色模式/掃描間距/線寬/精細度/含字框）。
 */
function exportZentangle(fmt) {
  const mode = _config?.mode;
  if (mode !== "hollow" && mode !== "bg") {
    setStatus("匯出限空心填充/背景鑲嵌模式（純禪繞的手放圖樣另計）", true);
    return;
  }
  if (!_regions.some((r) => r.tangle)) {
    setStatus("目前沒有圖樣可匯出——先點縮圖上圖樣", true);
    return;
  }
  const tileSize = currentTileSize();
  const tileMm = TILE_MM[_config?.tileSize] || TILE_MM.standard;
  const paths = collectExportPaths({
    regions: _regions,
    mappedContours: currentMappedContours(),
    params: _enhancerParams,
    tileSize, tileMm,
    baseLineWidth: TANGLE_LINE_WIDTH,
    includeOutline: _exportOpts.includeOutline,
    fillMode: _exportOpts.fillMode,
    scanSpacingMm: _exportOpts.scanSpacingMm,
    curveSegs: _exportOpts.curveSegs,
    arcSegs: Math.round(_exportOpts.curveSegs * 1.6),
    paramsToOpts,
  });
  const nSeg = paths.strokes.length + paths.fills.length + paths.outline.length;
  if (nSeg === 0) {
    setStatus("裁切後無可匯出路徑（圖樣可能全落在區段外）", true);
    return;
  }
  const char = (_charInput?.value || "禪繞").trim() || "禪繞";
  const emitOpts = {tileSize, tileMm, strokeMm: _exportOpts.strokeMm,
                    includeOutline: _exportOpts.includeOutline};
  let content, mime, ext;
  if (fmt === "svg") {
    content = pathsToSvg(paths, emitOpts);
    mime = "image/svg+xml"; ext = "svg";
  } else if (fmt === "dxf") {
    content = pathsToDxf(paths, emitOpts);
    mime = "application/dxf"; ext = "dxf";
  } else {
    content = pathsToGcode(paths, emitOpts);
    mime = "text/plain"; ext = "gcode";
  }
  const blob = new Blob([content], {type: mime});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `zentangle_${char}_${_config.tileSize}.${ext}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  const fillNote = _exportOpts.fillMode === "scan"
    ? `、${paths.fills.length} 掃描填充` : "";
  setStatus(`已匯出 ${ext.toUpperCase()}：${paths.strokes.length} 圖樣折線` +
            fillNote + ` + ${paths.outline.length} 字框（${tileMm}mm 紙磚）`);
}

/**
 * 5dk — 匯出設定 UI（全域一組；改 _exportOpts → 下次匯出生效）。
 */
function buildExportControls() {
  const host = document.getElementById("zentangle-export-opts");
  if (!host) return;
  host.innerHTML = "";
  // 填色模式 select。
  const fillWrap = document.createElement("label");
  fillWrap.style.cssText = "font-size:11px;color:var(--muted);display:inline-flex;align-items:center;gap:3px;";
  fillWrap.appendChild(document.createTextNode("填色形狀 "));
  const sel = document.createElement("select");
  sel.style.cssText = "font-size:11px;";
  for (const [v, label] of [["outline", "輪廓化"], ["scan", "雷雕掃描填充"], ["skip", "略過"]]) {
    const o = document.createElement("option");
    o.value = v; o.textContent = label;
    if (v === _exportOpts.fillMode) o.selected = true;
    sel.appendChild(o);
  }
  sel.addEventListener("change", () => { _exportOpts.fillMode = sel.value; });
  fillWrap.appendChild(sel);
  host.appendChild(fillWrap);
  // 數值滑桿：掃描間距 / 線寬 / 曲線精細度。
  const mkSlider = (label, key, min, max, step, fmtFn) => {
    const wrap = document.createElement("label");
    wrap.style.cssText = "font-size:11px;color:var(--muted);display:inline-flex;align-items:center;gap:4px;white-space:nowrap;";
    const val = document.createElement("span");
    val.style.cssText = "min-width:30px;text-align:right;font-variant-numeric:tabular-nums;";
    val.textContent = fmtFn(_exportOpts[key]);
    const rng = document.createElement("input");
    rng.type = "range"; rng.min = min; rng.max = max; rng.step = step;
    rng.value = String(_exportOpts[key]); rng.style.cssText = "width:70px;";
    rng.addEventListener("input", () => {
      _exportOpts[key] = rng.valueAsNumber; val.textContent = fmtFn(rng.valueAsNumber);
    });
    wrap.appendChild(document.createTextNode(label + " "));
    wrap.appendChild(rng); wrap.appendChild(val);
    host.appendChild(wrap);
  };
  mkSlider("掃描間距", "scanSpacingMm", 0.3, 3, 0.1, (v) => v.toFixed(1) + "mm");
  mkSlider("線寬", "strokeMm", 0.1, 1.0, 0.05, (v) => v.toFixed(2));
  mkSlider("曲線精細", "curveSegs", 8, 48, 4, (v) => String(v));
  // 含字框 checkbox。
  const olWrap = document.createElement("label");
  olWrap.style.cssText = "font-size:11px;color:var(--muted);cursor:pointer;display:inline-flex;align-items:center;gap:3px;";
  const cb = document.createElement("input");
  cb.type = "checkbox"; cb.checked = _exportOpts.includeOutline;
  cb.addEventListener("change", () => { _exportOpts.includeOutline = cb.checked; });
  olWrap.appendChild(cb);
  olWrap.appendChild(document.createTextNode("含字框輪廓"));
  host.appendChild(olWrap);
}

function wireSplitControls() {
  const btn = document.getElementById("zentangle-split-toggle");
  if (btn) btn.addEventListener("click", () => setSplitMode(!_splitMode));
  const chk = document.getElementById("zentangle-split-lines");
  if (chk) {
    chk.checked = _showSplitLines;
    chk.addEventListener("change", () => {
      _showSplitLines = chk.checked;
      redrawAll();
      setStatus(_showSplitLines ? "切分線 → 顯示（淡虛線）" : "切分線 → 隱藏");
    });
  }
  // 5dh: 清除區段（按鈕才清空——模式切換不清）。
  const clearBtn = document.getElementById("zentangle-region-clear");
  if (clearBtn) clearBtn.addEventListener("click", clearRegions);
  // 5dj-4/5dk: 延伸效果向量匯出（SVG / G-code / DXF）＋匯出設定 UI。
  const svgBtn = document.getElementById("zentangle-export-svg");
  if (svgBtn) svgBtn.addEventListener("click", () => exportZentangle("svg"));
  const gcodeBtn = document.getElementById("zentangle-export-gcode");
  if (gcodeBtn) gcodeBtn.addEventListener("click", () => exportZentangle("gcode"));
  const dxfBtn = document.getElementById("zentangle-export-dxf");
  if (dxfBtn) dxfBtn.addEventListener("click", () => exportZentangle("dxf"));
  buildExportControls();
  // 5dh: 朝向鈕——直接改選中區段的圖樣朝向（同鍵盤 ⬆⬇⬅➡）。
  document.querySelectorAll(".zt-orient-btn").forEach((ob) => {
    ob.addEventListener("click", () => {
      const dir = ob.dataset.orient;
      if (!setRegionOrientation(dir)) {
        setStatus("先點紙磚選一個區段，再按朝向鈕", true);
      }
    });
  });
  // 5dh: 切割線互動——mousemove 預覽/調彎、dblclick 定案。
  const canvas = document.getElementById("zentangle-canvas");
  if (canvas) {
    canvas.addEventListener("mousemove", (e) => {
      if (!_splitMode || !_splitState) return;
      const pt = clickToTileLocal(e, canvas);
      if (pt) handleSplitMove(pt);
    });
    canvas.addEventListener("dblclick", (e) => {
      if (!_splitMode) return;
      e.preventDefault();
      commitSplit();
    });
  }
}

function selectRegionAtClick(e, canvas) {
  const pt = clickToTileLocal(e, canvas);
  if (!pt) return;
  const region = resolveRegionAt(
    _regions, currentMappedContours(), pt[0], pt[1]);
  if (!region) {
    if (_selectedRegionId !== null) {
      _selectedRegionId = null;
      redrawAll();
      refreshEnhancerToggles();
      setStatus("已取消選取");
    }
    return;
  }
  _selectedRegionId = region.id;
  redrawAll();
  refreshEnhancerToggles();
  const tangleLabel = region.tangle
    ? (TANGLES[region.tangle]?.label || region.tangle)
    : "留白";
  const ens = ENHANCERS.filter((k) => region.enhancers && region.enhancers[k])
    .map((k) => ENHANCER_LABELS[k]);
  setStatus(
    `已選區段 ${region.id}（${region.kind === "glyph" ? "字內" : "背景"}）` +
    `· ${tangleLabel} · 朝向 ${region.orientation}` +
    (ens.length ? ` · 延伸：${ens.join("、")}` : "") +
    "——縮圖換圖樣、勾延伸技法、⬆⬇⬅➡ 轉朝向、點空白取消"
  );
}

/**
 * 圖樣鈕列：改選中區段的 tangle（null = 留白）。
 * 5di（驗收回饋）：**未選取＝套用到目前模式全部區段**——bg 單一整區
 * 時「點縮圖直接切換」符合直覺；hollow 多帶＝整字統一圖樣。
 * 有選取時維持 5df-3 的單區段編輯。
 */
function setRegionTangle(key) {
  if (key !== null && !TANGLES[key]) {
    setStatus(`未知 tangle: ${key}`, true);
    return;
  }
  const r = selectedRegion();
  if (r) {
    r.tangle = key;
    redrawAll();
    setStatus(
      key ? `區段 ${r.id} 圖樣 → ${TANGLES[key].label}` : `區段 ${r.id} → 留白`
    );
    return;
  }
  if (_regions.length === 0) {
    setStatus(
      "目前沒有區段——選「空心填充/背景鑲嵌」模式並按「載入字框」",
      true
    );
    return;
  }
  for (const region of _regions) region.tangle = key;
  redrawAll();
  setStatus(
    (key
      ? `全部區段圖樣 → ${TANGLES[key].label}`
      : "全部區段 → 留白") +
    "（點紙磚選單一區段＝個別改）"
  );
}

/** 方向鍵（情境切換的「選中」分支）：改選中區段朝向。 */
function setRegionOrientation(dir) {
  const r = selectedRegion();
  if (!r) return false;
  r.orientation = dir;
  redrawAll();
  const labels = {up: "上", right: "右", down: "下", left: "左"};
  setStatus(`區段 ${r.id} 朝向 → ${labels[dir] || dir}`);
  return true;
}

/** 單一縮圖鈕：36px canvas 跑該圖樣 builder；點擊＝setRegionTangle。 */
function makeThumbButton(key, title) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "zt-region-btn";
  btn.title = title;                       // hover 顯示英文名
  btn.style.cssText =
    "padding:2px;border:1px solid var(--border);border-radius:3px;" +
    "background:#fff;cursor:pointer;line-height:0;";
  btn.addEventListener("click", () => setRegionTangle(key));
  const cv = document.createElement("canvas");
  cv.width = 36;
  cv.height = 36;
  const c2 = cv.getContext("2d");
  if (c2) {
    c2.strokeStyle = TANGLE_STROKE;
    c2.fillStyle = TANGLE_FILL;
    c2.lineWidth = 1;
    c2.lineJoin = "round";
    c2.lineCap = "round";
    // 5dh 數值 spacing：縮圖用小間距讓 36px 內看得到圖樣單元。
    renderTangleSpecs(c2, buildTangle(key, {x: 1, y: 1, w: 34, h: 34}, 13));
  }
  btn.appendChild(cv);
  return btn;
}

/**
 * 5dj-1 — 三排式工具列：上排 basic（iCSO 五符號）、下排 classic（8 圖樣）
 * 各自從 registry 依 category 動態生成（單一事實源——新圖樣入 registry
 * 標好 category 即自動歸位）。留白鈕掛在 basic 排尾。
 */
function buildRegionToolbar() {
  const basicHost = document.getElementById("zentangle-basic-buttons");
  const classicHost = document.getElementById("zentangle-classic-buttons");
  if (basicHost) {
    basicHost.innerHTML = "";
    for (const t of listTangles({category: "basic"})) {
      basicHost.appendChild(makeThumbButton(t.key, t.label));
    }
    // 留白鈕（文字，沒有圖像可縮）掛在基本排尾。
    const blank = document.createElement("button");
    blank.type = "button";
    blank.title = "Blank — 清空區段的圖樣";
    blank.style.cssText =
      "padding:3px 8px;border:1px solid var(--border);border-radius:3px;" +
      "background:#fafaf8;cursor:pointer;font-size:12px;height:40px;";
    blank.textContent = "留白";
    blank.addEventListener("click", () => setRegionTangle(null));
    basicHost.appendChild(blank);
  }
  if (classicHost) {
    classicHost.innerHTML = "";
    for (const t of listTangles({category: "classic"})) {
      classicHost.appendChild(makeThumbButton(t.key, t.label));
    }
  }
  // 5dj-1: 延伸技法 toggle 列。
  buildEnhancerToggles();
  // 5dj-3: 推薦組合快捷鈕 + 全域參數滑桿。
  buildComboButtons();
  buildParamSliders();
}

/**
 * 5dj-3 — 推薦組合快捷鈕（COMBOS 單一事實源）。點鈕＝一鍵套用
 * tangle + 一組 enhancers 到區段（沿 5di 模型：未選套全部、選中只改該區）。
 */
function buildComboButtons() {
  const host = document.getElementById("zentangle-combo-buttons");
  if (!host) return;
  host.innerHTML = "";
  for (const combo of COMBOS) {
    const btn = document.createElement("button");
    btn.type = "button";
    const ens = ENHANCERS.filter((k) => combo.enhancers[k])
      .map((k) => ENHANCER_LABELS[k].split(" ")[0]).join("＋");
    const tLabel = (TANGLES[combo.tangle]?.label || combo.tangle).split(" ")[0];
    btn.title = `${tLabel}＋${ens}`;
    btn.textContent = combo.label;
    btn.style.cssText =
      "padding:3px 10px;border:1px solid var(--border);border-radius:12px;" +
      "background:#fafaf8;cursor:pointer;font-size:12px;";
    btn.addEventListener("click", () => setRegionCombo(combo));
    host.appendChild(btn);
  }
}

/**
 * 5dj-3 — 套用推薦組合到區段（5di 模型）。設 tangle + 覆蓋 enhancers。
 */
function setRegionCombo(combo) {
  const apply = (r) => {
    r.tangle = combo.tangle;
    r.enhancers = normalizeEnhancers(combo.enhancers);
  };
  const sel = selectedRegion();
  if (sel) {
    apply(sel);
    redrawAll();
    refreshEnhancerToggles();
    setStatus(`區段 ${sel.id} → ${combo.label}`);
    return;
  }
  if (_regions.length === 0) {
    setStatus("目前沒有區段——選「空心填充/背景鑲嵌」並按「載入字框」", true);
    return;
  }
  for (const r of _regions) apply(r);
  redrawAll();
  refreshEnhancerToggles();
  setStatus(`全部區段 → ${combo.label}（點紙磚選單一區段＝個別套）`);
}

/**
 * 5dj-3 — 全域延伸參數滑桿（ENHANCER_PARAM_DEFS 單一事實源）。
 * 一組滑桿即時套用到所有已勾該技法的區段（改 _enhancerParams → redraw）。
 */
function buildParamSliders() {
  const host = document.getElementById("zentangle-param-sliders");
  if (!host) return;
  host.innerHTML = "";
  for (const def of ENHANCER_PARAM_DEFS) {
    const wrap = document.createElement("label");
    wrap.style.cssText =
      "font-size:11px;color:var(--muted);display:inline-flex;align-items:center;" +
      "gap:4px;white-space:nowrap;";
    const val = document.createElement("span");
    val.style.cssText = "min-width:28px;text-align:right;font-variant-numeric:tabular-nums;";
    const fmt = (v) => (def.step < 1 ? v.toFixed(2) : String(v));
    val.textContent = fmt(_enhancerParams[def.key]);
    const rng = document.createElement("input");
    rng.type = "range";
    rng.min = String(def.min); rng.max = String(def.max);
    rng.step = String(def.step); rng.value = String(_enhancerParams[def.key]);
    rng.style.cssText = "width:76px;";
    rng.addEventListener("input", () => {
      _enhancerParams[def.key] = rng.valueAsNumber;
      val.textContent = fmt(rng.valueAsNumber);
      redrawAll();
    });
    wrap.appendChild(document.createTextNode(def.label + " "));
    wrap.appendChild(rng);
    wrap.appendChild(val);
    host.appendChild(wrap);
  }
}

/**
 * 5dj-1 — 延伸技法 toggle 列（ENHANCERS 單一事實源）。每個是 checkbox；
 * 勾/取消套用 5di 慣例：未選區段＝套目前模式全部區段、選中＝只改該區。
 * checkbox 反映「選中區段的狀態」（未選時反映全部區段是否一致）。
 */
function buildEnhancerToggles() {
  const host = document.getElementById("zentangle-enhancer-toggles");
  if (!host) return;
  host.innerHTML = "";
  for (const key of ENHANCERS) {
    const lbl = document.createElement("label");
    lbl.style.cssText =
      "font-size:12px;cursor:pointer;display:inline-flex;align-items:center;" +
      "gap:3px;padding:2px 6px;border:1px solid var(--border);border-radius:3px;";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.dataset.enhancer = key;
    cb.addEventListener("change", () => setRegionEnhancer(key, cb.checked));
    lbl.appendChild(cb);
    lbl.appendChild(document.createTextNode(ENHANCER_LABELS[key]));
    host.appendChild(lbl);
  }
  refreshEnhancerToggles();
}

/** 依「選中區段（或全部區段一致值）」刷新 toggle 勾選狀態。 */
function refreshEnhancerToggles() {
  const host = document.getElementById("zentangle-enhancer-toggles");
  if (!host) return;
  const sel = selectedRegion();
  host.querySelectorAll("input[data-enhancer]").forEach((cb) => {
    const key = cb.dataset.enhancer;
    if (sel) {
      cb.checked = !!(sel.enhancers && sel.enhancers[key]);
      cb.indeterminate = false;
    } else if (_regions.length > 0) {
      // 未選：全部區段一致才顯示勾/空，否則 indeterminate。
      const vals = _regions.map((r) => !!(r.enhancers && r.enhancers[key]));
      const allOn = vals.every(Boolean);
      const allOff = vals.every((v) => !v);
      cb.checked = allOn;
      cb.indeterminate = !allOn && !allOff;
    } else {
      cb.checked = false;
      cb.indeterminate = false;
    }
  });
}

/**
 * 5dj-1 — 勾/取消延伸技法（5di 套用模型）：
 *   有選取 → 只改該區段；未選取 → 套用到目前模式全部區段。
 */
function setRegionEnhancer(key, on) {
  if (!ENHANCERS.includes(key)) return;
  const apply = (r) => {
    r.enhancers = normalizeEnhancers(r.enhancers);
    r.enhancers[key] = on;
  };
  const sel = selectedRegion();
  if (sel) {
    apply(sel);
    redrawAll();
    refreshEnhancerToggles();
    setStatus(`區段 ${sel.id} ${ENHANCER_LABELS[key]} → ${on ? "開" : "關"}`);
    return;
  }
  if (_regions.length === 0) {
    setStatus("目前沒有區段——選「空心填充/背景鑲嵌」並按「載入字框」", true);
    refreshEnhancerToggles();
    return;
  }
  for (const r of _regions) apply(r);
  redrawAll();
  refreshEnhancerToggles();
  setStatus(`全部區段 ${ENHANCER_LABELS[key]} → ${on ? "開" : "關"}` +
            "（點紙磚選單一區段＝個別調）");
}

/**
 * 6z-3.5 — Render USER-PLACED tangle units inside the outline interior.
 *
 * Behavior switch from 6z-3:
 *   - 6z-3 (auto-fill): drawTangleLayer 用 buildTangle(key, area, density) 鋪滿 grid
 *   - 6z-3.5 (user-place): iterate _placedUnits, render each via TANGLES[].buildUnit
 *
 * Why: acquisition-first thesis — 「user 親手畫」 比 auto-fill 「按一個 button 一鍵成型」
 * 更接近 v0.3 §1 主流程「從基底元素開始畫疊加」 設計。User feedback (5/8): 「目前
 * 看起來是自動填滿、後續會如何操控這些元素的疊加方式」 — 直接挑明了 auto-fill ≠ final UX。
 *
 * Q3=B: only pure mode 視覺 (hollow/bg fallback to pure for now, 6z-3.X 補)。
 * Path2D clip("evenodd") 處理 nested contour（如「日」 內框是 hole）。
 */
function drawTangleLayer(mappedContours) {
  if (_placedUnits.length === 0) return;
  if (!Array.isArray(mappedContours) || mappedContours.length === 0) return;
  // Build outline Path2D (one sub-path per contour) for clip.
  const clipPath = new Path2D();
  for (const poly of mappedContours) {
    if (!Array.isArray(poly) || poly.length < 3) continue;
    clipPath.moveTo(poly[0][0], poly[0][1]);
    for (let i = 1; i < poly.length; i++) {
      clipPath.lineTo(poly[i][0], poly[i][1]);
    }
    clipPath.closePath();
  }
  _ctx.save();
  _ctx.clip(clipPath, "evenodd");
  _ctx.strokeStyle = TANGLE_STROKE;
  _ctx.fillStyle = TANGLE_FILL;
  _ctx.lineWidth = TANGLE_LINE_WIDTH;
  _ctx.lineJoin = "round";
  _ctx.lineCap = "round";
  for (const unit of _placedUnits) {
    const t = TANGLES[unit.tangle];
    if (!t || typeof t.buildUnit !== "function") continue;
    let specs = t.buildUnit(unit.cx, unit.cy, PLACED_UNIT_SCALE);
    // 6z-5a: apply depth_dir transform first (forward/backward/left/right).
    if (unit.pseudo_3d && unit.pseudo_3d.depth_dir) {
      specs = applyPseudo3DToSpecs(
        specs,
        unit.cx,
        unit.cy,
        unit.pseudo_3d.depth_dir,
        unit.pseudo_3d.depth_degree
      );
    }
    // 6z-5b: chain curve_mode transform after depth_dir.
    // Pipeline: spec → depth_dir → curve_mode → render
    if (unit.pseudo_3d && unit.pseudo_3d.curve_mode) {
      specs = applyCurveModeToSpecs(
        specs,
        unit.cx,
        unit.cy,
        unit.pseudo_3d.curve_mode,
        unit.pseudo_3d.curve_degree,
        PLACED_UNIT_SCALE
      );
    }
    renderTangleSpecs(_ctx, specs);
  }
  _ctx.restore();
}

/**
 * 6z-3.5 — Inverse the active ctx transform to map a viewport (canvas px)
 * point to TILE-LOCAL coords. Used by the click placement handler so units
 * rotate + pan along with the rest of the tile (stored in tile-local, the
 * subsequent render inside `withTileRotation` re-applies the forward
 * transform — net effect: clicks land where user expects).
 *
 * Forward transform applied at draw time:
 *   M = T(pan) · T(c) · R(θ) · T(-c)
 *   x' = pan + c + R(θ)(p - c)
 * Inverse:
 *   p = c + R(-θ)(x' - pan - c)
 */
function viewportToTileLocal(viewX, viewY) {
  const ts = currentTileSize();
  const cx = ts / 2;
  const cy = ts / 2;
  const [panX, panY] = computePanOffset();
  const θ = -(_rotationDegrees * Math.PI) / 180;
  const cosθ = Math.cos(θ);
  const sinθ = Math.sin(θ);
  const ux = viewX - panX;
  const uy = viewY - panY;
  const dx = ux - cx;
  const dy = uy - cy;
  return [cx + dx * cosθ - dy * sinθ, cy + dx * sinθ + dy * cosθ];
}

/**
 * Backward-compatible alias — earlier sub-phases called this directly.
 * Now redirects through redrawAll so the pipeline stays unified.
 */
function drawTileBackground() {
  redrawAll();
}

/**
 * Resize the canvas backing buffer to match the current tile size.
 * Should be called whenever _config.tileSize changes — after this, redraw.
 */
function resizeCanvasToConfig() {
  const canvas = document.getElementById("zentangle-canvas");
  if (!canvas) return;
  const ts = currentTileSize();
  if (canvas.width !== ts || canvas.height !== ts) {
    canvas.width = ts;
    canvas.height = ts;
    // Re-fetch ctx because resizing the canvas resets state.
    _ctx = canvas.getContext("2d");
  }
}

function drawOutline(mappedContours) {
  if (!_ctx) return;
  _ctx.strokeStyle = OUTLINE_COLOR;
  _ctx.lineWidth = OUTLINE_WIDTH;
  _ctx.lineJoin = "round";
  _ctx.lineCap = "round";
  for (const poly of mappedContours) {
    if (poly.length < 2) continue;
    _ctx.beginPath();
    _ctx.moveTo(poly[0][0], poly[0][1]);
    for (let i = 1; i < poly.length; i++) {
      _ctx.lineTo(poly[i][0], poly[i][1]);
    }
    _ctx.closePath();
    _ctx.stroke();
  }
}

// ---------------------------------------------------------------------------
// Server interaction
// ---------------------------------------------------------------------------

async function loadSources() {
  setStatus("載入字體清單…");
  const r = await fetch("/api/zentangle/sources");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const data = await r.json();
  if (!_sourceSelect) return;
  _sourceSelect.innerHTML = "";
  for (const s of data.sources || []) {
    const opt = document.createElement("option");
    opt.value = s.key;
    opt.textContent = s.label + (s.ready ? "" : "（字體未安裝）");
    if (!s.ready) opt.disabled = true;
    if (s.key === "moe_kaishu") opt.selected = true;  // Q1 default
    _sourceSelect.appendChild(opt);
  }
  setStatus("字體清單已載入");
}

async function fetchOutline(char, source) {
  const url =
    "/api/zentangle/outline?char=" +
    encodeURIComponent(char) +
    "&source=" +
    encodeURIComponent(source);
  const r = await fetch(url);
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try {
      const err = await r.json();
      if (err.detail) detail = err.detail;
    } catch (_) {
      /* swallow — non-JSON body */
    }
    throw new Error(detail);
  }
  return r.json();
}

async function renderOutline() {
  if (!_ctx) return;
  const char = (_charInput?.value || "").trim();
  if (char.length !== 1) {
    setStatus("請輸入一個漢字", true);
    return;
  }
  const source = _sourceSelect?.value || "moe_kaishu";
  setStatus(`載入「${char}」（${source}）…`);
  // 6z-2.1: paint frame at current rotation immediately so user sees the
  // rotated empty tile while fetch is in flight (better than blank canvas).
  redrawAll();
  let payload;
  try {
    payload = await fetchOutline(char, source);
  } catch (e) {
    setStatus(`載入失敗：${e.message}`, true);
    return;
  }
  const contours = payload.contours || [];
  if (!contoursAreClosed(contours)) {
    setStatus("字框資料不完整（contour 點數 < 3）", true);
    return;
  }
  // 6z-2.1: cache fetched contours so subsequent rotation/tile-size changes
  // re-draw without re-hitting the server (eliminates slider-drag race + lag,
  // resolves 6z-2 R1 risk).
  _cachedContours = contours;
  // 5dh: 字形重載 → hollow 區段（依字形切帶）失效重抽；bg 暫存保留。
  _regionStash.hollow = null;
  ensureRegions();
  redrawAll();
  refreshEnhancerToggles();
  // Status: report what's currently on the canvas (post-mapping count).
  const ts = currentTileSize();
  const tm = currentTileMargin();
  const mapped = mapContourToTile(contours, computeBbox(contours), ts, tm);
  const totalPts = mapped.reduce((acc, p) => acc + p.length, 0);
  setStatus(
    `OK · ${mapped.length} contour / ${totalPts} 點 · ${source} · em=${payload.em_size}`
  );
}

// ---------------------------------------------------------------------------
// Status helper
// ---------------------------------------------------------------------------

function setStatus(msg, isError = false) {
  if (!_statusEl) return;
  _statusEl.textContent = msg;
  _statusEl.style.color = isError ? "var(--accent, #c33)" : "var(--muted, #888)";
}

// ---------------------------------------------------------------------------
// 6z-1D — Force-modal main menu (D-C 強紀律弱預設 enforcement)
// ---------------------------------------------------------------------------

/**
 * Read persisted config from localStorage. Returns null when absent or
 * schema mismatch (force re-prompt instead of silently using stale data —
 * this is the schema-versioning + strict-on-mismatch pattern from the
 * stroke-order auto-memory `feedback_schema_versioning_with_migration`).
 */
function readConfig() {
  try {
    const raw = localStorage.getItem(CONFIG_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (
      !parsed ||
      typeof parsed !== "object" ||
      parsed.schema !== CONFIG_SCHEMA_VERSION
    ) {
      // Unknown / older schema → force re-prompt rather than silently
      // upgrade. (D-C: "force user verify, no silent default".)
      return null;
    }
    if (!parsed.char || !parsed.mode || !parsed.tileSize) return null;
    return parsed;
  } catch (_e) {
    return null;
  }
}

function writeConfig(cfg) {
  try {
    localStorage.setItem(
      CONFIG_STORAGE_KEY,
      JSON.stringify({ schema: CONFIG_SCHEMA_VERSION, ...cfg })
    );
  } catch (e) {
    console.warn("[zentangle] writeConfig failed:", e);
  }
}

function clearConfig() {
  try {
    localStorage.removeItem(CONFIG_STORAGE_KEY);
  } catch (_e) {
    /* swallow */
  }
}

/**
 * Apply an in-memory config to the running UI:
 *   - main-screen char input
 *   - inline mode + tile_size radios (6z-1.2)
 *   - config display strip
 * Called on first boot (DEFAULT_CONFIG / restored), and as the side-effect of
 * any inline control change.
 */
function applyConfig(cfg) {
  _config = cfg;
  if (_charInput) _charInput.value = cfg.char;
  // 6z-1.2: sync inline mode + tile radios so reload / boot reflects state.
  document.querySelectorAll('input[name="zentangle-mode"]').forEach((r) => {
    r.checked = r.value === cfg.mode;
  });
  document.querySelectorAll('input[name="zentangle-tile"]').forEach((r) => {
    r.checked = r.value === cfg.tileSize;
  });
  if (_configDisplay) {
    _configDisplay.textContent =
      `紙磚: 字="${cfg.char}", 模式=${MODE_LABELS[cfg.mode] || cfg.mode}, ` +
      `尺寸=${TILE_LABELS[cfg.tileSize] || cfg.tileSize}`;
  }
}

// ---------------------------------------------------------------------------
// 6z-1.2 — Inline control wiring (replaces 6z-1D modal lifecycle)
// ---------------------------------------------------------------------------
//
// Pattern: any inline control change → mutate _config → persist → re-render.
// Char input is debounced (~300ms) so the canvas doesn't thrash mid-typing;
// other controls (radios, source select) re-render immediately because each
// click is a deliberate, atomic choice.

const CHAR_DEBOUNCE_MS = 300;
let _charDebounceTimer = null;

function commitConfigChange(partial) {
  // Merge `partial` into the current config and propagate.
  _config = { ..._config, ...partial };
  writeConfig(_config);
  if (_configDisplay) {
    _configDisplay.textContent =
      `紙磚: 字="${_config.char}", 模式=${
        MODE_LABELS[_config.mode] || _config.mode
      }, 尺寸=${TILE_LABELS[_config.tileSize] || _config.tileSize}`;
  }
}

function wireInlineControls() {
  // 字 input — debounce keystrokes, also commit on Enter / blur.
  if (_charInput) {
    const flushChar = () => {
      const v = (_charInput.value || "").trim();
      if (v.length !== 1) {
        setStatus("請輸入一個漢字", true);
        return;
      }
      if (v === _config?.char) return;  // no-op on same value
      commitConfigChange({ char: v });
      // 6z-2.1: char change invalidates cache (different glyph polylines).
      _cachedContours = null;
      renderOutline().catch((e) =>
        setStatus(`載入字框失敗：${e.message}`, true)
      );
    };
    _charInput.addEventListener("input", () => {
      clearTimeout(_charDebounceTimer);
      _charDebounceTimer = setTimeout(flushChar, CHAR_DEBOUNCE_MS);
    });
    _charInput.addEventListener("blur", () => {
      clearTimeout(_charDebounceTimer);
      flushChar();
    });
    _charInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        clearTimeout(_charDebounceTimer);
        flushChar();
      }
    });
  }
  // 字體 select — change → render.
  if (_sourceSelect) {
    _sourceSelect.addEventListener("change", () => {
      // Source isn't part of persisted config (rotates per-session), so we
      // just re-render with the new source.
      // 6z-2.1: source change invalidates cache (different glyph shape).
      _cachedContours = null;
      renderOutline().catch((e) =>
        setStatus(`載入字框失敗：${e.message}`, true)
      );
    });
  }
  // 模式 radio — 5dh: change → persist + 恢復該模式暫存（互不清空）。
  document.querySelectorAll('input[name="zentangle-mode"]').forEach((r) => {
    r.addEventListener("change", (e) => {
      commitConfigChange({ mode: e.target.value });
      ensureRegions();
      redrawAll();
      refreshEnhancerToggles();
      const hint =
        e.target.value === "pure"
          ? "（點 canvas 手放圖樣）"
          : `（${_regions.length} 區段；切換自動保留、「清除區段」才清空）`;
      setStatus(`模式 → ${MODE_LABELS[e.target.value]}${hint}`);
    });
  });
  // 紙磚尺寸 radio — 6z-2b: change → persist + resize canvas + 6z-2.1 redraw
  // from cache (no re-fetch needed; tile size only affects mapping, not glyph).
  document.querySelectorAll('input[name="zentangle-tile"]').forEach((r) => {
    r.addEventListener("change", (e) => {
      commitConfigChange({ tileSize: e.target.value });
      resizeCanvasToConfig();
      // 5dh: band 是 tile-local px，尺寸變更 → 兩模式暫存皆失效。
      _regionStash.hollow = null;
      _regionStash.bg = null;
      ensureRegions();
      redrawAll();
      refreshEnhancerToggles();
      setStatus(`紙磚尺寸 → ${TILE_LABELS[e.target.value]}`);
    });
  });
  // 6z-2c rotation 控件 — inline UI buttons + slider + L1/L2 reset/prev.
  wireRotationControls();
}

// ---------------------------------------------------------------------------
// 6z-2c — Inline rotation controls + ANGLE_RESET / ANGLE_PREV wiring
// ---------------------------------------------------------------------------

function applyRotation(newDeg, { skipHistory = false } = {}) {
  // Normalise to (-180, 180] for cleaner display + comparisons.
  let n = newDeg % 360;
  if (n > 180) n -= 360;
  if (n <= -180) n += 360;
  if (n === _rotationDegrees) return;  // no-op
  if (!skipHistory) {
    _rotationHistory.push(_rotationDegrees);
    if (_rotationHistory.length > ROTATION_HISTORY_MAX) {
      _rotationHistory.shift();
    }
  }
  _rotationDegrees = n;
  // Reflect in inline UI.
  const slider = document.getElementById("zentangle-rotation-slider");
  if (slider && slider.valueAsNumber !== n) slider.value = String(n);
  const display = document.getElementById("zentangle-rotation-display");
  if (display) display.textContent = `${n}°`;
  // 6z-2.1: redraw uses cached contours — frame + outline rotate together
  // via ctx transform. No re-fetch, so slider drag is responsive.
  redrawAll();
}

function angleReset() {
  applyRotation(0);
}

function anglePrev() {
  if (_rotationHistory.length === 0) {
    setStatus("沒有上次角度紀錄", true);
    return;
  }
  const prev = _rotationHistory.pop();
  // skipHistory=true so we don't push the current angle (we're popping).
  applyRotation(prev, { skipHistory: true });
}

function rotationDelta(degrees) {
  applyRotation(_rotationDegrees + degrees);
}

function wireRotationControls() {
  // 8 preset angle buttons.
  document.querySelectorAll(".zt-rot-preset").forEach((btn) => {
    btn.addEventListener("click", () => {
      const deg = parseInt(btn.dataset.deg, 10);
      if (!Number.isFinite(deg)) return;
      applyRotation(deg);
    });
  });
  // Continuous slider — live update on input (drag).
  const slider = document.getElementById("zentangle-rotation-slider");
  if (slider) {
    slider.addEventListener("input", () => {
      applyRotation(slider.valueAsNumber);
    });
  }
  // Reset button → 0°.
  const resetBtn = document.getElementById("zentangle-rot-reset");
  if (resetBtn) resetBtn.addEventListener("click", angleReset);
  // 上次角度 button → history pop.
  const prevBtn = document.getElementById("zentangle-rot-prev");
  if (prevBtn) prevBtn.addEventListener("click", anglePrev);
  // Hook ACTIONS dispatch (鍵盤 Q / Shift+Q via 6z-1E wireInputScaffolding).
  // The dispatchAction stub still logs; we override at the action handler
  // level here so the same key binding produces real effect now.
  _actionHandlers["angle-reset"] = angleReset;
  _actionHandlers["angle-prev"] = anglePrev;
  _actionHandlers["tile-rotate-delta"] = (delta) => rotationDelta(delta);
  // 6z-2.2: pan buttons.
  wirePanControls();
  // 6z-3c: tangle picker + △/R 鍵 cycle.
  wireTangleControls();
}

// ---------------------------------------------------------------------------
// 6z-3c — Tangle picker + cycle action
// ---------------------------------------------------------------------------

function setActiveTangle(key) {
  if (key !== "none" && !TANGLES[key]) {
    setStatus(`未知 tangle: ${key}`, true);
    return;
  }
  if (key === _activeTangle) return;
  _activeTangle = key;
  // Sync inline radio.
  document.querySelectorAll('input[name="zentangle-tangle"]').forEach((r) => {
    r.checked = r.value === key;
  });
  redrawAll();
  setStatus(
    key === "none" ? "Tangle → 無" : `Tangle → ${TANGLES[key].label}`
  );
}

function cycleTangle() {
  // Order: none → registered tangles in registry order → loop.
  const order = ["none", ...listTangles().map((t) => t.key)];
  const idx = order.indexOf(_activeTangle);
  const next = order[(idx + 1) % order.length];
  setActiveTangle(next);
}

function wireTangleControls() {
  document.querySelectorAll('input[name="zentangle-tangle"]').forEach((r) => {
    r.addEventListener("change", (e) => setActiveTangle(e.target.value));
  });
  // 6z-1E ACTION wiring → register real handler (replaces stub fallback).
  _actionHandlers["cycle-tangle"] = cycleTangle;
  // 6z-3.5 / 5df-3: canvas left-click → 分流（pure 放 unit、hollow/bg 選區段）。
  const canvas = document.getElementById("zentangle-canvas");
  if (canvas) {
    canvas.addEventListener("click", (e) => onCanvasClick(e, canvas));
  }
  // 5df-3: 區段編輯圖樣鈕列（從 registry 動態生成）。
  buildRegionToolbar();
  // 5df-4: 切分模式 + 切分線顯示開關。
  wireSplitControls();
  // 6z-3.5: REPEAT_3 / R 鍵 → 3x repeat last unit along _lastDirection.
  _actionHandlers["repeat-3"] = repeatLast3;
  _actionHandlers["repeat-fill"] = repeatLast3;  // 6z-3.5 fallback; R2 「到底」 留 6z-3.5.X
  // 6z-3.5: 「清除已放」 button.
  const clearBtn = document.getElementById("zentangle-clear-units");
  if (clearBtn) clearBtn.addEventListener("click", clearPlacedUnits);
  // 6z-5a: pseudo-3D 透視控件 + Arrow 鍵 ACTION。
  wirePseudo3DControls();
}

// ---------------------------------------------------------------------------
// 6z-5a — Pseudo-3D 透視 控件 (4 方向 + slider + 無透視)
// ---------------------------------------------------------------------------

function setPerspectiveDir(dir) {
  // dir: "forward" | "backward" | "left" | "right" | null
  if (!isValidDepthDir(dir)) {
    setStatus(`unknown depth_dir: ${dir}`, true);
    return;
  }
  _stickyDepthDir = dir;
  // Apply to last unit (preview); also update sticky for new units.
  if (_placedUnits.length > 0) {
    const last = _placedUnits[_placedUnits.length - 1];
    last.pseudo_3d = dir
      ? {depth_dir: dir, depth_degree: _stickyDepthDegree}
      : null;
  }
  refreshPerspectiveButtonHighlight();
  redrawAll();
  if (dir === null) {
    setStatus("透視 → 無 (sticky cleared)");
  } else {
    const labels = {
      forward: "前 (foreshortening)",
      backward: "後 (擴張)",
      left: "左 (剪切右厚)",
      right: "右 (剪切左厚)",
    };
    setStatus(
      `透視 → ${labels[dir]}, degree=${_stickyDepthDegree.toFixed(2)}; 後續 placed unit sticky inherit`
    );
  }
}

function setPerspectiveDegree(degree) {
  const d = Math.max(0, Math.min(1, degree));
  _stickyDepthDegree = d;
  // Sync display
  const display = document.getElementById("zentangle-p3d-display");
  if (display) display.textContent = d.toFixed(2);
  // Update last unit's degree if it has pseudo_3d
  if (_placedUnits.length > 0) {
    const last = _placedUnits[_placedUnits.length - 1];
    if (last.pseudo_3d) last.pseudo_3d.depth_degree = d;
  }
  redrawAll();
}

function clearPerspective() {
  setPerspectiveDir(null);
}

function refreshPerspectiveButtonHighlight() {
  document.querySelectorAll(".zt-p3d-btn").forEach((btn) => {
    const isActive = btn.dataset.dir === _stickyDepthDir;
    btn.style.background = isActive ? "var(--accent, #c33)" : "#fafaf8";
    btn.style.color = isActive ? "#fff" : "#444";
    btn.style.borderColor = isActive ? "var(--accent, #c33)" : "var(--border)";
  });
}

function wirePseudo3DControls() {
  // 4 direction buttons.
  document.querySelectorAll(".zt-p3d-btn").forEach((btn) => {
    btn.addEventListener("click", () => setPerspectiveDir(btn.dataset.dir));
  });
  // depth_degree slider.
  const slider = document.getElementById("zentangle-p3d-slider");
  if (slider) {
    slider.addEventListener("input", () => setPerspectiveDegree(slider.valueAsNumber));
  }
  // 「無透視」 button.
  const clearBtn = document.getElementById("zentangle-p3d-clear");
  if (clearBtn) clearBtn.addEventListener("click", clearPerspective);
  // ↑↓←→ Arrow 鍵 ACTION — 5df-3 情境切換（QODA 使用者定案）：
  //   有選中區段 → 方向鍵歸區段朝向（keyDir up/right/down/left 恰是
  //   ORIENTATIONS 字面值，直接透傳）
  //   未選中     → 維持 6z-5a 透視（KEY_DIR_TO_PSEUDO3D 轉譯）
  _actionHandlers["pseudo3d-dir"] = (keyDir) => {
    if (_selectedRegionId !== null && setRegionOrientation(keyDir)) return;
    const dir = KEY_DIR_TO_PSEUDO3D[keyDir];
    if (!dir) return;
    setPerspectiveDir(dir);
  };
  // 6z-5b: curve mode controls.
  wireCurveModeControls();
}

// ---------------------------------------------------------------------------
// 6z-5b — Curve mode 控件 (軸 1 高-邊低 only; 軸 2-4 留 6z-5c)
// ---------------------------------------------------------------------------

function setCurveMode(mode) {
  if (!isValidCurveMode(mode)) {
    setStatus(`unknown curve_mode: ${mode}`, true);
    return;
  }
  _stickyCurveMode = mode;
  if (_placedUnits.length > 0) {
    const last = _placedUnits[_placedUnits.length - 1];
    if (mode === null) {
      // Don't wipe entire pseudo_3d (depth_dir may still be set); just clear curve fields.
      if (last.pseudo_3d) {
        last.pseudo_3d.curve_mode = null;
        last.pseudo_3d.curve_degree = 0;
      }
    } else {
      last.pseudo_3d = last.pseudo_3d || {
        depth_dir: null,
        depth_degree: 0,
        curve_mode: null,
        curve_degree: 0,
      };
      last.pseudo_3d.curve_mode = mode;
      last.pseudo_3d.curve_degree = _stickyCurveDegree;
    }
  }
  refreshCurveModeButtonHighlight();
  redrawAll();
  if (mode === null) {
    setStatus("曲度 → 無 (sticky cleared)");
  } else {
    const labels = {
      "high-mid": "中高邊低",
      "high-sides": "邊高中低",
      "left-high": "左高右低",
      "right-high": "右高左低",
    };
    setStatus(
      `曲度 → ${labels[mode]}, degree=${_stickyCurveDegree.toFixed(2)}; 後續 placed unit sticky inherit`
    );
  }
}

function setCurveDegree(degree) {
  const d = Math.max(0, Math.min(1, degree));
  _stickyCurveDegree = d;
  const display = document.getElementById("zentangle-curve-display");
  if (display) display.textContent = d.toFixed(2);
  if (_placedUnits.length > 0) {
    const last = _placedUnits[_placedUnits.length - 1];
    if (last.pseudo_3d && last.pseudo_3d.curve_mode) {
      last.pseudo_3d.curve_degree = d;
    }
  }
  redrawAll();
}

function clearCurveMode() {
  setCurveMode(null);
}

function refreshCurveModeButtonHighlight() {
  document.querySelectorAll(".zt-curve-btn").forEach((btn) => {
    const isActive = btn.dataset.curve === _stickyCurveMode;
    btn.style.background = isActive ? "var(--accent, #c33)" : "#fafaf8";
    btn.style.color = isActive ? "#fff" : "#444";
    btn.style.borderColor = isActive ? "var(--accent, #c33)" : "var(--border)";
  });
}

function wireCurveModeControls() {
  document.querySelectorAll(".zt-curve-btn").forEach((btn) => {
    btn.addEventListener("click", () => setCurveMode(btn.dataset.curve));
  });
  const slider = document.getElementById("zentangle-curve-slider");
  if (slider) {
    slider.addEventListener("input", () => setCurveDegree(slider.valueAsNumber));
  }
  const clearBtn = document.getElementById("zentangle-curve-clear");
  if (clearBtn) clearBtn.addEventListener("click", clearCurveMode);
}

/**
 * 6z-3.5 — Translate browser click event to TILE-LOCAL coords + push unit.
 */
function placeUnitAtClick(e, canvas) {
  if (_activeTangle === "none") {
    setStatus("先選一個 tangle (Crescent Moon / Florz)，再點 canvas 放置", true);
    return;
  }
  if (!TANGLES[_activeTangle]) return;
  // Browser click → tile-local（5df-3 抽出共用 helper；旋轉/pan 反變換同前）。
  const pt = clickToTileLocal(e, canvas);
  if (!pt) return;
  const [tx, ty] = pt;
  // 6z-5a/b: new units inherit sticky pseudo_3d (depth_dir + curve_mode).
  // Build pseudo_3d only if any sticky field is active — keeps null short-
  // circuit working when neither is set.
  const pseudo_3d =
    _stickyDepthDir || _stickyCurveMode
      ? {
          depth_dir: _stickyDepthDir,
          depth_degree: _stickyDepthDegree,
          curve_mode: _stickyCurveMode,
          curve_degree: _stickyCurveDegree,
        }
      : null;
  _placedUnits.push({tangle: _activeTangle, cx: tx, cy: ty, pseudo_3d});
  // Update _lastDirection if we have ≥ 2 units.
  if (_placedUnits.length >= 2) {
    const a = _placedUnits[_placedUnits.length - 2];
    const b = _placedUnits[_placedUnits.length - 1];
    _lastDirection = [b.cx - a.cx, b.cy - a.cy];
  }
  redrawAll();
  const dirHint =
    _lastDirection !== null
      ? `；方向 (${_lastDirection[0].toFixed(0)}, ${_lastDirection[1].toFixed(0)})、R 鍵 repeat 3 次`
      : "；再點一下定方向";
  setStatus(
    `已放置 ${_placedUnits.length} 個 ${TANGLES[_activeTangle].label}${dirHint}`
  );
}

/**
 * 6z-3.5 — Repeat the last placed unit 3 times along _lastDirection.
 */
function repeatLast3() {
  if (_placedUnits.length === 0) {
    setStatus("沒有已放置的 unit，先點 canvas 放第一個", true);
    return;
  }
  if (_lastDirection === null) {
    setStatus("需要至少 2 個 unit 才能定方向；再點一下 canvas", true);
    return;
  }
  const last = _placedUnits[_placedUnits.length - 1];
  const [dx, dy] = _lastDirection;
  for (let i = 1; i <= 3; i++) {
    _placedUnits.push({
      tangle: last.tangle,
      cx: last.cx + dx * i,
      cy: last.cy + dy * i,
    });
  }
  redrawAll();
  setStatus(
    `Repeat 3 次完成、共 ${_placedUnits.length} 個 unit；繼續點 / 再 R / 清除`
  );
}

/**
 * 6z-3.5 — Clear all placed units (本 session 內 reset).
 */
function clearPlacedUnits() {
  if (_placedUnits.length === 0) {
    setStatus("沒有 unit 可清除");
    return;
  }
  const n = _placedUnits.length;
  _placedUnits = [];
  _lastDirection = null;
  redrawAll();
  setStatus(`已清除 ${n} 個 unit`);
}

/**
 * 6z-2.2 — pan button handlers. Toggle behaviour:
 *   click same side  → reset to "center"
 *   click new side   → switch _panState to that side
 * Visual indicator: active button gets a thicker border + bg highlight.
 */
function togglePan(side) {
  _panState = _panState === side ? "center" : side;
  refreshPanButtonHighlight();
  redrawAll();
  if (_panState === "center") {
    setStatus("紙磚 pan → 中心");
  } else {
    const labels = { top: "上邊角", bottom: "下邊角", left: "左邊角", right: "右邊角" };
    setStatus(
      `紙磚 pan → 露出 ${labels[_panState]}（${Math.round(rotationOverflow())} px；再按一次回中心）`
    );
  }
}

function refreshPanButtonHighlight() {
  document.querySelectorAll(".zt-pan-btn").forEach((btn) => {
    const isActive = btn.dataset.pan === _panState;
    btn.style.background = isActive ? "var(--accent, #c33)" : "#fafaf8";
    btn.style.color = isActive ? "#fff" : "#444";
    btn.style.borderColor = isActive ? "var(--accent, #c33)" : "var(--border)";
  });
}

function wirePanControls() {
  document.querySelectorAll(".zt-pan-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const side = btn.dataset.pan;
      if (!["top", "bottom", "left", "right"].includes(side)) return;
      togglePan(side);
    });
  });
}

// ---------------------------------------------------------------------------
// 6z-1E — Input scaffolding
// ---------------------------------------------------------------------------
//
// Goal: define the action vocab now and route 鍵盤 + 滑鼠 + Web Gamepad
// API events through a single dispatcher. Action handlers are stubs that
// log to status — real wiring (切割 mode、tangle cycle、pseudo-3D etc) is
// in 6z-2 ~ 6z-7. Keeping this layer slim now means future sub-phases
// only swap handlers, not re-architect dispatch.

/**
 * Action vocab. Each entry is the canonical name future sub-phases will
 * attach handlers to. Drawn from v0.3 §2.1 PS2 button mapping + §3.1
 * keyboard mapping.
 */
const ACTIONS = {
  CONFIRM: "confirm",                // ✕ Cross / Space / right-click
  CANCEL: "cancel",                  // ○ Circle / Z / middle-click
  CYCLE_BASE: "cycle-base-shape",    // □ Square / F
  CYCLE_TANGLE: "cycle-tangle",      // △ Triangle / R
  REPEAT_3: "repeat-3",              // R1 / E
  REPEAT_FILL: "repeat-fill",        // R2 / Shift+E
  ANGLE_RESET: "angle-reset",        // L1 / Q
  ANGLE_PREV: "angle-prev",          // L2 / Shift+Q
  TILE_ROTATE_DELTA: "tile-rotate-delta",  // R-stick / IJKL → arg: degrees
  DEFORM_DELTA: "deform-delta",      // L-stick / WASD → args: dx, dy
  PSEUDO3D_DIR: "pseudo3d-dir",      // D-Pad / 方向鍵 → arg: 'up'/'down'/'left'/'right'
  MENU_OPEN: "menu-open",            // PSB_START / Esc / M
  CYCLE_SIZE: "cycle-size",          // PSB_SELECT / Tab
  CYCLE_DENSITY: "cycle-density",    // L3 / C
  CYCLE_LAYER: "cycle-layer",        // R3 / V
};

// 鍵盤 mapping per v0.3 §3.1.
const KEY_MAP = {
  " ": ACTIONS.CONFIRM,
  z: ACTIONS.CANCEL,
  Z: ACTIONS.CANCEL,
  f: ACTIONS.CYCLE_BASE,
  F: ACTIONS.CYCLE_BASE,
  r: ACTIONS.CYCLE_TANGLE,
  R: ACTIONS.CYCLE_TANGLE,
  e: ACTIONS.REPEAT_3,        // (Shift+E handled below)
  q: ACTIONS.ANGLE_RESET,     // (Shift+Q handled below)
  Tab: ACTIONS.CYCLE_SIZE,
  c: ACTIONS.CYCLE_DENSITY,
  C: ACTIONS.CYCLE_DENSITY,
  v: ACTIONS.CYCLE_LAYER,
  V: ACTIONS.CYCLE_LAYER,
  Escape: ACTIONS.MENU_OPEN,
  m: ACTIONS.MENU_OPEN,
  M: ACTIONS.MENU_OPEN,
  ArrowUp: [ACTIONS.PSEUDO3D_DIR, "up"],
  ArrowDown: [ACTIONS.PSEUDO3D_DIR, "down"],
  ArrowLeft: [ACTIONS.PSEUDO3D_DIR, "left"],
  ArrowRight: [ACTIONS.PSEUDO3D_DIR, "right"],
};

// 6z-2c: action handler registry. Each phase swaps in real handlers; any
// action without a registered handler falls back to the status-bar stub
// (so 6z-3+ ACTIONS can land incrementally without a runtime crash).
const _actionHandlers = Object.create(null);

/**
 * Dispatch an action through the registry. Registered handlers are called
 * with the trailing args; unregistered actions degrade to the status-bar
 * stub from 6z-1E (preserves visibility for in-progress phases).
 */
function dispatchAction(action, ...args) {
  if (!action) return;
  const handler = _actionHandlers[action];
  if (typeof handler === "function") {
    try {
      handler(...args);
    } catch (e) {
      setStatus(`[input] ${action} 處理失敗：${e.message}`, true);
    }
    return;
  }
  setStatus(
    `[input] ${action}` + (args.length ? ` (${args.join(", ")})` : "") +
      "  (handler 待 6z-3+ wire)",
    false
  );
}

function wireInputScaffolding() {
  // 鍵盤 — listen on the zentangle view (not document) so other modes
  // aren't affected.
  const view = document.getElementById("zentangle-view");
  if (view) {
    // tabindex makes the section keyboard-focusable.
    if (!view.hasAttribute("tabindex")) view.setAttribute("tabindex", "-1");
    view.addEventListener("keydown", (e) => {
      // Don't hijack typing in input/select fields.
      const tag = e.target?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      // Shift modifiers: Shift+E = REPEAT_FILL, Shift+Q = ANGLE_PREV.
      if (e.shiftKey && (e.key === "e" || e.key === "E")) {
        dispatchAction(ACTIONS.REPEAT_FILL);
        e.preventDefault();
        return;
      }
      if (e.shiftKey && (e.key === "q" || e.key === "Q")) {
        dispatchAction(ACTIONS.ANGLE_PREV);
        e.preventDefault();
        return;
      }
      const mapped = KEY_MAP[e.key];
      if (!mapped) return;
      e.preventDefault();
      if (Array.isArray(mapped)) {
        dispatchAction(mapped[0], mapped[1]);
      } else {
        dispatchAction(mapped);
      }
    });
  }
  // 滑鼠 — bind on the canvas only (pointer events stay scoped).
  const canvas = document.getElementById("zentangle-canvas");
  if (canvas) {
    canvas.addEventListener("contextmenu", (e) => {
      // Right-click → confirm. Suppress browser context menu.
      e.preventDefault();
      dispatchAction(ACTIONS.CONFIRM);
    });
    canvas.addEventListener("auxclick", (e) => {
      // Middle-click → cancel.
      if (e.button === 1) {
        e.preventDefault();
        dispatchAction(ACTIONS.CANCEL);
      }
    });
    canvas.addEventListener("wheel", (e) => {
      // Wheel → cycle size; Shift+wheel → density; Ctrl+wheel → tile rotation.
      // Stub: just dispatch the action; sign of deltaY routes via 6z-7.
      e.preventDefault();
      if (e.shiftKey) dispatchAction(ACTIONS.CYCLE_DENSITY);
      else if (e.ctrlKey)
        dispatchAction(ACTIONS.TILE_ROTATE_DELTA, e.deltaY > 0 ? 5 : -5);
      else dispatchAction(ACTIONS.CYCLE_SIZE);
    }, { passive: false });
  }
  // Web Gamepad API — auto-detect connection. Real polling loop lives in 6z-7.
  if (typeof window !== "undefined" && "addEventListener" in window) {
    window.addEventListener("gamepadconnected", (e) => {
      const gp = e.gamepad;
      setStatus(
        `Gamepad 已連接：${gp.id} (mapping=${gp.mapping || "unknown"}) — ` +
        `完整 wiring 在 6z-7，目前僅鍵盤+滑鼠 active`,
        false
      );
    });
    window.addEventListener("gamepaddisconnected", (e) => {
      setStatus(`Gamepad 已斷開：${e.gamepad.id}`, false);
    });
  }
}

// Exported for unit testing the action registry shape (future).
export { ACTIONS, KEY_MAP };
