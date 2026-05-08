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
  applyCurveModeToPoint,
  applyCurveModeToSpec,
  applyCurveModeToSpecs,
  isValidCurveMode,
  VALID_CURVE_MODES,
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

// ---------- 6z-5b applyCurveModeToPoint ----------

test("applyCurveModeToPoint: null mode → identity", () => {
  const [x, y] = applyCurveModeToPoint(50, 30, 100, 100, null, 0.5, 45);
  assert.equal(x, 50);
  assert.equal(y, 30);
});

test("applyCurveModeToPoint: 0 degree → identity", () => {
  const [x, y] = applyCurveModeToPoint(50, 30, 100, 100, "high-mid", 0, 45);
  assert.equal(x, 50);
  assert.equal(y, 30);
});

test("applyCurveModeToPoint: 0 unit_scale → identity (defensive)", () => {
  const [x, y] = applyCurveModeToPoint(50, 30, 100, 100, "high-mid", 0.5, 0);
  assert.equal(x, 50);
  assert.equal(y, 30);
});

test("applyCurveModeToPoint: high-mid lifts central column maximally", () => {
  // Point at unit center (dx = 0) → curve = 1 - 0² = 1 → max y-lift
  // y' = 100 - 1 * 1 * 45 * 0.5 = 100 - 22.5 = 77.5 (Y-down: smaller = higher)
  const [x, y] = applyCurveModeToPoint(100, 100, 100, 100, "high-mid", 1, 45);
  assert.equal(x, 100);
  assert.ok(approxEq(y, 77.5));
});

test("applyCurveModeToPoint: high-mid leaves edges unchanged (curve=0)", () => {
  // Point at |dx| = unit_scale → tx = ±1 → curve = 0 → y unchanged
  const [x, y] = applyCurveModeToPoint(145, 100, 100, 100, "high-mid", 1, 45);
  assert.equal(x, 145);
  assert.ok(approxEq(y, 100));
});

test("applyCurveModeToPoint: high-mid mid-distance gives mid-curve", () => {
  // dx = 22.5 (half unit_scale) → tx = 0.5 → curve = 1 - 0.25 = 0.75
  // y' = 100 - 0.75 * 1 * 45 * 0.5 = 100 - 16.875 = 83.125
  const [x, y] = applyCurveModeToPoint(122.5, 100, 100, 100, "high-mid", 1, 45);
  assert.ok(approxEq(y, 83.125));
});

test("applyCurveModeToPoint: high-sides is INVERSE of high-mid (1 - curve)", () => {
  // At center: high-mid = 1 (max), high-sides = 0 (no effect)
  const [, yHM] = applyCurveModeToPoint(100, 100, 100, 100, "high-mid", 1, 45);
  const [, yHS] = applyCurveModeToPoint(100, 100, 100, 100, "high-sides", 1, 45);
  assert.ok(yHM < 100);   // pulled up
  assert.ok(approxEq(yHS, 100));  // unchanged at center
});

test("applyCurveModeToPoint: left-high lifts left edge maximally", () => {
  // Point at far left: tx = -1 → curve = (1 - (-1))/2 = 1 → max lift
  const [, y] = applyCurveModeToPoint(55, 100, 100, 100, "left-high", 1, 45);
  // y' = 100 - 1 * 1 * 45 * 0.5 = 77.5
  assert.ok(approxEq(y, 77.5));
});

test("applyCurveModeToPoint: right-high lifts right edge maximally", () => {
  const [, y] = applyCurveModeToPoint(145, 100, 100, 100, "right-high", 1, 45);
  assert.ok(approxEq(y, 77.5));
});

test("applyCurveModeToPoint: x is never changed (curve is y-shear only)", () => {
  for (const mode of VALID_CURVE_MODES) {
    const [x] = applyCurveModeToPoint(123, 87, 100, 100, mode, 0.5, 45);
    assert.equal(x, 123, `mode=${mode} x changed`);
  }
});

test("applyCurveModeToPoint: clamps |dx/us| > 1 (defensive)", () => {
  // Point way outside unit_scale (dx=200, us=45 → tx clamped to 1)
  const [, y] = applyCurveModeToPoint(300, 100, 100, 100, "high-mid", 1, 45);
  // tx clamped to 1 → curve = 0 → y unchanged
  assert.ok(approxEq(y, 100));
});

// ---------- applyCurveModeToSpec ----------

test("applyCurveModeToSpec: ORB transforms center, preserves r", () => {
  const spec = {type: SPEC_ORB, cx: 100, cy: 100, r: 10};
  const out = applyCurveModeToSpec(spec, 100, 100, "high-mid", 1, 45);
  assert.ok(approxEq(out.cx, 100));
  assert.ok(approxEq(out.cy, 77.5));
  assert.equal(out.r, 10);  // r unchanged for curve mode
});

test("applyCurveModeToSpec: LINE transforms both endpoints", () => {
  const spec = {type: SPEC_LINE, x1: 90, y1: 100, x2: 110, y2: 100};
  const out = applyCurveModeToSpec(spec, 100, 100, "high-mid", 1, 45);
  // x1=90: tx=-10/45=-0.222, curve=1-0.0494=0.9506, y'=100-0.9506*45*0.5=78.6
  assert.ok(approxEq(out.y1, 100 - (1 - (10 / 45) ** 2) * 45 * 0.5));
});

test("applyCurveModeToSpec: null mode returns same ref", () => {
  const spec = {type: SPEC_DOT, cx: 50, cy: 50, r: 2};
  const out = applyCurveModeToSpec(spec, 100, 100, null, 1, 45);
  assert.equal(out, spec);
});

// ---------- applyCurveModeToSpecs ----------

test("applyCurveModeToSpecs: maps each spec independently", () => {
  const specs = [
    {type: SPEC_DOT, cx: 100, cy: 100, r: 2},
    {type: SPEC_DOT, cx: 145, cy: 100, r: 2},  // edge, unchanged
  ];
  const out = applyCurveModeToSpecs(specs, 100, 100, "high-mid", 1, 45);
  assert.ok(approxEq(out[0].cy, 77.5));
  assert.ok(approxEq(out[1].cy, 100));
});

test("applyCurveModeToSpecs: empty / null guard", () => {
  assert.deepEqual(applyCurveModeToSpecs([], 0, 0, "high-mid", 1, 45), []);
  assert.deepEqual(applyCurveModeToSpecs(null, 0, 0, "high-mid", 1, 45), []);
});

// ---------- isValidCurveMode / VALID_CURVE_MODES ----------

test("isValidCurveMode: 4 valid + null", () => {
  assert.ok(isValidCurveMode(null));
  for (const m of VALID_CURVE_MODES) {
    assert.ok(isValidCurveMode(m), `mode=${m} should be valid`);
  }
});

test("isValidCurveMode: invalid", () => {
  assert.equal(isValidCurveMode("middle-low"), false);
  assert.equal(isValidCurveMode(""), false);
  assert.equal(isValidCurveMode(undefined), false);
});

test("VALID_CURVE_MODES: order matches v0.3 §4.1 list", () => {
  assert.deepEqual(VALID_CURVE_MODES, [
    "high-mid",
    "high-sides",
    "left-high",
    "right-high",
  ]);
});
