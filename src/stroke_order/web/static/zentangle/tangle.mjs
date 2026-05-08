// Phase 6z-3 — Tangle 庫 + ICSO building blocks (pure module, Node testable).
//
// Architecture:
//   ICSO building block specs (line / curve / s_shape / orb / dot)
//     ↓ pure generator functions (buildCrescentMoon / buildFlorz / etc.)
//   tangle specs array
//     ↓ renderTangleSpecs(ctx, specs) — DOM-coupled, mechanical mapping
//   ctx draw operations
//
// Spec format:
//   line   : {type: "line",    x1, y1, x2, y2}
//   curve  : {type: "curve",   x1, y1, cx, cy, x2, y2}              // quadratic
//   s_shape: {type: "s_shape", x1, y1, x2, y2}                       // auto-control
//   orb    : {type: "orb",     cx, cy, r, startAngle?, endAngle?, fill?}
//   dot    : {type: "dot",     cx, cy, r}                            // always filled
//
// Generators receive `area` (the bounding box to fill) + `density` enum.
// For 6z-3 MVP: 2 tangles (Crescent Moon, Florz). Other 4 (Hollibaugh /
// Tipple / Mooka / Static) defer to 6z-3.X per Q2=B user decision.

export const SPEC_LINE = "line";
export const SPEC_CURVE = "curve";
export const SPEC_S_SHAPE = "s_shape";
export const SPEC_ORB = "orb";
export const SPEC_DOT = "dot";

// Density → grid spacing (px). User picks via 6z-1.x density radio later;
// 6z-3 uses "medium" default since no UI yet. Keeping enum for future.
const DENSITY_SPACING = {
  low: 70,
  medium: 45,
  high: 28,
};

function _spacingFor(density) {
  return DENSITY_SPACING[density] || DENSITY_SPACING.medium;
}

// ---------------------------------------------------------------------------
// Tangle generators (pure)
// ---------------------------------------------------------------------------

/**
 * Crescent Moon — rows of half-arcs (crescents) with dots beneath.
 * Each cell:
 *   ┌─────┐
 *   │ ╭─╮ │   ← top arc (orb half)
 *   │ ╰─╯ │
 *   │  ·  │   ← dot below
 *   └─────┘
 *
 * @param {{x:number, y:number, w:number, h:number}} area
 * @param {string} density - "low" | "medium" | "high"
 * @returns {Array<object>} spec list
 */
export function buildCrescentMoon(area, density = "medium") {
  if (!area || area.w <= 0 || area.h <= 0) return [];
  const spacing = _spacingFor(density);
  const r = spacing * 0.35;
  const specs = [];
  for (let cy = area.y + spacing; cy < area.y + area.h - 4; cy += spacing) {
    for (let cx = area.x + spacing; cx < area.x + area.w - 4; cx += spacing) {
      // Top half-arc (crescent opening downward).
      specs.push({
        type: SPEC_ORB,
        cx,
        cy,
        r,
        startAngle: Math.PI,           // 180° (left)
        endAngle: Math.PI * 2,         // 360° / 0° (right)
        fill: false,
      });
      // Dot directly beneath the crescent's lower edge.
      specs.push({
        type: SPEC_DOT,
        cx,
        cy: cy + r + 6,
        r: 1.6,
      });
    }
  }
  return specs;
}

/**
 * Florz — geometric grid of 4-petal flowers (4 small orbs + center dot).
 *
 *   · ○ ·
 *   ○ · ○   ← 4 petals around center dot
 *   · ○ ·
 *
 * @param {{x, y, w, h}} area
 * @param {string} density
 * @returns {Array<object>}
 */
export function buildFlorz(area, density = "medium") {
  if (!area || area.w <= 0 || area.h <= 0) return [];
  const spacing = _spacingFor(density);
  const petalR = spacing * 0.22;
  const petalOffset = spacing * 0.32;
  const specs = [];
  for (let cy = area.y + spacing; cy < area.y + area.h - 4; cy += spacing) {
    for (let cx = area.x + spacing; cx < area.x + area.w - 4; cx += spacing) {
      // 4 petal orbs (N/E/S/W).
      const petals = [
        [cx, cy - petalOffset],
        [cx + petalOffset, cy],
        [cx, cy + petalOffset],
        [cx - petalOffset, cy],
      ];
      for (const [px, py] of petals) {
        specs.push({
          type: SPEC_ORB,
          cx: px,
          cy: py,
          r: petalR,
          fill: false,
        });
      }
      // Center dot.
      specs.push({type: SPEC_DOT, cx, cy, r: 1.4});
    }
  }
  return specs;
}

// ---------------------------------------------------------------------------
// 6z-3.5 — Single-unit builders (user-place pattern)
// ---------------------------------------------------------------------------
//
// Each unit builder takes (cx, cy, scale) and returns specs for ONE tangle
// unit centered at (cx, cy). `scale` is roughly the spacing param of the
// grid version — controls visual size. Used by user-clickable placement
// (vs grid auto-fill via build*).

