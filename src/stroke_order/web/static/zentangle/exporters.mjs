// Phase 5dj-4 — 禪繞延伸效果向量匯出（SVG / G-code），pure module, Node testable.
//
// 目標：讓雷切機、寫字機能輸出禪繞的裝飾筆劃（含 5dj 全部延伸技法）。
// 禪繞全在前端 canvas，spec 幾何也全在前端——匯出＝把「畫面上實際渲染
// 的 spec」序列化成向量格式，與 drawRegionLayer 同一條管線（build →
// orient → enhance）產出的 specs。
//
// 三步（QODA A/A/A 定案）：
//   1. flatten：每個 spec 攤平成折線；填色形狀（dot/tri）輪廓化成閉合折線
//      （筆／雷射都走得了邊框）——A 案輪廓化。
//   2. clip：取樣裁切——折線細分、逐小段判斷中點是否在區段可見區
//      （glyph: 字形 evenodd ∩ band；bg: band ∖ 字形），只留內部段。忠實
//      貼合畫面、雷切/寫字機都切得對——A 案取樣裁切。
//   3. emit：折線 → SVG（mm 尺寸，含填色版供檢視）或 G-code（專案慣例）。
//
// 座標：spec 為 tile-local px（y 向下）。匯出換算成 mm：scale = tileMm/tilePx。
// G-code flip_y（機器 Y 向上）：Y_mm =(tilePx - y_px)·scale。

import {
  SPEC_LINE, SPEC_CURVE, SPEC_S_SHAPE, SPEC_ORB, SPEC_DOT,
  SPEC_POLYLINE, SPEC_TRI,
  buildTangleOriented,
} from "./tangle.mjs?v=__V__";
import {flattenSShape} from "./enhancers.mjs?v=__V__";
import {applyEnhancers, hasAnyEnhancer} from "./enhancers.mjs?v=__V__";
import {pickSpacing, pointInGlyph, pointInRegion, regionPolygon} from "./regions.mjs?v=__V__";

// 紙磚實體尺寸（mm）——對應 TILE_SIZES 的 px（zentangle.js）。
export const TILE_MM = {bijou: 50, standard: 90, apprentice: 135};

// ---------------------------------------------------------------------------
// 1) flatten：spec → 折線（{points:[[x,y],...], closed:bool}）
// ---------------------------------------------------------------------------

/** quadratic 攤平成 segs+1 點。 */
function flattenQuad(P0, P1, P2, segs) {
  const pts = [];
  for (let i = 0; i <= segs; i++) {
    const t = i / segs, u = 1 - t;
    pts.push([u*u*P0[0] + 2*u*t*P1[0] + t*t*P2[0],
              u*u*P0[1] + 2*u*t*P1[1] + t*t*P2[1]]);
  }
  return pts;
}

/** 圓/弧攤平；完整圓回傳閉合折線。 */
function flattenArc(cx, cy, r, a0, a1, segs) {
  const pts = [];
  for (let i = 0; i <= segs; i++) {
    const a = a0 + (a1 - a0) * (i / segs);
    pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]);
  }
  return pts;
}

/**
 * spec → 折線陣列（一個 spec 可能攤成一條）。填色形狀輪廓化：
 *   dot → 小圓周（閉合）；tri → 三頂點（閉合）。
 * @returns {Array<{points, closed}>}
 */
