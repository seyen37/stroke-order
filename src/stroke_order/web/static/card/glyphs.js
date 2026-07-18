// ======================================================================
// card/glyphs.js — 手寫卡片模式（5et-R2）字形提供層。
//
// 介面：registry.provider(char, glyphSpec) → SVG 片段字串（EM 2048、
// 原點左上、Y-down）或 null（fallback 系統字型）。同步查快取；未命中
// 則排程非同步載入、完成後呼叫 requestRender() 讓編輯器重繪。
//
// 三來源：
//   handwriting — /handwriting 頁存在 IndexedDB 的自寫筆跡
//                 （stroke-order-practice / traces，EM 2048 polylines）
//   userfont    — 本機 TTF/OTF（opentype.js 經 /vendor 同源代理，5cn 慣例）
//   style       — 伺服器內建五風格 /api/handwriting/reference/{char}
//                 （M/L/Q/C outline cmds，EM 2048）
// ======================================================================

const EM = 2048;
const DB_NAME = 'stroke-order-practice';
const STORE_TRACES = 'traces';

export function createGlyphRegistry({ requestRender } = {}) {
  const cache = new Map();      // key → SVG 片段字串 | null（確認無資料）
  const pending = new Set();    // 排程中防重複
  let userFont = null;          // opentype.Font
  const notify = typeof requestRender === 'function' ? requestRender : () => {};

  function key(source, style, ch) {
    return `${source}|${source === 'style' ? style : '-'}|${ch}`;
  }

  function provider(ch, glyph) {
    const source = glyph?.source ?? 'system';
    if (source === 'system' || /\s/.test(ch)) return null;
    if (source === 'userfont') return userFont ? userFontFragment(userFont, ch) : null;
    const k = key(source, glyph?.style ?? 'kaishu', ch);
    if (cache.has(k)) return cache.get(k);
    schedule(k, source, glyph?.style ?? 'kaishu', ch);
    return null; // 載入期間先以系統字型墊底
  }

  function schedule(k, source, style, ch) {
    if (pending.has(k)) return;
    pending.add(k);
    const job = source === 'handwriting' ? loadHandwriting(ch) : loadStyle(ch, style);
    job
      .then((frag) => { cache.set(k, frag); })
      .catch(() => { cache.set(k, null); })
      .finally(() => { pending.delete(k); notify(); });
  }

  async function loadUserFontFile(file) {
    const opentype = await ensureOpentype();
    const buf = await file.arrayBuffer();
    userFont = opentype.parse(buf);
    notify();
    return userFont;
  }

  return {
    provider,
    loadUserFontFile,
    hasUserFont: () => !!userFont,
    clearCache: () => { cache.clear(); notify(); },
  };
}

// ---- handwriting（IndexedDB，同源直讀 /handwriting 的資料庫） --------

function openPracticeDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function loadHandwriting(ch) {
  const db = await openPracticeDb();
  try {
    if (!db.objectStoreNames.contains(STORE_TRACES)) return null;
    const traces = await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_TRACES, 'readonly');
      const idx = tx.objectStore(STORE_TRACES).index('char');
      const req = idx.getAll(ch);
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
    if (!traces.length) return null;
    traces.sort((a, b) => (b.ts || 0) - (a.ts || 0)); // 取最新一筆
    return traceFragment(traces[0]);
  } finally {
    db.close();
  }
}

export function traceFragment(trace) {
  const polys = (trace.strokes || [])
    .map((s) => (s.points || [])
      .map((p) => `${Math.round(p.x)},${Math.round(p.y)}`)
      .join(' '))
    .filter((pts) => pts.length)
    .map((pts) => `<polyline points="${pts}"/>`)
    .join('');
  if (!polys) return null;
  // 與 handwriting/exporter.js 同慣例：EM 2048、stroke-width 40、圓端點
  return (
    `<g fill="none" stroke="currentColor" stroke-width="40"` +
    ` stroke-linecap="round" stroke-linejoin="round">${polys}</g>`
  );
}

// ---- style（伺服器內建風格 outline） ---------------------------------

async function loadStyle(ch, style) {
  const r = await fetch(
    `/api/handwriting/reference/${encodeURIComponent(ch)}?style=${encodeURIComponent(style)}`,
  );
  if (!r.ok) return null;
  const data = await r.json();
  return outlineFragment(data.strokes || []);
}

export function outlineFragment(strokes) {
  const ds = [];
  for (const s of strokes) {
    const d = outlineToPathD(s.outline || []);
    if (d) ds.push(d);
  }
  if (!ds.length) return null;
  return `<g fill="currentColor">${ds.map((d) => `<path d="${d}"/>`).join('')}</g>`;
}

//: M/L/Q/C 指令列 → path d 字串（EM 座標原樣）。
//: 欄位契約＝IR outline 慣例（同 handwriting/reference.js _buildPath2D）：
//: Q={begin:{x,y}, end:{x,y}}、C={begin, mid, end}——非 x1/y1 扁平欄位。
export function outlineToPathD(cmds) {
  const out = [];
  for (const c of cmds) {
    switch (c.type) {
      case 'M': out.push(`M${rd(c.x)} ${rd(c.y)}`); break;
      case 'L': out.push(`L${rd(c.x)} ${rd(c.y)}`); break;
      case 'Q':
        out.push(`Q${rd(c.begin?.x)} ${rd(c.begin?.y)} ${rd(c.end?.x)} ${rd(c.end?.y)}`);
        break;
      case 'C':
        out.push(
          `C${rd(c.begin?.x)} ${rd(c.begin?.y)} ${rd(c.mid?.x)} ${rd(c.mid?.y)}` +
          ` ${rd(c.end?.x)} ${rd(c.end?.y)}`,
        );
        break;
      case 'Z': out.push('Z'); break;
      default: break;
    }
  }
  return out.length ? out.join('') : null;
}

function rd(v) {
  return Math.round(Number(v) * 10) / 10;
}

// ---- userfont（opentype.js，5cn 慣例） -------------------------------

let _opentypeP = null;

function ensureOpentype() {
  if (globalThis.opentype) return Promise.resolve(globalThis.opentype);
  if (_opentypeP) return _opentypeP;
  _opentypeP = new Promise((resolve, reject) => {
    const tag = document.createElement('script');
    const timer = setTimeout(() => {
      tag.remove();
      _opentypeP = null;
      reject(new Error('opentype.js 載入逾時（20s）'));
    }, 20000);
    tag.src = '/vendor/opentype.min.js?v=1.3.4';
    tag.onload = () => { clearTimeout(timer); resolve(globalThis.opentype); };
    tag.onerror = () => {
      clearTimeout(timer);
      _opentypeP = null;
      reject(new Error('opentype.js 載入失敗'));
    };
    document.head.appendChild(tag);
  });
  return _opentypeP;
}

function userFontFragment(font, ch) {
  try {
    const upem = font.unitsPerEm || 1000;
    const scale = EM / upem;
    const baseY = (font.ascender || upem * 0.88) * scale;
    const adv = font.getAdvanceWidth(ch, EM);
    const x = Math.max(0, (EM - adv) / 2); // 置中（5cn 慣例）
    const d = font.getPath(ch, x, baseY, EM).toPathData(1);
    if (!d) return null;
    return `<g fill="currentColor"><path d="${d}"/></g>`;
  } catch {
    return null;
  }
}
