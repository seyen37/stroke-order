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
} from "./tangle.mjs";
import {flattenSShape} from "./enhancers.mjs";
import {applyEnhancers, hasAnyEnhancer} from "./enhancers.mjs";
import {pickSpacing, pointInGlyph, pointInRegion} from "./regions.mjs";

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
      // 輪廓化：小圓周（閉合折線）。
      const n = Math.max(6, Math.round(arcSegs * 0.4));
      return [{points: flattenArc(spec.cx, spec.cy, Math.max(spec.r, 0.4),
                                  0, Math.PI * 2, n), closed: true}];
    }
    case SPEC_TRI: {
      const p = spec.points || [];
      if (p.length < 3) return [];
      return [{points: [p[0], p[1], p[2]], closed: true}];
    }
    default:
      return [];
  }
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

/**
 * 取樣裁切：把折線細分（step px），逐小段以中點判斷是否可見，連續可見
 * 的點串成子折線（出界即斷）。閉合折線先展開成環（尾接頭）再裁。
 * @returns {Array<Array<[x,y]>>} 裁切後的開放折線群（可能 0..N 條）
 */
export function clipPolyline(pl, region, mappedContours, opts = {}) {
  const step = opts.step ?? 2.0;             // 細分步長（px）
  const src = pl.points;
  if (!Array.isArray(src) || src.length < 2) return [];
  const pts = pl.closed ? [...src, src[0]] : src;
  const out = [];
  let cur = [];
  const pushPt = (p) => { cur.push(p); };
  const flush = () => { if (cur.length >= 2) out.push(cur); cur = []; };
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const n = Math.max(1, Math.ceil(len / step));
    for (let k = 0; k < n; k++) {
      const t0 = k / n, t1 = (k + 1) / n;
      const m = [a[0] + (b[0]-a[0])*(t0+t1)/2, a[1] + (b[1]-a[1])*(t0+t1)/2];
      const p0 = [a[0] + (b[0]-a[0])*t0, a[1] + (b[1]-a[1])*t0];
      const p1 = [a[0] + (b[0]-a[0])*t1, a[1] + (b[1]-a[1])*t1];
      if (pointVisible(region, mappedContours, m[0], m[1])) {
        if (cur.length === 0) pushPt(p0);
        pushPt(p1);
      } else {
        flush();
      }
    }
  }
  flush();
  return out;
}

// ---------------------------------------------------------------------------
// 3) collect：所有區段的 enhanced+clipped 折線（＋字框 outline）
// ---------------------------------------------------------------------------

/**
 * 收集匯出折線。與 drawRegionLayer 同管線（buildTangleOriented →
 * applyEnhancers），再取樣裁切到區段可見區。
 *
 * @param {object} ctx - {regions, mappedContours, params, tileSize, tileMargin,
 *                        baseLineWidth, includeOutline}
 * @returns {{strokes: Array<Array<[x,y]>>, outline: Array<Array<[x,y]>>}}
 */
export function collectExportPaths(ctx) {
  const {regions, mappedContours, params, tileSize,
         baseLineWidth = 1, includeOutline = true,
         paramsToOpts} = ctx;
  const strokes = [];
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
    for (const spec of specs) {
      for (const pl of flattenSpec(spec)) {
        for (const seg of clipPolyline(pl, region, mappedContours)) {
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
  return {strokes, outline};
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
 * SVG 匯出（mm 尺寸；5bt 契約：width = viewBox 跨度 mm）。字框輪廓較粗、
 * 圖樣較細。填色形狀已在 flatten 輪廓化，這裡一律 stroke。
 */
export function pathsToSvg(paths, opts = {}) {
  const {tileSize, tileMm, strokeMm = 0.3, outlineMm = 0.5} = opts;
  const sx = tileMm / tileSize, sy = tileMm / tileSize;
  const w = fmt(tileMm), h = fmt(tileMm);
  const lines = [];
  lines.push('<?xml version="1.0" encoding="UTF-8"?>');
  lines.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}mm" height="${h}mm" ` +
             `viewBox="0 0 ${w} ${h}">`);
  lines.push('  <g fill="none" stroke="#000" stroke-linecap="round" stroke-linejoin="round">');
  if (paths.outline && paths.outline.length) {
    lines.push(`    <g stroke-width="${outlineMm}" data-layer="outline">`);
    for (const seg of paths.outline)
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
  out.push("");
  out.push("; --- epilogue ---");
  out.push(`${penUp} ; ensure pen up`);
  out.push(`G0 X${fmt(ox)} Y${fmt(oy)} F${travel} ; return home`);
  out.push("; done");
  return out.join("\n") + "\n";
}
