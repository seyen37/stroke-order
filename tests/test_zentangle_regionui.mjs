// Phase 5di — 縮圖鈕互動模型回歸鎖（驗收回饋修正）.
//
// Run: node --test tests/test_zentangle_regionui.mjs
//
// zentangle.js 是 DOM glue、無法直接 import 測行為，這裡鎖「原始碼結構
// 契約」（同 5cm/5cf 的斷言鎖哲學）：
//   1. setRegionTangle 未選取時要套用到全部區段（不再只丟提示）
//   2. clearRegions 改「全部留白」語意——不得再整批刪區段/清暫存，
//      且要自動退出 ✂ 切分模式
//   3. index.html 的 zentangle.js 要帶 ?v= 版本 query（§11.4 快取鍵紀律）
//      且與本輪版號一致

import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {dirname, join} from "node:path";
import {fileURLToPath} from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const ZJS = readFileSync(
  join(ROOT, "src/stroke_order/web/static/zentangle/zentangle.js"), "utf8");
const INDEX = readFileSync(
  join(ROOT, "src/stroke_order/web/static/index.html"), "utf8");

/** 取出 `function name(...) {...}` 的完整本體（大括號配對）。 */
function fnBody(src, name) {
  const start = src.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `function ${name} not found`);
  let i = src.indexOf("{", start);
  let depth = 0;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth += 1;
    else if (src[i] === "}") {
      depth -= 1;
      if (depth === 0) return src.slice(start, i + 1);
    }
  }
  throw new Error(`unbalanced braces in ${name}`);
}

test("5di: setRegionTangle 未選取＝套用全部區段", () => {
  const body = fnBody(ZJS, "setRegionTangle");
  assert.match(body, /for \(const region of _regions\) region\.tangle = key/,
    "未選取時必須迴圈套用到全部區段");
  assert.match(body, /全部區段/,
    "套用全部後要有明確狀態回饋");
});

test("5di: clearRegions ＝全部留白、非刪除；退出切分模式", () => {
  const body = fnBody(ZJS, "clearRegions");
  assert.doesNotMatch(body, /_regionStash\[mode\] = null/,
    "清除不得再清暫存（會回到「點什麼都沒反應」死路）");
  assert.doesNotMatch(body, /_regions = \[\]/,
    "清除不得整批刪區段（保留結構讓縮圖立即可再上圖樣）");
  assert.match(body, /region\.tangle = null/,
    "清除＝把每個區段設為留白");
  assert.match(body, /setSplitMode\(false\)/,
    "清除要自動退出 ✂ 切分模式");
});

test("§11.4: index.html 載入 zentangle.js 帶版本 query 且 ≥180", () => {
  const m = INDEX.match(/zentangle\/zentangle\.js\?v=(\d+)/);
  assert.ok(m, "zentangle.js 必須帶 ?v= cache-busting query");
  assert.ok(parseInt(m[1], 10) >= 183, `?v=${m[1]} 應 ≥ 183（5dj-3）`);
});