export function flattenSpec(spec, opts = {}) {
  const arcSegs = opts.arcSegs ?? 40;
  const curveSegs = opts.curveSegs ?? 24;
  switch (spec.type) {
    case SPEC_LINE:
      return [{points: [[spec.x1, spec.y1], [spec.x2, spec.y2]], closed: false}];
    case SPEC_CURVE:
      return [{points: flattenQuad([spec.x1, spec.y1], [spec.cx, spec.cy],
                                   [spec.x2, spec.y2], curveSegs), closed: false}];
    case SPEC_S_SHAPE:
      return [{points: flattenSShape(spec, curveSegs), closed: false}];
    case SPEC_POLYLINE:
      return [{points: (spec.points || []).slice(), closed: false}];
    case SPEC_ORB: {
      const a0 = spec.startAngle ?? 0;
      const a1 = spec.endAngle ?? Math.PI * 2;
      const full = spec.startAngle === undefined && spec.endAngle === undefined;
      const n = Math.max(6, Math.round(arcSegs * Math.abs(a1 - a0) / (Math.PI * 2)));
      return [{points: flattenArc(spec.cx, spec.cy, spec.r, a0, a1, n),
               closed: full}];
    }
    case SPEC_DOT: {
      // 填色型（fill:true）：閉合小圓周；collect 依 fillMode 決定輪廓/掃描。
      const n = Math.max(6, Math.round(arcSegs * 0.4));
      return [{points: flattenArc(spec.cx, spec.cy, Math.max(spec.r, 0.4),
                                  0, Math.PI * 2, n), closed: true, fill: true}];
    }
    case SPEC_TRI: {
      const p = spec.points || [];
      if (p.length < 3) return [];
      return [{points: [p[0], p[1], p[2]], closed: true, fill: true}];
    }
    default:
      return [];
  }
}

// ---------------------------------------------------------------------------
// 1b) scanline 填充：閉合多邊形 → 平行水平掃描線（雷雕填色）
// ---------------------------------------------------------------------------

/**
 * 掃描填充：水平線陣列與多邊形求交、配對區間 → 水平線段。
 * spacing 為 px（呼叫端由 mm 換算）。回傳開放折線群（每段兩點）。
 */
export function scanlineFill(poly, spacing) {
  if (!Array.isArray(poly) || poly.length < 3 || !(spacing > 0)) return [];
  let ymin = Infinity, ymax = -Infinity;
  for (const [, y] of poly) { if (y < ymin) ymin = y; if (y > ymax) ymax = y; }
  const segs = [];
  // 從 ymin 半格起掃、避免恰壓頂點。
  for (let y = ymin + spacing * 0.5; y < ymax; y += spacing) {
    const xs = [];
    for (let i = 0; i < poly.length; i++) {
      const [x1, y1] = poly[i];
      const [x2, y2] = poly[(i + 1) % poly.length];
      // 邊跨越掃描線 y（半開區間避免頂點重複計數）。
      if ((y1 <= y && y2 > y) || (y2 <= y && y1 > y)) {
        xs.push(x1 + (x2 - x1) * (y - y1) / (y2 - y1));
      }
    }
    xs.sort((a, b) => a - b);
    for (let k = 0; k + 1 < xs.length; k += 2) {
      if (xs[k + 1] - xs[k] > 1e-6) segs.push([[xs[k], y], [xs[k + 1], y]]);
    }
  }
  return segs;
}

// ---------------------------------------------------------------------------
// 2) clip：取樣裁切折線 → 只留在區段可見區內的子折線
// ---------------------------------------------------------------------------

/** 點在「區段可見區」內？glyph: 字形內 ∩ band；bg: 字形外 ∩ band。 */
function pointVisible(region, mappedContours, x, y) {
  if (!pointInRegion(region, x, y)) return false;
  const hasGlyph = Array.isArray(mappedContours) && mappedContours.length > 0;
  const inGlyph = hasGlyph ? pointInGlyph(mappedContours, x, y) : false;
  if (region.kind === "glyph") return hasGlyph && inGlyph;
  return !inGlyph;                      // bg：字形墨面不算背景
}

