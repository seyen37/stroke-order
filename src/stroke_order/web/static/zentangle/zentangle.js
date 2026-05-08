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
  renderTangleSpecs,
  listTangles,
} from "./tangle.mjs";
import {
  applyPseudo3DToSpecs,
  isValidDepthDir,
  VALID_DEPTH_DIRS,
  applyCurveModeToSpecs,
  isValidCurveMode,
  VALID_CURVE_MODES,
} from "./pseudo3d.mjs";

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
    if (_cachedContours && contoursAreClosed(_cachedContours)) {
      const ts = currentTileSize();
      const tm = currentTileMargin();
      const bbox = computeBbox(_cachedContours);
      const mapped = mapContourToTile(_cachedContours, bbox, ts, tm);
      drawOutline(mapped);
      // 6z-3d: tangle layer (clip 在 outline 內，mode=pure 視覺；hollow/bg 暫 fallback)
      drawTangleLayer(mapped);
    }
  });
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
  redrawAll();
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
  // 模式 radio — change → persist; visual diff arrives in 6z-3 (fill phase).
  document.querySelectorAll('input[name="zentangle-mode"]').forEach((r) => {
    r.addEventListener("change", (e) => {
      commitConfigChange({ mode: e.target.value });
      // No re-render needed in 6z-1 (no visual diff yet); status reflects.
      setStatus(
        `模式 → ${MODE_LABELS[e.target.value]} (視覺差異將在 6z-3 fill phase 啟用)`
      );
    });
  });
  // 紙磚尺寸 radio — 6z-2b: change → persist + resize canvas + 6z-2.1 redraw
  // from cache (no re-fetch needed; tile size only affects mapping, not glyph).
  document.querySelectorAll('input[name="zentangle-tile"]').forEach((r) => {
    r.addEventListener("change", (e) => {
      commitConfigChange({ tileSize: e.target.value });
      resizeCanvasToConfig();
      redrawAll();
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
  // 6z-3.5: canvas left-click → place tangle unit at click point.
  const canvas = document.getElementById("zentangle-canvas");
  if (canvas) {
    canvas.addEventListener("click", (e) => placeUnitAtClick(e, canvas));
  }
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
  // ↑↓←→ Arrow 鍵 ACTION → setPerspectiveDir (translate via KEY_DIR_TO_PSEUDO3D).
  // (6z-1E KEY_MAP already dispatches PSEUDO3D_DIR with arg; we register the handler.)
  _actionHandlers["pseudo3d-dir"] = (keyDir) => {
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
  // Browser click → canvas px (account for CSS scaling).
  const rect = canvas.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const viewX = (e.clientX - rect.left) * scaleX;
  const viewY = (e.clientY - rect.top) * scaleY;
  // Inverse transform → tile-local (so rotation + pan compose naturally).
  const [tx, ty] = viewportToTileLocal(viewX, viewY);
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
