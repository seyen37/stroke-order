// Phase 5dj-4 — Node tests：禪繞延伸效果向量匯出（SVG / G-code）.
//
// Run: node --test tests/test_zentangle_exporters.mjs

import test from "node:test";
import assert from "node:assert/strict";

import {
  SPEC_LINE, SPEC_CURVE, SPEC_S_SHAPE, SPEC_ORB, SPEC_DOT,
  SPEC_POLYLINE, SPEC_TRI,
} from "../src/stroke_order/web/static/zentangle/tangle.mjs";
import {
  TILE_MM, flattenSpec, clipPolyline, collectExportPaths,
  pathsToSvg, pathsToGcode,
} from "../src/stroke_order/web/static/zentangle/exporters.mjs";
import {paramsToOpts} from "../src/stroke_order/web/static/zentangle/enhancers.mjs";

// ---------------------------------------------------------------------------
// flatten
// ---------------------------------------------------------------------------

test("flattenSpec：line/curve/s_shape/polyline 開放折線", () => {
  assert.equal(flattenSpec({type: SPEC_LINE, x1:0,y1:0,x2:10,y2:0})[0].closed, false);
  assert.ok(flattenSpec({type: SPEC_CURVE, x1:0,y1:0,cx:5,cy:5,x2:10,y2:0})[0].points.length > 2);
  assert.ok(flattenSpec({type: SPEC_S_SHAPE, x1:0,y1:0,x2:20,y2:0})[0].points.length > 4);
  const pl = flattenSpec({type: SPEC_POLYLINE, points:[[0,0],[1,1],[2,0]]})[0];
  assert.deepEqual(pl.points, [[0,0],[1,1],[2,0]]);
});

test("flattenSpec：完整 orb 閉合、弧開放", () => {
  assert.equal(flattenSpec({type: SPEC_ORB, cx:0,cy:0,r:10})[0].closed, true);
  assert.equal(
    flattenSpec({type: SPEC_ORB, cx:0,cy:0,r:10,startAngle:0,endAngle:1})[0].closed,
    false);
});

test("flattenSpec：dot/tri 輪廓化為閉合折線", () => {
  const dot = flattenSpec({type: SPEC_DOT, cx:5,cy:5,r:2})[0];
  assert.equal(dot.closed, true);
  assert.ok(dot.points.length >= 6, "點輪廓化成小圓周");
  const tri = flattenSpec({type: SPEC_TRI, points:[[0,0],[10,0],[0,10]]})[0];
  assert.equal(tri.closed, true);
  assert.equal(tri.points.length, 3);
});

// ---------------------------------------------------------------------------
// clip（取樣裁切）
// ---------------------------------------------------------------------------

test("clipPolyline：bg 區段——字形外留、字形內剪掉", () => {
  // 字形＝中央方塊 [40,60]²；區段＝整塊 bg [0,100]²。
  const glyph = [[[40,40],[60,40],[60,60],[40,60]]];
  const region = {kind:"bg", band:{x:0,y:0,w:100,h:100}};
  // 一條水平線 y=50 從 x=0 到 100，穿過字形中段。
  const pl = {points:[[0,50],[100,50]], closed:false};
  const segs = clipPolyline(pl, region, glyph, {step:2});
  // 應斷成兩段（左段 x<40、右段 x>60），字形內段被剪。
  assert.ok(segs.length >= 2, `bg 裁切應斷成 ≥2 段，得 ${segs.length}`);
  // 每段的點都在字形外（x<40 或 x>60）。
  for (const seg of segs)
    for (const [x] of seg)
      assert.ok(x <= 41 || x >= 59, `裁切後點 x=${x} 應在字形外`);
});

test("clipPolyline：glyph 區段——字形內留、外剪掉", () => {
  const glyph = [[[40,40],[60,40],[60,60],[40,60]]];
  const region = {kind:"glyph", band:{x:0,y:0,w:100,h:100}};
  const pl = {points:[[0,50],[100,50]], closed:false};
  const segs = clipPolyline(pl, region, glyph, {step:2});
  // 只留字形內 [40,60] 一段。
  assert.equal(segs.length, 1);
  for (const [x] of segs[0])
    assert.ok(x >= 39 && x <= 61, `glyph 裁切點 x=${x} 應在字形內`);
});

