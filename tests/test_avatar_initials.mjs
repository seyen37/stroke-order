// Phase 5b r29j: avatar.mjs _initialsSpec pure logic tests (Node).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { _initialsSpec } from '../src/stroke_order/web/static/gallery/avatar.mjs';


test('_initialsSpec: display_name 第一字 (中文)', () => {
  const s = _initialsSpec({ id: 1, email: 'a@t', display_name: '王小明' });
  assert.equal(s.char, '王');
});

test('_initialsSpec: display_name 第一字 (英文 → 大寫)', () => {
  const s = _initialsSpec({ id: 1, email: 'a@t', display_name: 'alice' });
  assert.equal(s.char, 'A');
});

test('_initialsSpec: display_name 空 → email handle 第一字', () => {
  const s = _initialsSpec({ id: 1, email: 'bob@example.com' });
  assert.equal(s.char, 'B');
});

test('_initialsSpec: 全空 → "?"', () => {
  const s = _initialsSpec({});
  assert.equal(s.char, '?');
  assert.equal(_initialsSpec(null).char, '?');
});

test('_initialsSpec: 同 user_id 永遠同色（stable hash）', () => {
  const s1 = _initialsSpec({ id: 42, email: 'x@y' });
  const s2 = _initialsSpec({ id: 42, email: 'different@email' });
  // 即使其他欄位不同，只要 id 相同色就一樣
  assert.equal(s1.color, s2.color);
});

test('_initialsSpec: 不同 id 通常不同色（distribution check）', () => {
  // 8 種 palette，跑 50 個 id 應該至少打中 4 種以上不同色
  const colors = new Set();
  for (let i = 1; i <= 50; i++) {
    colors.add(_initialsSpec({ id: i, email: `u${i}@t` }).color);
  }
  assert.ok(colors.size >= 4, `expected ≥4 distinct colors, got ${colors.size}`);
});

test('_initialsSpec: color always from palette (8 fixed)', () => {
  const PALETTE = [
    '#5b8def', '#36a64f', '#ec407a', '#fb8c00',
    '#7e57c2', '#26a69a', '#d4af37', '#e53935',
  ];
  for (let i = 1; i <= 30; i++) {
    const s = _initialsSpec({ id: i, email: 't@t' });
    assert.ok(PALETTE.includes(s.color),
      `${s.color} not in palette for id=${i}`);
  }
});

test('_initialsSpec: 中文 surrogate pair 安全切（取 1 字）', () => {
  // 𠮷 是 U+20BB7，在 UTF-16 是 surrogate pair
  const s = _initialsSpec({ id: 1, email: 't@t', display_name: '𠮷田' });
  // [...str][0] 應拿到 '𠮷' (整個 grapheme)，不是壞掉的 high surrogate
  assert.equal(s.char, '𠮷');
});
