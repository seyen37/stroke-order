// Phase 6z-5a — Pseudo-3D 變形 pure helpers (Node testable).
//
// Per v0.3 §4 設計, this MVP implements DEPTH_DIR (4 directions) only.
// CURVE_MODE (4 axes: high-mid / high-sides / left-high / right-high) defers
// to 6z-5b per senior review note #2 (避免 4×4 = 16 組合過早爆炸 scope).
//
// Transform is per-unit local (relative to unit center ucx, ucy), not global
// tile-wide perspective — each placed tangle unit can have its own pseudo_3d
// state and transforms independently.
//
// Spec format input/output: same shape as tangle.mjs SPEC_* — line/curve/
// s_shape/orb/dot. ORB/DOT also have their `r` scaled for forward/backward.

import {
  SPEC_LINE,
  SPEC_CURVE,
  SPEC_S_SHAPE,
  SPEC_ORB,
  SPEC_DOT,
} from "./tangle.mjs?v=__V__";

// Coefficients chosen for visual distinguishability at degree=1:
//   forward/backward: ±50% scale around unit center
//   left/right:       40% horizontal shear per unit-height
const SCALE_COEF = 0.5;
const SHEAR_COEF = 0.4;

/**
 * Transform a single (x, y) point per pseudo_3d spec, around unit center.
 *
 * @param {number} x
 * @param {number} y
 * @param {number} ucx - unit center x (perspective pivot)
 * @param {number} ucy - unit center y
 * @param {string|null} depth_dir - "forward" | "backward" | "left" | "right" | null
 * @param {number} depth_degree - 0..1 (0 or null = identity)
 * @returns {[number, number]} transformed [x, y]
 */
export function applyPseudo3DToPoint(x, y, ucx, ucy, depth_dir, depth_degree) {
  if (!depth_dir || !depth_degree) return [x, y];
  const d = depth_degree;
  const dx = x - ucx;
  const dy = y - ucy;
  switch (depth_dir) {
    case "forward": {
      const k = 1 - d * SCALE_COEF;
      return [ucx + dx * k, ucy + dy * k];
    }
    case "backward": {
      const k = 1 + d * SCALE_COEF;
      return [ucx + dx * k, ucy + dy * k];
    }
    case "left":
      // Right side appears thicker — shift x by +dy * coef (Y-down: dy>0
      // means below center, pushed right; dy<0 means above, pushed left)
      return [x + dy * d * SHEAR_COEF, y];
    case "right":
      return [x - dy * d * SHEAR_COEF, y];
    default:
      return [x, y];
  }
}

/**
 * Compute the radius scaling factor for a given depth_dir + degree.
 * Used for ORB/DOT specs to scale their `r` field consistently with the
 * center-point transform (so the orb visually shrinks/grows together).
 *
 * @returns {number} multiplicative factor (1 = no change)
 */
export function pseudo3DRadiusScale(depth_dir, depth_degree) {
  if (!depth_dir || !depth_degree) return 1;
  const d = depth_degree;
  switch (depth_dir) {
    case "forward":  return 1 - d * SCALE_COEF;
    case "backward": return 1 + d * SCALE_COEF;
    case "left":
    case "right":
      // Shear preserves area scale 1 → r unchanged
      return 1;
    default: return 1;
  }
}

/**
 * Transform an entire spec (any of line/curve/s_shape/orb/dot) per pseudo_3d.
 * Returns a new spec object — input is not mutated.
 */
export function applyPseudo3DToSpec(spec, ucx, ucy, depth_dir, depth_degree) {
  if (!spec || !depth_dir || !depth_degree) return spec;
  const tp = (x, y) =>
    applyPseudo3DToPoint(x, y, ucx, ucy, depth_dir, depth_degree);
  switch (spec.type) {
    case SPEC_LINE: {
      const [x1, y1] = tp(spec.x1, spec.y1);
      const [x2, y2] = tp(spec.x2, spec.y2);
      return {...spec, x1, y1, x2, y2};
    }
    case SPEC_CURVE: {
      const [x1, y1] = tp(spec.x1, spec.y1);
      const [cx, cy] = tp(spec.cx, spec.cy);
      const [x2, y2] = tp(spec.x2, spec.y2);
      return {...spec, x1, y1, cx, cy, x2, y2};
    }
    case SPEC_S_SHAPE: {
      const [x1, y1] = tp(spec.x1, spec.y1);
      const [x2, y2] = tp(spec.x2, spec.y2);
      return {...spec, x1, y1, x2, y2};
    }
    case SPEC_ORB:
    case SPEC_DOT: {
      const [cx, cy] = tp(spec.cx, spec.cy);
      const r = spec.r * pseudo3DRadiusScale(depth_dir, depth_degree);
      return {...spec, cx, cy, r};
    }
    default:
      return spec;
  }
}

/**
 * Convenience: transform an array of specs.
 */
export function applyPseudo3DToSpecs(specs, ucx, ucy, depth_dir, depth_degree) {
  if (!Array.isArray(specs)) return [];
  if (!depth_dir || !depth_degree) return specs;
  return specs.map((s) =>
    applyPseudo3DToSpec(s, ucx, ucy, depth_dir, depth_degree)
  );
}

/**
 * Validate that depth_dir is one of the 4 supported values (or null).
 * Used by callers + tests as a sanity check before storing in unit state.
 */
