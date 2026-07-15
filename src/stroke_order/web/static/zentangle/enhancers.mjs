// Phase 5dj-1 — Tangle Enhancers（延伸/裝飾技法，pure module, Node testable）。
//
// 禪繞畫的「延伸元素」＝把已畫好的 spec 列後處理，讓平面圖樣長出質感、
// 立體感、華麗感。本模組把每個技法寫成純函式：吃 spec 列（＋area/選項）
// → 回傳「延伸後的新 spec 列」，絕不改輸入。
//
// 管線位置（zentangle.js 消費）：
//   build(基本符號/經典圖樣) → orientSpecs(朝向) → applyEnhancers(延伸) → render
// 放在朝向之後＝延伸幾何以「畫面上實際筆劃」為準，與紙磚旋轉/朝向解耦。
//
// 本輪（5dj-1）落地三個最泛用技法：
//   Aura      光環線   ：沿筆劃外緣加平行副本（漣漪擴散、聚焦）
//   Weighting 加厚壓重 ：局部加粗線寬（毛筆撇捺的立體流動感）
//   Rounding  圓化塗黑 ：交接/端點圓化並填黑小塊（消除生硬尖角）
//
// 其餘 4 技法（Sparkle 閃光留白／Perfs 襯飾小圓／Coffering 金庫效應／
// Dewdrop 露珠）與混搭規則留後輪。
//
// 能力邊界誠實（skill 降級階梯原則）：
//   - Aura 對 curve/s_shape 走「端點沿弦法線平移」近似平行曲線——大彎
//     曲率下與真平行曲線有肉眼可辨誤差，但對禪繞小尺度筆劃足夠。
//   - Rounding 為「端點圓化近似」：在筆劃端點放小填黑圓，模擬轉角塗黑；
//     尚未做真正的「兩線相交銳角偵測 + 三角填黑」（留後輪升級）。

import {
  SPEC_LINE, SPEC_CURVE, SPEC_S_SHAPE, SPEC_ORB, SPEC_DOT,
} from "./tangle.mjs";

// 可用的延伸技法 key（UI toggle 據此生成；registry 哲學＝單一事實源）。
export const ENHANCERS = ["aura", "weighting", "rounding"];

export const ENHANCER_LABELS = {
  aura: "光環線 Aura",
  weighting: "加厚 Weighting",
  rounding: "圓化 Rounding",
};

// 預設參數（區段可覆寫；本輪固定值，UI 微調留後輪）。
const AURA_GAP = 4;          // 光環線與原筆劃的間距（px）
const AURA_RINGS = 1;        // 圈數
const WEIGHTING_FACTOR = 2.6; // 加厚後線寬倍率（相對 base=1）
const ROUNDING_R = 2.0;      // 端點圓化小黑圓半徑（px）

// ---------------------------------------------------------------------------
// 幾何小工具
// ---------------------------------------------------------------------------

/** 取 spec 的兩端點（stroke 類）或中心（orb/dot）。回傳 [[x,y],...]。 */
function specEndpoints(s) {
  switch (s.type) {
    case SPEC_LINE:
    case SPEC_S_SHAPE:
      return [[s.x1, s.y1], [s.x2, s.y2]];
    case SPEC_CURVE:
      return [[s.x1, s.y1], [s.x2, s.y2]];
    default:
      return [];
  }
}

/** 單位法線（垂直於 a→b）。退化回 [0,0]。 */
function unitNormal(ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay;
  const len = Math.hypot(dx, dy);
  if (len < 1e-9) return [0, 0];
  return [-dy / len, dx / len];
}

// ---------------------------------------------------------------------------
// Aura（光環線）
// ---------------------------------------------------------------------------

/**
 * 對單一 spec 產生光環副本（不含原 spec）。ring=1..rings。
 *   line    : 沿法線平移 gap·ring 的平行線
 *   curve   : 三控制點各沿「弦法線」平移（近似平行曲線）
 *   s_shape : 端點沿弦法線平移（renderer 會重算 S 控制點）
 *   orb     : 同心放大 r + gap·ring（保留 start/endAngle＝弧也擴）
 *   dot     : 外圈 orb（r = dotR + gap·ring，不填）＝點的光環
 */
