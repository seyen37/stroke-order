// v0.14.299 P2 — static/myfont/core.mjs 純邏輯。node --test tests/test_myfont_core.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  MAX_NAME_CHARS, MAX_TOTAL_CHARS, parseChars, thinTrack, traceToTracks,
  buildPayload, latestByChar, fontFileName,
} from '../src/stroke_order/web/static/myfont/core.mjs';

test('常數：名字 6 字、總數 100 字', () => {
  assert.equal(MAX_NAME_CHARS, 6);
  assert.equal(MAX_TOTAL_CHARS, 100);
});

test('parseChars：依序去重、去空白控制字元、surrogate pair 不拆', () => {
  assert.deepEqual(parseChars(' 王小明 王\t'), ['王', '小', '明']);
  assert.deepEqual(parseChars('𪚥𪚥a'), ['𪚥', 'a']);
  assert.deepEqual(parseChars(''), []);
  assert.deepEqual(parseChars(null), []);
  assert.deepEqual(parseChars('\u0007王'), ['王']);
});

test('thinTrack：保留首尾、丟近點', () => {
  assert.deepEqual(thinTrack([[0,0],[1,1],[2,2],[10,0],[11,0],[30,0]]),
                   [[0,0],[10,0],[30,0]]);
  assert.deepEqual(thinTrack([[0,0],[1,1]]), [[0,0],[1,1]]);
  assert.deepEqual(thinTrack([]), []);
});

test('thinTrack：密集取樣大幅精簡、形狀端點守恆', () => {
  const dense = Array.from({length: 1001}, (_, i) => [i * 2, 1000]);   // 每 2 單位一點
  const t = thinTrack(dense);
  assert.ok(t.length < 400, `應精簡：${t.length}`);
  assert.deepEqual(t[0], [0, 1000]);
  assert.deepEqual(t[t.length - 1], [2000, 1000]);
});

test('traceToTracks：六元組→[x,y]、輕觸剔除', () => {
  const tr = [{points: [[0,0,0,.5,0,0],[100,0,5,.5,0,0]]}, {points: [[5,5,0,.5,0,0]]}];
  assert.deepEqual(traceToTracks(tr), [[[0,0],[100,0]]]);
});

test('buildPayload：沒有有效筆畫的字列入 skipped', () => {
  const { body, skipped } = buildPayload({
    '王': [{points: [[0,0,0],[500,0,1]]}],
    '小': [{points: [[1,1,0]]}],
  }, { weight: 180, owner: '王小' });
  assert.deepEqual(Object.keys(body.chars), ['王']);
  assert.deepEqual(skipped, ['小']);
  assert.equal(body.weight, 180);
  assert.equal(body.cap, 'round');
  assert.equal(body.owner, '王小');
});

test('latestByChar：只挑想要的字、取最新、忽略空筆畫', () => {
  const traces = [
    {char: '王', ts: '2026-10-01T00:00:00Z', strokes: [{points: [[1,1]]}]},
    {char: '王', ts: '2026-10-19T00:00:00Z', strokes: [{points: [[2,2]]}]},
    {char: '小', ts: '2026-10-19T00:00:00Z', strokes: []},
    {char: '明', ts: '2026-10-19T00:00:00Z', strokes: [{points: [[3,3]]}]},
  ];
  const out = latestByChar(traces, ['王', '小']);
  assert.deepEqual(Object.keys(out), ['王']);
  assert.deepEqual(out['王'], [{points: [[2,2]]}]);
});

test('fontFileName：去除檔名非法字元與空白', () => {
  assert.equal(fontFileName('王 小/明'), '王小明_手寫字型.ttf');
  assert.equal(fontFileName(''), '手寫字型.ttf');
});
