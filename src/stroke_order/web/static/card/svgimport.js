// ======================================================================
// card/svgimport.js — 手寫卡片模式（5et-R3）SVG 匯入與淨化。
//
// 信任邊界：外部 SVG（使用者選檔）與 /api/doodle 回傳都經 sanitizeSvgText
// 才存入 model；render.js 對 art fragment 原樣嵌入，**唯一**合法來源就是
// 這裡的輸出。判斷函式（allowlist/viewBox 解析）是純函式供 node 直測；
// DOM 走訪（DOMParser/XMLSerializer）僅瀏覽器執行，由 Playwright E2E 驗。
// ======================================================================

//: 元素 allowlist——純向量繪圖子集。刻意排除：script/foreignObject/
//: image（外部資源）/use（href 出逃面）/animate*/filter 一族。
export const ALLOWED_TAGS = new Set([
  'svg', 'g', 'path', 'rect', 'circle', 'ellipse', 'line',
  'polyline', 'polygon', 'defs', 'clipPath',
  'linearGradient', 'radialGradient', 'stop',
  'title', 'desc', 'text', 'tspan',
]);

//: 屬性判斷：on* 事件一律拒；href 家族一律拒；style 內含 url(/expression 拒。
export function isAllowedAttr(name, value) {
  const n = String(name).toLowerCase();
  if (n.startsWith('on')) return false;
  if (n === 'href' || n === 'xlink:href') return false;
  if (n === 'style') {
    const v = String(value).toLowerCase();
    if (v.includes('url(') || v.includes('expression')) return false;
  }
  return true;
}

//: viewBox 字串 → {vw, vh}；退回 width/height（含單位剝除）；無效回 null。
export function parseSvgSize(viewBox, widthAttr, heightAttr) {
  if (viewBox) {
    const parts = String(viewBox).trim().split(/[\s,]+/).map(Number);
    if (parts.length === 4 && parts.every(Number.isFinite) && parts[2] > 0 && parts[3] > 0) {
      return { vx: parts[0], vy: parts[1], vw: parts[2], vh: parts[3] };
    }
  }
  const w = parseFloat(widthAttr);
  const h = parseFloat(heightAttr);
  if (Number.isFinite(w) && Number.isFinite(h) && w > 0 && h > 0) {
    return { vx: 0, vy: 0, vw: w, vh: h };
  }
  return null;
}

//: 是否為「鋪滿整張畫布的背景矩形」（doodle 伺服器輸出自帶白底，嵌卡要拿掉）。
export function isBackgroundRect(attrs, size) {
  const x = parseFloat(attrs.x ?? '0') || 0;
  const y = parseFloat(attrs.y ?? '0') || 0;
  const w = parseFloat(attrs.width ?? '');
  const h = parseFloat(attrs.height ?? '');
  if (!Number.isFinite(w) || !Number.isFinite(h)) return false;
  const near = (a, b) => Math.abs(a - b) <= Math.max(1, b * 0.02);
  return near(x, size.vx) && near(y, size.vy) && near(w, size.vw) && near(h, size.vh);
}

//: fragment 大小上限（localStorage 5MB 安全帶；超過拒收請使用者縮圖）。
export const MAX_FRAG_CHARS = 300_000;

// ---- 瀏覽器端：DOM 走訪淨化 ------------------------------------------

//: svgText → { frag, vx, vy, vw, vh } 或 { error }。
//: opts.dropBackgroundRect：doodle 匯入時去白底。
export function sanitizeSvgText(svgText, opts = {}) {
  let doc;
  try {
    doc = new DOMParser().parseFromString(svgText, 'image/svg+xml');
  } catch {
    return { error: '無法解析 SVG' };
  }
  const root = doc.documentElement;
  if (!root || root.nodeName.toLowerCase() !== 'svg' || doc.querySelector('parsererror')) {
    return { error: 'SVG 格式錯誤' };
  }
  const size = parseSvgSize(
    root.getAttribute('viewBox'), root.getAttribute('width'), root.getAttribute('height'),
  );
  if (!size) return { error: 'SVG 缺少 viewBox 或寬高' };

  const walk = (el) => {
    for (const child of [...el.children]) {
      const tag = child.nodeName.toLowerCase();
      if (!ALLOWED_TAGS.has(tag) || tag === 'svg') {
        child.remove();
        continue;
      }
      if (
        opts.dropBackgroundRect && tag === 'rect' &&
        isBackgroundRect(attrMap(child), size)
      ) {
        child.remove();
        continue;
      }
      for (const attr of [...child.attributes]) {
        if (!isAllowedAttr(attr.name, attr.value)) child.removeAttribute(attr.name);
      }
      walk(child);
    }
  };
  walk(root);

  const ser = new XMLSerializer();
  const frag = [...root.children].map((c) => ser.serializeToString(c)).join('');
  if (!frag.trim()) return { error: 'SVG 淨化後沒有可用內容' };
  if (frag.length > MAX_FRAG_CHARS) {
    return { error: `圖案過大（${Math.round(frag.length / 1000)}KB > 300KB）——請先縮小或簡化` };
  }
  return { frag, ...size };
}

function attrMap(el) {
  const m = {};
  for (const a of el.attributes) m[a.name] = a.value;
  return m;
}
