// Phase 5df-2 — Node tests for regions.mjs（區段模型＋隨機填充）.
//
// Run: node --test tests/test_zentangle_regions.mjs

import test from "node:test";
import assert from "node:assert/strict";

import {
  pointInPolygon,
  polyBbox,
  groupContours,
  splitBandRect,
  computeGlyphRegions,
  computeBgRegions,
  assignRandomTangles,
  pickDensity,
  hitTestRegions,
} from "../src/stroke_order/web/static/zentangle/regions.mjs";
import {
  listTangles,
  buildTangleOriented,
  ORIENTATIONS,
} from "../src/stroke_order/web/static/zentangle/tangle.mjs";

// 決定性 rand：依序吐出固定值序列（用完循環）。
function seqRand(vals) {
  let i = 0;
  return () => vals[i++ % vals.length];
}

// 合成形狀先行（PRINCIPLES §8.5）：正方形 contour 產生器。
function square(x, y, size) {
  return [[x, y], [x + size, y], [x + size, y + size], [x, y + size]];
}

// ---------- pointInPolygon / polyBbox ----------

test("5df-2: pointInPolygon basic in/out", () => {
  const sq = square(10, 10, 100);
  assert.ok(pointInPolygon(60, 60, sq));
  assert.ok(!pointInPolygon(5, 60, sq));
  assert.ok(!pointInPolygon(200, 200, sq));
});

test("5df-2: polyBbox returns band-format rect", () => {
  const bb = polyBbox(square(10, 20, 100));
  assert.deepEqual(bb, {x: 10, y: 20, w: 100, h: 100});
  assert.equal(polyBbox([]), null);
});

// ---------- groupContours ----------

test("5df-2: groupContours 口-style（外框＋孔）→ 1 元件含 2 contour", () => {
  const contours = [square(0, 0, 200), square(50, 50, 100)];  // 外、孔
  const comps = groupContours(contours);
  assert.equal(comps.length, 1);
  assert.equal(comps[0].indices.length, 2);
  assert.equal(comps[0].indices[0], 0);        // 外輪廓領頭
  assert.deepEqual(comps[0].bbox, {x: 0, y: 0, w: 200, h: 200});
});

test("5df-2: groupContours 明-style（兩獨立元件各含孔）→ 2 元件", () => {
  const contours = [
    square(0, 0, 150),      // 左外
    square(30, 30, 90),     // 左孔
    square(200, 0, 150),    // 右外
    square(230, 30, 90),    // 右孔
  ];
  const comps = groupContours(contours);
  assert.equal(comps.length, 2);
  const byLead = Object.fromEntries(comps.map((c) => [c.indices[0], c]));
  assert.deepEqual(byLead[0].indices.sort(), [0, 1]);
  assert.deepEqual(byLead[2].indices.sort(), [2, 3]);
});

test("5df-2: groupContours 孔洞掛到最貼身的外輪廓", () => {
  // 大外框包住小外框（深度 2 ＝仍是「外」）情境不在字形資料出現，
  // 但孔要掛「包含它且 bbox 最小」的外——用兩個同時包含孔的外驗證。
  // 外 A(0,0,300) 包含 外 B?? — 改用：孔同時被兩層包含時掛內層。
  // 簡化為實際字形會出現的巢狀：外(0,0,300) > 孔(20,20,260) > 外(50,50,200) > 孔(80,80,140)
  const contours = [
    square(0, 0, 300),
    square(20, 20, 260),
    square(50, 50, 200),
    square(80, 80, 140),
  ];
  const comps = groupContours(contours);
  assert.equal(comps.length, 2);                 // 深度 0、2 是外
  const inner = comps.find((c) => c.indices[0] === 2);
  assert.ok(inner.indices.includes(3), "內層孔掛內層外輪廓");
});

// ---------- splitBandRect ----------

