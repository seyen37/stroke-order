// Phase 6z-5a — Node tests for pseudo3d.mjs pure helpers.
//
// Run: node --test tests/test_zentangle_pseudo3d.mjs

import test from "node:test";
import assert from "node:assert/strict";

import {
  applyPseudo3DToPoint,
  applyPseudo3DToSpec,
  applyPseudo3DToSpecs,
  pseudo3DRadiusScale,
  isValidDepthDir,
  VALID_DEPTH_DIRS,
} from "../src/stroke_order/web/static/zentangle/pseudo3d.mjs";

import {
  SPEC_LINE,
  SPEC_ORB,
  SPEC_DOT,
} from "../src/stroke_order/web/static/zentangle/tangle.mjs";

const TOL = 1e-9;
function approxEq(a, b, tol = TOL) {
  return Math.abs(a - b) < tol;
}

// ---------- applyPseudo3DToPoint ----------

test("applyPseudo3DToPoint: null depth_dir → identity", () => {
  const [x, y] = applyPseudo3DToPoint(50, 30, 100, 100, null, 0.5);
  assert.equal(x, 50);
  assert.equal(y, 30);
});

test("applyPseudo3DToPoint: 0 degree → identity even with depth_dir set", () => {
  const [x, y] = applyPseudo3DToPoint(50, 30, 100, 100, "forward", 0);
  assert.equal(x, 50);
  assert.equal(y, 30);
});

test("applyPseudo3DToPoint: forward shrinks toward unit center", () => {
  const [x, y] = applyPseudo3DToPoint(120, 100, 100, 100, "forward", 1);
  // (120-100, 100-100) = (20, 0); k = 1 - 1*0.5 = 0.5
  // → (100 + 20*0.5, 100 + 0*0.5) = (110, 100)
  assert.ok(approxEq(x, 110));
  assert.ok(approxEq(y, 100));
});

test("applyPseudo3DToPoint: backward expands away from center", () => {
  const [x, y] = applyPseudo3DToPoint(120, 100, 100, 100, "backward", 1);
  // k = 1 + 1*0.5 = 1.5 → (100 + 20*1.5, 100) = (130, 100)
  assert.ok(approxEq(x, 130));
  assert.ok(approxEq(y, 100));
});

test("applyPseudo3DToPoint: left shears x by +dy*coef", () => {
  // Point above center (dy = -10, Y-down)
  const [x, y] = applyPseudo3DToPoint(50, 90, 100, 100, "left", 1);
  // x' = 50 + (-10) * 1 * 0.4 = 50 - 4 = 46
  assert.ok(approxEq(x, 46));
  assert.equal(y, 90);
});

test("applyPseudo3DToPoint: right shears x by -dy*coef", () => {
  const [x, y] = applyPseudo3DToPoint(50, 90, 100, 100, "right", 1);
  // x' = 50 - (-10) * 1 * 0.4 = 50 + 4 = 54
  assert.ok(approxEq(x, 54));
  assert.equal(y, 90);
});

test("applyPseudo3DToPoint: point AT center is unchanged for any direction", () => {
  for (const dir of ["forward", "backward", "left", "right"]) {
    const [x, y] = applyPseudo3DToPoint(100, 100, 100, 100, dir, 1);
    assert.ok(approxEq(x, 100), `dir=${dir} center x changed`);
    assert.ok(approxEq(y, 100), `dir=${dir} center y changed`);
  }
});

test("applyPseudo3DToPoint: forward + backward at same degree are inverse-ish", () => {
  // Apply forward then backward at same degree should NOT round-trip exactly
  // because k_fwd * k_bwd = (1-d/2)(1+d/2) = 1 - d²/4 ≠ 1.
  // But the symmetric property: forward by d and backward by d give scale
  // factors equidistant from 1 (1-d/2 and 1+d/2).
  const fwdScale = pseudo3DRadiusScale("forward", 0.5);
  const bwdScale = pseudo3DRadiusScale("backward", 0.5);
  assert.ok(approxEq(fwdScale, 0.75));
  assert.ok(approxEq(bwdScale, 1.25));
  assert.ok(approxEq(fwdScale + bwdScale, 2));  // symmetric around 1
});

// ---------- pseudo3DRadiusScale ----------

test("pseudo3DRadiusScale: identity cases", () => {
  assert.equal(pseudo3DRadiusScale(null, 0.5), 1);
  assert.equal(pseudo3DRadiusScale("forward", 0), 1);
  assert.equal(pseudo3DRadiusScale("forward", null), 1);
});

