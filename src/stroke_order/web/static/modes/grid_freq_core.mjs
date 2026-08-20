// ======================================================================
// W4 分級選字 — 純邏輯層（零相依、node 可直測，同 gallery/hash.mjs 慣例）
//
// 資料契約（由 tests/test_grid_freq_pick.py 鎖住）：
//   /api/coverset/moe_elementary_5021 的 chars 順序 ≡ frequency_rank 順序
//   （rank 1..N 連續無跳號）→ 第 N 名就是 chars[N-1]，切片即選字，
//   不需要新端點（§95：只連不抓就沒有相依）。
//
// 誠實標示（評估建議書的風險註記）：frequency_rank 是「字頻名次」的
// 代理，不代表年級難度——標示只寫「字頻 第 N–M 名」，絕不寫學段。
// ======================================================================

/** 字帖輸入框的上限（與 /api/grid 的 chars max_length、UI maxlength 同值；
 *  parity 由 pytest 鎖住，這裡不是第二事實源而是同一數字的前端落點）。 */
export const MAX_PICK = 40;

/**
 * 依字頻名次切片選字。
 *
 * @param {string[]} chars  字頻序字表（chars[i] = 第 i+1 名）
 * @param {*} from   起始名次（1-based；壞值夾回 [1, chars.length]）
 * @param {*} count  字數（壞值夾回 [1, MAX_PICK]；再被表尾截短）
 * @returns {{chars: string[], from: number, to: number}|null}
 *   選出的字與實際名次區間（to 含端）；空表回 null。
 */
export function pickByRank(chars, from, count) {
  if (!Array.isArray(chars) || chars.length === 0) return null;
  let f = Math.trunc(Number(from));
  if (!Number.isFinite(f)) f = 1;
  f = Math.min(Math.max(f, 1), chars.length);
  let n = Math.trunc(Number(count));
  if (!Number.isFinite(n)) n = 1;
  n = Math.min(Math.max(n, 1), MAX_PICK);
  const picked = chars.slice(f - 1, f - 1 + n);
  return { chars: picked, from: f, to: f + picked.length - 1 };
}

/**
 * 帶入後的提示文字。誠實標示：只講名次，不講學段。
 *
 * @param {{from: number, to: number, chars: string[]}} pick
 * @param {number} total 字表總字數
 */
export function pickHint(pick, total) {
  return `已帶入字頻第 ${pick.from}–${pick.to} 名（共 ${pick.chars.length} 字`
    + `／表內 ${total} 字）。名次是字頻排序，不代表年級難度。`;
}