test("5df-2: splitBandRect 沿長軸切、恰好鋪滿、不重疊", () => {
  const rect = {x: 10, y: 20, w: 300, h: 100};   // 寬 → 垂直切
  const bands = splitBandRect(rect, 3);
  assert.equal(bands.length, 3);
  let edge = rect.x;
  for (const b of bands) {
    assert.ok(Math.abs(b.x - edge) < 1e-9, "帶首尾相接");
    assert.equal(b.y, rect.y);
    assert.equal(b.h, rect.h);
    edge = b.x + b.w;
  }
  assert.ok(Math.abs(edge - (rect.x + rect.w)) < 1e-9, "鋪滿到右緣");
  // 高瘦 rect → 水平切
  const tall = splitBandRect({x: 0, y: 0, w: 100, h: 300}, 2);
  assert.equal(tall[0].w, 100);
  assert.ok(tall[1].y > tall[0].y);
});

test("5df-2: splitBandRect n≤1 防禦 → 整塊 1 帶", () => {
  const rect = {x: 0, y: 0, w: 100, h: 50};
  assert.equal(splitBandRect(rect, 0).length, 1);
  assert.deepEqual(splitBandRect(rect, 1)[0], rect);
});

// ---------- computeGlyphRegions ----------

test("5df-2: computeGlyphRegions 帶都在元件 bbox 內（鐵則：界內）", () => {
  const contours = [square(50, 50, 300), square(120, 120, 160)];
  const regions = computeGlyphRegions(contours, {rand: seqRand([0.9])});
  assert.ok(regions.length >= 2 && regions.length <= 4);
  for (const r of regions) {
    assert.equal(r.kind, "glyph");
    assert.ok(r.band.x >= 50 - 1e-9 && r.band.x + r.band.w <= 350 + 1e-9);
    assert.ok(r.band.y >= 50 - 1e-9 && r.band.y + r.band.h <= 350 + 1e-9);
  }
});

test("5df-2: computeGlyphRegions rand 注入＝決定性帶數", () => {
  const contours = [square(0, 0, 400)];
  // rand=0.0 → wanted=2；rand=0.99 → wanted=4
  assert.equal(
    computeGlyphRegions(contours, {rand: seqRand([0.0])}).length, 2);
  assert.equal(
    computeGlyphRegions(contours, {rand: seqRand([0.99])}).length, 4);
});

test("5df-2: 極小元件（如點、頓筆）退成 1 帶不硬切", () => {
  const contours = [square(0, 0, 50)];           // long=50 < MIN_BAND_PX*2
  const regions = computeGlyphRegions(contours, {rand: seqRand([0.99])});
  assert.equal(regions.length, 1);
  assert.deepEqual(regions[0].band, {x: 0, y: 0, w: 50, h: 50});
});

test("5df-2: 多元件各自切帶、id 全域唯一", () => {
  const contours = [square(0, 0, 200), square(300, 0, 200)];
  const regions = computeGlyphRegions(contours, {rand: seqRand([0.5])});
  assert.equal(regions.length, 6);               // 3 帶 × 2 元件
  const ids = new Set(regions.map((r) => r.id));
  assert.equal(ids.size, regions.length);
});

// ---------- computeBgRegions ----------

test("5df-2: computeBgRegions 象限分支 → 4 塊、鋪滿內框", () => {
  const regions = computeBgRegions(600, 60, {rand: seqRand([0.1])});
  assert.equal(regions.length, 4);
  let area = 0;
  for (const r of regions) {
    assert.equal(r.kind, "bg");
    assert.ok(r.band.x >= 60 - 1e-9 && r.band.x + r.band.w <= 540 + 1e-9);
    assert.ok(r.band.y >= 60 - 1e-9 && r.band.y + r.band.h <= 540 + 1e-9);
    area += r.band.w * r.band.h;
  }
  assert.ok(Math.abs(area - 480 * 480) < 1e-6, "面積守恆＝不重疊不漏縫");
});

