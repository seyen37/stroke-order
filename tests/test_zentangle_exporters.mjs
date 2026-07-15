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
  pathsToSvg, pathsToGcode, buildClipEdges,
  scanlineFill, pathsToDxf, layersToDxf, DXF_LAYER_COLORS,
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

// ---------------------------------------------------------------------------
// 5dj-5 — 精確 even-odd 真裁切（vs 取樣近似）
// ---------------------------------------------------------------------------

test("5dj-5: 裁切邊界精確落在字形邊上（非 px 級近似）", () => {
  // 字形＝方塊 [40,60]²；glyph 區段全 band。水平線 y=50 穿過。
  const glyph = [[[40,40],[60,40],[60,60],[40,60]]];
  const region = {kind:"glyph", band:{x:0,y:0,w:100,h:100}};
  const pl = {points:[[0,50],[100,50]], closed:false};
  const segs = clipPolyline(pl, region, glyph);
  assert.equal(segs.length, 1, "字形內恰一段");
  const seg = segs[0];
  const x0 = seg[0][0], x1 = seg[seg.length-1][0];
  // 精確：端點恰在 x=40 / x=60（取樣近似會有 ±step 誤差）。
  assert.ok(Math.abs(x0 - 40) < 1e-6, `左界精確=40，得 ${x0}`);
  assert.ok(Math.abs(x1 - 60) < 1e-6, `右界精確=60，得 ${x1}`);
});

test("5dj-5: bg 裁切——字形兩側精確斷點", () => {
  const glyph = [[[40,40],[60,40],[60,60],[40,60]]];
  const region = {kind:"bg", band:{x:0,y:0,w:100,h:100}};
  const pl = {points:[[0,50],[100,50]], closed:false};
  const segs = clipPolyline(pl, region, glyph);
  assert.equal(segs.length, 2, "字形兩側各一段");
  // 左段 [0,40]、右段 [60,100]，斷點精確。
  const left = segs.find((s) => s[0][0] < 5);
  const right = segs.find((s) => s[0][0] > 55);
  assert.ok(Math.abs(left[left.length-1][0] - 40) < 1e-6, "左段止於 x=40");
  assert.ok(Math.abs(right[0][0] - 60) < 1e-6, "右段起於 x=60");
});

test("5dj-5: 跨多條字形邊仍在內＝合併成一段（不碎裂）", () => {
  // 兩個相鄰方塊拼成長條 [20,80]×[40,60]（共邊 x=50）。
  const glyph = [[[20,40],[50,40],[50,60],[20,60]],
                 [[50,40],[80,40],[80,60],[50,60]]];
  const region = {kind:"glyph", band:{x:0,y:0,w:100,h:100}};
  const pl = {points:[[0,50],[100,50]], closed:false};
  const segs = clipPolyline(pl, region, glyph);
  // 穿過 x=50 共邊但整段都在字形內 → 應是一整段 [20,80]，不碎成兩段。
  assert.equal(segs.length, 1, `應合併成一段，得 ${segs.length}`);
  assert.ok(Math.abs(segs[0][0][0] - 20) < 1e-6);
  assert.ok(Math.abs(segs[0][segs[0].length-1][0] - 80) < 1e-6);
});

test("5dj-5: 5df-4 切分區段用 poly 邊界（非 band 矩形）", () => {
  // 三角形切分區段（poly）；一條線穿過，裁切用三角形邊界。
  const region = {kind:"bg",
                  band:{x:0,y:0,w:100,h:100},
                  poly:[[10,10],[90,10],[10,90]]};   // 直角三角
  const pl = {points:[[0,20],[100,20]], closed:false};
  const segs = clipPolyline(pl, region, null);
  assert.equal(segs.length, 1);
  // y=20 與三角形斜邊 x+y=100... 斜邊 (90,10)-(10,90): x+y=100。y=20→x=80。
  // 左界＝三角左邊 x=10；右界＝斜邊 x=80。
  assert.ok(Math.abs(segs[0][0][0] - 10) < 1e-6, "左界 x=10");
  assert.ok(Math.abs(segs[0][segs[0].length-1][0] - 80) < 1e-6, "斜邊界 x=80");
});

test("5dj-5: buildClipEdges = 區段邊 + 字形邊", () => {
  const glyph = [[[40,40],[60,40],[60,60],[40,60]]];  // 4 邊
  const region = {kind:"glyph", band:{x:0,y:0,w:100,h:100}};  // 4 邊
  const edges = buildClipEdges(region, glyph);
  assert.equal(edges.length, 8, "band 4 + 字形 4 = 8 邊");
});

test("5dj-5: 完整圓（閉合折線）裁切在字形內＝閉合處也正確", () => {
  const glyph = [[[10,10],[90,10],[90,90],[10,90]]];   // 大方塊含整個圓
  const region = {kind:"glyph", band:{x:0,y:0,w:100,h:100}};
  // 圓心 (50,50) r=20 完全在字形內 → 裁切後應保留（閉合展開後一整段）。
  const circle = flattenSpec({type:"orb", cx:50, cy:50, r:20})[0];
  const segs = clipPolyline(circle, region, glyph);
  assert.ok(segs.length >= 1, "圓在字形內應保留");
  const nPts = segs.reduce((a, s) => a + s.length, 0);
  assert.ok(nPts >= circle.points.length - 1, "點數大致守恆（全在內）");
});

// ---------------------------------------------------------------------------
// 5dk — 雷雕掃描填充 / 填色模式 / DXF 三層
// ---------------------------------------------------------------------------

