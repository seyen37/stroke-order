// Phase 5df-2 — 區段模型 + 隨機填充 (pure module, Node testable).
//
// 資料模型（5df-2 設計草稿 ①）：
//   region = {id, kind: "glyph" | "bg", band: {x, y, w, h},
//             tangle: <registry key>, orientation: "up"|"right"|"down"|"left"}
//
//   glyph 區段：字形「元件」（外輪廓＋其孔洞）bbox 沿長軸切 1~4 帶。
//   bg 區段  ：紙磚內框（margin 內）切帶或切象限——字形本體在渲染端
//              以 evenodd clip 當「洞」扣掉，這裡只管矩形切分。
//
// 渲染（zentangle.js 消費）＝canvas 雙重 clip：
//   glyph: ctx.clip(glyphPath, "evenodd") ∩ ctx.clip(bandRect)
//   bg   : ctx.clip(bandRect) ∩ ctx.clip(bigRect + glyphPath, "evenodd")
//
// 隨機性全部走注入的 rand()（預設 Math.random）——node 測試給定值
// 序列即可決定性驗證（同 5df-1 _hash01 哲學：可測第一）。
//
// hit-test（5df-3 預留）：hitTestRegions 只做 point-in-band 的矩形判斷；
// glyph 區段的「點是否落在字形內」由 DOM 端 ctx.isPointInPath 補完。

import {ORIENTATIONS} from "./tangle.mjs";

// ---------------------------------------------------------------------------
// 幾何基元
// ---------------------------------------------------------------------------

/** Ray-casting 點在多邊形內（even-odd）。poly = [[x,y], ...]。 */
export function pointInPolygon(x, y, poly) {
  if (!Array.isArray(poly) || poly.length < 3) return false;
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) &&
        x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

/** polyline bbox → {x, y, w, h}（band 格式，與 tangle area 同構）。 */
export function polyBbox(poly) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const pt of poly) {
    if (!Array.isArray(pt) || pt.length < 2) continue;
    const [x, y] = pt;
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }
  if (minX === Infinity) return null;
  return {x: minX, y: minY, w: maxX - minX, h: maxY - minY};
}

function _unionRect(a, b) {
  if (!a) return b;
  if (!b) return a;
  const x = Math.min(a.x, b.x);
  const y = Math.min(a.y, b.y);
  return {
    x, y,
    w: Math.max(a.x + a.w, b.x + b.w) - x,
    h: Math.max(a.y + a.h, b.y + b.h) - y,
  };
}

// ---------------------------------------------------------------------------
// 元件分組（外輪廓 vs 孔洞）
// ---------------------------------------------------------------------------

/**
 * 把 contour 陣列分組成「元件」：偶數層＝外輪廓、奇數層＝孔洞；
 * 孔洞掛到「包含它、且 bbox 面積最小」的外輪廓上（最貼身的那個）。
 *
 * @param {Array} contours - [[[x,y], ...], ...]（tile-local px、已閉合語意）
 * @returns {Array<{indices: number[], bbox: {x,y,w,h}}>}
 *          indices[0] 恆為外輪廓 index；bbox 含孔洞聯集（＝外輪廓 bbox）。
 */
export function groupContours(contours) {
  if (!Array.isArray(contours)) return [];
  const valid = [];
  for (let i = 0; i < contours.length; i++) {
    const poly = contours[i];
    if (!Array.isArray(poly) || poly.length < 3) continue;
    const bbox = polyBbox(poly);
    if (!bbox) continue;
    valid.push({i, poly, bbox});
  }
  // 每個 contour 的包含深度＝有幾個「別的」contour 包住它的代表點。
  const depth = new Map();
  for (const c of valid) {
    const [rx, ry] = c.poly[0];
    let d = 0;
    for (const other of valid) {
      if (other.i === c.i) continue;
      if (pointInPolygon(rx, ry, other.poly)) d += 1;
    }
    depth.set(c.i, d);
  }
  const outers = valid.filter((c) => depth.get(c.i) % 2 === 0);
  const holes = valid.filter((c) => depth.get(c.i) % 2 === 1);
  const comps = outers.map((o) => ({indices: [o.i], bbox: {...o.bbox}}));
  for (const h of holes) {
    const [rx, ry] = h.poly[0];
    let best = null;
    let bestArea = Infinity;
    for (let k = 0; k < outers.length; k++) {
      const o = outers[k];
      if (!pointInPolygon(rx, ry, o.poly)) continue;
      const area = o.bbox.w * o.bbox.h;
      if (area < bestArea) {
        bestArea = area;
        best = k;
      }
    }
    if (best !== null) {
      comps[best].indices.push(h.i);
      comps[best].bbox = _unionRect(comps[best].bbox, h.bbox);
    } else {
      // 防禦：找不到宿主（資料異常）→ 自成一個元件，不丟資料。
      comps.push({indices: [h.i], bbox: {...h.bbox}});
    }
  }
  return comps;
}

// ---------------------------------------------------------------------------
// 帶切分
// ---------------------------------------------------------------------------

/**
 * 沿長軸把矩形切成 n 帶（首尾相接、恰好鋪滿、不重疊）。
 * w ≥ h → 垂直切（帶並排在 x 方向）；否則水平切。
 */
export function splitBandRect(rect, n) {
  const count = Math.max(1, Math.floor(n) || 1);
  const bands = [];
  if (rect.w >= rect.h) {
    for (let i = 0; i < count; i++) {
      const x0 = rect.x + (rect.w * i) / count;
      const x1 = rect.x + (rect.w * (i + 1)) / count;
      bands.push({x: x0, y: rect.y, w: x1 - x0, h: rect.h});
    }
  } else {
    for (let i = 0; i < count; i++) {
      const y0 = rect.y + (rect.h * i) / count;
      const y1 = rect.y + (rect.h * (i + 1)) / count;
      bands.push({x: rect.x, y: y0, w: rect.w, h: y1 - y0});
    }
  }
  return bands;
}