test("5df-2: computeBgRegions 帶分支 → 2~4 帶、方向由 rand 決定", () => {
  // rand: 0.9(→帶) , 0.99(→4 帶) , 0.1(→水平)
  const horiz = computeBgRegions(600, 60, {rand: seqRand([0.9, 0.99, 0.1])});
  assert.equal(horiz.length, 4);
  for (const r of horiz) assert.equal(r.band.w, 480);   // 橫向滿寬
  // rand: 0.9(→帶) , 0.0(→2 帶) , 0.9(→垂直)
  const vert = computeBgRegions(600, 60, {rand: seqRand([0.9, 0.0, 0.9])});
  assert.equal(vert.length, 2);
  for (const r of vert) assert.equal(r.band.h, 480);    // 縱向滿高
});

// ---------- assignRandomTangles ----------

test("5df-2: assignRandomTangles 指派合法 tangle＋朝向、不改輸入", () => {
  const keys = listTangles().map((t) => t.key);
  const base = computeBgRegions(600, 60, {rand: seqRand([0.1])});
  const out = assignRandomTangles(base, keys, {rand: seqRand([0.0, 0.3, 0.6, 0.9])});
  assert.equal(out.length, base.length);
  assert.equal(base[0].tangle, undefined, "輸入不被 mutate");
  for (const r of out) {
    assert.ok(keys.includes(r.tangle), r.tangle);
    assert.ok(ORIENTATIONS.includes(r.orientation), r.orientation);
  }
  // 決定性：rand 固定 0 → 全部第一個 key + "up"
  const all0 = assignRandomTangles(base, keys, {rand: () => 0});
  for (const r of all0) {
    assert.equal(r.tangle, keys[0]);
    assert.equal(r.orientation, "up");
  }
});

test("5df-2: assignRandomTangles 空 key 清單 → throw", () => {
  assert.throws(() => assignRandomTangles([], [], {}), /non-empty/);
});

// ---------- pickDensity / hitTestRegions ----------

test("5df-2: pickDensity 窄帶 high、寬帶 medium", () => {
  assert.equal(pickDensity({x: 0, y: 0, w: 300, h: 80}), "high");
  assert.equal(pickDensity({x: 0, y: 0, w: 300, h: 150}), "medium");
});

test("5df-2: hitTestRegions 命中/落空/上層優先（5df-3 預留）", () => {
  const regions = [
    {id: "r0", kind: "bg", band: {x: 0, y: 0, w: 200, h: 200}},
    {id: "r1", kind: "glyph", band: {x: 50, y: 50, w: 100, h: 100}},
  ];
  assert.equal(hitTestRegions(regions, 100, 100).id, "r1");  // 疊區取後者
  assert.equal(hitTestRegions(regions, 10, 10).id, "r0");
  assert.equal(hitTestRegions(regions, 500, 500), null);
});

// ---------- 鐵則整合：區段帶餵 buildTangleOriented 全部界內 ----------

test("5df-2: 全 8 圖樣 × 4 朝向在典型區段帶內不越界（鐵則）", () => {
  const bands = [
    {x: 60, y: 60, w: 480, h: 120},    // bg 橫帶
    {x: 100, y: 100, w: 120, h: 320},  // glyph 縱帶
    {x: 200, y: 200, w: 90, h: 90},    // 小元件整塊
  ];
  for (const {key} of listTangles()) {
    for (const band of bands) {
      for (const orient of ORIENTATIONS) {
        const specs = buildTangleOriented(key, band, pickDensity(band), orient);
        for (const sp of specs) {
          const pts =
            sp.type === "line" || sp.type === "s_shape"
              ? [[sp.x1, sp.y1], [sp.x2, sp.y2]]
              : sp.type === "curve"
                ? [[sp.x1, sp.y1], [sp.cx, sp.cy], [sp.x2, sp.y2]]
                : [[sp.cx, sp.cy]];
          for (const [x, y] of pts) {
            assert.ok(
              x >= band.x - 1 && x <= band.x + band.w + 1,
              `${key}/${orient} x=${x} band=${JSON.stringify(band)}`);
            assert.ok(
              y >= band.y - 1 && y <= band.y + band.h + 1,
              `${key}/${orient} y=${y} band=${JSON.stringify(band)}`);
          }
        }
      }
    }
  }
});
