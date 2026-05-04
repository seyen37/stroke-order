// ======================================================================
// gallery/avatar.mjs — Phase 5b r29j: avatar render helper.
//
// API:
//   avatarHtml(user, size=24)
//
//   - user:  { id, email, display_name?, avatar_url? }
//   - size:  pixel side length (also drives font-size for initials)
//
// Behavior:
//   - 若 user.avatar_url 存在 → render <img>
//   - 否則 → render <span class="gl-avatar gl-avatar--initials"> 含 1-2
//     字 initials（display_name 第一字 / email handle 第一字）+ 由 hash
//     算出的固定背景色（同一 user_id 永遠同色）
//
// Pure helper `_initialsSpec(user)` 抽出 initials + color logic 供 Node test。
// ======================================================================

// 固定 8 色 palette — 對 hash 取 mod 選色（HSL 基底，暖冷各半）
const PALETTE = [
  '#5b8def', '#36a64f', '#ec407a', '#fb8c00',
  '#7e57c2', '#26a69a', '#d4af37', '#e53935',
];

/**
 * Pure: pick initials char + palette color from user record.
 * No DOM access — testable from Node.
 */
export function _initialsSpec(user) {
  if (!user) return { char: '?', color: PALETTE[0] };

  // 1. char: display_name 第一字 → email handle 第一字 → '?'
  let raw = (user.display_name || '').trim();
  if (!raw) {
    const email = user.email || '';
    raw = (email.split('@')[0] || '').trim();
  }
  // 取 1 個 grapheme（中文 1 字 / 英文 1 字母）
  // 對中文先取 [...str][0]（避免 surrogate pair 切壞）
  const char = raw ? [...raw][0].toUpperCase() : '?';

  // 2. color: id (numeric) hash → palette index
  // FNV-ish 簡單 hash for stable across reload；id 沒給時 fallback email
  const seed = String(user.id ?? user.email ?? char);
  let h = 0;
  for (let i = 0; i < seed.length; i++) {
    h = (h * 31 + seed.charCodeAt(i)) | 0;  // |0 強制 int32
  }
  const color = PALETTE[Math.abs(h) % PALETTE.length];
  return { char, color };
}

function _escape(s) {
  return String(s ?? '').replace(/[<>&"']/g, ch => ({
    '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;',
  })[ch]);
}

/**
 * Render avatar HTML string. Caller injects via innerHTML.
 *
 * @param {object} user — { id, email, display_name?, avatar_url? }
 * @param {number} size — pixel side length (default 24)
 * @returns {string} HTML
 */
export function avatarHtml(user, size = 24) {
  const px = Math.max(8, Math.floor(size));
  const sizeStyle = `width:${px}px;height:${px}px;`;
  if (user && user.avatar_url) {
    return `<img class="gl-avatar gl-avatar--img"
                  src="${_escape(user.avatar_url)}"
                  alt="${_escape(user.display_name || user.email || '使用者')}"
                  style="${sizeStyle}"
                  loading="lazy">`;
  }
  const spec = _initialsSpec(user);
  // 字級依 size 算（約 0.45x） 避免大 avatar 字太小
  const fontSize = Math.max(8, Math.floor(px * 0.45));
  return `<span class="gl-avatar gl-avatar--initials"
                style="${sizeStyle}background:${spec.color};` +
                  `font-size:${fontSize}px"
                aria-label="${_escape(user?.display_name || user?.email || '使用者')}"
                role="img">${_escape(spec.char)}</span>`;
}