/** lerp（沿 a→b，參數 t）。 */
function lerpAB(a, b, t) {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

/**
 * 線段交點參數：回傳 a→b 上的參數 t（∈[0,1]，與 c→d 相交），否則 null。
 * 平行/共線回傳 null（共線邊界貢獻端點交點由相鄰非平行邊補上）。
 */
function segParamT(a, b, c, d) {
  const rx = b[0] - a[0], ry = b[1] - a[1];
  const sx = d[0] - c[0], sy = d[1] - c[1];
  const denom = rx * sy - ry * sx;
  if (Math.abs(denom) < 1e-12) return null;
  const qx = c[0] - a[0], qy = c[1] - a[1];
  const t = (qx * sy - qy * sx) / denom;
  const u = (qx * ry - qy * rx) / denom;
  if (t < -1e-9 || t > 1 + 1e-9 || u < -1e-9 || u > 1 + 1e-9) return null;
  return Math.min(1, Math.max(0, t));
}

/**
 * 5dj-5 — 裁切邊界邊：區段形狀多邊形（band 或 5df-4 切分 poly）＋所有
 * 字形 contour 邊。線段與這些邊求精確交點＝真裁切分割點。
 * @returns {Array<[[x,y],[x,y]]>}
 */
export function buildClipEdges(region, mappedContours) {
  const edges = [];
  const rp = regionPolygon(region);
  for (let i = 0; i < rp.length; i++) edges.push([rp[i], rp[(i + 1) % rp.length]]);
  if (Array.isArray(mappedContours)) {
    for (const poly of mappedContours) {
      if (!Array.isArray(poly) || poly.length < 2) continue;
      for (let i = 0; i < poly.length; i++)
        edges.push([poly[i], poly[(i + 1) % poly.length]]);
    }
  }
  return edges;
}

/**
 * 一段 [a,b] 的「保留區間」（升序 [t0,t1]）：與所有邊界邊求精確交點 →
 * 沿線參數排序去重 → 相鄰交點間以中點 even-odd 判斷是否在區段可見區，
 * 保留在內的區間 → 合併連續保留區間（跨字形邊但仍在內＝一整段）。
 */
function keptIntervalsOnSeg(a, b, region, mappedContours, edges) {
  const ts = [0, 1];
  for (const [c, d] of edges) {
    const t = segParamT(a, b, c, d);
    if (t !== null) ts.push(t);
  }
  ts.sort((x, y) => x - y);
  const uniq = [];
  for (const t of ts)
    if (!uniq.length || t - uniq[uniq.length - 1] > 1e-7) uniq.push(t);
  const kept = [];
  for (let k = 0; k < uniq.length - 1; k++) {
    const t0 = uniq[k], t1 = uniq[k + 1];
    const m = lerpAB(a, b, (t0 + t1) / 2);
    if (pointVisible(region, mappedContours, m[0], m[1])) {
      const last = kept[kept.length - 1];
      if (last && Math.abs(last[1] - t0) < 1e-7) last[1] = t1;   // 合併連續
      else kept.push([t0, t1]);
    }
  }
  return kept;
}

/**
 * 5dj-5 真裁切（精確 even-odd）：折線的每一段與「區段形狀 + 字形輪廓」
 * 求精確交點分割，只留在區段可見區（glyph: 字形 evenodd ∩ 區段；bg:
 * 區段 ∖ 字形）的子區間。裁切邊界精確落在字形/區段邊上，無 px 級鋸齒。
 * 跨段連續（前段延伸到終點、後段從起點續）則串成同一條折線。
 * 閉合折線先展開成環再裁。
 *
 * @returns {Array<Array<[x,y]>>} 裁切後的開放折線群（可能 0..N 條）
 */
export function clipPolyline(pl, region, mappedContours, opts = {}) {
  const src = pl.points;
  if (!Array.isArray(src) || src.length < 2) return [];
  const pts = pl.closed ? [...src, src[0]] : src;
  const edges = opts.edges || buildClipEdges(region, mappedContours);
  const out = [];
  let cur = [];
  const flush = () => { if (cur.length >= 2) out.push(cur); cur = []; };
  let prevToEnd = false;                      // 前段是否延伸到終點（t1=1）
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    const intervals = keptIntervalsOnSeg(a, b, region, mappedContours, edges);
    if (intervals.length === 0) { flush(); prevToEnd = false; continue; }
    for (let j = 0; j < intervals.length; j++) {
      const [t0, t1] = intervals[j];
      const P0 = lerpAB(a, b, t0), P1 = lerpAB(a, b, t1);
      if (j === 0 && prevToEnd && t0 <= 1e-7 && cur.length > 0) {
        cur.push(P1);                          // 跨段續：a==前段 b、跳過重複點
      } else {
        flush();
        cur = [P0, P1];
      }
    }
    prevToEnd = intervals[intervals.length - 1][1] >= 1 - 1e-7;
  }
  flush();
  return out;
}

// ---------------------------------------------------------------------------
// 3) collect：所有區段的 enhanced+clipped 折線（＋字框 outline）
// ---------------------------------------------------------------------------

