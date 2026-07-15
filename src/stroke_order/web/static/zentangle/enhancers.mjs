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
// 5dj-2：第二批四技法（sparkle/perfs/coffering/dewdrop）併入。
// 陣列順序＝UI 顯示順序；套用順序另見 applyEnhancers（固定管線）。
export const ENHANCERS = [
  "aura", "weighting", "rounding",
  "sparkle", "perfs", "coffering", "dewdrop",
];

export const ENHANCER_LABELS = {
  aura: "光環線 Aura",
  weighting: "加厚 Weighting",
  rounding: "圓化 Rounding",
  sparkle: "閃光留白 Sparkle",
  perfs: "襯飾小圓 Perfs",
  coffering: "金庫效應 Coffering",
  dewdrop: "露珠 Dewdrop",
};

// 預設參數（區段可覆寫；本輪固定值，UI 微調留後輪）。
const AURA_GAP = 4;          // 光環線與原筆劃的間距（px）
const AURA_RINGS = 1;        // 圈數
const WEIGHTING_FACTOR = 2.6; // 加厚後線寬倍率（相對 base=1）
const ROUNDING_R = 2.0;      // 端點圓化小黑圓半徑（px）
const SPARKLE_GAP = 0.20;    // 閃光留白：中段留白佔筆劃長度比例
const PERFS_SPACING = 9;     // 襯飾小圓：沿筆劃等距間隔（px）
const PERFS_R = 1.6;         // 襯飾小圓半徑（px）
const COFFERING_INSET = 0.55; // 金庫：內縮圈半徑比例
const DEWDROP_R_RATIO = 0.30; // 露珠：半徑相對區段短邊比例

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

// ---------------------------------------------------------------------------
// 5dj-2 幾何工具：曲線攤平 / quadratic 分割 / 沿路徑取樣
// ---------------------------------------------------------------------------

/** lerp。 */
function lerp(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]; }

/**
 * de Casteljau 取 quadratic 在 [0,t1] 的左半段（回傳新 quadratic 三控制點）。
 * P0,P1,P2 是原三點。
 */
function quadLeft(P0, P1, P2, t) {
  const a = lerp(P0, P1, t);
  const b = lerp(P1, P2, t);
  const m = lerp(a, b, t);        // 曲線上 t 點
  return [P0, a, m];
}
/** quadratic 在 [t,1] 的右半段。 */
function quadRight(P0, P1, P2, t) {
  const a = lerp(P0, P1, t);
  const b = lerp(P1, P2, t);
  const m = lerp(a, b, t);
  return [m, b, P2];
}

/** 沿 spec 路徑等距取樣點（Perfs 用）。回傳 [[x,y],...]（含端點）。 */
function sampleAlong(s, spacing) {
  const pts = [];
  if (s.type === SPEC_LINE || s.type === SPEC_S_SHAPE) {
    // 直線近似（S 線以弦近似取樣＝襯飾沿弦排，MVP 可接受）。
    const len = Math.hypot(s.x2 - s.x1, s.y2 - s.y1);
    const n = Math.max(1, Math.round(len / spacing));
    for (let i = 0; i <= n; i++) pts.push(lerp([s.x1, s.y1], [s.x2, s.y2], i / n));
  } else if (s.type === SPEC_CURVE) {
    const P0 = [s.x1, s.y1], P1 = [s.cx, s.cy], P2 = [s.x2, s.y2];
    // 估長（控制多邊形近似）→ 決定段數。
    const approx = Math.hypot(P1[0] - P0[0], P1[1] - P0[1]) +
                   Math.hypot(P2[0] - P1[0], P2[1] - P1[1]);
    const n = Math.max(1, Math.round(approx / spacing));
    for (let i = 0; i <= n; i++) {
      const t = i / n, u = 1 - t;
      pts.push([u * u * P0[0] + 2 * u * t * P1[0] + t * t * P2[0],
                u * u * P0[1] + 2 * u * t * P1[1] + t * t * P2[1]]);
    }
  } else if (s.type === SPEC_ORB) {
    const a0 = s.startAngle ?? 0, a1 = s.endAngle ?? Math.PI * 2;
    const arc = Math.abs(a1 - a0) * s.r;
    const n = Math.max(3, Math.round(arc / spacing));
    for (let i = 0; i <= n; i++) {
      const a = a0 + (a1 - a0) * (i / n);
      pts.push([s.cx + s.r * Math.cos(a), s.cy + s.r * Math.sin(a)]);
    }
  }
  return pts;
}

