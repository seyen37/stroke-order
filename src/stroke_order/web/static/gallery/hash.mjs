// ======================================================================
// gallery/hash.mjs — Phase 5b r29f: URL hash <-> state pure helpers.
//
// Hash schema (URLSearchParams style):
//   #user=42&sort=likes&q=曼陀羅&kind=mandala&upload=123
//
// Encoded keys (whitelist — bookmarkedOnly / page intentionally excluded):
//   user        → state.userFilter     (positive integer)
//   sort        → state.sort           ('newest' | 'likes' | 'hot')
//   q           → state.q              (string, max 100 chars — server enforces)
//   kind        → state.kindFilter     ('psd' | 'mandala')
//   upload      → state.deepLinkUploadId  (r29g: positive integer，
//                  prepend + 4s flash highlight，4 秒後 state 自清但 hash 留)
//
// Excluded:
//   bookmarkedOnly → 私人 view，不該分享
//   page           → ephemeral，分享連結帶 page=3 體驗差
//   me / items / total / profile / deepLinkUpload (full obj) → derived data
//
// Pure functions: no DOM access, no mutation of inputs. Importable from
// both browser (gallery.js) and Node (tests/test_hash_route.mjs).
// ======================================================================

const ALLOWED_SORTS = ['newest', 'likes', 'hot'];
const ALLOWED_KINDS = ['psd', 'mandala'];

/**
 * Serialize a state object to a hash string (with leading '#', or '' if empty).
 * Only encodes whitelist keys. 'newest' sort and empty strings are omitted
 * (canonical form — round-trip parses back to same state).
 *
 * @param {object} s — full state object (only whitelist keys read)
 * @returns {string} '#user=42&sort=likes' or ''
 */
export function stateToHash(s) {
  const params = new URLSearchParams();
  if (s && Number.isInteger(s.userFilter) && s.userFilter > 0) {
    params.set('user', String(s.userFilter));
  }
  if (s && s.sort && s.sort !== 'newest' && ALLOWED_SORTS.includes(s.sort)) {
    params.set('sort', s.sort);
  }
  if (s && typeof s.q === 'string' && s.q !== '') {
    params.set('q', s.q);
  }
  if (s && s.kindFilter && ALLOWED_KINDS.includes(s.kindFilter)) {
    params.set('kind', s.kindFilter);
  }
  // r29g: deep-link 單張 upload — 用 deepLinkUploadId（state shape 對應 id 欄位）
  if (s && Number.isInteger(s.deepLinkUploadId) && s.deepLinkUploadId > 0) {
    params.set('upload', String(s.deepLinkUploadId));
  }
  const str = params.toString();
  return str ? '#' + str : '';
}

/**
 * Parse a hash string into a state-patch object. Always returns the same
 * shape (canonical defaults filled in for missing keys), so callers can
 * blindly assign without checking presence.
 *
 * Invalid values are silently coerced to default (security: defends against
 * crafted hash like #user=DROP_TABLE).
 *
 * @param {string} hash — typically window.location.hash, may be '' or '#...'
 * @returns {object} { userFilter, sort, q, kindFilter } — always all 4 keys
 */
export function parseHash(hash) {
  const out = {
    userFilter: null,
    sort: 'newest',
    q: '',
    kindFilter: '',
    deepLinkUploadId: null,
  };
  const raw = String(hash || '').replace(/^#/, '');
  if (!raw) return out;
  let params;
  try {
    params = new URLSearchParams(raw);
  } catch {
    return out;  // 異常輸入 → 全 default
  }
  // user → positive integer only
  const user = params.get('user');
  if (user !== null) {
    const n = Number(user);
    if (Number.isInteger(n) && n > 0) out.userFilter = n;
  }
  // sort → whitelist
  const sort = params.get('sort');
  if (sort && ALLOWED_SORTS.includes(sort)) out.sort = sort;
  // q → trimmed, length-capped
  const q = params.get('q');
  if (typeof q === 'string') {
    const trimmed = q.slice(0, 100);
    if (trimmed) out.q = trimmed;
  }
  // kind → whitelist
  const kind = params.get('kind');
  if (kind && ALLOWED_KINDS.includes(kind)) out.kindFilter = kind;
  // r29g: upload (deep-link target) → positive integer only
  const upload = params.get('upload');
  if (upload !== null) {
    const n = Number(upload);
    if (Number.isInteger(n) && n > 0) out.deepLinkUploadId = n;
  }
  return out;
}

/**
 * Produce a state-patch object equivalent to "no hash" — useful for callers
 * who want defaults without parsing an empty string.
 */
export function emptyPatch() {
  return parseHash('');
}
