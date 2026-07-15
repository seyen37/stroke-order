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
 * bg 區段：單一整區＝紙磚內框（margin 內）全域。
 * 字形扣除交給渲染端的 evenodd clip——這裡只管矩形佈局。
 *
 * 5dh（使用者定案）：背景鑲嵌預設**填滿整個字形以外區域**，
 * 不再隨機切帶/象限——要細分交給 ✂ 切分工具（splitRegionBy*）。
 *
 * @param {number} tileSize - 紙磚 px（正方形）
 * @param {number} margin - 內縮 px
 * @param {{rand?: () => number}} _opts - 保留簽名相容（不再使用）
 * @returns {Array<{id, kind: "bg", band}>}
 */
export function computeBgRegions(tileSize, margin, _opts = {}) {
  return [{
    id: "r0",
    kind: "bg",
    band: {
      x: margin,
      y: margin,
      w: tileSize - 2 * margin,
      h: tileSize - 2 * margin,
    },
  }];
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
    // 5dj-1/2: 延伸技法集合（預設全關；per-region 獨立）。
    // 空物件＝全關（渲染端 normalizeEnhancers 缺欄補 false，涵蓋全部 key）。
    enhancers: {},
  }));
}

/**
 * 5dh 帶尺寸 → 連續 spacing（px）：元素大小跟著區塊自動調整，
 * 取代 5df-2 的兩檔密度。glyph 區段（筆畫區塊）用較密的除數
 * ——筆畫窄、元素要跟著縮才看得見；bg 區段用較疏。
 * 單一純函式＝渲染與縮圖等消費者共用。
 */
export function pickSpacing(band, kind = "bg") {
  const s = Math.min(band.w, band.h);
  const spacing = kind === "glyph" ? s / 4.5 : s / 3.2;
  return Math.max(9, Math.min(46, spacing));
}

/**
 * 5df-3 預留 hit-test：回傳「點落在哪個區段的 band 內」（後者優先＝
 * 渲染疊序的最上層）。純矩形判斷；字形遮罩感知版見 resolveRegionAt。
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

/**
 * 5df-3 — 點是否在「字形內」（evenodd 跨 contour：被奇數個 contour
 * 包住＝字形墨面；孔洞內＝偶數＝字形外）。與渲染端 clip(glyphPath,
 * "evenodd") 同語意，但純幾何、node 可測（不依賴 ctx.isPointInPath）。
 */
export function pointInGlyph(mappedContours, x, y) {
  if (!Array.isArray(mappedContours)) return false;
  let count = 0;
  for (const poly of mappedContours) {
    if (!Array.isArray(poly) || poly.length < 3) continue;
    if (pointInPolygon(x, y, poly)) count += 1;
  }
  return count % 2 === 1;
}

/**
 * 5df-4 — 點是否在區段內：有自訂切分 poly 的區段用多邊形判斷，
 * 純矩形區段用 band 判斷（單一函式＝選取與切分共用）。
 */
export function pointInRegion(region, x, y) {
  if (Array.isArray(region.poly)) {
    return pointInPolygon(x, y, region.poly);
  }
  const {band} = region;
  return x >= band.x && x <= band.x + band.w &&
         y >= band.y && y <= band.y + band.h;
}

/**
 * 5df-3 — 遮罩感知的區段命中：只選「點真的落在該區段可見墨區」的
 * 區段——glyph 區段要求點在字形內、bg 區段要求點在字形外。
 * 疊序上層（陣列後者）優先，與 hitTestRegions 一致。
 * 5df-4：有 poly 的區段（切分後）用多邊形判斷。
 *
 * @param {Array} regions
 * @param {Array|null} mappedContours - 字形未載入時傳 null：
 *        glyph 區段一律不可選、bg 區段退成純 band 判斷。
 * @returns {object|null}
 */
export function resolveRegionAt(regions, mappedContours, x, y) {
  if (!Array.isArray(regions)) return null;
  const hasGlyph =
    Array.isArray(mappedContours) && mappedContours.length > 0;
  const inGlyph = hasGlyph ? pointInGlyph(mappedContours, x, y) : false;
  for (let i = regions.length - 1; i >= 0; i--) {
    const r = regions[i];
    if (!pointInRegion(r, x, y)) continue;
    if (r.kind === "glyph") {
      if (!hasGlyph || !inGlyph) continue;
      return r;
    }
    // bg：字形墨面不算背景（字形未載入＝全部算背景）。
    if (inGlyph) continue;
    return r;
  }
  return null;
}