// 帶的最小長軸尺寸（px）——比這窄的帶塞不進任何 tangle 網格，
// 元件太小就少切幾帶（極小元件＝1 帶整塊）。
const MIN_BAND_PX = 60;

// ---------------------------------------------------------------------------
// 區段生成
// ---------------------------------------------------------------------------

/**
 * glyph 區段：每個字形元件 bbox 沿長軸隨機切 2~4 帶
 * （受 MIN_BAND_PX 上限保護，極小元件退成 1 帶）。
 *
 * @param {Array} mappedContours - tile-local px contours（mapContourToTile 輸出）
 * @param {{rand?: () => number}} opts
 * @returns {Array<{id, kind: "glyph", band}>}
 */
export function computeGlyphRegions(mappedContours, opts = {}) {
  const rand = opts.rand || Math.random;
  const comps = groupContours(mappedContours);
  const regions = [];
  for (const comp of comps) {
    const long = Math.max(comp.bbox.w, comp.bbox.h);
    const maxByPx = Math.max(1, Math.floor(long / MIN_BAND_PX));
    const wanted = 2 + Math.floor(rand() * 3);        // 2~4
    const n = Math.min(4, Math.max(1, Math.min(wanted, maxByPx)));
    for (const band of splitBandRect(comp.bbox, n)) {
      regions.push({id: `r${regions.length}`, kind: "glyph", band});
    }
  }
  return regions;
}

/**
 * bg 區段：紙磚內框（margin 內）隨機切「帶」或「象限」。
 * 字形扣除交給渲染端的 evenodd clip——這裡只管矩形佈局。
 *
 * @param {number} tileSize - 紙磚 px（正方形）
 * @param {number} margin - 內縮 px
 * @param {{rand?: () => number}} opts
 * @returns {Array<{id, kind: "bg", band}>}
 */
export function computeBgRegions(tileSize, margin, opts = {}) {
  const rand = opts.rand || Math.random;
  const inner = {
    x: margin,
    y: margin,
    w: tileSize - 2 * margin,
    h: tileSize - 2 * margin,
  };
  let bands;
  if (rand() < 0.5) {
    // 象限：4 塊 2×2。
    const hw = inner.w / 2;
    const hh = inner.h / 2;
    bands = [
      {x: inner.x, y: inner.y, w: hw, h: hh},
      {x: inner.x + hw, y: inner.y, w: inner.w - hw, h: hh},
      {x: inner.x, y: inner.y + hh, w: hw, h: inner.h - hh},
      {x: inner.x + hw, y: inner.y + hh, w: inner.w - hw, h: inner.h - hh},
    ];
  } else {
    // 帶：2~4 帶；方向由 rand 決定（內框是正方形、長軸無從偏好）。
    const n = 2 + Math.floor(rand() * 3);
    const horizontal = rand() < 0.5;
    bands = [];
    for (let i = 0; i < n; i++) {
      const t0 = i / n;
      const t1 = (i + 1) / n;
      bands.push(
        horizontal
          ? {x: inner.x, y: inner.y + inner.h * t0,
             w: inner.w, h: inner.h * (t1 - t0)}
          : {x: inner.x + inner.w * t0, y: inner.y,
             w: inner.w * (t1 - t0), h: inner.h}
      );
    }
  }
  return bands.map((band, i) => ({id: `r${i}`, kind: "bg", band}));
}

/**
 * 隨機指派 tangle＋朝向（5df-2 設計草稿 ③）。
 * 不改輸入（回傳新陣列）；rand 可注入＝決定性測試。
 *
 * @param {Array} regions - computeGlyphRegions / computeBgRegions 輸出
 * @param {Array<string>} tangleKeys - listTangles() 的 key 清單
 * @param {{rand?: () => number}} opts
 */
export function assignRandomTangles(regions, tangleKeys, opts = {}) {
  const rand = opts.rand || Math.random;
  if (!Array.isArray(tangleKeys) || tangleKeys.length === 0) {
    throw new Error("assignRandomTangles: tangleKeys must be non-empty");
  }
  return regions.map((r) => ({
    ...r,
    tangle: tangleKeys[Math.floor(rand() * tangleKeys.length) % tangleKeys.length],
    orientation: ORIENTATIONS[
      Math.floor(rand() * ORIENTATIONS.length) % ORIENTATIONS.length
    ],
  }));
}

/**
 * 帶尺寸 → 密度：窄帶用 high（間距 28px）才塞得進圖樣，
 * 寬帶用 medium。單一純函式＝SVG 匯出等未來消費者共用。
 */
export function pickDensity(band) {
  return Math.min(band.w, band.h) < 100 ? "high" : "medium";
}

/**
 * 5df-3 預留 hit-test：回傳「點落在哪個區段的 band 內」（後者優先＝
 * 渲染疊序的最上層）。glyph 區段還需 DOM 端 ctx.isPointInPath 確認
 * 點真的在字形內——這裡是純幾何層，不碰 canvas。
 *
 * @returns {object|null} region or null
 */
export function hitTestRegions(regions, x, y) {
  if (!Array.isArray(regions)) return null;
  for (let i = regions.length - 1; i >= 0; i--) {
    const {band} = regions[i];
    if (x >= band.x && x <= band.x + band.w &&
        y >= band.y && y <= band.y + band.h) {
      return regions[i];
    }
  }
  return null;
}
