// ======================================================================
// teacher/classcore.mjs — /class 課堂筆順的純邏輯（v0.14.302 R3）
// 輸入解析、下載網址、詞語查找；不碰 DOM，node 測試直接驗。
// ======================================================================

/** 一次最多幾個字（/api/grid、/api/steps 上限 40；課堂投影 10 綽綽有餘）。 */
export const MAX_CHARS = 10;

/** 文字 → 字陣列：只留漢字（含擴充區）、依序保留重複字（詞裡的疊字要照教）。 */
export function parseQuery(text) {
  const out = [];
  for (const ch of String(text || '')) {
    if (/\p{Script=Han}/u.test(ch)) out.push(ch);
    if (out.length >= MAX_CHARS) break;
  }
  return out;
}

/** 寫字格至少幾行：字帖每字一直行，字太少整頁只剩細長一條；把詞重複
 *  到至少 6 行（10 格高 × 6 行 ≈ A4 直式比例），老師一張就能發。 */
export const MIN_GRID_COLUMNS = 6;

export function gridChars(q) {
  const s = [...String(q || '')];
  if (!s.length) return '';
  const out = [];
  while (out.length < MIN_GRID_COLUMNS) out.push(...s);
  return out.slice(0, Math.max(MIN_GRID_COLUMNS, s.length)).join('');
}

/** A4 寫字格（字帖）PDF：米字格、每字一直行 10 格（範字＋描紅＋空格）。 */
export function gridUrl(q) {
  const p = new URLSearchParams({
    chars: gridChars(q), guide: 'mi', cols: '10', format: 'pdf',
    paper: 'a4', download: 'true',
  });
  return '/api/grid?' + p.toString();
}

/** 分解圖每列格數：跟著筆畫數走（一列排完最好讀），夾在伺服器 4–20
 *  範圍內，再壓到 10 以免投影時格子太小。 */
export function stepsCols(strokeCount) {
  const n = Math.round(Number(strokeCount) || 0);
  return Math.max(4, Math.min(10, n));
}

/** 逐筆分解圖：svg 給畫面、pdf 給下載。 */
export function stepsUrl(ch, format, strokeCount) {
  const p = new URLSearchParams({
    chars: ch, guide: 'mi', cols: String(stepsCols(strokeCount)),
    cell_size: '72', format,
  });
  if (format !== 'svg') p.set('download', 'true');
  return '/api/steps?' + p.toString();
}

/** 在第一個字的教育部常用詞裡找整個詞；找不到回 null（不裝懂）。 */
export function findWord(dict, word) {
  if (!dict || !dict.found) return null;
  return (dict.words || []).find(w => w.word === word) || null;
}

/** R4 投影模式鍵盤：遙控簡報筆多半送 PageUp/PageDown 與方向鍵。
 *  空白＝播放、→／PageDown＝下一筆、↑↓＝換字、W＝描寫切換、Esc＝離開。 */
export function projectionKey(key) {
  switch (key) {
    case ' ': case 'Enter': return 'play';
    case 'ArrowRight': case 'PageDown': return 'step';
    case 'ArrowUp': return 'prev';
    case 'ArrowDown': return 'next';
    case 'w': case 'W': return 'trace';
    case 'Escape': return 'exit';
    default: return null;
  }
}
