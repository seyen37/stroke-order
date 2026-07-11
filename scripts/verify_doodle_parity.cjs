/* Phase 5ca — doodle_engine.js × Python parity 驗證（node 側）
 * 用法：node scripts/verify_doodle_parity.cjs
 * 產出 /tmp/parity_js.json，再跑 scripts/verify_doodle_parity.py 比對。 */
const path = require("path");
const eng = require(path.join(__dirname, "..", "src", "stroke_order",
                              "web", "static", "doodle_engine.js"));

// ---- Image A: 160x120 RGB 程序合成（黑矩形＋灰圓＋斜線＋漸層帶） ----
const W = 160, H = 120;
const rgba = new Uint8ClampedArray(W * H * 4).fill(255);
function setpx(x, y, v) {
  const p = (y * W + x) * 4;
  rgba[p] = v; rgba[p + 1] = v; rgba[p + 2] = v; rgba[p + 3] = 255;
}
for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
  let v = null;
  if (x >= 30 && x < 60 && y >= 20 && y < 50) v = 0;
  else if ((x - 110) ** 2 + (y - 60) ** 2 <= 625) v = 128;
  else if (x - y === 10 && x >= 10 && x < 80) v = 0;
  else if (y >= 90 && y < 110) v = Math.trunc(x * 255 / 159);
  if (v !== null) setpx(x, y, v);
}
const gray = eng.autocontrast(eng.grayscale(rgba, W, H), 2);
const svg = eng.buildDoodleSvg(gray, W, H,
  {canvasWidthMm: 150, threshold: 50, lineColor: "#222", lineWidth: 0.4});

// ---- Image B: 200x150 灰階，外框＋主體，驗 autoCropBox ----
const W2 = 200, H2 = 150;
const g2 = new Uint8Array(W2 * H2).fill(255);
for (let y = 0; y < H2; y++) for (let x = 0; x < W2; x++) {
  const onFrame = ((y === 30 || y === 31 || y === 118 || y === 119) &&
                   x >= 40 && x < 160) ||
                  ((x === 40 || x === 41 || x === 158 || x === 159) &&
                   y >= 30 && y < 120);
  if (onFrame) g2[y * W2 + x] = 0;
  else if (x >= 80 && x < 120 && y >= 60 && y < 90) g2[y * W2 + x] = 50;
}
const box = eng.autoCropBox(g2, W2, H2, true, true);
require("fs").writeFileSync("/tmp/parity_js.json",
                            JSON.stringify({svg, box}));
console.log("js ok, box=", box, "svg bytes=", svg.length);
