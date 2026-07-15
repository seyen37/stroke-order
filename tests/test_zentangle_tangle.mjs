// Phase 6z-3 — Node tests for tangle.mjs pure helpers.
//
// Run: node --test tests/test_zentangle_tangle.mjs

import test from "node:test";
import assert from "node:assert/strict";

import {
  SPEC_LINE,
  SPEC_CURVE,
  SPEC_S_SHAPE,
  SPEC_ORB,
  SPEC_DOT,
  TANGLES,
  ORIENTATIONS,
  buildCrescentMoon,
  buildFlorz,
  buildCrescentMoonUnit,
  buildFlorzUnit,
  buildTangle,
  buildTangleOriented,
  orientSpecs,
  listTangles,
} from "../src/stroke_order/web/static/zentangle/tangle.mjs";

const AREA = {x: 0, y: 0, w: 400, h: 400};

// ---------- 5df-1: 新六圖樣＋朝向 ----------

const NEW_KEYS = ["tipple", "bales", "printemps", "paradox",
                  "flux", "hollibaugh"];

function _pts(sp) {
  if (sp.type === "line" || sp.type === "s_shape") {
    return [[sp.x1, sp.y1], [sp.x2, sp.y2]];
  }
  if (sp.type === "curve") {
    return [[sp.x1, sp.y1], [sp.cx, sp.cy], [sp.x2, sp.y2]];
  }
  return [[sp.cx, sp.cy]];
}

test("5df-1: registry has six new classic keys", () => {
  // 5dj-1：registry 擴為 13（5 basic iCSO + 8 classic）；此鎖只驗
  //「6 個 5df-1 新圖樣仍在」，總數改由 classic 過濾器斷言。
  assert.equal(listTangles({category: "classic"}).length, 8);
  for (const k of NEW_KEYS) assert.ok(TANGLES[k], k);
});

test("5df-1: each new tangle fills area and stays in bounds", () => {
  for (const k of NEW_KEYS) {
    const specs = buildTangle(k, AREA, "medium");
    assert.ok(specs.length > 0, k);
    for (const sp of specs) {
      for (const [x, y] of _pts(sp)) {
        assert.ok(x >= AREA.x - 1 && x <= AREA.x + AREA.w + 1, `${k} x=${x}`);
        assert.ok(y >= AREA.y - 1 && y <= AREA.y + AREA.h + 1, `${k} y=${y}`);
      }
    }
  }
});

test("5df-1: orientSpecs rotates a line 90° about area centre", () => {
  const area = {x: 0, y: 0, w: 100, h: 100};
  const [o] = orientSpecs(
    [{type: "line", x1: 50, y1: 10, x2: 50, y2: 90}], "right", area);
  // (50,10)→(90,50)、(50,90)→(10,50)：垂直線轉成水平線
  assert.equal(Math.round(o.x1), 90);
  assert.equal(Math.round(o.y1), 50);
  assert.equal(Math.round(o.x2), 10);
  assert.equal(Math.round(o.y2), 50);
});

test("5df-1: orientSpecs shifts orb arc angles", () => {
  const area = {x: 0, y: 0, w: 100, h: 100};
  const [o] = orientSpecs(
    [{type: "orb", cx: 50, cy: 50, r: 10,
      startAngle: 0, endAngle: Math.PI}], "down", area);
  assert.ok(Math.abs(o.startAngle - Math.PI) < 1e-9);
  assert.ok(Math.abs(o.endAngle - 2 * Math.PI) < 1e-9);
});

test("5df-1: buildTangleOriented keeps non-square area in bounds", () => {
  const rect = {x: 10, y: 20, w: 300, h: 120};   // 寬扁區域
  for (const orient of ORIENTATIONS) {
    const specs = buildTangleOriented("bales", rect, "medium", orient);
    assert.ok(specs.length > 0, orient);
    for (const sp of specs) {
      for (const [x, y] of _pts(sp)) {
        assert.ok(x >= rect.x - 1 && x <= rect.x + rect.w + 1,
                  `${orient} x=${x}`);
        assert.ok(y >= rect.y - 1 && y <= rect.y + rect.h + 1,
                  `${orient} y=${y}`);
      }
    }
  }
});

// ---------- spec constants ----------

