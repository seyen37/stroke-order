// Phase 5dj-1 — Node tests：iCSO 五大基本符號 + 延伸技法（enhancers）.
//
// Run: node --test tests/test_zentangle_enhancers.mjs

import test from "node:test";
import assert from "node:assert/strict";

import {
  TANGLES, TANGLE_CATEGORIES, listTangles, buildTangle, buildTangleOriented,
  SPEC_LINE, SPEC_CURVE, SPEC_S_SHAPE, SPEC_ORB, SPEC_DOT,
} from "../src/stroke_order/web/static/zentangle/tangle.mjs";
import {
  ENHANCERS, ENHANCER_LABELS,
  applyAura, applyWeighting, applyRounding,
  applyEnhancers, normalizeEnhancers, hasAnyEnhancer,
} from "../src/stroke_order/web/static/zentangle/enhancers.mjs";

const AREA = {x: 0, y: 0, w: 200, h: 200};
const BASIC_KEYS = ["dot", "line", "curve_c", "s_curve", "orb"];

// ---------------------------------------------------------------------------
// iCSO 五大基本符號
// ---------------------------------------------------------------------------

test("registry 有 5 個 basic 符號（iCSO）", () => {
  const basics = listTangles({category: "basic"});
  assert.equal(basics.length, 5);
  assert.deepEqual(basics.map((t) => t.key).sort(), BASIC_KEYS.slice().sort());
});

test("registry 有 8 個 classic 圖樣", () => {
  assert.equal(listTangles({category: "classic"}).length, 8);
});

test("listTangles() 不帶參數＝全部 13、且每項有 category", () => {
  const all = listTangles();
  assert.equal(all.length, 13);
  for (const t of all) {
    assert.ok(TANGLE_CATEGORIES.includes(t.category), `${t.key} category`);
  }
});

test("每個 basic 符號都能 build 出非空 spec 且型別合法", () => {
  const okTypes = new Set([SPEC_LINE, SPEC_CURVE, SPEC_S_SHAPE, SPEC_ORB, SPEC_DOT]);
  for (const key of BASIC_KEYS) {
    const specs = buildTangle(key, AREA);
    assert.ok(specs.length > 0, `${key} 應非空`);
    for (const s of specs) assert.ok(okTypes.has(s.type), `${key} spec type ${s.type}`);
  }
});

test("basic 符號 spec 全部落在 area 界內（含筆劃外伸）", () => {
  // 各筆劃的有效外伸半徑（用來擴張界限容忍）。
  for (const key of BASIC_KEYS) {
    for (const s of buildTangle(key, AREA)) {
      const pts = [];
      if (s.type === SPEC_ORB || s.type === SPEC_DOT) {
        const rr = s.r + 0.5;
        pts.push([s.cx - rr, s.cy - rr], [s.cx + rr, s.cy + rr]);
      } else {
        pts.push([s.x1, s.y1], [s.x2, s.y2]);
      }
      for (const [x, y] of pts) {
        assert.ok(x >= AREA.x - 1 && x <= AREA.x + AREA.w + 1 &&
                  y >= AREA.y - 1 && y <= AREA.y + AREA.h + 1,
                  `${key} 越界 (${x.toFixed(1)},${y.toFixed(1)})`);
      }
    }
  }
});

test("basic 符號都有 buildUnit（user-place）", () => {
  for (const key of BASIC_KEYS) {
    assert.equal(typeof TANGLES[key].buildUnit, "function", `${key}.buildUnit`);
    const u = TANGLES[key].buildUnit(50, 50, 40);
    assert.ok(Array.isArray(u) && u.length >= 1, `${key} unit 非空`);
  }
});

test("basic 符號吃 orientSpecs 四向不炸、點數守恆", () => {
  for (const key of BASIC_KEYS) {
    const up = buildTangleOriented(key, AREA, "medium", "up");
    for (const dir of ["right", "down", "left"]) {
      const rot = buildTangleOriented(key, AREA, "medium", dir);
      assert.equal(rot.length, up.length, `${key} ${dir} 點數守恆`);
    }
  }
});

// ---------------------------------------------------------------------------
// Aura
// ---------------------------------------------------------------------------

test("Aura：line 產生一條平行副本（法線平移 gap）", () => {
  const specs = [{type: SPEC_LINE, x1: 0, y1: 0, x2: 0, y2: 10}];  // 垂直線
  const out = applyAura(specs, {gap: 4, rings: 1});
  assert.equal(out.length, 2);              // 原 + 光環
  const aura = out[1];
  // 垂直線法線＝水平方向，x 平移 ±4。
  assert.ok(Math.abs(Math.abs(aura.x1) - 4) < 1e-9, "x 平移 gap");
  assert.equal(aura.y1, 0);
  assert.equal(aura.y2, 10);
});

test("Aura：orb 產生同心放大圈，rings 控制圈數", () => {
  const specs = [{type: SPEC_ORB, cx: 50, cy: 50, r: 10, fill: false}];
  const out = applyAura(specs, {gap: 3, rings: 2});
  assert.equal(out.length, 3);              // 原 + 2 圈
  assert.equal(out[1].r, 13);
  assert.equal(out[2].r, 16);
  assert.equal(out[1].fill, false);
});

