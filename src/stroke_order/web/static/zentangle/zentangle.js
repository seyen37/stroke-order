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
  rotateContours,
} from "./outline.mjs";

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

function drawTileBackground() {
  if (!_ctx) return;
  const ts = currentTileSize();
  const tm = currentTileMargin();
  // Clear → white background → 4-corner dots → thin border.
  _ctx.clearRect(0, 0, ts, ts);
  _ctx.fillStyle = "#ffffff";
  _ctx.fillRect(0, 0, ts, ts);
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
  drawTileBackground();
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
  const bbox = computeBbox(contours);
  // 6z-2b: tile size dynamic; 6z-2c: rotation applied AFTER mapping (pivot
  // = canvas center per Q4 user decision).
  const ts = currentTileSize();
  const tm = currentTileMargin();
  const mappedRaw = mapContourToTile(contours, bbox, ts, tm);
  const mapped =
    _rotationDegrees !== 0
      ? rotateContours(mappedRaw, _rotationDegrees, [ts / 2, ts / 2])
      : mappedRaw;
  drawOutline(mapped);
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
  // 紙磚尺寸 radio — 6z-2b: change → persist + resize canvas + re-render.
  document.querySelectorAll('input[name="zentangle-tile"]').forEach((r) => {
    r.addEventListener("change", (e) => {
      commitConfigChange({ tileSize: e.target.value });
      resizeCanvasToConfig();
      drawTileBackground();
      renderOutline().catch((err) =>
        setStatus(`載入字框失敗：${err.message}`, true)
      );
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
  // Re-render to apply rotation.
  drawTileBackground();
  renderOutline().catch((e) =>
    setStatus(`旋轉重繪失敗：${e.message}`, true)
  );
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
