// ======================================================================
// myfont/core.mjs — /myfont「寫你的名字→得到字型」的純邏輯（v0.14.299 P2）。
//
// 純函式、無 DOM——node --test 直測（tests/test_myfont_core.mjs）。
// 頁面（static/myfont.html）只做接線。筆跡只存在使用者瀏覽器
// （IndexedDB 練習紀錄）；要字型時才連同筆跡送 POST /api/handfont，
// 伺服器算完即丟（P1）。
// ======================================================================

/** 名字最多幾個「不同的字」（三分鐘體驗的範圍）。 */
export const MAX_NAME_CHARS = 6;
/** 一顆字型最多幾個字——與伺服器 HANDFONT_MAX_CHARS parity（pytest 另鎖）。 */
export const MAX_TOTAL_CHARS = 100;
/** 送出前的點距精簡門檻（EM 2048 單位；約 0.3% 字寬，肉眼無差）。 */
export const THIN_MIN_DIST = 6;

const _SKIP = /[\s\p{C}]/u;

/** 字串 → 依序、去重、去空白／控制字元的字陣列（正確處理 surrogate pair）。 */
export function parseChars(text) {
  const out = [];
  const seen = new Set();
  for (const ch of Array.from(String(text ?? ''))) {
    if (_SKIP.test(ch) || seen.has(ch)) continue;
    seen.add(ch);
    out.push(ch);
  }
  return out;
}

/**
 * 折線點距精簡：保留首尾，丟掉離上一個保留點不到 minDist 的點。
 * 指標事件取樣很密（每筆數百點），100 字原始點數會超過伺服器 20 萬點
 * 上限；精簡只用在送出的請求，瀏覽器裡的練習紀錄保留原始取樣。
 */
export function thinTrack(track, minDist = THIN_MIN_DIST) {
  const pts = (track || []).filter(p => Array.isArray(p) && p.length >= 2);
  if (pts.length <= 2) return pts.map(p => [p[0], p[1]]);
  const out = [[pts[0][0], pts[0][1]]];
  const d2 = minDist * minDist;
  for (let i = 1; i < pts.length - 1; i++) {
    const [lx, ly] = out[out.length - 1];
    const dx = pts[i][0] - lx, dy = pts[i][1] - ly;
    if (dx * dx + dy * dy >= d2) out.push([pts[i][0], pts[i][1]]);
  }
  const last = pts[pts.length - 1];
  out.push([last[0], last[1]]);
  return out;
}

/** trace strokes（六元組點列）→ 精簡後的純 [x,y] 折線；<2 點的筆畫剔除。 */
export function traceToTracks(traceStrokes, minDist = THIN_MIN_DIST) {
  return (traceStrokes || [])
    .map(s => thinTrack((s.points || []).map(p => [p[0], p[1]]), minDist))
    .filter(t => t.length >= 2);
}

/**
 * {字: trace strokes} → POST /api/handfont 的 body。
 * 沒有有效筆畫的字略過（回傳的 skipped 讓頁面誠實告知）。
 */
export function buildPayload(written, { weight = 120, owner = '' } = {}) {
  const chars = {};
  const skipped = [];
  for (const [ch, strokes] of Object.entries(written || {})) {
    const tracks = traceToTracks(strokes);
    if (tracks.length) chars[ch] = tracks;
    else skipped.push(ch);
  }
  return { body: { chars, weight, cap: 'round', owner: owner || '' }, skipped };
}

/** 練習紀錄（IndexedDB traces）→ {字: 最新一筆的 strokes}，只挑 wanted 裡的字。 */
export function latestByChar(traces, wanted) {
  const want = new Set(wanted || []);
  const best = new Map();
  for (const t of traces || []) {
    if (!t || !want.has(t.char) || !Array.isArray(t.strokes) || !t.strokes.length) continue;
    const prev = best.get(t.char);
    if (!prev || String(t.ts || '') > String(prev.ts || '')) best.set(t.char, t);
  }
  const out = {};
  for (const [ch, t] of best) out[ch] = t.strokes;
  return out;
}

/** 下載檔名：名字_手寫字型.ttf（去掉檔名不允許的字元）。 */
export function fontFileName(name) {
  const safe = String(name || '').replace(/[\\/:*?"<>|\s]/g, '').slice(0, 20);
  return `${safe ? safe + '_' : ''}手寫字型.ttf`;
}