/**
 * One Crescent Moon unit: top half-arc + dot below.
 * @param {number} cx - center x
 * @param {number} cy - center y
 * @param {number} scale - "spacing" equivalent; arc r = scale * 0.35
 * @returns {Array<object>} specs (1 orb + 1 dot)
 */
export function buildCrescentMoonUnit(cx, cy, scale = 45) {
  const r = scale * 0.35;
  return [
    {
      type: SPEC_ORB,
      cx,
      cy,
      r,
      startAngle: Math.PI,
      endAngle: Math.PI * 2,
      fill: false,
    },
    {type: SPEC_DOT, cx, cy: cy + r + 6, r: 1.6},
  ];
}

/**
 * One Florz unit: 4 petal orbs (N/E/S/W) + center dot.
 * @param {number} cx
 * @param {number} cy
 * @param {number} scale - "spacing" equivalent; petal offset = scale * 0.32
 * @returns {Array<object>} specs (4 orbs + 1 dot)
 */
export function buildFlorzUnit(cx, cy, scale = 45) {
  const petalR = scale * 0.22;
  const petalOffset = scale * 0.32;
  const petals = [
    [cx, cy - petalOffset],
    [cx + petalOffset, cy],
    [cx, cy + petalOffset],
    [cx - petalOffset, cy],
  ];
  const specs = petals.map(([px, py]) => ({
    type: SPEC_ORB,
    cx: px,
    cy: py,
    r: petalR,
    fill: false,
  }));
  specs.push({type: SPEC_DOT, cx, cy, r: 1.4});
  return specs;
}

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

export const TANGLES = {
  crescent_moon: {
    label: "Crescent Moon",
    build: buildCrescentMoon,
    buildUnit: buildCrescentMoonUnit,
  },
  florz: {
    label: "Florz",
    build: buildFlorz,
    buildUnit: buildFlorzUnit,
  },
};

export function listTangles() {
  return Object.entries(TANGLES).map(([key, t]) => ({key, label: t.label}));
}

export function buildTangle(key, area, density = "medium") {
  const t = TANGLES[key];
  if (!t) throw new Error(`Unknown tangle: ${key}`);
  return t.build(area, density);
}

// ---------------------------------------------------------------------------
// Renderer (DOM-coupled but mechanical — kept here so the pure builders
// know the spec shape they need to produce)
// ---------------------------------------------------------------------------

/**
 * Render a tangle spec list onto a canvas 2D context. Caller owns the
 * stroke/fill style — set ctx.strokeStyle / fillStyle / lineWidth before.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Array<object>} specs
 */
export function renderTangleSpecs(ctx, specs) {
  if (!ctx || !Array.isArray(specs) || specs.length === 0) return;
  for (const s of specs) {
    if (!s || typeof s.type !== "string") continue;
    ctx.beginPath();
    switch (s.type) {
      case SPEC_LINE:
        ctx.moveTo(s.x1, s.y1);
        ctx.lineTo(s.x2, s.y2);
        ctx.stroke();
        break;
      case SPEC_CURVE:
        ctx.moveTo(s.x1, s.y1);
        ctx.quadraticCurveTo(s.cx, s.cy, s.x2, s.y2);
        ctx.stroke();
        break;
      case SPEC_S_SHAPE: {
        // Auto-derive 2 control points for an S between (x1,y1) and (x2,y2)
        const mx = (s.x1 + s.x2) / 2;
        const my = (s.y1 + s.y2) / 2;
        const dx = s.x2 - s.x1;
        const dy = s.y2 - s.y1;
        // Perpendicular offset for S-bend (1/4 of length).
        const len = Math.hypot(dx, dy);
        const off = len * 0.25;
        const nx = -dy / (len || 1);
        const ny = dx / (len || 1);
        ctx.moveTo(s.x1, s.y1);
        ctx.bezierCurveTo(
          s.x1 + nx * off, s.y1 + ny * off,
          mx - nx * off, my - ny * off,
          mx, my
        );
        ctx.bezierCurveTo(
          mx + nx * off, my + ny * off,
          s.x2 - nx * off, s.y2 - ny * off,
          s.x2, s.y2
        );
        ctx.stroke();
        break;
      }
      case SPEC_ORB:
        ctx.arc(
          s.cx, s.cy, s.r,
          s.startAngle ?? 0,
          s.endAngle ?? Math.PI * 2
        );
        if (s.fill) ctx.fill();
        else ctx.stroke();
        break;
      case SPEC_DOT:
        ctx.arc(s.cx, s.cy, s.r, 0, Math.PI * 2);
        ctx.fill();
        break;
      default:
        // Unknown spec — skip silently (forward-compat for 6z-3.X new types).
        break;
    }
  }
}
