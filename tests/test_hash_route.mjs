// ======================================================================
// Phase 5b r29f: hash-route helper unit tests (Node node:test runner).
//
// Run:
//   node --test tests/test_hash_route.mjs
//
// Tests pure functions stateToHash / parseHash from gallery/hash.mjs.
// No DOM / no FastAPI / no server — just data shape & round-trip.
// ======================================================================

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  stateToHash, parseHash, emptyPatch,
} from '../src/stroke_order/web/static/gallery/hash.mjs';


// --- defaults helper for terser tests
function defState(overrides = {}) {
  return {
    userFilter: null,
    sort: 'newest',
    q: '',
    kindFilter: '',
    deepLinkUploadId: null,  // r29g
    bookmarkedOnly: false,  // 應被 stateToHash 忽略
    page: 1,                 // 應被 stateToHash 忽略
    me: { id: 1 },           // 應被 stateToHash 忽略
    ...overrides,
  };
}


// ============================================================ stateToHash

test('stateToHash: empty state → empty string (canonical)', () => {
  assert.equal(stateToHash(defState()), '');
});

test('stateToHash: userFilter=42 → #user=42', () => {
  assert.equal(stateToHash(defState({ userFilter: 42 })), '#user=42');
});

test('stateToHash: sort=likes → #sort=likes (newest 不寫)', () => {
  assert.equal(stateToHash(defState({ sort: 'likes' })), '#sort=likes');
  // newest 是 default → 不寫
  assert.equal(stateToHash(defState({ sort: 'newest' })), '');
});