test("5dk: scanlineFill 方塊 → 水平線段填滿、間距正確", () => {
  const sq = [[0,0],[20,0],[20,20],[0,20]];
  const segs = scanlineFill(sq, 5);
  assert.ok(segs.length >= 3, `20 高 /5 間距 → ≥3 條，得 ${segs.length}`);
  for (const [[x0,y0],[x1,y1]] of segs) {
    assert.equal(y0, y1, "水平線");
    assert.ok(Math.abs(x0 - 0) < 1e-6 && Math.abs(x1 - 20) < 1e-6, "跨滿方塊寬");
  }
});

test("5dk: scanlineFill 三角形 → 線段寬度隨高度變化", () => {
  const tri = [[0,0],[20,0],[0,20]];  // 直角三角，上寬下窄
  const segs = scanlineFill(tri, 4);
  assert.ok(segs.length >= 2);
  // 靠近 y=0 的線段較長、靠近 y=20 較短。
  const widths = segs.map(([[x0],[x1]]) => x1 - x0);
  assert.ok(widths[0] > widths[widths.length-1], "上寬下窄");
});

test("5dk: scanlineFill 退化輸入回空", () => {
  assert.deepEqual(scanlineFill([[0,0],[1,1]], 5), []);   // <3 點
  assert.deepEqual(scanlineFill([[0,0],[9,0],[9,9]], 0), []);  // spacing 0
});

function fillCtx(fillMode) {
  // 字形＝大方塊；區段 glyph 內放 tangle 帶 rounding（產生 tri 填色形狀）。
  const glyph = [[[10,10],[90,10],[90,90],[10,90]]];
  return {
    regions: [{id:"r0", kind:"glyph", band:{x:10,y:10,w:80,h:80},
               tangle:"line", orientation:"up", enhancers:{rounding:true}}],
    mappedContours: glyph, params: {}, tileSize: 100, tileMm: 100,
    baseLineWidth: 1, paramsToOpts, fillMode, scanSpacingMm: 2,
  };
}

test("5dk: collectExportPaths 回 strokes/fills/outline 三欄", () => {
  const r = collectExportPaths(fillCtx("outline"));
  assert.ok("strokes" in r && "fills" in r && "outline" in r);
});

test("5dk: fillMode scan → fills 有掃描線、outline 模式 fills 空", () => {
  const scan = collectExportPaths(fillCtx("scan"));
  const outline = collectExportPaths(fillCtx("outline"));
  assert.ok(scan.fills.length > 0, "scan 模式產生掃描填充線");
  assert.equal(outline.fills.length, 0, "outline 模式無 fills（輪廓歸 strokes）");
});

test("5dk: fillMode skip → 填色形狀完全略過（fills 空、strokes 較少）", () => {
  const skip = collectExportPaths(fillCtx("skip"));
  const outline = collectExportPaths(fillCtx("outline"));
  assert.equal(skip.fills.length, 0);
  assert.ok(skip.strokes.length <= outline.strokes.length,
            "skip 略過填色輪廓 → strokes ≤ outline 模式");
});

test("5dk: layersToDxf R12 結構（LAYER table + POLYLINE + flip_y）", () => {
  const dxf = layersToDxf([
    {name:"CUT", polys:[{points:[[0,0],[10,0],[10,10]], closed:true}]},
    {name:"ENGRAVE", polys:[{points:[[2,2],[8,8]], closed:false}]},
  ]);
  assert.match(dxf, /AC1009/, "R12");
  assert.match(dxf, /LAYER\n2\nCUT/, "CUT 層");
  assert.match(dxf, /POLYLINE\n\s*8\nCUT/, "CUT 圖元");
  assert.match(dxf, /EOF/);
  // flip_y：y=10 → DXF Y=-10。
  assert.match(dxf, /20\n-10/, "flip_y 生效");
});

test("5dk: DXF_LAYER_COLORS 三層", () => {
  assert.equal(DXF_LAYER_COLORS.CUT, 1);
  assert.equal(DXF_LAYER_COLORS.ENGRAVE, 7);
  assert.equal(DXF_LAYER_COLORS.WRITE, 5);
});

test("5dk: pathsToDxf 三層——CUT=字框、ENGRAVE=線+填、WRITE=僅線", () => {
  const paths = {
    strokes: [[[10,10],[90,10]]],
    fills: [[[20,20],[80,20]]],
    outline: [[[0,0],[100,0],[100,100],[0,100],[0,0]]],
  };
  const dxf = pathsToDxf(paths, {tileSize:100, tileMm:100});
  assert.match(dxf, /LAYER\n2\nCUT/);
  assert.match(dxf, /LAYER\n2\nENGRAVE/);
  assert.match(dxf, /LAYER\n2\nWRITE/);
  // ENGRAVE 含 strokes + fills（2 條 POLYLINE 在 ENGRAVE 層）。
  const engBlocks = (dxf.match(/POLYLINE\n\s*8\nENGRAVE/g) || []).length;
  assert.equal(engBlocks, 2, "ENGRAVE = 線 + 填 共 2");
  const wrBlocks = (dxf.match(/POLYLINE\n\s*8\nWRITE/g) || []).length;
  assert.equal(wrBlocks, 1, "WRITE = 僅線 1");
});

test("5dk: SVG/G-code 含 fills 層", () => {
  const paths = {strokes:[[[0,0],[10,0]]], fills:[[[2,2],[8,2]]], outline:[]};
  assert.match(pathsToSvg(paths, {tileSize:100, tileMm:90}), /data-layer="fill"/);
  assert.match(pathsToGcode(paths, {tileSize:100, tileMm:90}), /fill 掃描填充/);
});
