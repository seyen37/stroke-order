// Phase 6z-1C — Node tests for outline.mjs pure helpers.
//
// Run: node --test tests/test_zentangle_outline.mjs
//      (or `node --test tests/`)

import test from "node:test";
import assert from "node:assert/strict";

import {
  computeBbox,
  mapContourToTile,
  contoursAreClosed,
  rotateContours,
} from "../src/stroke_order/web/static/zentangle/outline.mjs";

// ---------- fixtures ----------

const SQUARE_CONTOURS = [
  [
    [0, 0],
    [100, 0],
    [100, 100],
    [0, 100],
  ],
];

const TWO_CONTOURS = [
  [[0, 0], [100, 0], [100, 100], [0, 100]],     // outer
  [[20, 20], [80, 20], [80, 80], [20, 80]],     // inner
];

// ---------- computeBbox ----------

test("computeBbox: empty input", () => {
  assert.equal(computeBbox([]), null);
  assert.equal(computeBbox(null), null);
  assert.equal(computeBbox(undefined), null);
});

test("computeBbox: single square contour", () => {
  const bb = computeBbox(SQUARE_CONTOURS);
  assert.deepEqual(bb, {
    minX: 0, minY: 0, maxX: 100, maxY: 100, width: 100, height: 100,
  });
});

test("computeBbox: two contours expands to outer", () => {
  const bb = computeBbox(TWO_CONTOURS);
  assert.equal(bb.minX, 0);
  assert.equal(bb.maxX, 100);
});

test("computeBbox: ignores non-finite points", () => {
  const bad = [[[NaN, 0], [50, 50], [Infinity, 99]]];
  const bb = computeBbox(bad);
  assert.equal(bb.minX, 50);
  assert.equal(bb.maxX, 50);
});

test("computeBbox: ignores malformed entries", () => {
  const mixed = [
    [[10, 10]],            // valid singleton
    "not-an-array",        // ignored
    [["x", "y"]],          // non-numeric ignored
    [[20, 20], [30, 30]],  // valid pair
  ];
  const bb = computeBbox(mixed);
  assert.equal(bb.minX, 10);
  assert.equal(bb.maxX, 30);
});

// ---------- mapContourToTile ----------

test("mapContourToTile: empty → []", () => {
  assert.deepEqual(mapContourToTile([], null, 600, 60), []);
});

test("mapContourToTile: square fills inner box", () => {
  const out = mapContourToTile(SQUARE_CONTOURS, null, 600, 60);
  assert.equal(out.length, 1);
  // Inner box: 60..540 (480px). Square is uniform → uses full 480 in both axes.
  // First point (0,0) → (60, 60); third point (100,100) → (540, 540).
  const poly = out[0];
  assert.equal(poly.length, 4);
  // Tolerate tiny float drift.
  const tol = 1e-6;
  assert.ok(Math.abs(poly[0][0] - 60) < tol);
  assert.ok(Math.abs(poly[0][1] - 60) < tol);
  assert.ok(Math.abs(poly[2][0] - 540) < tol);
  assert.ok(Math.abs(poly[2][1] - 540) < tol);
});

test("mapContourToTile: tall glyph centers horizontally", () => {
  // 50 wide × 100 tall — narrower than tall, so scaled to fit height.
  const tallContours = [[[0, 0], [50, 0], [50, 100], [0, 100]]];
  const out = mapContourToTile(tallContours, null, 600, 60);
  const poly = out[0];
  // Inner 480, scale = min(480/50, 480/100) = 4.8
  // Scaled: 50*4.8=240 wide, 100*4.8=480 tall
  // Horizontal center: 60 + (480-240)/2 = 60 + 120 = 180
  // Vertical center: 60 + (480-480)/2 = 60
  const tol = 1e-6;
  assert.ok(Math.abs(poly[0][0] - 180) < tol);  // left of glyph
  assert.ok(Math.abs(poly[0][1] - 60) < tol);   // top
  assert.ok(Math.abs(poly[1][0] - 420) < tol);  // right of glyph
});

test("mapContourToTile: rejects bad tileSize", () => {
  assert.throws(
    () => mapContourToTile(SQUARE_CONTOURS, null, 0, 0),
    /tileSize/
  );
  assert.throws(
    () => mapContourToTile(SQUARE_CONTOURS, null, -10, 0),
    /tileSize/
  );
});

test("mapContourToTile: rejects margin >= tileSize/2", () => {
  assert.throws(
    () => mapContourToTile(SQUARE_CONTOURS, null, 100, 50),
    /margin/
  );
  assert.throws(
    () => mapContourToTile(SQUARE_CONTOURS, null, 100, -1),
    /margin/
  );
});

test("mapContourToTile: degenerate single-point contour skipped (< 2 pts)", () => {
  const out = mapContourToTile([[[10, 10]]], null, 600, 60);
  assert.deepEqual(out, []);
});

test("mapContourToTile: two contours both mapped", () => {
  const out = mapContourToTile(TWO_CONTOURS, null, 600, 60);
  assert.equal(out.length, 2);
  assert.equal(out[0].length, 4);
  assert.equal(out[1].length, 4);
});

// ---------- contoursAreClosed ----------

test("contoursAreClosed: empty → false", () => {
  assert.equal(contoursAreClosed([]), false);
  assert.equal(contoursAreClosed(null), false);
});

