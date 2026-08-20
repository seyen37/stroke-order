// ======================================================================
// W4 分級選字 — 純邏輯層 node 測試（同 test_hash_route.mjs 慣例）。
//
// Run:  node --test tests/test_grid_freq_core.mjs
//
// 只測 pickByRank / pickHint：夾限、截尾、空表防禦、誠實標示措辭。
// 資料契約（chars 順序 ≡ frequency_rank）在 pytest 那邊鎖。
// ======================================================================

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  MAX_PICK, pickByRank, pickHint,
} from '../src/stroke_order/web/static/modes/grid_freq_core.mjs';

const CHARS = Array.from({ length: 100 }, (_, i) => String(i + 1));

test('pickByRank: 基本切片——第 5 名起取 3 字', () => {
  const p = pickByRank(CHARS, 5, 3);
  assert.deepEqual(p.chars, ['5', '6', '7']);
  assert.equal(p.from, 5);
  assert.equal(p.to, 7);
});

test('pickByRank: from=1 是第一名（1-based，無 off-by-one）', () => {
  const p = pickByRank(CHARS, 1, 2);
  assert.deepEqual(p.chars, ['1', '2']);
});

test('pickByRank: 表尾截短——to 反映實得，不虛報', () => {
  const p = pickByRank(CHARS, 99, 10);
  assert.deepEqual(p.chars, ['99', '100']);
  assert.equal(p.to, 100);
});

test('pickByRank: from 夾回 [1, 表長]', () => {
  assert.equal(pickByRank(CHARS, 0, 5).from, 1);
  assert.equal(pickByRank(CHARS, -3, 5).from, 1);
  assert.equal(pickByRank(CHARS, 9999, 5).from, 100);
});

test('pickByRank: count 夾回 [1, MAX_PICK]', () => {
  assert.equal(pickByRank(CHARS, 1, 0).chars.length, 1);
  assert.equal(pickByRank(CHARS, 1, 9999).chars.length, MAX_PICK);
});

test('pickByRank: 非數字輸入不炸——from 退 1、count 退 1', () => {
  const p = pickByRank(CHARS, 'abc', 'xyz');
  assert.equal(p.from, 1);
  assert.deepEqual(p.chars, ['1']);
});

test('pickByRank: 小數截整（表單 number 仍可能給 3.7）', () => {
  const p = pickByRank(CHARS, 3.7, 2.9);
  assert.equal(p.from, 3);
  assert.equal(p.chars.length, 2);
});

test('pickByRank: 空表／非陣列回 null', () => {
  assert.equal(pickByRank([], 1, 5), null);
  assert.equal(pickByRank(null, 1, 5), null);
  assert.equal(pickByRank('abc', 1, 5), null);
});

test('pickByRank: 不改輸入陣列', () => {
  const arr = ['a', 'b', 'c'];
  pickByRank(arr, 1, 2);
  assert.deepEqual(arr, ['a', 'b', 'c']);
});

test('MAX_PICK = 40（與 /api/grid chars 上限 parity——pytest 另鎖）', () => {
  assert.equal(MAX_PICK, 40);
});

test('pickHint: 講名次與字數，且否認年級', () => {
  const p = pickByRank(CHARS, 5, 3);
  const h = pickHint(p, CHARS.length);
  assert.match(h, /第 5–7 名/);
  assert.match(h, /共 3 字/);
  assert.match(h, /不代表年級難度/);
});
