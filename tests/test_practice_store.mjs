// 5ew-R3：共用儲存層轉換器（純函式）——node --test 直測
// trace（EM 2048 六元組）↔ user-dict（純 [x,y]）雙向轉換契約。
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  TRACE_EM, traceStrokesToUserDict, swStrokesToTraceStrokes,
} from "../src/stroke_order/web/static/handwriting/storage.js";

test("TRACE_EM＝2048（與 canvas.js EM_SIZE、卡片 glyphs 同一座標系）", () => {
  assert.equal(TRACE_EM, 2048);
});

test("traceStrokesToUserDict：六元組點列 → 純 [x,y]；短筆畫（<2 點）剔除", () => {
  const traces = [
    { points: [[10, 20, 0, 0.5, 0, 0], [30, 40, 16, 0.7, 1, 2]] },
    { points: [[99, 99, 0, 0.5, 0, 0]] },              // 1 點＝誤觸，剔除
    { points: [[1, 2, 0, 0.5, 0, 0], [3, 4, 8, 0.6, 0, 0],
               [5, 6, 16, 0.6, 0, 0]] },
  ];
  const out = traceStrokesToUserDict(traces);
  assert.equal(out.length, 2);
  assert.deepEqual(out[0], [[10, 20], [30, 40]]);
  assert.deepEqual(out[1], [[1, 2], [3, 4], [5, 6]]);
});

test("traceStrokesToUserDict：空／缺 points 防禦", () => {
  assert.deepEqual(traceStrokesToUserDict([]), []);
  assert.deepEqual(traceStrokesToUserDict(null), []);
  assert.deepEqual(traceStrokesToUserDict([{}]), []);
});

test("swStrokesToTraceStrokes：canvas 像素 → EM 2048 等比縮放", () => {
  // 360px 畫布：(180,90) → (1024,512)
  const out = swStrokesToTraceStrokes([[[180, 90], [360, 360]]], 360, 360);
  assert.equal(out.length, 1);
  const pts = out[0].points;
  assert.equal(pts[0][0], 1024);
  assert.equal(pts[0][1], 512);
  assert.equal(pts[1][0], 2048);
  assert.equal(pts[1][1], 2048);
});

test("swStrokesToTraceStrokes：六元組形狀（t=0、壓力 0.5——誠實降階不捏造時序）", () => {
  const out = swStrokesToTraceStrokes([[[0, 0], [10, 10]]], 2048, 2048);
  for (const p of out[0].points) {
    assert.equal(p.length, 6);
    assert.equal(p[2], 0);      // t
    assert.equal(p[3], 0.5);    // pressure
  }
  assert.equal(out[0].duration_ms, 0);
  assert.deepEqual(out[0].pen_down_at, [0, 0]);
  assert.deepEqual(out[0].pen_up_at, [10, 10]);
  assert.equal(out[0].device, "unknown");
});

test("swStrokesToTraceStrokes：短筆畫剔除＋座標夾在 [0, 2048]", () => {
  const out = swStrokesToTraceStrokes(
    [[[9, 9]], [[-50, 0], [400, 400]]], 360, 360);
  assert.equal(out.length, 1);                 // 1 點筆畫剔除
  assert.equal(out[0].points[0][0], 0);        // -50 夾回 0
  assert.equal(out[0].points[1][0], 2048);     // 超界夾回 2048
});

test("round-trip：sw → trace → user-dict 折線點數守恆", () => {
  const sw = [[[10, 10], [50, 50], [90, 90]]];
  const trace = swStrokesToTraceStrokes(sw, 100, 100);
  const back = traceStrokesToUserDict(trace);
  assert.equal(back.length, 1);
  assert.equal(back[0].length, 3);
  // 100px 畫布 → EM：x10 → 204.8
  assert.ok(Math.abs(back[0][0][0] - 204.8) < 1e-9);
});
