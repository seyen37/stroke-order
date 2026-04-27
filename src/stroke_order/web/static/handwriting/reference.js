// ======================================================================
// reference.js — Fetch & render the faded reference glyph onto bg canvas.
//
// Why this exists
// ---------------
//   In 臨摹 (trace) mode the user wants to see what they're aiming at.
//   We fetch the outline of the chosen char + style from the
//   /api/handwriting/reference/{char} endpoint, which returns native
//   EM 2048 (Y-down) — exactly the same coord system the user's strokes
//   are captured in. So we can render the outline directly onto the bg
//   canvas with a simple linear scale (cssW / EM_SIZE).
//
// Each outline is a list of M/L/Q/C commands; we replay them with
// Path2D and fill at low opacity (#cccccc) to read as a faded hint.
// ======================================================================

const EM_SIZE = 2048;
const FILL_COLOR = '#cccccc';
const FILL_ALPHA = 0.55;   // matches sutra reference layer (5ca)

const _cache = new Map();   // key = `${char}|${style}` → strokes JSON

/**
 * Fetch reference outline from the backend (cached in-memory).
 * @returns {Promise<Array<{outline: object[]}>>}  empty if no glyph
 */
export async function fetchReference(char, style = 'kaishu') {
  if (!char) return [];
  const key = `${char}|${style}`;
  if (_cache.has(key)) return _cache.get(key);

  const url = `/api/handwriting/reference/${encodeURIComponent(char)}` +
              `?style=${encodeURIComponent(style)}`;
  let strokes = [];
  try {
    const r = await fetch(url);
    if (r.ok) {
      const data = await r.json();
      strokes = data.strokes || [];
    } else {
      console.warn(`reference fetch failed: ${r.status} for ${char}/${style}`);
    }
  } catch (e) {
    console.warn('reference fetch error', e);
  }
  _cache.set(key, strokes);
  return strokes;
}

/**
 * Render the reference glyph to a 2D context filling [0,w]×[0,h] (CSS
 * pixels). Caller is responsible for clearing / pre-rendering the grid
 * underneath if desired.
 *
 * Does nothing if `strokes` is empty (no outline available — e.g. seal
 * font missing the char, or style with skeleton-only data).
 *
 * 5d-7-bugfix: bbox-center the outline. Different fonts place their
 * glyphs at different positions inside the EM 2048 box — kaishu sits
 * roughly centred (~ y in [200, 1850]), but lishu/seal commonly skew
 * downward. Naively mapping EM (0..2048) onto canvas (0..w,0..h)
 * therefore renders lishu/seal glyphs visibly off-centre. We fix this
 * by computing the outline's bounding box, translating so its centre
 * lands on the canvas centre, and keeping the EM scale uniform so the
 * glyph keeps its native proportions.
 */
export function drawReference(ctx, w, h, strokes) {
  if (!strokes || strokes.length === 0) return;
  const bbox = _outlineBBox(strokes);
  if (!bbox) return;

  const cx = (bbox.minX + bbox.maxX) / 2;
  const cy = (bbox.minY + bbox.maxY) / 2;

  // Uniform EM scale — square canvas, so w == h in practice. Use min()
  // defensively in case the canvas is non-square.
  const scale = Math.min(w, h) / EM_SIZE;

  ctx.save();
  ctx.globalAlpha = FILL_ALPHA;
  ctx.fillStyle   = FILL_COLOR;
  ctx.strokeStyle = 'none';

  // Move bbox centre → canvas centre, then scale EM units to CSS pixels.
  ctx.translate(w / 2 - cx * scale, h / 2 - cy * scale);
  ctx.scale(scale, scale);

  for (const stroke of strokes) {
    const path = _buildPath2D(stroke.outline);
    if (path) ctx.fill(path, 'nonzero');
  }
  ctx.restore();
}

// Compute the bbox of every outline anchor + control point across
// all strokes. Returns null if no points found.
function _outlineBBox(strokes) {
  let minX = Infinity, maxX = -Infinity;
  let minY = Infinity, maxY = -Infinity;
  const consider = (x, y) => {
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  };
  for (const stroke of strokes) {
    for (const c of stroke.outline || []) {
      switch (c.type) {
        case 'M':
        case 'L':
          consider(c.x, c.y);
          break;
        case 'Q':
          consider(c.begin.x, c.begin.y);
          consider(c.end.x,   c.end.y);
          break;
        case 'C':
          consider(c.begin.x, c.begin.y);
          consider(c.mid.x,   c.mid.y);
          consider(c.end.x,   c.end.y);
          break;
        // Z and unknowns: skip
      }
    }
  }
  if (!isFinite(minX)) return null;
  return { minX, maxX, minY, maxY };
}

// Build a Path2D in raw EM coordinates (no scale baked in — caller is
// responsible for ctx.transform).
function _buildPath2D(cmds) {
  if (!cmds || !cmds.length) return null;
  const p = new Path2D();
  for (const c of cmds) {
    switch (c.type) {
      case 'M':
        p.moveTo(c.x, c.y);
        break;
      case 'L':
        p.lineTo(c.x, c.y);
        break;
      case 'Q':
        p.quadraticCurveTo(
          c.begin.x, c.begin.y,
          c.end.x,   c.end.y,
        );
        break;
      case 'C':
        p.bezierCurveTo(
          c.begin.x, c.begin.y,
          c.mid.x,   c.mid.y,
          c.end.x,   c.end.y,
        );
        break;
      case 'Z':
        p.closePath();
        break;
      default:
        // ignore unknown commands
        break;
    }
  }
  // Outline closures aren't always explicit Z in our data — closing
  // here is harmless even when already closed.
  p.closePath();
  return p;
}

/** Drop the in-memory cache (e.g. after style change to free memory). */
export function clearReferenceCache() {
  _cache.clear();
}