// ---------------------------------------------------------------------------
// 5df-4 — 自訂切分（點到點直線把區段剖成兩半）
// ---------------------------------------------------------------------------
//
// 資料模型擴充：region 可帶選配 `poly`（tile-local 頂點陣列）＝自訂
// 切分後的形狀；band 同步更新為 poly 的 bbox（圖樣生成仍吃矩形 area，
// 渲染端 clip 換成 poly path、圖樣不外漏）。無 poly ＝原生矩形區段。

/** Shoelace 面積（絕對值）。 */
export function polygonArea(poly) {
  if (!Array.isArray(poly) || poly.length < 3) return 0;
  let s = 0;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    s += poly[j][0] * poly[i][1] - poly[i][0] * poly[j][1];
  }
  return Math.abs(s) / 2;
}

/** 區段的形狀多邊形：poly 或 band 四角（順時針）。 */
export function regionPolygon(region) {
  if (Array.isArray(region.poly)) return region.poly;
  const {x, y, w, h} = region.band;
  return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
}

/**
 * Sutherland–Hodgman 半平面裁剪：保留「線 A→B 的 keepSign 側」。
 * side(P) = cross(B−A, P−A)；keepSign=+1 保留 side≥0、−1 保留 side≤0。
 * 凸多邊形進、凸多邊形出（矩形/切分後的半塊都是凸的）。
 */
export function clipPolygonByLine(poly, ax, ay, bx, by, keepSign) {
  const dx = bx - ax;
  const dy = by - ay;
  const side = (p) => (dx * (p[1] - ay) - dy * (p[0] - ax)) * keepSign;
  const out = [];
  for (let i = 0; i < poly.length; i++) {
    const cur = poly[i];
    const nxt = poly[(i + 1) % poly.length];
    const sc = side(cur);
    const sn = side(nxt);
    if (sc >= 0) out.push(cur);
    if ((sc > 0 && sn < 0) || (sc < 0 && sn > 0)) {
      const t = sc / (sc - sn);
      out.push([
        cur[0] + (nxt[0] - cur[0]) * t,
        cur[1] + (nxt[1] - cur[1]) * t,
      ]);
    }
  }
  return out;
}

// 切太偏產生細條的守門：任一半面積 < 原面積 2% 視為沒切到。
const MIN_SPLIT_AREA_RATIO = 0.02;

/** 線段交點：a→b（參數 t）與 c→d（參數 s）；不相交回傳 null。 */
function _segIntersect(a, b, c, d) {
  const rx = b[0] - a[0];
  const ry = b[1] - a[1];
  const sx = d[0] - c[0];
  const sy = d[1] - c[1];
  const denom = rx * sy - ry * sx;
  if (Math.abs(denom) < 1e-12) return null;
  const qx = c[0] - a[0];
  const qy = c[1] - a[1];
  const t = (qx * sy - qy * sx) / denom;
  const s = (qx * ry - qy * rx) / denom;
  if (t < -1e-9 || t > 1 + 1e-9 || s < -1e-9 || s > 1 + 1e-9) return null;
  return {t, s, pt: [a[0] + rx * t, a[1] + ry * t]};
}

/**
 * 5dh — 以開放折線（圍籬）把區段剖成兩半。曲線切割的幾何核心：
 * 呼叫端把貝茲曲線攤平成折線、兩端沿切線延長到區段外再餵進來。
 *
 * 演算法：圍籬與區段邊界求交點（沿圍籬排序）→ 恰 2 個交點才可切
 * （0＝沒穿過、>2＝曲率太大來回穿越，拒絕）→ 邊界順向鏈＋圍籬
 * 內段組成兩個新多邊形。**支援凹多邊形**（曲線切出的半塊再切
 * 也正確——半平面裁剪對凹形會出錯，故直線切也改走此路）。
 *
 * 兩半繼承 kind / tangle / orientation；band 更新為各自 poly 的
 * bbox；id 預設父 id 加 a/b 後綴（可巢狀＝天然唯一）。
 *
 * @param {object} region
 * @param {Array<[number, number]>} fence - 折線頂點（首尾在區段外）
 * @returns {{ok: true, parts: [object, object]} |
 *           {ok: false, reason: string}}
 */
