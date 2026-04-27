// ======================================================================
// grid.js — Render practice-cell helper grids onto a canvas.
//
// Seven styles (matching the BUttaiwan / 教育部 reference sites):
//
//   mizi        米字格 — outer frame + center cross + two diagonals
//   jiugong     九宮格 — outer frame + 3×3 split (two horizontal + two
//                          vertical lines)
//   new-jiugong 新九宮格 — 九宮格 + a center dot (mark optical center)
//   tianzi      田字格 — outer frame + center cross only
//   huizi       回字格 — outer frame + inner frame at 70% (中宮)
//   frame       僅字身框 — just the outer frame
//   none        無格線 — no-op
//
// All renders honour the canvas's CSS-pixel size and use device-pixel
// crisp lines. They paint into a 2D context that's already been
// `setTransform(dpr, 0, 0, dpr, 0, 0)` (see canvas.js — bg/ink share
// the same DPR setup).
//
// Colours are grey (#bbb / #d0d0d0) so they stay subtle behind the user's
// black ink and the faded reference glyph.
// ======================================================================

const FRAME_COLOR  = '#7a7a7a';
const HELPER_COLOR = '#cdcdcd';
const FRAME_WIDTH  = 1.0;       // CSS px (DPR-scaled by ctx transform)
const HELPER_WIDTH = 0.6;
const HELPER_DASH  = [3, 3];

export const GRID_STYLES = [
  'mizi', 'jiugong', 'new-jiugong', 'tianzi', 'huizi', 'frame', 'none',
];

/**
 * Draw a grid into `ctx` covering [0, w] × [0, h] (CSS pixels).
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} w
 * @param {number} h
 * @param {string} style — one of GRID_STYLES
 */
export function drawGrid(ctx, w, h, style) {
  ctx.save();
  ctx.clearRect(0, 0, w, h);

  if (style === 'none') {
    ctx.restore();
    return;
  }

  // ---- outer frame (always except 'none') ----
  ctx.strokeStyle = FRAME_COLOR;
  ctx.lineWidth   = FRAME_WIDTH;
  // Inset by 0.5px so the line lands on a single pixel column.
  const f = FRAME_WIDTH / 2;
  ctx.strokeRect(f, f, w - FRAME_WIDTH, h - FRAME_WIDTH);

  if (style === 'frame') {
    ctx.restore();
    return;
  }

  // ---- helper lines (dashed grey) ----
  ctx.strokeStyle = HELPER_COLOR;
  ctx.lineWidth   = HELPER_WIDTH;
  ctx.setLineDash(HELPER_DASH);

  switch (style) {
    case 'mizi':         _mizi(ctx, w, h);        break;
    case 'tianzi':       _tianzi(ctx, w, h);      break;
    case 'jiugong':      _jiugong(ctx, w, h);     break;
    case 'new-jiugong':  _newJiugong(ctx, w, h);  break;
    case 'huizi':        _huizi(ctx, w, h);       break;
    default:
      // unknown → just leave the outer frame
      break;
  }

  ctx.restore();
}

// ----- per-style renderers (helper layer only) ------------------------

function _tianzi(ctx, w, h) {
  // center cross
  _line(ctx, w / 2, 0,     w / 2, h);
  _line(ctx, 0,     h / 2, w,     h / 2);
}

function _mizi(ctx, w, h) {
  _tianzi(ctx, w, h);
  // two diagonals
  _line(ctx, 0, 0, w, h);
  _line(ctx, 0, h, w, 0);
}

function _jiugong(ctx, w, h) {
  // 3x3: two vertical + two horizontal
  _line(ctx, w / 3,     0, w / 3,     h);
  _line(ctx, 2 * w / 3, 0, 2 * w / 3, h);
  _line(ctx, 0, h / 3,     w, h / 3);
  _line(ctx, 0, 2 * h / 3, w, 2 * h / 3);
}

function _newJiugong(ctx, w, h) {
  _jiugong(ctx, w, h);
  // center optical dot — 1.5px solid grey
  ctx.save();
  ctx.setLineDash([]);
  ctx.fillStyle = FRAME_COLOR;
  ctx.beginPath();
  ctx.arc(w / 2, h / 2, 1.6, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function _huizi(ctx, w, h) {
  // inner box at 70% (中宮)
  const ix = w * 0.15;
  const iy = h * 0.15;
  const iw = w * 0.70;
  const ih = h * 0.70;
  ctx.save();
  ctx.setLineDash([]);
  ctx.lineWidth = HELPER_WIDTH;
  ctx.strokeRect(ix, iy, iw, ih);
  ctx.restore();
}

// ----- low-level helper -----------------------------------------------

function _line(ctx, x1, y1, x2, y2) {
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
}