/**
 * 收集匯出折線。與 drawRegionLayer 同管線（buildTangleOriented →
 * applyEnhancers），再以 5dj-5 精確 even-odd 真裁切到區段可見區。
 * 每區段的裁切邊界（區段形狀＋字形輪廓）預算一次、跨該區所有折線復用。
 *
 * 5dk：填色形狀（dot/tri，flatten fill:true）依 fillMode 分流——
 *   "outline"（預設）：輪廓當描邊 → strokes
 *   "scan"           ：掃描線填滿 → fills（雷雕）
 *   "skip"           ：略過
 * 掃描間距 scanSpacingMm 由 tileMm/tileSize 換算成 px。
 * strokes/fills 分開回傳＝DXF 可分 ENGRAVE（線＋填）／WRITE（僅線）。
 *
 * @param {object} ctx - {regions, mappedContours, params, tileSize, tileMm,
 *                        baseLineWidth, includeOutline, fillMode, scanSpacingMm,
 *                        arcSegs, curveSegs}
 * @returns {{strokes, fills, outline}} 各為 Array<Array<[x,y]>>
 */
export function collectExportPaths(ctx) {
  const {regions, mappedContours, params, tileSize, tileMm = 90,
         baseLineWidth = 1, includeOutline = true,
         fillMode = "outline", scanSpacingMm = 1.0,
         arcSegs, curveSegs, paramsToOpts} = ctx;
  const flattenOpts = {};
  if (arcSegs) flattenOpts.arcSegs = arcSegs;
  if (curveSegs) flattenOpts.curveSegs = curveSegs;
  const scanSpacingPx = Math.max(1, scanSpacingMm * tileSize / tileMm);
  const strokes = [];
  const fills = [];
  for (const region of regions || []) {
    if (!region.tangle) continue;
    if (region.kind === "glyph" &&
        !(Array.isArray(mappedContours) && mappedContours.length > 0)) continue;
    let specs = buildTangleOriented(
      region.tangle, region.band,
      pickSpacing(region.band, region.kind), region.orientation);
    if (hasAnyEnhancer(region.enhancers)) {
      const opts = paramsToOpts
        ? paramsToOpts(params, {baseLineWidth, area: region.band})
        : {baseLineWidth, area: region.band};
      specs = applyEnhancers(specs, region.enhancers, opts);
    }
    // 5dj-5：裁切邊界每區段預算一次（避免每條折線重建字形邊列表）。
    const edges = buildClipEdges(region, mappedContours);
    for (const spec of specs) {
      for (const pl of flattenSpec(spec, flattenOpts)) {
        if (pl.fill) {
          // 填色形狀依 fillMode 分流。
          if (fillMode === "skip") continue;
          if (fillMode === "scan") {
            for (const seg of scanlineFill(pl.points, scanSpacingPx)) {
              for (const c of clipPolyline({points: seg, closed: false},
                                           region, mappedContours, {edges})) {
                fills.push(c);
              }
            }
            continue;
          }
          // "outline"：輪廓當描邊，落入 strokes（下方共用裁切）。
        }
        for (const seg of clipPolyline(pl, region, mappedContours, {edges})) {
          strokes.push(seg);
        }
      }
    }
  }
  const outline = [];
  if (includeOutline && Array.isArray(mappedContours)) {
    for (const poly of mappedContours) {
      if (Array.isArray(poly) && poly.length >= 2) outline.push([...poly, poly[0]]);
    }
  }
  return {strokes, fills, outline};
}

// ---------------------------------------------------------------------------
// 4) emit：折線 → SVG / G-code
// ---------------------------------------------------------------------------

function fmt(n) { return Number(n.toFixed(3)); }

/** 折線群 → SVG polyline points 屬性字串（mm）。 */
function plToPoints(seg, sx, sy) {
  return seg.map(([x, y]) => `${fmt(x * sx)},${fmt(y * sy)}`).join(" ");
}

/**
 * SVG 匯出（mm 尺寸；5bt 契約：width = viewBox 跨度 mm）。三層：outline
 * 字框（較粗）／tangle 圖樣線／fill 掃描填充（5dk，scan 模式才有）。
 */