export function splitRegionByPolyline(region, fence, opts = {}) {
  if (!Array.isArray(fence) || fence.length < 2) {
    return {ok: false, reason: "切割線無效"};
  }
  const poly = regionPolygon(region);
  const n = poly.length;
  const total = polygonArea(poly);
  if (total <= 0) return {ok: false, reason: "區段退化（面積為零）"};
  // 圍籬 × 邊界全交點，沿圍籬里程排序＋去重（頂點命中會重複）。
  const hits = [];
  for (let k = 0; k < fence.length - 1; k++) {
    for (let i = 0; i < n; i++) {
      const h = _segIntersect(fence[k], fence[k + 1],
                              poly[i], poly[(i + 1) % n]);
      if (h) hits.push({fpos: k + h.t, edge: i, s: h.s, pt: h.pt});
    }
  }
  hits.sort((p, q) => p.fpos - q.fpos);
  const uniq = [];
  for (const h of hits) {
    const last = uniq[uniq.length - 1];
    if (last &&
        Math.hypot(h.pt[0] - last.pt[0], h.pt[1] - last.pt[1]) < 1e-6) {
      continue;
    }
    uniq.push(h);
  }
  if (uniq.length !== 2) {
    return {ok: false,
            reason: `切割線穿越區段邊界 ${uniq.length} 次` +
                    "（需恰 2 次——未貫穿或彎曲過度來回穿越）"};
  }
  const [X1, X2] = uniq;
  // 圍籬位於區段內的中段頂點。
  const interior = [];
  for (let k = 0; k < fence.length; k++) {
    if (k > X1.fpos && k < X2.fpos) interior.push(fence[k]);
  }
  // 邊界順向鏈：from 交點所在邊往前走到 to 交點所在邊。
  const chainForward = (from, to) => {
    const out = [];
    if (from.edge === to.edge && to.s >= from.s) return out;
    let idx = (from.edge + 1) % n;
    for (let cnt = 0; cnt <= n; cnt++) {
      out.push(poly[idx]);
      if (idx === to.edge) break;
      idx = (idx + 1) % n;
    }
    return out;
  };
  const partA = [X1.pt, ...chainForward(X1, X2), X2.pt,
                 ...interior.slice().reverse()];
  const partB = [X2.pt, ...chainForward(X2, X1), X1.pt, ...interior];
  const minArea = total * (opts.minAreaRatio ?? MIN_SPLIT_AREA_RATIO);
  const areaA = polygonArea(partA);
  const areaB = polygonArea(partB);
  if (partA.length < 3 || partB.length < 3 ||
      areaA < minArea || areaB < minArea) {
    return {ok: false, reason: "切出的部分太窄（細條 < 2% 面積）"};
  }
  if (Math.abs(areaA + areaB - total) > total * 0.02) {
    return {ok: false, reason: "切割幾何異常（面積不守恆），請重切"};
  }
  const [idA, idB] = opts.ids || [`${region.id}a`, `${region.id}b`];
  const mk = (id, p) => ({
    id,
    kind: region.kind,
    band: polyBbox(p) || region.band,
    poly: p,
    tangle: region.tangle,
    orientation: region.orientation,
    // 5dj-1: 兩半繼承延伸技法（複製一份、互不影響）。
    enhancers: {...(region.enhancers || {})},
  });
  return {ok: true, parts: [mk(idA, partA), mk(idB, partB)]};
}

/**
 * 5df-4 — 沿 A→B 延伸直線把區段剖成兩半。
 * 5dh 改為 splitRegionByPolyline 的包裝（直線＝兩點圍籬向外延長）
 * ——凹多邊形（曲線切過的半塊）再直切也正確。
 */
export function splitRegionByLine(region, a, b, opts = {}) {
  const [ax, ay] = a;
  const [bx, by] = b;
  const len = Math.hypot(bx - ax, by - ay);
  if (len < 4) {
    return {ok: false, reason: "兩點太近，無法定義切分線"};
  }
  const ext = Math.hypot(region.band.w, region.band.h) * 2 + 10;
  const ux = (bx - ax) / len;
  const uy = (by - ay) / len;
  const fence = [
    [ax - ux * ext, ay - uy * ext],
    [bx + ux * ext, by + uy * ext],
  ];
  return splitRegionByPolyline(region, fence, opts);
}