test('stateToHash: q="曼陀羅" → URL-encoded', () => {
  const got = stateToHash(defState({ q: '曼陀羅' }));
  // URLSearchParams 會 encode 中文（%E6...）
  assert.match(got, /^#q=%E6%9B%BC%E9%99%80%E7%BE%85$/);
});

test('stateToHash: kindFilter=mandala → #kind=mandala', () => {
  assert.equal(stateToHash(defState({ kindFilter: 'mandala' })), '#kind=mandala');
});

test('stateToHash: 多欄位組合（順序固定 = canonical）', () => {
  const got = stateToHash(defState({
    userFilter: 42, sort: 'likes', q: 'abc', kindFilter: 'mandala',
  }));
  // URLSearchParams 內部 set 順序 = 我們 set 的順序：user, sort, q, kind
  assert.equal(got, '#user=42&sort=likes&q=abc&kind=mandala');
});

test('stateToHash: bookmarkedOnly + page 永遠不進 hash（隱私 / ephemeral）', () => {
  const got = stateToHash(defState({
    bookmarkedOnly: true, page: 5,
  }));
  assert.equal(got, '');  // 兩者都不該觸發任何 key
});

test('stateToHash: invalid sort 不寫', () => {
  // 'random' 不在 whitelist → 應 ignore
  assert.equal(stateToHash(defState({ sort: 'random' })), '');
});

test('stateToHash: invalid kind 不寫', () => {
  assert.equal(stateToHash(defState({ kindFilter: 'unknown' })), '');
});

test('stateToHash: userFilter=0 / 負數 / 非整數 不寫', () => {
  assert.equal(stateToHash(defState({ userFilter: 0 })),     '');
  assert.equal(stateToHash(defState({ userFilter: -1 })),    '');
  assert.equal(stateToHash(defState({ userFilter: 1.5 })),   '');
  assert.equal(stateToHash(defState({ userFilter: 'abc' })), '');
});


// ============================================================ parseHash

test('parseHash: empty → all defaults', () => {
  assert.deepEqual(parseHash(''),  emptyPatch());
  assert.deepEqual(parseHash('#'), emptyPatch());
  assert.deepEqual(parseHash(),    emptyPatch());
  assert.deepEqual(parseHash(null), emptyPatch());
});

test('parseHash: #user=42 → userFilter=42', () => {
  assert.deepEqual(parseHash('#user=42'), {
    userFilter: 42, sort: 'newest', q: '', kindFilter: '',
    deepLinkUploadId: null,
  });
});

test('parseHash: 不帶 leading # 也吃', () => {
  assert.deepEqual(parseHash('user=42'), {
    userFilter: 42, sort: 'newest', q: '', kindFilter: '',
    deepLinkUploadId: null,
  });
});

test('parseHash: 中文 q decode', () => {
  // URLSearchParams 自動 decode percent-encoded
  const p = parseHash('#q=%E6%9B%BC%E9%99%80%E7%BE%85');
  assert.equal(p.q, '曼陀羅');
});

test('parseHash: 全欄位組合', () => {
  const p = parseHash('#user=42&sort=likes&q=abc&kind=mandala&upload=99');
  assert.deepEqual(p, {
    userFilter: 42, sort: 'likes', q: 'abc', kindFilter: 'mandala',
    deepLinkUploadId: 99,
  });
});

test('parseHash: 惡意 user=DROP_TABLE → null（防注入）', () => {
  const p = parseHash('#user=DROP_TABLE');
  assert.equal(p.userFilter, null);
});

test('parseHash: 惡意 sort=evil → fallback newest', () => {
  const p = parseHash('#sort=evil');
  assert.equal(p.sort, 'newest');
});

test('parseHash: 惡意 kind=javascript → fallback empty', () => {
  const p = parseHash('#kind=javascript');
  assert.equal(p.kindFilter, '');
});

test('parseHash: q 過長截斷到 100', () => {
  const long = 'a'.repeat(200);
  const p = parseHash('#q=' + long);
  assert.equal(p.q.length, 100);
});

test('parseHash: 未知 key 忽略', () => {
  const p = parseHash('#user=42&unknown=xyz&evil=hax');
  assert.deepEqual(p, {
    userFilter: 42, sort: 'newest', q: '', kindFilter: '',
    deepLinkUploadId: null,
  });
});


// ============================================================ round-trip

test('round-trip: state → hash → state → 同 state', () => {
  const original = defState({
    userFilter: 7, sort: 'hot', q: '搜尋詞', kindFilter: 'mandala',
  });
  const hash = stateToHash(original);
  const recovered = parseHash(hash);
  // 比對只保留可往返欄位
  assert.deepEqual(recovered, {
    userFilter: 7, sort: 'hot', q: '搜尋詞', kindFilter: 'mandala',
    deepLinkUploadId: null,
  });
});

test('round-trip: empty state ↔ empty hash', () => {
  assert.equal(stateToHash(defState()), '');
  assert.deepEqual(parseHash(''), emptyPatch());
  // double round-trip
  const hash = stateToHash(defState({}));
  assert.deepEqual(parseHash(hash), emptyPatch());
});

test('round-trip: special chars (& = #) 安全', () => {
  // & = % # 都是 URL 特殊符
  const tricky = 'a&b=c%d#e';
  const original = defState({ q: tricky });
  const hash = stateToHash(original);
  const recovered = parseHash(hash);
  assert.equal(recovered.q, tricky);
});


// ============================================================ r29g: upload key

test('stateToHash: deepLinkUploadId=99 → #upload=99', () => {
  assert.equal(
    stateToHash(defState({ deepLinkUploadId: 99 })),
    '#upload=99',
  );
});

test('stateToHash: deepLinkUploadId 跟 user/sort 並存', () => {
  // 順序：user, sort, q, kind, upload — 等同 set 順序
  const got = stateToHash(defState({
    userFilter: 5, sort: 'likes', deepLinkUploadId: 99,
  }));
  assert.equal(got, '#user=5&sort=likes&upload=99');
});

test('stateToHash: deepLinkUploadId=0 / 負數 / 字串 不寫', () => {
  assert.equal(stateToHash(defState({ deepLinkUploadId: 0 })),     '');
  assert.equal(stateToHash(defState({ deepLinkUploadId: -1 })),    '');
  assert.equal(stateToHash(defState({ deepLinkUploadId: 1.5 })),   '');
  assert.equal(stateToHash(defState({ deepLinkUploadId: 'abc' })), '');
});

test('parseHash: #upload=123 → deepLinkUploadId=123', () => {
  const p = parseHash('#upload=123');
  assert.equal(p.deepLinkUploadId, 123);
  assert.equal(p.userFilter, null);
  assert.equal(p.sort, 'newest');
});

test('parseHash: 惡意 upload=<script> → null', () => {
  assert.equal(parseHash('#upload=<script>').deepLinkUploadId, null);
  assert.equal(parseHash('#upload=-1').deepLinkUploadId, null);
  assert.equal(parseHash('#upload=0').deepLinkUploadId, null);
  assert.equal(parseHash('#upload=1.5').deepLinkUploadId, null);
});

test('round-trip r29g: state with upload → hash → state', () => {
  const original = defState({
    userFilter: 7, sort: 'hot', q: '搜尋', kindFilter: 'mandala',
    deepLinkUploadId: 999,
  });
  const recovered = parseHash(stateToHash(original));
  assert.deepEqual(recovered, {
    userFilter: 7, sort: 'hot', q: '搜尋', kindFilter: 'mandala',
    deepLinkUploadId: 999,
  });
});