test("Aura：dot 的光環＝外圈 orb（不填）", () => {
  const specs = [{type: SPEC_DOT, cx: 5, cy: 5, r: 2}];
  const out = applyAura(specs, {gap: 4, rings: 1});
  assert.equal(out.length, 2);
  assert.equal(out[1].type, SPEC_ORB);
  assert.equal(out[1].r, 6);
  assert.equal(out[1].fill, false);
});

test("Aura：不改輸入陣列", () => {
  const specs = [{type: SPEC_ORB, cx: 0, cy: 0, r: 5, fill: false}];
  const before = JSON.stringify(specs);
  applyAura(specs, {gap: 3, rings: 1});
  assert.equal(JSON.stringify(specs), before);
});

// ---------------------------------------------------------------------------
// Weighting
// ---------------------------------------------------------------------------

test("Weighting：stroke 類加 lw；填色 dot 不變", () => {
  const specs = [
    {type: SPEC_LINE, x1: 0, y1: 0, x2: 10, y2: 0},
    {type: SPEC_CURVE, x1: 0, y1: 0, cx: 5, cy: 5, x2: 10, y2: 0},
    {type: SPEC_DOT, cx: 3, cy: 3, r: 2},
  ];
  const out = applyWeighting(specs, {factor: 3, baseLineWidth: 1});
  assert.equal(out[0].lw, 3);
  assert.equal(out[1].lw, 3);
  assert.equal(out[2].lw, undefined, "填色 dot 不加 lw");
});

test("Weighting：填色 orb 不加 lw、描邊 orb 加", () => {
  const out = applyWeighting([
    {type: SPEC_ORB, cx: 0, cy: 0, r: 5, fill: true},
    {type: SPEC_ORB, cx: 0, cy: 0, r: 5, fill: false},
  ], {factor: 2});
  assert.equal(out[0].lw, undefined);
  assert.equal(out[1].lw, 2);
});

// ---------------------------------------------------------------------------
// Rounding
// ---------------------------------------------------------------------------

test("Rounding：stroke 端點放小黑圓、共點去重", () => {
  const specs = [
    {type: SPEC_LINE, x1: 0, y1: 0, x2: 10, y2: 0},
    {type: SPEC_LINE, x1: 10, y1: 0, x2: 10, y2: 10},  // 與前一條共用 (10,0)
  ];
  const out = applyRounding(specs, {r: 2});
  const dots = out.filter((s) => s.type === SPEC_DOT);
  // 端點 (0,0),(10,0),(10,10) 去重後＝3 個（(10,0) 共用只放一次）。
  assert.equal(dots.length, 3);
  for (const d of dots) assert.equal(d.r, 2);
});

test("Rounding：orb/dot 不產生端點（無 stroke 端點）", () => {
  const out = applyRounding([{type: SPEC_ORB, cx: 0, cy: 0, r: 5, fill: false}], {r: 2});
  assert.equal(out.filter((s) => s.type === SPEC_DOT).length, 0);
});

// ---------------------------------------------------------------------------
// 管線
// ---------------------------------------------------------------------------

test("ENHANCERS 有 3 個、都有 label", () => {
  assert.deepEqual(ENHANCERS, ["aura", "weighting", "rounding"]);
  for (const k of ENHANCERS) assert.ok(ENHANCER_LABELS[k], `${k} label`);
});

test("normalizeEnhancers 缺欄補 false", () => {
  assert.deepEqual(normalizeEnhancers(null),
    {aura: false, weighting: false, rounding: false});
  assert.deepEqual(normalizeEnhancers({aura: true}),
    {aura: true, weighting: false, rounding: false});
});

test("hasAnyEnhancer 正確", () => {
  assert.equal(hasAnyEnhancer(null), false);
  assert.equal(hasAnyEnhancer({rounding: true}), true);
});

test("applyEnhancers：全關＝原樣（長度不變）", () => {
  const specs = buildTangle("orb", AREA);
  const out = applyEnhancers(specs, {});
  assert.equal(out.length, specs.length);
});

test("applyEnhancers：全開＝三技法都作用（比原多）", () => {
  const specs = [{type: SPEC_LINE, x1: 0, y1: 0, x2: 10, y2: 0}];
  const out = applyEnhancers(specs, {aura: true, weighting: true, rounding: true},
                             {gap: 3, factor: 2, r: 1.5});
  // weighting 給 lw、aura +1 平行線、rounding +2 端點圓 → 至少 4 spec。
  assert.ok(out.length >= 4, `全開後 ${out.length} specs`);
  assert.ok(out.some((s) => s.lw), "有加厚");
  assert.ok(out.filter((s) => s.type === SPEC_DOT).length >= 2, "有端點圓");
});

test("applyEnhancers：空輸入回空", () => {
  assert.deepEqual(applyEnhancers([], {aura: true}), []);
});
