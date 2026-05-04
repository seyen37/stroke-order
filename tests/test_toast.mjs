// ======================================================================
// Phase 5b r29h: toast _toastSpec validator unit tests (Node node:test).
//
// Run:
//   node --test tests/test_toast.mjs
//
// 只測純 logic（_toastSpec）— DOM 操作 (showToast 主體) 走 manual E2E。
// ======================================================================

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { _toastSpec } from '../src/stroke_order/web/static/gallery/toast.mjs';


// ============================================================ type validation

test('_toastSpec: default type = info', () => {
  const s = _toastSpec('hello');
  assert.equal(s.type, 'info');
  assert.equal(s.classNames, 'gl-toast gl-toast--info');
});

test('_toastSpec: 3 valid types preserved', () => {
  for (const type of ['info', 'warning', 'error']) {
    const s = _toastSpec('m', type);
    assert.equal(s.type, type);
    assert.equal(s.classNames, `gl-toast gl-toast--${type}`);
  }
});

test('_toastSpec: invalid type → fallback info', () => {
  for (const bad of ['success', 'random', '', null, undefined, 123]) {
    const s = _toastSpec('m', bad);
    assert.equal(s.type, 'info', `bad type=${JSON.stringify(bad)}`);
  }
});


// ============================================================ duration validation

test('_toastSpec: default duration = 5000', () => {
  const s = _toastSpec('m');
  assert.equal(s.duration, 5000);
});

test('_toastSpec: custom duration preserved', () => {
  assert.equal(_toastSpec('m', 'info', 1000).duration, 1000);
  assert.equal(_toastSpec('m', 'info', 12345).duration, 12345);
});

test('_toastSpec: invalid duration → fallback 5000', () => {
  for (const bad of [0, -1, NaN, Infinity, -Infinity, null, undefined, 'abc']) {
    const s = _toastSpec('m', 'info', bad);
    assert.equal(s.duration, 5000, `bad duration=${JSON.stringify(bad)}`);
  }
});


// ============================================================ message handling

test('_toastSpec: message coerced to string', () => {
  assert.equal(_toastSpec('hello').message, 'hello');
  assert.equal(_toastSpec(42).message, '42');
  // null/undefined → empty string（避免 'null' / 'undefined' 字面）
  assert.equal(_toastSpec(null).message, '');
  assert.equal(_toastSpec(undefined).message, '');
  assert.equal(_toastSpec().message, '');
});

test('_toastSpec: message 不 escape（DOM 端用 textContent 自動防 XSS）', () => {
  // toast.mjs 把 message 賦給 textContent，不 innerHTML — 故 spec 不需 escape
  const s = _toastSpec('<script>alert(1)</script>');
  assert.equal(s.message, '<script>alert(1)</script>');
});


// ============================================================ shape

test('_toastSpec: returns expected 4-key shape', () => {
  const s = _toastSpec('m', 'warning', 3000);
  assert.deepEqual(Object.keys(s).sort(),
    ['classNames', 'duration', 'message', 'type']);
});