test("contoursAreClosed: all >= 3 points → true", () => {
  assert.equal(contoursAreClosed(SQUARE_CONTOURS), true);
  assert.equal(contoursAreClosed(TWO_CONTOURS), true);
});

test("contoursAreClosed: any contour < 3 pts → false", () => {
  assert.equal(contoursAreClosed([[[0, 0], [1, 1]]]), false);
  assert.equal(
    contoursAreClosed([SQUARE_CONTOURS[0], [[0, 0], [1, 1]]]),
    false
  );
});

// ---------- rotateContours (6z-2a) ----------

const TOL = 1e-9;
function approxEqual(actual, expected, tol = TOL) {
  return Math.abs(actual - expected) < tol;
}

test("rotateContours: 0 degrees is identity", () => {
  const out = rotateContours(SQUARE_CONTOURS, 0, [50, 50]);
  assert.equal(out.length, 1);
  assert.equal(out[0].length, 4);
  for (let i = 0; i < 4; i++) {
    assert.ok(approxEqual(out[0][i][0], SQUARE_CONTOURS[0][i][0]));
    assert.ok(approxEqual(out[0][i][1], SQUARE_CONTOURS[0][i][1]));
  }
});

test("rotateContours: 90° clockwise about origin maps (1,0) → (0,1)", () => {
  const single = [[[1, 0]]];
  // Point lists < 3 are filtered by mapContourToTile, but rotateContours
  // accepts them — the function is generic. Wrap in larger poly to keep
  // it through the rotateContours filter (≥1 pt rotated).
  const triangle = [[[1, 0], [0, 0], [0, 1]]];
  const out = rotateContours(triangle, 90, [0, 0]);
  // (1,0) rotated 90° CW (Y-down) → (0, 1)
  assert.ok(approxEqual(out[0][0][0], 0), `expected x≈0, got ${out[0][0][0]}`);
  assert.ok(approxEqual(out[0][0][1], 1), `expected y≈1, got ${out[0][0][1]}`);
  // (0,1) → (-1, 0)
  assert.ok(approxEqual(out[0][2][0], -1), `expected x≈-1, got ${out[0][2][0]}`);
  assert.ok(approxEqual(out[0][2][1], 0), `expected y≈0, got ${out[0][2][1]}`);
});

test("rotateContours: 180° flips coordinates about pivot", () => {
  const tri = [[[10, 20], [30, 40], [50, 60]]];
  const out = rotateContours(tri, 180, [0, 0]);
  // 180° about origin → negate
  assert.ok(approxEqual(out[0][0][0], -10));
  assert.ok(approxEqual(out[0][0][1], -20));
  assert.ok(approxEqual(out[0][2][0], -50));
  assert.ok(approxEqual(out[0][2][1], -60));
});

test("rotateContours: 360° returns to original (within tolerance)", () => {
  const out = rotateContours(SQUARE_CONTOURS, 360, [50, 50]);
  for (let i = 0; i < 4; i++) {
    assert.ok(approxEqual(out[0][i][0], SQUARE_CONTOURS[0][i][0], 1e-6));
    assert.ok(approxEqual(out[0][i][1], SQUARE_CONTOURS[0][i][1], 1e-6));
  }
});

test("rotateContours: rotation about non-origin pivot keeps pivot fixed", () => {
  // The pivot itself should be unchanged for any angle.
  const triWithPivot = [[[100, 100], [50, 50], [0, 0]]];
  const out = rotateContours(triWithPivot, 47, [100, 100]);
  // First point IS the pivot → unchanged
  assert.ok(approxEqual(out[0][0][0], 100, 1e-9));
  assert.ok(approxEqual(out[0][0][1], 100, 1e-9));
});

test("rotateContours: -90° is inverse of +90°", () => {
  const tri = [[[5, 0], [10, 5], [0, 10]]];
  const forward = rotateContours(tri, 90, [0, 0]);
  const back = rotateContours(forward, -90, [0, 0]);
  for (let i = 0; i < 3; i++) {
    assert.ok(approxEqual(back[0][i][0], tri[0][i][0], 1e-9));
    assert.ok(approxEqual(back[0][i][1], tri[0][i][1], 1e-9));
  }
});

test("rotateContours: empty input → []", () => {
  assert.deepEqual(rotateContours([], 45, [0, 0]), []);
  assert.deepEqual(rotateContours(null, 45, [0, 0]), []);
});

test("rotateContours: rejects non-finite degrees", () => {
  assert.throws(
    () => rotateContours(SQUARE_CONTOURS, NaN, [0, 0]),
    /degrees/
  );
  assert.throws(
    () => rotateContours(SQUARE_CONTOURS, Infinity, [0, 0]),
    /degrees/
  );
});

test("rotateContours: rejects bad center shape", () => {
  assert.throws(
    () => rotateContours(SQUARE_CONTOURS, 45, [0]),
    /center/
  );
  assert.throws(
    () => rotateContours(SQUARE_CONTOURS, 45, [NaN, 0]),
    /center/
  );
  assert.throws(
    () => rotateContours(SQUARE_CONTOURS, 45, "bad"),
    /center/
  );
});

test("rotateContours: skips malformed points but keeps polyline", () => {
  const bad = [[[0, 0], [NaN, 5], [10, 10]]];
  const out = rotateContours(bad, 0, [0, 0]);
  // 3 pts in, NaN one filtered, 2 valid pts kept
  assert.equal(out[0].length, 2);
});