test("clipPolyline：band 也限制（超出 band 剪掉）", () => {
  const region = {kind:"bg", band:{x:0,y:0,w:50,h:100}};  // 只到 x=50
  const pl = {points:[[0,20],[100,20]], closed:false};
  const segs = clipPolyline(pl, region, null, {step:2});
  assert.equal(segs.length, 1);
  for (const [x] of segs[0]) assert.ok(x <= 51, `超出 band 應剪，x=${x}`);
});

// ---------------------------------------------------------------------------
// collect + emit
// ---------------------------------------------------------------------------

function sampleCtx() {
  const glyph = [[[30,30],[70,30],[70,70],[30,70]]];  // 方塊字形
  return {
    regions: [
      {id:"r0", kind:"glyph", band:{x:30,y:30,w:40,h:40},
       tangle:"line", orientation:"up", enhancers:{}},
    ],
    mappedContours: glyph,
    params: {}, tileSize: 100, tileMm: 90, baseLineWidth: 1,
    paramsToOpts,
  };
}

test("collectExportPaths：回傳 strokes + outline，strokes 裁在字形內", () => {
  const {strokes, outline} = collectExportPaths(sampleCtx());
  assert.ok(strokes.length > 0, "有圖樣折線");
  assert.ok(outline.length > 0, "有字框輪廓");
  // 圖樣點都在字形方塊 [30,70] 附近（裁切生效）。
  for (const seg of strokes)
    for (const [x, y] of seg)
      assert.ok(x >= 28 && x <= 72 && y >= 28 && y <= 72,
                `裁切後圖樣點 (${x},${y}) 應在字形內`);
});

test("collectExportPaths：enhancers 生效（aura 增加折線數）", () => {
  const base = collectExportPaths(sampleCtx());
  const ctx2 = sampleCtx();
  ctx2.regions[0].enhancers = {aura: true};
  const withAura = collectExportPaths(ctx2);
  assert.ok(withAura.strokes.length > base.strokes.length,
            "aura 後折線變多");
});

test("collectExportPaths：留白區段（無 tangle）跳過", () => {
  const ctx = sampleCtx();
  ctx.regions[0].tangle = null;
  assert.equal(collectExportPaths(ctx).strokes.length, 0);
});

test("pathsToSvg：mm 尺寸、width=viewBox 跨度、含兩層", () => {
  const paths = {strokes: [[[10,10],[90,10]]], outline: [[[0,0],[100,0],[100,100],[0,100],[0,0]]]};
  const svg = pathsToSvg(paths, {tileSize:100, tileMm:90});
  assert.match(svg, /width="90mm" height="90mm"/);
  assert.match(svg, /viewBox="0 0 90 90"/);
  assert.match(svg, /data-layer="outline"/);
  assert.match(svg, /data-layer="tangle"/);
  assert.match(svg, /<polyline/);
});

test("pathsToGcode：專案慣例（G21/G90、M3 S90/M5、flip_y、home）", () => {
  const paths = {strokes: [[[0,0],[100,0]]], outline: []};
  const g = pathsToGcode(paths, {tileSize:100, tileMm:90});
  assert.match(g, /G21 ; mm/);
  assert.match(g, /G90 ; absolute/);
  assert.match(g, /M3 S90/);
  assert.match(g, /M5/);
  assert.match(g, /G0 X10 Y10 F6000 ; home/);
  // flip_y：tile y=0 → 機器 Y = oy + (100-0)*0.9 = 10 + 90 = 100。
  assert.match(g, /Y100/);
});

test("pathsToGcode：每折線 = 移動→落筆→G1 串→抬筆", () => {
  const paths = {strokes: [[[0,0],[50,0],[50,50]]], outline: []};
  const g = pathsToGcode(paths, {tileSize:100, tileMm:100}).split("\n");
  const iDown = g.findIndex((l) => l.includes("M3 S90"));
  const iUp = g.findIndex((l, k) => k > iDown && l === "M5");
  assert.ok(iDown >= 0 && iUp > iDown, "有落筆再抬筆");
  const g1 = g.filter((l) => l.startsWith("G1 ")).length;
  assert.ok(g1 >= 2, `折線 3 點 → ≥2 G1，得 ${g1}`);
});

test("TILE_MM 三檔存在", () => {
  assert.equal(TILE_MM.bijou, 50);
  assert.equal(TILE_MM.standard, 90);
  assert.equal(TILE_MM.apprentice, 135);
});