test("pseudo3DRadiusScale: left/right preserve r (shear is area-preserving 1D)", () => {
  assert.equal(pseudo3DRadiusScale("left", 1), 1);
  assert.equal(pseudo3DRadiusScale("right", 0.5), 1);
});

// ---------- applyPseudo3DToSpec — ORB/DOT scale r ----------

test("applyPseudo3DToSpec: ORB scales r for forward", () => {
  const spec = {type: SPEC_ORB, cx: 110, cy: 100, r: 10, startAngle: 0, endAngle: Math.PI};
  const out = applyPseudo3DToSpec(spec, 100, 100, "forward", 1);
  assert.ok(approxEq(out.r, 5));    // r * 0.5
  assert.ok(approxEq(out.cx, 105)); // pulled toward center
  assert.equal(out.startAngle, 0);  // pass-through preserved
  assert.equal(out.endAngle, Math.PI);
});

test("applyPseudo3DToSpec: DOT scales r for backward", () => {
  const spec = {type: SPEC_DOT, cx: 110, cy: 100, r: 2};
  const out = applyPseudo3DToSpec(spec, 100, 100, "backward", 1);
  assert.ok(approxEq(out.r, 3));    // r * 1.5
  assert.ok(approxEq(out.cx, 115)); // pushed away
});

test("applyPseudo3DToSpec: ORB r unchanged for left/right (shear)", () => {
  const spec = {type: SPEC_ORB, cx: 110, cy: 100, r: 10};
  const out = applyPseudo3DToSpec(spec, 100, 100, "left", 1);
  assert.equal(out.r, 10);
});

// ---------- applyPseudo3DToSpec — LINE ----------

test("applyPseudo3DToSpec: LINE transforms both endpoints", () => {
  const spec = {type: SPEC_LINE, x1: 90, y1: 100, x2: 110, y2: 100};
  const out = applyPseudo3DToSpec(spec, 100, 100, "forward", 1);
  assert.ok(approxEq(out.x1, 95));   // pulled toward center
  assert.ok(approxEq(out.x2, 105));
});

// ---------- applyPseudo3DToSpec — null/0 identity ----------

test("applyPseudo3DToSpec: null depth_dir → returns same spec", () => {
  const spec = {type: SPEC_ORB, cx: 110, cy: 100, r: 10};
  const out = applyPseudo3DToSpec(spec, 100, 100, null, 1);
  assert.equal(out, spec);  // strict equality (no copy made)
});

test("applyPseudo3DToSpec: 0 degree → returns same spec", () => {
  const spec = {type: SPEC_DOT, cx: 50, cy: 50, r: 2};
  const out = applyPseudo3DToSpec(spec, 100, 100, "forward", 0);
  assert.equal(out, spec);
});

// ---------- applyPseudo3DToSpecs (array convenience) ----------

test("applyPseudo3DToSpecs: maps each spec independently", () => {
  const specs = [
    {type: SPEC_DOT, cx: 110, cy: 100, r: 2},
    {type: SPEC_DOT, cx: 100, cy: 110, r: 2},
  ];
  const out = applyPseudo3DToSpecs(specs, 100, 100, "forward", 1);
  assert.equal(out.length, 2);
  assert.ok(approxEq(out[0].cx, 105));
  assert.ok(approxEq(out[1].cy, 105));
});

test("applyPseudo3DToSpecs: empty / null guard", () => {
  assert.deepEqual(applyPseudo3DToSpecs([], 0, 0, "forward", 1), []);
  assert.deepEqual(applyPseudo3DToSpecs(null, 0, 0, "forward", 1), []);
});

// ---------- isValidDepthDir / VALID_DEPTH_DIRS ----------

test("isValidDepthDir: 4 valid + null", () => {
  assert.ok(isValidDepthDir(null));
  assert.ok(isValidDepthDir("forward"));
  assert.ok(isValidDepthDir("backward"));
  assert.ok(isValidDepthDir("left"));
  assert.ok(isValidDepthDir("right"));
});

test("isValidDepthDir: invalid", () => {
  assert.equal(isValidDepthDir("up"), false);
  assert.equal(isValidDepthDir("down"), false);
  assert.equal(isValidDepthDir(""), false);
  assert.equal(isValidDepthDir(undefined), false);
});

test("VALID_DEPTH_DIRS: order is stable for UI dropdown / cycle", () => {
  assert.deepEqual(VALID_DEPTH_DIRS, ["forward", "backward", "left", "right"]);
});
