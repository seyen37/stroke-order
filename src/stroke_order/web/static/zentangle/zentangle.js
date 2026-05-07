// Phase 6z-1C — Zentangle mode DOM glue.
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
//   - Input handling → 6z-1E (scaffolding only, full wiring in 6z-7)
//   - Force-modal main menu → 6z-1D
//   - Pseudo-3D + tile rotation → 6z-2/6z-5

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

// Defer-once init flag — avoids repeated DOM lookups when user toggles
// modes back and forth.
let _booted = false;
let _ctx = null;
let _statusEl = null;
let _charInput = null;
let _sourceSelect = null;

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
  // Auto-render the default char on first boot so the canvas isn't blank.
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