function auraOfSpec(s, gap, rings) {
  const out = [];
  for (let ring = 1; ring <= rings; ring++) {
    const d = gap * ring;
    switch (s.type) {
      case SPEC_LINE: {
        const [nx, ny] = unitNormal(s.x1, s.y1, s.x2, s.y2);
        out.push({type: SPEC_LINE,
                  x1: s.x1 + nx * d, y1: s.y1 + ny * d,
                  x2: s.x2 + nx * d, y2: s.y2 + ny * d});
        break;
      }
      case SPEC_S_SHAPE: {
        const [nx, ny] = unitNormal(s.x1, s.y1, s.x2, s.y2);
        out.push({type: SPEC_S_SHAPE,
                  x1: s.x1 + nx * d, y1: s.y1 + ny * d,
                  x2: s.x2 + nx * d, y2: s.y2 + ny * d});
        break;
      }
      case SPEC_CURVE: {
        const [nx, ny] = unitNormal(s.x1, s.y1, s.x2, s.y2);
        out.push({type: SPEC_CURVE,
                  x1: s.x1 + nx * d, y1: s.y1 + ny * d,
                  cx: s.cx + nx * d, cy: s.cy + ny * d,
                  x2: s.x2 + nx * d, y2: s.y2 + ny * d});
        break;
      }
      case SPEC_ORB: {
        out.push({...s, r: s.r + d, fill: false});
        break;
      }
      case SPEC_DOT: {
        out.push({type: SPEC_ORB, cx: s.cx, cy: s.cy,
                  r: s.r + d, fill: false});
        break;
      }
      default:
        break;
    }
  }
  return out;
}

/** Aura：回傳「原 spec + 每個 spec 的光環副本」。 */
export function applyAura(specs, opts = {}) {
  const gap = opts.gap ?? AURA_GAP;
  const rings = Math.max(1, Math.floor(opts.rings ?? AURA_RINGS));
  const out = [];
  for (const s of specs) {
    out.push(s);
    for (const a of auraOfSpec(s, gap, rings)) out.push(a);
  }
  return out;
}

// ---------------------------------------------------------------------------
// Weighting（加厚 / 壓重）
// ---------------------------------------------------------------------------

/**
 * Weighting：對 stroke 類 spec（line/curve/s_shape）加粗線寬（帶 lw 欄位，
 * renderTangleSpecs 讀取）。orb 描邊也加粗；dot（填色）維持不變。
 * 回傳新陣列（不改輸入）。
 */
export function applyWeighting(specs, opts = {}) {
  const factor = opts.factor ?? WEIGHTING_FACTOR;
  const base = opts.baseLineWidth ?? 1;
  const lw = base * factor;
  return specs.map((s) => {
    if (s.type === SPEC_DOT) return {...s};
    if (s.type === SPEC_ORB && s.fill) return {...s};
    return {...s, lw};
  });
}

// ---------------------------------------------------------------------------
// Rounding（圓化 / 塗黑）— MVP 端點圓化近似
// ---------------------------------------------------------------------------

/**
 * Rounding（MVP 近似）：在每個 stroke spec 的端點放小填黑圓，模擬
 * 「轉角圓化＋三角塗黑」的視覺重量。回傳「原 spec + 端點小黑圓」。
 * 端點去重（共點只放一個）＝相鄰筆劃交接處不疊黑。
 *
 * 誠實標注：這是端點近似，非真正的銳角偵測＋三角填黑（留後輪）。
 */
export function applyRounding(specs, opts = {}) {
  const r = opts.r ?? ROUNDING_R;
  const out = specs.slice();
  const seen = [];
  const dup = (x, y) =>
    seen.some(([sx, sy]) => Math.hypot(sx - x, sy - y) < r);
  for (const s of specs) {
    for (const [x, y] of specEndpoints(s)) {
      if (dup(x, y)) continue;
      seen.push([x, y]);
      out.push({type: SPEC_DOT, cx: x, cy: y, r});
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// 管線
// ---------------------------------------------------------------------------

/** region.enhancers 的正規形（缺欄補 false）。 */
export function normalizeEnhancers(e) {
  const o = {};
  for (const k of ENHANCERS) o[k] = !!(e && e[k]);
  return o;
}

/**
 * 套用一組延伸技法到 spec 列。config = {aura, weighting, rounding} 布林。
 * 順序（固定）：weighting（改線寬）→ aura（外擴、光環也繼承粗細）→
 * rounding（端點塗黑，畫在最上）。全關＝原樣回傳（同參考語意上的複製）。
 *
 * @param {Array} specs
 * @param {object} config - 布林旗標（缺＝false）
 * @param {object} opts   - 透傳各技法參數（gap/rings/factor/r/baseLineWidth）
 */
export function applyEnhancers(specs, config, opts = {}) {
  if (!Array.isArray(specs) || specs.length === 0) return [];
  const c = normalizeEnhancers(config);
  let out = specs;
  if (c.weighting) out = applyWeighting(out, opts);
  if (c.aura) out = applyAura(out, opts);
  if (c.rounding) out = applyRounding(out, opts);
  return out;
}

/** 是否有任一技法開啟（渲染端短路用）。 */
export function hasAnyEnhancer(config) {
  const c = normalizeEnhancers(config);
  return ENHANCERS.some((k) => c[k]);
}