test("spec type constants are stable strings", () => {
  assert.equal(SPEC_LINE, "line");
  assert.equal(SPEC_CURVE, "curve");
  assert.equal(SPEC_S_SHAPE, "s_shape");
  assert.equal(SPEC_ORB, "orb");
  assert.equal(SPEC_DOT, "dot");
});

// ---------- buildCrescentMoon ----------

test("buildCrescentMoon: returns array of specs", () => {
  const specs = buildCrescentMoon(AREA, "medium");
  assert.ok(Array.isArray(specs));
  assert.ok(specs.length > 0);
});

test("buildCrescentMoon: every spec has type field", () => {
  const specs = buildCrescentMoon(AREA, "medium");
  for (const s of specs) {
    assert.ok(typeof s.type === "string");
    assert.ok([SPEC_ORB, SPEC_DOT].includes(s.type));
  }
});

test("buildCrescentMoon: orb specs carry geometry", () => {
  const specs = buildCrescentMoon(AREA, "medium");
  const orbs = specs.filter((s) => s.type === SPEC_ORB);
  assert.ok(orbs.length > 0);
  for (const o of orbs) {
    assert.ok(Number.isFinite(o.cx));
    assert.ok(Number.isFinite(o.cy));
    assert.ok(o.r > 0);
    assert.ok(typeof o.startAngle === "number");
    assert.ok(typeof o.endAngle === "number");
  }
});

test("buildCrescentMoon: density affects spec count", () => {
  const low = buildCrescentMoon(AREA, "low").length;
  const med = buildCrescentMoon(AREA, "medium").length;
  const high = buildCrescentMoon(AREA, "high").length;
  assert.ok(low < med, `low(${low}) should be < medium(${med})`);
  assert.ok(med < high, `medium(${med}) should be < high(${high})`);
});

test("buildCrescentMoon: empty area → []", () => {
  assert.deepEqual(buildCrescentMoon({x: 0, y: 0, w: 0, h: 0}, "medium"), []);
  assert.deepEqual(buildCrescentMoon(null, "medium"), []);
});

// ---------- buildFlorz ----------

test("buildFlorz: returns 4-petal pattern (orb count divisible by 4 + dot)", () => {
  const specs = buildFlorz(AREA, "medium");
  const orbs = specs.filter((s) => s.type === SPEC_ORB);
  const dots = specs.filter((s) => s.type === SPEC_DOT);
  // 4 petals per cell → orbs ≈ 4 × dots
  assert.ok(orbs.length === 4 * dots.length, `${orbs.length} orbs vs ${dots.length} dots`);
});

test("buildFlorz: empty area → []", () => {
  assert.deepEqual(buildFlorz({x: 0, y: 0, w: 0, h: 0}, "medium"), []);
});

test("buildFlorz: density scales count", () => {
  const low = buildFlorz(AREA, "low").length;
  const high = buildFlorz(AREA, "high").length;
  assert.ok(high > low);
});

// ---------- registry ----------

test("listTangles: matches registry (6z-3 MVP=2 → 5df-1=8)", () => {
  const list = listTangles();
  assert.equal(list.length, Object.keys(TANGLES).length);
  const keys = list.map((t) => t.key);
  assert.ok(keys.includes("crescent_moon"));
  assert.ok(keys.includes("florz"));
});

test("listTangles: each entry has key + label", () => {
  for (const t of listTangles()) {
    assert.ok(typeof t.key === "string" && t.key.length > 0);
    assert.ok(typeof t.label === "string" && t.label.length > 0);
  }
});

test("buildTangle: dispatches by key", () => {
  const cm = buildTangle("crescent_moon", AREA);
  const fz = buildTangle("florz", AREA);
  assert.ok(cm.length > 0);
  assert.ok(fz.length > 0);
  // Florz has 4 petals + 1 dot per cell = 5 specs/cell.
  // Crescent has 1 orb + 1 dot per cell = 2 specs/cell.
  // Same area + density → florz should have more specs.
  assert.ok(fz.length > cm.length);
});

test("buildTangle: unknown key throws", () => {
  assert.throws(() => buildTangle("not-a-tangle", AREA), /Unknown tangle/);
});

test("TANGLES registry shape: each has label + build()", () => {
  for (const [key, t] of Object.entries(TANGLES)) {
    assert.ok(typeof key === "string");
    assert.ok(typeof t.label === "string");
    assert.ok(typeof t.build === "function");
  }
});