export function pathsToSvg(paths, opts = {}) {
  const {tileSize, tileMm, strokeMm = 0.3, outlineMm = 0.5, envelope = null} = opts;
  const sx = tileMm / tileSize, sy = tileMm / tileSize;
  const w = fmt(tileMm), h = fmt(tileMm);
  const lines = [];
  lines.push('<?xml version="1.0" encoding="UTF-8"?>');
  lines.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}mm" height="${h}mm" ` +
             `viewBox="0 0 ${w} ${h}">`);
  // 5fv：統一出口信封（與後端 exporters/envelope.py 同格式）——
  // 分享庫收件側驗此憑據；禪繞是唯一前端產 SVG 的模式。
  if (envelope && envelope.mode) {
    const payload = {schema: "stroke-order-export-v1", mode: envelope.mode};
    if (envelope.appVersion) payload.app_version = envelope.appVersion;
    if (envelope.params) payload.params = envelope.params;
    const body = JSON.stringify(payload).replace(/\]\]>/g, "]]\\u003e");
    lines.push(`  <metadata><stroke-order-export><![CDATA[${body}]]>` +
               `</stroke-order-export></metadata>`);
  }
  lines.push('  <g fill="none" stroke="#000" stroke-linecap="round" stroke-linejoin="round">');
  if (paths.outline && paths.outline.length) {
    lines.push(`    <g stroke-width="${outlineMm}" data-layer="outline">`);
    for (const seg of paths.outline)
      lines.push(`      <polyline points="${plToPoints(seg, sx, sy)}"/>`);
    lines.push("    </g>");
  }
  if (paths.fills && paths.fills.length) {
    lines.push(`    <g stroke-width="${strokeMm}" data-layer="fill">`);
    for (const seg of paths.fills)
      lines.push(`      <polyline points="${plToPoints(seg, sx, sy)}"/>`);
    lines.push("    </g>");
  }
  lines.push(`    <g stroke-width="${strokeMm}" data-layer="tangle">`);
  for (const seg of paths.strokes)
    lines.push(`      <polyline points="${plToPoints(seg, sx, sy)}"/>`);
  lines.push("    </g>");
  lines.push("  </g>");
  lines.push("</svg>");
  return lines.join("\n") + "\n";
}

/**
 * G-code 匯出（專案慣例：G21/G90、M5/M3 S90、G0 F6000/G1 F3000、G4 P150、
 * flip_y、origin 10,10）。每條折線＝移到起點 → 落筆 → 沿點 → 抬筆。
 */
export function pathsToGcode(paths, opts = {}) {
  const {tileSize, tileMm, feed = 3000, travel = 6000,
         ox = 10.0, oy = 10.0, dwellMs = 150, includeOutline = true} = opts;
  const s = tileMm / tileSize;
  const penUp = "M5", penDown = "M3 S90";
  // flip_y：機器 Y 向上；tile y 向下。Y_mm = origin + (tilePx - y)·s。
  const xf = ([x, y]) => [ox + x * s, oy + (tileSize - y) * s];
  const out = [];
  out.push("; --- stroke-order 禪繞延伸效果 G-code ---");
  out.push("; NOTE: 圖樣為裝飾筆劃（幾何近似、非教育部筆順）；填色形狀已輪廓化");
  out.push(`; tile=${tileMm}mm feed=${feed} travel=${travel}`);
  out.push("G21 ; mm");
  out.push("G90 ; absolute");
  out.push(`${penUp} ; pen up (start)`);
  out.push(`G4 P${dwellMs}`);
  out.push(`G0 X${fmt(ox)} Y${fmt(oy)} F${travel} ; home`);
  const emit = (segs, label) => {
    out.push("");
    out.push(`; --- ${label} (${segs.length} paths) ---`);
    for (const seg of segs) {
      if (seg.length < 2) continue;
      let [x, y] = xf(seg[0]);
      out.push(`G0 X${fmt(x)} Y${fmt(y)} F${travel}`);
      out.push(penDown);
      out.push(`G4 P${dwellMs}`);
      for (let i = 1; i < seg.length; i++) {
        [x, y] = xf(seg[i]);
        out.push(`G1 X${fmt(x)} Y${fmt(y)} F${feed}`);
      }
      out.push(`G4 P${dwellMs}`);
      out.push(penUp);
    }
  };
  if (includeOutline && paths.outline && paths.outline.length)
    emit(paths.outline, "outline 字框");
  emit(paths.strokes, "tangle 圖樣");
  if (paths.fills && paths.fills.length) emit(paths.fills, "fill 掃描填充");
  out.push("");
  out.push("; --- epilogue ---");
  out.push(`${penUp} ; ensure pen up`);
  out.push(`G0 X${fmt(ox)} Y${fmt(oy)} F${travel} ; return home`);
  out.push("; done");
  return out.join("\n") + "\n";
}

