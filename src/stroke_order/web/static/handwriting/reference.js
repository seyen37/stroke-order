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
const _inflight = new Map();   // key → Promise（5ew-R1：預載與畫面請求去重）

export async function fetchReference(char, style = 'kaishu') {
  if (!char) return [];
  const key = `${char}|${style}`;
  if (_cache.has(key)) return _cache.get(key);
  if (_inflight.has(key)) return _inflight.get(key);   // 同字請求只發一次

  const url = `/api/handwriting/reference/${encodeURIComponent(char)}` +
              `?style=${encodeURIComponent(style)}`;
  const p = (async () => {
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
    _inflight.delete(key);
    return strokes;
  })();
  _inflight.set(key, p);
  return p;
}

/**
 * 5ew-R1：背景預載後續字的參考字形。
 *
 * 教材（如抄經經典）的字序已知——練當前字時把後面 n 個字先抓回來：
 * 命中本模組記憶體快取＋瀏覽器 HTTP 快取，同時暖了伺服器端 5eu 回應
 * 快取（/api/handwriting/reference 在快取前綴清單內）。按「下一字」
 * 時參考字形即時出現，不再等 render。
 *
 * 低併發（2）循序抓：不擠爆伺服器（篆/隸 skeleton 抽取偏重）；
 * fire-and-forget、錯誤靜默（輪到該字時 fetchReference 會再試）。
 */
export function prefetchReferences(chars, style = 'kaishu', concurrency = 2) {
  const queue = (chars || []).filter(
    c => c && !_cache.has(`${c}|${style}`) && !_inflight.has(`${c}|${style}`));
  let i = 0;
  const worker = async () => {
    while (i < queue.length) {
      const c = queue[i++];
      await fetchReference(c, style).catch(() => {});
    }
  };
  for (let k = 0; k < Math.min(concurrency, queue.length); k++) worker();
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

  // 5fm：以「墨跡實框」正規化到畫布 ~86%（取代固定 EM 1:1 比例）。
  // 舊法 scale = min(w,h)/EM_SIZE 把整個 EM 2048 框直接鋪滿畫布——滿框字
  // 如「春」墨跡近乎撐滿 EM，於是頂到／溢出米字格（實機回報：字體過大超出
  // 米字框）。改成量墨跡長邊、填滿畫布 86% 並置中，每個字固定佔比、既大又不
  // 溢框，且與逐字手寫彈窗（modes/handwrite.js swBuildCellRefImg）同一比例。
  const FILL = 0.86;
  const span = Math.max(bbox.maxX - bbox.minX, bbox.maxY - bbox.minY) || EM_SIZE;
  const scale = (FILL * Math.min(w, h)) / span;

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