export const VALID_DEPTH_DIRS = ["forward", "backward", "left", "right"];

export function isValidDepthDir(dir) {
  return dir === null || VALID_DEPTH_DIRS.includes(dir);
}

// ---------------------------------------------------------------------------
// 6z-5b — Curve mode (per v0.3 §4.1 L-stick 4 軸 deformation curvature)
// ---------------------------------------------------------------------------
//
// 6z-5b MVP 只實作 軸 1「中高邊低」 (high-mid) — central column elevated,
// sides sunken. Per-unit local transform applied AFTER depth_dir (chained
// via wirePseudo3DControls in zentangle.js).
//
// 軸 2-4 (high-sides / left-high / right-high) 留 6z-5c 視 5b 視覺豐富度
// 評估是否補完。本檔已預埋 isValidCurveMode + VALID_CURVE_MODES 接口、
// applyCurveModeToPoint switch 也已實作 4 軸 (但 zentangle.js 6z-5b UI
// 只暴露軸 1)；6z-5c 解鎖只需開 UI button、不動 pure module。

export const VALID_CURVE_MODES = [
  "high-mid",     // 中央高、兩側低 (parabola y=x² inverted, Y-down 是 -y)
  "high-sides",   // 兩側高、中央低 (倒拋物線)
  "left-high",    // 左高斜下到右低 (linear gradient)
  "right-high",   // 右高斜下到左低
];

export function isValidCurveMode(mode) {
  return mode === null || VALID_CURVE_MODES.includes(mode);
}

// Max y-offset (in unit_scale units) at curve_degree=1.
const CURVE_COEF = 0.5;

/**
 * Transform a single (x, y) point per curve_mode, around unit center, at
 * given curve_degree (0..1) and unit_scale (the unit's "radius" or extent
 * — used to normalise (x, y) - (ucx, ucy) into [-1, 1]).
 *
 * @param {number} x
 * @param {number} y
 * @param {number} ucx - unit center x
 * @param {number} ucy - unit center y
 * @param {string|null} curve_mode - "high-mid" | "high-sides" | "left-high" | "right-high" | null
 * @param {number} curve_degree - 0..1
 * @param {number} unit_scale - unit's normalising scale (typically PLACED_UNIT_SCALE)
 * @returns {[number, number]}
 */
export function applyCurveModeToPoint(x, y, ucx, ucy, curve_mode, curve_degree, unit_scale) {
  if (!curve_mode || !curve_degree || !unit_scale) return [x, y];
  const us = unit_scale;
  const dx = x - ucx;
  // Normalise dx into [-1, 1] for easier curve math (clamp for points
  // outside unit_scale — rare but defensive).
  const tx = Math.max(-1, Math.min(1, dx / us));
  let curve;  // 0..1, multiplied by curve_degree * us * CURVE_COEF for final offset
  switch (curve_mode) {
    case "high-mid":
      curve = 1 - tx * tx;       // 1 at center, 0 at edges
      break;
    case "high-sides":
      curve = tx * tx;           // 0 at center, 1 at edges
      break;
    case "left-high":
      curve = (1 - tx) / 2;      // 1 at left (tx=-1), 0 at right (tx=1)
      break;
    case "right-high":
      curve = (1 + tx) / 2;      // 0 at left, 1 at right
      break;
    default:
      return [x, y];
  }
  // Y-down: subtract to move "up" visually.
  return [x, y - curve * curve_degree * us * CURVE_COEF];
}

/**
 * Apply curve_mode transform to a spec. Like applyPseudo3DToSpec but for
 * curve_mode (depth_dir 已在 caller 套過、本 helper 不重複 apply)。
 */
export function applyCurveModeToSpec(spec, ucx, ucy, curve_mode, curve_degree, unit_scale) {
  if (!spec || !curve_mode || !curve_degree || !unit_scale) return spec;
  const tp = (x, y) =>
    applyCurveModeToPoint(x, y, ucx, ucy, curve_mode, curve_degree, unit_scale);
  switch (spec.type) {
    case SPEC_LINE: {
      const [x1, y1] = tp(spec.x1, spec.y1);
      const [x2, y2] = tp(spec.x2, spec.y2);
      return {...spec, x1, y1, x2, y2};
    }
    case SPEC_CURVE: {
      const [x1, y1] = tp(spec.x1, spec.y1);
      const [cx, cy] = tp(spec.cx, spec.cy);
      const [x2, y2] = tp(spec.x2, spec.y2);
      return {...spec, x1, y1, cx, cy, x2, y2};
    }
    case SPEC_S_SHAPE: {
      const [x1, y1] = tp(spec.x1, spec.y1);
      const [x2, y2] = tp(spec.x2, spec.y2);
      return {...spec, x1, y1, x2, y2};
    }
    case SPEC_ORB:
    case SPEC_DOT: {
      const [cx, cy] = tp(spec.cx, spec.cy);
      // Curve mode is shear-y-only — preserves r (no radius scaling).
      return {...spec, cx, cy};
    }
    default:
      return spec;
  }
}

export function applyCurveModeToSpecs(specs, ucx, ucy, curve_mode, curve_degree, unit_scale) {
  if (!Array.isArray(specs)) return [];
  if (!curve_mode || !curve_degree || !unit_scale) return specs;
  return specs.map((s) =>
    applyCurveModeToSpec(s, ucx, ucy, curve_mode, curve_degree, unit_scale)
  );
}
