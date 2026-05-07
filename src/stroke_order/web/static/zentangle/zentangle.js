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

const TILE_SIZE = 600;        // px (Q2 user decision: 9cm 標準磚 → 600px)
const TILE_MARGIN = 60;       // px (~10% inset; 字 outline 不貼邊)
const DOT_RADIUS = 3;         // px
const DOT_COLOR = "#222";
const BORDER_COLOR = "#bbb";
const OUTLINE_COLOR = "#222";
const OUTLINE_WIDTH = 1.5;

// localStorage key for persisted force-modal config (per session, browser-local).
const CONFIG_STORAGE_KEY = "stroke_order.zentangle.config.v1";

// 6z-1D config schema. v1 is the very first; bump to v2 when fields shift.
const CONFIG_SCHEMA_VERSION = 1;

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
  // 6z-1D: force-modal lifecycle wiring.
  wireForceModal();
  // 6z-1E: input scaffolding (鍵盤 + 滑鼠 + Web Gamepad API stubs).
  wireInputScaffolding();

  // Try to restore config from localStorage. If absent → modal must run
  // before canvas is usable. If present → apply + render.
  const restored = readConfig();
  if (restored) {
    applyConfig(restored);
    renderOutline().catch((e) =>
      setStatus(`預設字框載入失敗：${e.message}（請選擇字體後手動載入）`, true)
    );
  } else {
    openModal();
  }
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
  // Clear → white background → 4-corner dots → thin border.
  _ctx.clearRect(0, 0, TILE_SIZE, TILE_SIZE);
  _ctx.fillStyle = "#ffffff";
  _ctx.fillRect(0, 0, TILE_SIZE, TILE_SIZE);
  // Thin border — inset by 1px so it lives inside the canvas.
  _ctx.strokeStyle = BORDER_COLOR;
  _ctx.lineWidth = 1;
  _ctx.strokeRect(0.5, 0.5, TILE_SIZE - 1, TILE_SIZE - 1);
  // 4-corner dots — classic Zentangle tile signature.
  _ctx.fillStyle = DOT_COLOR;
  const corners = [
    [TILE_MARGIN / 2, TILE_MARGIN / 2],
    [TILE_SIZE - TILE_MARGIN / 2, TILE_MARGIN / 2],
    [TILE_MARGIN / 2, TILE_SIZE - TILE_MARGIN / 2],
    [TILE_SIZE - TILE_MARGIN / 2, TILE_SIZE - TILE_MARGIN / 2],
  ];
  for (const [cx, cy] of corners) {
    _ctx.beginPath();
    _ctx.arc(cx, cy, DOT_RADIUS, 0, Math.PI * 2);
    _ctx.fill();
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
  const mapped = mapContourToTile(contours, bbox, TILE_SIZE, TILE_MARGIN);
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
 * Apply an in-memory config to the running UI (char input + display).
 * Called both on first confirm and on browser reload after restore.
 */
function applyConfig(cfg) {
  _config = cfg;
  if (_charInput) _charInput.value = cfg.char;
  if (_configDisplay) {
    _configDisplay.textContent =
      `已開磚: 字="${cfg.char}", 模式=${MODE_LABELS[cfg.mode] || cfg.mode}, ` +
      `紙磚=${TILE_LABELS[cfg.tileSize] || cfg.tileSize}`;
  }
}

function openModal() {
  const modal = document.getElementById("zentangle-modal");
  if (!modal) return;
  modal.style.display = "flex";
  // Reset modal inputs each time we open (force fresh selection — no
  // residual state).
  const charEl = document.getElementById("zm-char");
  if (charEl) charEl.value = "";
  document.querySelectorAll('input[name="zm-mode"]').forEach((r) => {
    r.checked = false;
  });
  document.querySelectorAll('input[name="zm-tile"]').forEach((r) => {
    r.checked = false;
  });
  updateConfirmButtonState();
  if (charEl) charEl.focus();
}

function closeModal() {
  const modal = document.getElementById("zentangle-modal");
  if (modal) modal.style.display = "none";
}

function readModalSelection() {
  const charEl = document.getElementById("zm-char");
  const modeEl = document.querySelector('input[name="zm-mode"]:checked');
  const tileEl = document.querySelector('input[name="zm-tile"]:checked');
  return {
    char: (charEl?.value || "").trim(),
    mode: modeEl?.value || "",
    tileSize: tileEl?.value || "",
  };
}

function updateConfirmButtonState() {
  const sel = readModalSelection();
  const valid =
    sel.char.length === 1 &&
    !!sel.mode &&
    !!sel.tileSize;
  const btn = document.getElementById("zm-confirm");
  if (!btn) return;
  btn.disabled = !valid;
  btn.style.opacity = valid ? "1" : "0.5";
  btn.style.cursor = valid ? "pointer" : "not-allowed";
}

function wireForceModal() {
  const modal = document.getElementById("zentangle-modal");
  if (!modal) return;
  // Live-validate as user types/picks.
  const charEl = document.getElementById("zm-char");
  if (charEl) charEl.addEventListener("input", updateConfirmButtonState);
  document.querySelectorAll('input[name="zm-mode"]').forEach((r) => {
    r.addEventListener("change", updateConfirmButtonState);
  });
  document.querySelectorAll('input[name="zm-tile"]').forEach((r) => {
    r.addEventListener("change", updateConfirmButtonState);
  });
  // Confirm button → save + close + apply + render.
  const confirmBtn = document.getElementById("zm-confirm");
  if (confirmBtn) {
    confirmBtn.addEventListener("click", () => {
      const sel = readModalSelection();
      if (!(sel.char.length === 1 && sel.mode && sel.tileSize)) return;
      writeConfig(sel);
      applyConfig(sel);
      closeModal();
      renderOutline().catch((e) =>
        setStatus(`載入字框失敗：${e.message}`, true)
      );
    });
  }
  // Block ESC dismissal — D-C strict no-escape (matches the modal's own
  // disclaimer text).
  modal.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
    }
  });
  // Block backdrop click dismissal as well — same strict policy.
  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      e.preventDefault();
      e.stopPropagation();
    }
  });
  // 「重新設定紙磚」button on the main view → clear + reopen.
  const resetBtn = document.getElementById("zentangle-reset");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      clearConfig();
      _config = null;
      if (_configDisplay) _configDisplay.textContent = "";
      openModal();
    });
  }
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

/**
 * Stub dispatcher. 6z-2 ~ 6z-7 will replace this with a registry of
 * per-action handlers; for now we just surface the action in the status
 * bar so manual E2E can confirm the dispatch table is wired.
 */
function dispatchAction(action, ...args) {
  if (!action) return;
  setStatus(
    `[input] ${action}` + (args.length ? ` (${args.join(", ")})` : ""),
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
