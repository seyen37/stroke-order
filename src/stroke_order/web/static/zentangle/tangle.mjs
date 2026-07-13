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
  // 5df-2 鐵則回補：下緣錨點外伸＝dot 中心 cy + r + 6，邊界要含它
  // （區段窄帶測試抓包——6z-3 舊 builder 未受過界內測試）。
  for (let cy = area.y + spacing;
       cy <= area.y + area.h - (r + 8); cy += spacing) {
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
  // 5df-2 鐵則回補：花瓣中心外伸 petalOffset，四向邊界都要含。
  const ext = petalOffset + 2;
  for (let cy = area.y + spacing;
       cy <= area.y + area.h - ext; cy += spacing) {
    for (let cx = area.x + spacing;
         cx <= area.x + area.w - ext; cx += spacing) {
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
// 5df-1 — 六個新圖樣（參考 Zentangle A-Z 經典圖樣：Tipple / Bales /
// Printemps / Paradox / Flux / Hollibaugh），全部走同一 spec 協定。
// ---------------------------------------------------------------------------

/** 決定性偽隨機（cell 座標雜湊）——同輸入永遠同輸出，可測試。 */
function _hash01(a, b) {
  let h = (a * 374761393 + b * 668265263) | 0;
  h = ((h ^ (h >> 13)) * 1274126177) | 0;
  return ((h ^ (h >> 16)) >>> 0) / 4294967296;
}

/** Tipple — 大小圓泡簇（jitter 網格＋決定性半徑）。 */
export function buildTipple(area, density = "medium") {
  if (!area || area.w <= 0 || area.h <= 0) return [];
  const s = _spacingFor(density) * 0.6;
  const specs = [];
  // 5df-2 鐵則回補：jitter 外伸 ±0.25s，邊界要含。
  const jext = s * 0.25 + 3;
  for (let cy = area.y + s; cy <= area.y + area.h - jext; cy += s) {
    for (let cx = area.x + s; cx <= area.x + area.w - jext; cx += s) {
      const jx = (_hash01(cx | 0, cy | 0) - 0.5) * s * 0.5;
      const jy = (_hash01(cy | 0, cx | 0) - 0.5) * s * 0.5;
      const r = s * (0.18 + 0.28 * _hash01((cx + cy) | 0, (cx * 3) | 0));
      specs.push({type: SPEC_ORB, cx: cx + jx, cy: cy + jy, r, fill: false});
    }
  }
  return specs;
}

/** Bales — 織紋：每格四條向心弧圍成飽滿菱形＋角點。 */
export function buildBales(area, density = "medium") {
  if (!area || area.w <= 0 || area.h <= 0) return [];
  const s = _spacingFor(density);
  const specs = [];
  // 5df-2 鐵則回補：格角錨點外伸 half=0.42s，邊界要含。
  const bext = s * 0.42 + 2;
  for (let cy = area.y + s; cy <= area.y + area.h - bext; cy += s) {
    for (let cx = area.x + s; cx <= area.x + area.w - bext; cx += s) {
      const half = s * 0.42;
      const bow = s * 0.30;
      // 上下左右四條向心弧（quadratic），端點在格角
      specs.push({type: SPEC_CURVE, x1: cx - half, y1: cy - half,
                  cx: cx, cy: cy - half + bow, x2: cx + half, y2: cy - half});
      specs.push({type: SPEC_CURVE, x1: cx - half, y1: cy + half,
                  cx: cx, cy: cy + half - bow, x2: cx + half, y2: cy + half});
      specs.push({type: SPEC_CURVE, x1: cx - half, y1: cy - half,
                  cx: cx - half + bow, cy: cy, x2: cx - half, y2: cy + half});
      specs.push({type: SPEC_CURVE, x1: cx + half, y1: cy - half,
                  cx: cx + half - bow, cy: cy, x2: cx + half, y2: cy + half});
      specs.push({type: SPEC_DOT, cx, cy, r: 1.2});
    }
  }
  return specs;
}

/** Printemps — 蝸牛螺旋：同心開口弧逐圈旋轉。 */
export function buildPrintemps(area, density = "medium") {
  if (!area || area.w <= 0 || area.h <= 0) return [];
  const s = _spacingFor(density) * 1.1;
  const specs = [];
  for (let cy = area.y + s; cy < area.y + area.h - 4; cy += s) {
    for (let cx = area.x + s; cx < area.x + area.w - 4; cx += s) {
      const rings = 3;
      for (let i = 1; i <= rings; i++) {
        const r = (s * 0.42) * (i / rings);
        const a0 = (i * Math.PI) / 2.2;         // 逐圈旋轉開口＝螺旋感
        specs.push({type: SPEC_ORB, cx, cy, r,
                    startAngle: a0, endAngle: a0 + Math.PI * 1.72,
                    fill: false});
      }
      specs.push({type: SPEC_DOT, cx, cy, r: 1.0});
    }
  }
  return specs;
}

/** Paradox — 三角迴旋：巢狀三角形逐層向內旋轉。 */
export function buildParadox(area, density = "medium") {
  if (!area || area.w <= 0 || area.h <= 0) return [];
  const s = _spacingFor(density) * 1.4;
  const specs = [];
  const R = s * 0.46;
  // 迴圈邊界含外接半徑 R——三角頂點不越格（node 界內測試抓包：
  // 舊邊界 -4 會讓最後一格頂點超出 area 約 3px）
  for (let cy = area.y + R + 2; cy <= area.y + area.h - R - 2; cy += s) {
    for (let cx = area.x + R + 2; cx <= area.x + area.w - R - 2; cx += s) {
      let v = [0, 1, 2].map(k => {
        const a = -Math.PI / 2 + (k * 2 * Math.PI) / 3;
        return [cx + R * Math.cos(a), cy + R * Math.sin(a)];
      });
      for (let step = 0; step < 6; step++) {
        for (let k = 0; k < 3; k++) {
          const [x1, y1] = v[k];
          const [x2, y2] = v[(k + 1) % 3];
          specs.push({type: SPEC_LINE, x1, y1, x2, y2});
        }
        const t = 0.18;                        // 頂點向次頂點推進＝迴旋
        v = v.map((p, k) => {
          const q = v[(k + 1) % 3];
          return [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t];
        });
      }
    }
  }
  return specs;
}

/** Flux — 葉藤：對角葉形（兩條鏡像曲線）＋葉心點。 */
export function buildFlux(area, density = "medium") {
  if (!area || area.w <= 0 || area.h <= 0) return [];
  const s = _spacingFor(density);
  const specs = [];
  let flip = false;
  // 5df-2 鐵則回補：葉端 0.38s＋控制點 0.34s 外伸，邊界取大者。
  const fext = s * 0.38 + 2;
  for (let cy = area.y + s; cy <= area.y + area.h - fext; cy += s) {
    for (let cx = area.x + s; cx <= area.x + area.w - fext; cx += s) {
      const half = s * 0.38;
      const d = flip ? -1 : 1;                 // 交錯方向＝藤蔓感
      const x1 = cx - half, y1 = cy + half * d;
      const x2 = cx + half, y2 = cy - half * d;
      const bow = s * 0.34;
      specs.push({type: SPEC_CURVE, x1, y1,
                  cx: cx - bow * d * 0.2, cy: cy - bow, x2, y2});
      specs.push({type: SPEC_CURVE, x1, y1,
                  cx: cx + bow * d * 0.2, cy: cy + bow, x2, y2});
      specs.push({type: SPEC_DOT, cx, cy, r: 1.2});
      flip = !flip;
    }
  }
  return specs;
}

/** Hollibaugh — 交疊直帶：整區長條帶（線對）錯落堆疊。 */
export function buildHollibaugh(area, density = "medium") {
  if (!area || area.w <= 0 || area.h <= 0) return [];
  const s = _spacingFor(density);
  const bandW = s * 0.42;
  const specs = [];
  let i = 0;
  // 迴圈上限含最大外伸（jitter ±0.2s ＋ bandW）——帶右緣不越界
  // （5df-1c：node 界內測試抓包，同 paradox 型蟲）
  const maxExt = s * 0.2 + bandW + 2;
  for (let x = area.x + s * 0.6;
       x < area.x + area.w - maxExt; x += s * 0.9) {
    const off = (_hash01(i, 7) - 0.5) * s * 0.4;
    const x1 = x + off, x2 = x + off + bandW;
    specs.push({type: SPEC_LINE, x1, y1: area.y + 2,
                x2: x1, y2: area.y + area.h - 2});
    specs.push({type: SPEC_LINE, x1: x2, y1: area.y + 2,
                x2: x2, y2: area.y + area.h - 2});
    i += 1;
  }
  return specs;
}

// ---------------------------------------------------------------------------
// 5df-1 — 朝向（曲度朝向）：單一純函式，所有圖樣自動獲得四向。
// 朝向與紙磚旋轉解耦——區段記自己的 orientation，渲染時呼叫端把
// 紙磚旋轉角疊加傳入即可（5df-3 的上下左右鈕直接改這個值）。
// ---------------------------------------------------------------------------

export const ORIENTATIONS = ["up", "right", "down", "left"];
const _ORIENT_DEG = {up: 0, right: 90, down: 180, left: 270};

/** 把 spec 列繞 area 中心旋轉到指定朝向（0/90/180/270）。 */
export function orientSpecs(specs, orientation, area) {
  const deg = _ORIENT_DEG[orientation] ?? 0;
  if (deg === 0) return specs;
  const rad = (deg * Math.PI) / 180;
  const cos = Math.round(Math.cos(rad));
  const sin = Math.round(Math.sin(rad));
  const cx0 = area.x + area.w / 2;
  const cy0 = area.y + area.h / 2;
  const rot = (x, y) => [
    cx0 + (x - cx0) * cos - (y - cy0) * sin,
    cy0 + (x - cx0) * sin + (y - cy0) * cos,
  ];
  return specs.map(sp => {
    const o = {...sp};
    if (sp.type === SPEC_LINE || sp.type === SPEC_S_SHAPE) {
      [o.x1, o.y1] = rot(sp.x1, sp.y1);
      [o.x2, o.y2] = rot(sp.x2, sp.y2);
    } else if (sp.type === SPEC_CURVE) {
      [o.x1, o.y1] = rot(sp.x1, sp.y1);
      [o.cx, o.cy] = rot(sp.cx, sp.cy);
      [o.x2, o.y2] = rot(sp.x2, sp.y2);
    } else {                                   // orb / dot
      [o.cx, o.cy] = rot(sp.cx, sp.cy);
      if (sp.startAngle !== undefined) o.startAngle = sp.startAngle + rad;
      if (sp.endAngle !== undefined) o.endAngle = sp.endAngle + rad;
    }
    return o;
  });
}

/** 建圖樣＋套朝向。90/270 時先以「轉置尺寸」建格（同中心），旋轉
 * 後恰好落回原區域——非正方形區域不會溢框。 */
export function buildTangleOriented(key, area, density = "medium",
                                    orientation = "up") {
  const deg = _ORIENT_DEG[orientation] ?? 0;
  let buildArea = area;
  if (deg === 90 || deg === 270) {
    const cx0 = area.x + area.w / 2;
    const cy0 = area.y + area.h / 2;
    buildArea = {x: cx0 - area.h / 2, y: cy0 - area.w / 2,
                 w: area.h, h: area.w};
  }
  return orientSpecs(buildTangle(key, buildArea, density), orientation, area);
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
  // 5df-1 新六圖樣（unit 版於 5df-3 互動輪視需要補）
  tipple:      {label: "Tipple",      build: buildTipple},
  bales:       {label: "Bales",       build: buildBales},
  printemps:   {label: "Printemps",   build: buildPrintemps},
  paradox:     {label: "Paradox",     build: buildParadox},
  flux:        {label: "Flux",        build: buildFlux},
  hollibaugh:  {label: "Hollibaugh",  build: buildHollibaugh},
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