// ---------------------------------------------------------------------------
// Sparkle（閃光留白）— 筆劃中段斷開留白，模擬反光高光
// ---------------------------------------------------------------------------

/**
 * Sparkle：把每個 stroke/弧 spec 從中段斷成兩段、中間留白 gap（比例）。
 *   line  : 切成 [0, 0.5-g/2] 與 [0.5+g/2, 1] 兩段
 *   curve : de Casteljau 分兩段（跳過中段）
 *   orb   : 弧角度範圍中段留角度 gap
 *   dot / s_shape : 原樣（點無中段可斷；s_shape 由 renderer 自算控制點、
 *           不易穩定切分——MVP 誠實維持原樣）
 * 回傳新陣列（不改輸入）。
 */
export function applySparkle(specs, opts = {}) {
  const g = Math.min(0.6, Math.max(0.02, opts.gap ?? SPARKLE_GAP));
  const t1 = 0.5 - g / 2, t2 = 0.5 + g / 2;
  const out = [];
  for (const s of specs) {
    if (s.type === SPEC_LINE) {
      const A = [s.x1, s.y1], B = [s.x2, s.y2];
      const p1 = lerp(A, B, t1), p2 = lerp(A, B, t2);
      out.push({...s, x1: A[0], y1: A[1], x2: p1[0], y2: p1[1]});
      out.push({...s, x1: p2[0], y1: p2[1], x2: B[0], y2: B[1]});
    } else if (s.type === SPEC_CURVE) {
      const P0 = [s.x1, s.y1], P1 = [s.cx, s.cy], P2 = [s.x2, s.y2];
      const L = quadLeft(P0, P1, P2, t1);
      const R = quadRight(P0, P1, P2, t2);
      out.push({...s, x1: L[0][0], y1: L[0][1], cx: L[1][0], cy: L[1][1],
                x2: L[2][0], y2: L[2][1]});
      out.push({...s, x1: R[0][0], y1: R[0][1], cx: R[1][0], cy: R[1][1],
                x2: R[2][0], y2: R[2][1]});
    } else if (s.type === SPEC_ORB) {
      const a0 = s.startAngle ?? 0, a1 = s.endAngle ?? Math.PI * 2;
      const span = a1 - a0;
      out.push({...s, startAngle: a0, endAngle: a0 + span * t1, fill: false});
      out.push({...s, startAngle: a0 + span * t2, endAngle: a1, fill: false});
    } else {
      out.push(s);   // dot / s_shape 原樣
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Perfs（襯飾小圓）— 沿筆劃外緣等距排一串微型小圈
// ---------------------------------------------------------------------------

/** Perfs：沿每個 stroke/orb 路徑等距放小 orb（不填）。回傳原 + 小圓。 */
export function applyPerfs(specs, opts = {}) {
  const spacing = opts.spacing ?? PERFS_SPACING;
  const r = opts.perfR ?? PERFS_R;
  const out = specs.slice();
  for (const s of specs) {
    if (s.type === SPEC_DOT) continue;   // 點不加珠
    for (const [x, y] of sampleAlong(s, spacing)) {
      out.push({type: SPEC_ORB, cx: x, cy: y, r, fill: false});
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Coffering（金庫效應）— 封閉形內縮圈 + 放射連角（逐筆，僅對 orb）
// ---------------------------------------------------------------------------

/**
 * Coffering（逐筆）：對每個「封閉圓」（完整 orb）往內畫縮小同心圈，
 * 並以 4 條放射線連接內外圈——製造凹陷/浮雕的金庫門視覺。
 * 非封閉 orb（有 start/endAngle 的弧）與其他 spec 略過（金庫效應需
 * 封閉幾何——誠實邊界，不硬套）。回傳原 + 內圈 + 放射線。
 */
export function applyCoffering(specs, opts = {}) {
  const inset = opts.inset ?? COFFERING_INSET;
  const out = specs.slice();
  for (const s of specs) {
    const isFullOrb = s.type === SPEC_ORB &&
      s.startAngle === undefined && s.endAngle === undefined;
    if (!isFullOrb) continue;
    const rin = s.r * inset;
    out.push({type: SPEC_ORB, cx: s.cx, cy: s.cy, r: rin, fill: false});
    // 4 條放射線（45°×4）連內外圈。
    for (let k = 0; k < 4; k++) {
      const a = Math.PI / 4 + (k * Math.PI) / 2;
      const ca = Math.cos(a), sa = Math.sin(a);
      out.push({type: SPEC_LINE,
                x1: s.cx + ca * rin, y1: s.cy + sa * rin,
                x2: s.cx + ca * s.r, y2: s.cy + sa * s.r});
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Dewdrop（露珠）— 整區一顆透明水滴（含高光 + 陰影）
// ---------------------------------------------------------------------------

/**
 * Dewdrop（整區一顆）：在區段中央疊一顆透明大圓（不填），加左上高光短弧
 * 與右下陰影弧，模擬水滴的折射立體感。需要 area（區段 band）；無 area
 * 則略過（縮圖等情境）。回傳原 + 水滴三件（畫在最上）。
 *
 * @param {Array} specs
 * @param {{x,y,w,h}} area
 */
export function applyDewdrop(specs, area, opts = {}) {
  if (!area || !(area.w > 0) || !(area.h > 0)) return specs.slice();
  const cx = area.x + area.w / 2;
  const cy = area.y + area.h / 2;
  const r = Math.min(area.w, area.h) * (opts.dewR ?? DEWDROP_R_RATIO);
  if (r < 3) return specs.slice();
  const out = specs.slice();
  // 主體透明圓。
  out.push({type: SPEC_ORB, cx, cy, r, fill: false});
  // 左上高光短弧（約 200°~250°）。
  out.push({type: SPEC_ORB, cx, cy, r: r * 0.72,
            startAngle: Math.PI * 1.15, endAngle: Math.PI * 1.5, fill: false});
  // 右下陰影弧（約 20°~70°，稍靠外）。
  out.push({type: SPEC_ORB, cx, cy, r: r * 0.9,
            startAngle: Math.PI * 0.12, endAngle: Math.PI * 0.42, fill: false});
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
 * 套用一組延伸技法到 spec 列。config = 布林旗標（key 見 ENHANCERS）。
 *
 * 固定管線順序（5dj-2，混搭自由多勾＝任意子集，順序保證合理不炸）：
 *   weighting  改線寬（後續斷段/副本各自保有粗細）
 *   → coffering 封閉形內縮凹陷（**須在 sparkle 前**——只認完整 orb，
 *               sparkle 先跑會把圓切成弧、coffering 就找不到封閉形）
 *   → sparkle  斷筆劃留白（含 coffering 內圈/放射線一起斷＝一致高光）
 *   → aura     外擴平行副本
 *   → perfs    沿緣排小圓
 *   → rounding 端點塗黑（斷段新端點也塗＝留白處收口）
 *   → dewdrop  整區一顆水滴（最上層、獨立疊加；需 opts.area）
 *
 * 全關＝原樣回傳（陣列複製）。
 *
 * @param {Array} specs
 * @param {object} config - 布林旗標（缺＝false）
 * @param {object} opts   - 各技法參數 + area（dewdrop 用區段 band）
 */
export function applyEnhancers(specs, config, opts = {}) {
  if (!Array.isArray(specs) || specs.length === 0) return [];
  const c = normalizeEnhancers(config);
  let out = specs;
  if (c.weighting) out = applyWeighting(out, opts);
  if (c.coffering) out = applyCoffering(out, opts);
  if (c.sparkle) out = applySparkle(out, opts);
  if (c.aura) out = applyAura(out, opts);
  if (c.perfs) out = applyPerfs(out, opts);
  if (c.rounding) out = applyRounding(out, opts);
  if (c.dewdrop) out = applyDewdrop(out, opts.area, opts);
  return out;
}

/** 是否有任一技法開啟（渲染端短路用）。 */
export function hasAnyEnhancer(config) {
  const c = normalizeEnhancers(config);
  return ENHANCERS.some((k) => c[k]);
}