// ---------- area edge cases ----------

test("build*: tiny area smaller than spacing returns 0 or few specs", () => {
  const tiny = {x: 0, y: 0, w: 30, h: 30};  // smaller than even high-density spacing
  const cm = buildCrescentMoon(tiny, "high");
  // High density has spacing 28; first iter (cy = 0+28, cx = 0+28) starts inside,
  // but next iter exceeds h. Expect at most ~2 cells worth.
  assert.ok(cm.length <= 4);
});

test("build*: rectangular area", () => {
  const rect = {x: 0, y: 0, w: 600, h: 200};
  const cm = buildCrescentMoon(rect, "medium");
  // More cells horizontally than vertically — at least the array isn't empty.
  assert.ok(cm.length > 0);
});

test("build*: offset area (non-zero origin)", () => {
  const offset = {x: 100, y: 100, w: 200, h: 200};
  const cm = buildCrescentMoon(offset, "medium");
  // All spec coords should be ≥ 100 (within or beyond the offset origin).
  for (const s of cm) {
    if (s.type === SPEC_ORB || s.type === SPEC_DOT) {
      assert.ok(s.cx >= 100);
      assert.ok(s.cy >= 100);
    }
  }
});

// ---------- 6z-3.5 single-unit builders ----------

test("buildCrescentMoonUnit: returns 2 specs (1 orb + 1 dot)", () => {
  const specs = buildCrescentMoonUnit(100, 100, 45);
  assert.equal(specs.length, 2);
  assert.equal(specs[0].type, SPEC_ORB);
  assert.equal(specs[1].type, SPEC_DOT);
});

test("buildCrescentMoonUnit: orb centered at given (cx, cy)", () => {
  const specs = buildCrescentMoonUnit(123, 456, 45);
  const orb = specs.find((s) => s.type === SPEC_ORB);
  assert.equal(orb.cx, 123);
  assert.equal(orb.cy, 456);
});

test("buildCrescentMoonUnit: dot is below the orb", () => {
  const specs = buildCrescentMoonUnit(100, 100, 45);
  const orb = specs.find((s) => s.type === SPEC_ORB);
  const dot = specs.find((s) => s.type === SPEC_DOT);
  assert.ok(dot.cy > orb.cy, "dot should be below orb on Y-down canvas");
});

test("buildCrescentMoonUnit: scale affects orb radius", () => {
  const small = buildCrescentMoonUnit(0, 0, 30);
  const large = buildCrescentMoonUnit(0, 0, 60);
  const smallR = small.find((s) => s.type === SPEC_ORB).r;
  const largeR = large.find((s) => s.type === SPEC_ORB).r;
  assert.ok(largeR > smallR);
});

test("buildFlorzUnit: returns 5 specs (4 orbs + 1 dot)", () => {
  const specs = buildFlorzUnit(100, 100, 45);
  assert.equal(specs.length, 5);
  const orbs = specs.filter((s) => s.type === SPEC_ORB);
  const dots = specs.filter((s) => s.type === SPEC_DOT);
  assert.equal(orbs.length, 4);
  assert.equal(dots.length, 1);
});

test("buildFlorzUnit: 4 petals symmetric around center", () => {
  const specs = buildFlorzUnit(100, 100, 45);
  const orbs = specs.filter((s) => s.type === SPEC_ORB);
  // Sum of (cx - center) and (cy - center) should be ≈ 0 (symmetric).
  const dxSum = orbs.reduce((acc, o) => acc + (o.cx - 100), 0);
  const dySum = orbs.reduce((acc, o) => acc + (o.cy - 100), 0);
  assert.ok(Math.abs(dxSum) < 1e-9);
  assert.ok(Math.abs(dySum) < 1e-9);
});

test("buildFlorzUnit: center dot at (cx, cy)", () => {
  const specs = buildFlorzUnit(50, 80, 45);
  const dot = specs.find((s) => s.type === SPEC_DOT);
  assert.equal(dot.cx, 50);
  assert.equal(dot.cy, 80);
});

test("TANGLES registry has buildUnit for both 6z-3 MVP tangles", () => {
  for (const key of ["crescent_moon", "florz"]) {
    assert.ok(typeof TANGLES[key].buildUnit === "function");
  }
});