// ---------------------------------------------------------------------------
// 5dk) DXF R12 分層匯出（CUT / ENGRAVE / WRITE，復刻 exporters/dxf.py 慣例）
// ---------------------------------------------------------------------------

//: AutoCAD 顏色索引（同 dxf.py：CUT 紅 / ENGRAVE 黑 / WRITE 藍）。
export const DXF_LAYER_COLORS = {CUT: 1, ENGRAVE: 7, WRITE: 5};

function dg(code, value) { return `${code}\n${value}\n`; }

/**
 * DXF R12 ASCII（POLYLINE/VERTEX/SEQEND；zero-dep；flip_y 機器 Y 向上）。
 * layers = [{name, polys:[{points:[[x,y]mm...], closed}]}]，順序保留。
 */
export function layersToDxf(layers, opts = {}) {
  const flipY = opts.flipY !== false;
  const sy = flipY ? -1 : 1;
  const out = [];
  out.push(dg(0, "SECTION") + dg(2, "HEADER"));
  out.push(dg(9, "$ACADVER") + dg(1, "AC1009"));
  out.push(dg(0, "ENDSEC"));
  out.push(dg(0, "SECTION") + dg(2, "TABLES"));
  out.push(dg(0, "TABLE") + dg(2, "LAYER") + dg(70, layers.length));
  for (const {name} of layers) {
    const color = DXF_LAYER_COLORS[name] ?? 7;
    out.push(dg(0, "LAYER") + dg(2, name) + dg(70, 0) + dg(62, color) + dg(6, "CONTINUOUS"));
  }
  out.push(dg(0, "ENDTAB") + dg(0, "ENDSEC"));
  out.push(dg(0, "SECTION") + dg(2, "ENTITIES"));
  for (const {name, polys} of layers) {
    for (const poly of polys) {
      const pts = poly.points;
      if (!Array.isArray(pts) || pts.length < 2) continue;
      out.push(dg(0, "POLYLINE") + dg(8, name) + dg(66, 1) + dg(70, poly.closed ? 1 : 0));
      for (const [x, y] of pts) {
        out.push(dg(0, "VERTEX") + dg(8, name) +
                 dg(10, fmt(x)) + dg(20, fmt(sy * y)) + dg(30, "0.0"));
      }
      out.push(dg(0, "SEQEND") + dg(8, name));
    }
  }
  out.push(dg(0, "ENDSEC") + dg(0, "EOF"));
  return out.join("");
}

/**
 * 禪繞路徑 → DXF 三層（5dk QODA 定案）：
 *   CUT（紅）    ：字框 outline（雷切輪廓）
 *   ENGRAVE（黑）：圖樣線 + 掃描填充（雷雕）
 *   WRITE（藍）  ：圖樣線（寫字機筆軌跡，不含掃描填充）
 * px → mm 換算後入 DXF（DXF 用 mm 空間、flip_y 由 layersToDxf 處理）。
 */
export function pathsToDxf(paths, opts = {}) {
  const {tileSize, tileMm} = opts;
  const s = tileMm / tileSize;
  const toMm = (segs) => (segs || []).map(
    (seg) => ({points: seg.map(([x, y]) => [x * s, y * s]), closed: false}));
  const outlineMm = (paths.outline || []).map(
    (seg) => ({points: seg.map(([x, y]) => [x * s, y * s]), closed: true}));
  const engrave = [...toMm(paths.strokes), ...toMm(paths.fills)];
  return layersToDxf([
    {name: "CUT", polys: outlineMm},
    {name: "ENGRAVE", polys: engrave},
    {name: "WRITE", polys: toMm(paths.strokes)},
  ], opts);
}
