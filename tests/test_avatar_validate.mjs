// Phase 5b r29k: validateAvatarFile pure logic tests (Node).
//
// Mirror server-side rules from gallery/service.py:
//   - type ∈ {image/png, image/jpeg}
//   - size ≤ 2 MB
//   - size > 0

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  validateAvatarFile, AVATAR_MAX_SIZE_BYTES,
} from '../src/stroke_order/web/static/gallery/avatar.mjs';


test('validateAvatarFile: PNG 1KB → ok', () => {
  const r = validateAvatarFile({ type: 'image/png', size: 1024 });
  assert.equal(r.ok, true);
  assert.equal(r.error, undefined);
});

test('validateAvatarFile: JPEG 500KB → ok', () => {
  const r = validateAvatarFile({ type: 'image/jpeg', size: 500 * 1024 });
  assert.equal(r.ok, true);
});

test('validateAvatarFile: GIF → reject (PNG/JPEG only)', () => {
  const r = validateAvatarFile({ type: 'image/gif', size: 1024 });
  assert.equal(r.ok, false);
  assert.match(r.error, /PNG|JPEG/);
});

test('validateAvatarFile: text/plain → reject', () => {
  const r = validateAvatarFile({ type: 'text/plain', size: 1024 });
  assert.equal(r.ok, false);
});

test('validateAvatarFile: 3MB > 2MB limit → reject', () => {
  const r = validateAvatarFile({
    type: 'image/png', size: 3 * 1024 * 1024,
  });
  assert.equal(r.ok, false);
  assert.match(r.error, /MB|超過|大小/);
});

test('validateAvatarFile: 邊界 — 恰 2MB → ok', () => {
  const r = validateAvatarFile({
    type: 'image/png', size: AVATAR_MAX_SIZE_BYTES,
  });
  assert.equal(r.ok, true);
});

test('validateAvatarFile: 0 bytes → reject', () => {
  const r = validateAvatarFile({ type: 'image/png', size: 0 });
  assert.equal(r.ok, false);
  assert.match(r.error, /空|empty/);
});

test('validateAvatarFile: null/undefined → reject', () => {
  assert.equal(validateAvatarFile(null).ok, false);
  assert.equal(validateAvatarFile(undefined).ok, false);
});

test('validateAvatarFile: charset 後綴不影響 (image/png; charset=...)', () => {
  // 某些 browser 偶爾帶 charset 後綴
  const r = validateAvatarFile({
    type: 'image/png; charset=binary', size: 1024,
  });
  assert.equal(r.ok, true);
});
