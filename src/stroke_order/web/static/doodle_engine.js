/* ============================================================
 * doodle_engine.js — Phase 5ca/5cb 塗鴉模式前端化
 *
 * 在瀏覽器內把「圖片 → 線稿 SVG」整段管線前端化，調參即時
 * 預覽、圖片不出本機。核心為純函式（吃 TypedArray），瀏覽器與
 * node 皆可執行 —— node 端用於與 Python 實作做 parity 驗證。
 *
 * 引擎表 DoodleEngines：
 *   browser — 5ca：復刻 exporters/doodle.py 的簡筆畫管線
 *   opencv  — 5cb：OpenCV.js WASM（CDN 惰性載入），自適應二值化
 *             ＋形態學去斑＋輪廓抽取＋approxPolyDP 簡化，
 *             高解析（預設 1000px）平滑線稿
 *   server  — POST /api/doodle（保底／API 相容）
 *
 * browser 管線與 Python 的對應：
 *   grayscale      ← PIL convert("L")   （Pillow L24 定點公式）
 *   autocontrast   ← ImageOps.autocontrast(cutoff=2)
 *   findEdges      ← ImageFilter.FIND_EDGES（3×3 Laplacian，邊界複製）
 *   rleRows        ← _rle_rows
 *   contentBbox    ← _content_bbox      （auto_crop 去空白）
 *   peelBorder     ← _peel_border       （auto_crop 剝外框）
 *   buildDoodleSvg ← render_doodle_svg  （同結構 SVG，mm 契約一致）
 * ============================================================ */
(function (root) {
"use strict";

/* ------------------------------------------------------------
 * 純函式核心（無 DOM 依賴；node 可直接 require）
 * ------------------------------------------------------------ */

/** RGBA（已壓平到白底）→ 灰階。Pillow 定點公式：
 *  L = (R*19595 + G*38470 + B*7471 + 0x8000) >> 16 */
function grayscale(rgba, w, h) {
  var out = new Uint8Array(w * h);
  for (var i = 0, p = 0; i < out.length; i++, p += 4) {
    out[i] = (rgba[p] * 19595 + rgba[p + 1] * 38470 +
              rgba[p + 2] * 7471 + 0x8000) >> 16;
  }
  return out;
}

/** ImageOps.autocontrast(gray, cutoff)。cutoff 為百分比（單值，
 *  低高兩端各截同量），LUT 用 int() 截斷，與 Pillow 一致。 */
function autocontrast(gray, cutoff) {
  cutoff = cutoff === undefined ? 2 : cutoff;
  var hist = new Array(256).fill(0);
  var i;
  for (i = 0; i < gray.length; i++) hist[gray[i]]++;
  var n = gray.length;
  if (cutoff) {
    var cut = Math.floor(n * cutoff / 100);
    var lo0, hi0;
    for (lo0 = 0; lo0 < 256; lo0++) {
      if (cut > hist[lo0]) { cut -= hist[lo0]; hist[lo0] = 0; }
      else { hist[lo0] -= cut; cut = 0; }
      if (cut <= 0) break;
    }
    cut = Math.floor(n * cutoff / 100);
    for (hi0 = 255; hi0 >= 0; hi0--) {
      if (cut > hist[hi0]) { cut -= hist[hi0]; hist[hi0] = 0; }
      else { hist[hi0] -= cut; cut = 0; }
      if (cut <= 0) break;
    }
  }
  var lo, hi;
  for (lo = 0; lo < 256 && !hist[lo]; lo++) {}
  for (hi = 255; hi >= 0 && !hist[hi]; hi--) {}
  var out = new Uint8Array(gray.length);
  if (hi <= lo) { out.set(gray); return out; }
  var scale = 255.0 / (hi - lo);
  var offset = -lo * scale;
  var lut = new Uint8Array(256);
  for (i = 0; i < 256; i++) {
    var v = Math.trunc(i * scale + offset);
    lut[i] = v < 0 ? 0 : (v > 255 ? 255 : v);
  }
  for (i = 0; i < gray.length; i++) out[i] = lut[gray[i]];
  return out;
}

/** ImageFilter.FIND_EDGES：3×3 kernel(-1×8, 中心 8)，scale=1、
 *  offset=0、夾到 0..255；最外一圈像素照 Pillow 慣例原樣複製。 */
function findEdges(gray, w, h) {
  var out = new Uint8Array(gray);          // 邊界 = 原值
  for (var y = 1; y < h - 1; y++) {
    for (var x = 1; x < w - 1; x++) {
      var c = y * w + x;
      var s = 8 * gray[c]
            - gray[c - w - 1] - gray[c - w] - gray[c - w + 1]
            - gray[c - 1]                  - gray[c + 1]
            - gray[c + w - 1] - gray[c + w] - gray[c + w + 1];
      out[c] = s < 0 ? 0 : (s > 255 ? 255 : s);
    }
  }
  return out;
}

/** edges > threshold（嚴格大於）→ 逐列 RLE。
 *  回傳 [y, xStart, xEndExclusive] 陣列。 */
function rleRows(edges, w, h, threshold) {
  var runs = [];
  for (var y = 0; y < h; y++) {
    var base = y * w;
    var inRun = false, start = 0;
    for (var x = 0; x < w; x++) {
      var on = edges[base + x] > threshold;
      if (on && !inRun) { inRun = true; start = x; }
      else if (!on && inRun) { inRun = false; runs.push([y, start, x]); }
    }
    if (inRun) runs.push([y, start, w]);
  }
  return runs;
}

/** _content_bbox：非空白像素外框。回傳 [L,T,R,B]（R/B exclusive）
 *  或 null（整張空白）。 */
function contentBbox(gray, w, h, whitespaceThreshold) {
  var L = w, T = h, R = -1, B = -1;
  for (var y = 0; y < h; y++) {
    for (var x = 0; x < w; x++) {
      if (gray[y * w + x] <= whitespaceThreshold) {
        if (x < L) L = x;
        if (x > R) R = x;
        if (y < T) T = y;
        if (y > B) B = y;
      }
    }
  }
  if (R < 0) return null;
  return [L, T, R + 1, B + 1];
}

/** _peel_border：從四邊迭代剝除「暗像素占比 ≥ minRatio」的框線列/行。
 *  回傳 [top, bottom, left, right] 剝除量。gray 視圖以 (offX,offY,sw,sh)
 *  指定子區域，避免複製大陣列。 */
function peelBorder(gray, w, offX, offY, sw, sh, opts) {
  var dark = opts.darknessThreshold, minRatio = opts.minRatio,
      maxPeel = opts.maxPeelPx;
  var top = 0, bottom = 0, left = 0, right = 0;
  function ratioRow(y, x0, x1) {
    var cnt = 0;
    for (var x = x0; x < x1; x++) if (gray[y * w + x] <= dark) cnt++;
    return cnt / (x1 - x0);
  }
  function ratioCol(x, y0, y1) {
    var cnt = 0;
    for (var y = y0; y < y1; y++) if (gray[y * w + x] <= dark) cnt++;
    return cnt / (y1 - y0);
  }
  for (;;) {
    if (sh - top - bottom < 4 || sw - left - right < 4) break;
    if (top >= maxPeel && bottom >= maxPeel &&
        left >= maxPeel && right >= maxPeel) break;
    var y0 = offY + top, y1 = offY + sh - bottom;
    var x0 = offX + left, x1 = offX + sw - right;
    var dTop = ratioRow(y0, x0, x1);
    var dBot = ratioRow(y1 - 1, x0, x1);
    var dLeft = ratioCol(x0, y0, y1);
    var dRight = ratioCol(x1 - 1, y0, y1);
    var peeled = false;
    if (dTop >= minRatio && top < maxPeel) { top++; peeled = true; }
    if (dBot >= minRatio && bottom < maxPeel) { bottom++; peeled = true; }
    if (dLeft >= minRatio && left < maxPeel) { left++; peeled = true; }
    if (dRight >= minRatio && right < maxPeel) { right++; peeled = true; }
    if (!peeled) break;
  }
  return [top, bottom, left, right];
}

/** auto_crop_image 的裁切框計算（不動像素，只回傳 [L,T,R,B]）。
 *  與 Python 同參數預設：whitespace 240 / darkness 100 /
 *  ratio 0.5 / maxPeel 40。 */
function autoCropBox(gray, w, h, trimWhitespace, removeBorder) {
  if (!trimWhitespace && !removeBorder) return [0, 0, w, h];
  var L = 0, T = 0, R = w, B = h;
  if (trimWhitespace) {
    var bbox = contentBbox(gray, w, h, 240);
    if (bbox === null) return [0, 0, w, h];   // 全空白：不裁
    L = bbox[0]; T = bbox[1]; R = bbox[2]; B = bbox[3];
  }
  if (removeBorder && R - L >= 4 && B - T >= 4) {
    var p = peelBorder(gray, w, L, T, R - L, B - T,
        {darknessThreshold: 100, minRatio: 0.5, maxPeelPx: 40});
    var pt = p[0], pb = p[1], pl = p[2], pr = p[3];
    L += pl; T += pt; R -= pr; B -= pb;
    if ((pt || pb || pl || pr) && trimWhitespace &&
        R - L >= 2 && B - T >= 2) {
      // 框內再去一次空白（掃描框常有白邊）
      var inner = contentBbox2(gray, w, L, T, R, B, 240);
      if (inner !== null) {
        var ll = inner[0], tt = inner[1], rr = inner[2], bb = inner[3];
        L = L + ll; T = T + tt;
        R = L + (rr - ll); B = T + (bb - tt);
      }
    }
  }
  L = Math.max(0, Math.min(L, w - 1));
  T = Math.max(0, Math.min(T, h - 1));
  R = Math.max(L + 1, Math.min(R, w));
  B = Math.max(T + 1, Math.min(B, h));
  return [L, T, R, B];
}

/** contentBbox 的子區域版（座標相對子區域左上）。 */
function contentBbox2(gray, w, x0, y0, x1, y1, thr) {
  var L = x1 - x0, T = y1 - y0, R = -1, B = -1;
  for (var y = y0; y < y1; y++) {
    for (var x = x0; x < x1; x++) {
      if (gray[y * w + x] <= thr) {
        var rx = x - x0, ry = y - y0;
        if (rx < L) L = rx;
        if (rx > R) R = rx;
        if (ry < T) T = ry;
        if (ry > B) B = ry;
      }
    }
  }
  if (R < 0) return null;
  return [L, T, R + 1, B + 1];
}

function xmlEscape(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
                  .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/* ---- SVG 共用幾何（5cb 抽出，供 browser／opencv 兩引擎共用；
 *      數學與 Python render_doodle_svg 完全一致） ---- */
function canvasGeom(w, h, opts) {
  var canvasWidthMm = opts.canvasWidthMm || 150.0;
  var marginMm = opts.marginMm === undefined ? 10.0 : opts.marginMm;
  var aspect = h / w;
  var innerW = canvasWidthMm - 2 * marginMm;
  var innerH = innerW * aspect;
  var canvasHeightMm = opts.canvasHeightMm;
  if (canvasHeightMm === undefined || canvasHeightMm === null) {
    canvasHeightMm = innerH + 2 * marginMm;
  } else {
    var availH = canvasHeightMm - 2 * marginMm;
    if (innerH > availH) { innerH = availH; innerW = innerH / aspect; }
  }
  return {
    canvasWidthMm: canvasWidthMm, canvasHeightMm: canvasHeightMm,
    marginMm: marginMm, sx: innerW / w, sy: innerH / h,
  };
}

function svgHeader(g, background) {
  return ['<svg xmlns="http://www.w3.org/2000/svg" ' +
          'viewBox="0 0 ' + g.canvasWidthMm + ' ' + g.canvasHeightMm + '" ' +
          'width="' + g.canvasWidthMm + 'mm" height="' +
          g.canvasHeightMm + 'mm">',
          '<rect x="0" y="0" width="' + g.canvasWidthMm +
          '" height="' + g.canvasHeightMm +
          '" fill="' + xmlEscape(background || "white") + '"/>'];
}

function annotationsSvg(annotations) {
  if (!annotations || !annotations.length) return "";
  var ann = ['<g class="annotations" font-family="sans-serif">'];
  for (var a = 0; a < annotations.length; a++) {
    var an = annotations[a];
    if (!an.text) continue;
    ann.push('<text x="' + an.x_mm + '" y="' + an.y_mm +
             '" font-size="' + (an.size_mm === undefined ? 3.0 : an.size_mm) +
             '" fill="' + xmlEscape(an.color || "#666") + '">' +
             xmlEscape(an.text) + '</text>');
  }
  ann.push("</g>");
  return ann.join("");
}

/** render_doodle_svg 的組裝段：吃已備妥的灰階（已 autocontrast），
 *  產出與 Python 同結構的 SVG 字串（mm 實體尺寸契約一致）。 */
function buildDoodleSvg(gray, w, h, opts) {
  var threshold = opts.threshold === undefined ? 50 : opts.threshold;
  var lineColor = opts.lineColor || "#222";
  var lineWidth = opts.lineWidth === undefined ? 0.4 : opts.lineWidth;

  var edges = findEdges(gray, w, h);
  var runs = rleRows(edges, w, h, threshold);
  var g = canvasGeom(w, h, opts);
  var sx = g.sx, sy = g.sy;

  var parts = svgHeader(g, opts.background);
  parts.push('<g transform="translate(' + g.marginMm + ',' + g.marginMm +
             ')" stroke="' + xmlEscape(lineColor) + '" fill="none" ' +
             'stroke-width="' + lineWidth + '" stroke-linecap="round">');
  for (var i = 0; i < runs.length; i++) {
    var y = runs[i][0], xs = runs[i][1], xe = runs[i][2];
    var x1 = xs * sx, x2 = xe * sx, ym = (y + 0.5) * sy;
    if (xe - xs === 1) {
      parts.push('<circle cx="' + (x1 + sx / 2).toFixed(2) +
                 '" cy="' + ym.toFixed(2) +
                 '" r="' + (sx * 0.4).toFixed(2) +
                 '" fill="' + xmlEscape(lineColor) + '" stroke="none"/>');
    } else {
      parts.push('<line x1="' + x1.toFixed(2) + '" y1="' + ym.toFixed(2) +
                 '" x2="' + x2.toFixed(2) + '" y2="' + ym.toFixed(2) + '"/>');
    }
  }
  parts.push("</g>");
  parts.push(annotationsSvg(opts.annotations));  // 空註解 → 空字串
  parts.push("</svg>");
  return parts.join("\n");
}

/** 5cb：輪廓折線 → SVG。polys = [{points:[[x,y],…], closed:bool}]，
 *  座標為處理解析度像素；畫布幾何與 buildDoodleSvg 同一套 mm 契約。 */
function contoursToSvg(polys, w, h, opts) {
  var lineColor = opts.lineColor || "#222";
  var lineWidth = opts.lineWidth === undefined ? 0.4 : opts.lineWidth;
  var g = canvasGeom(w, h, opts);
  var parts = svgHeader(g, opts.background);
  parts.push('<g transform="translate(' + g.marginMm + ',' + g.marginMm +
             ')" stroke="' + xmlEscape(lineColor) + '" fill="none" ' +
             'stroke-width="' + lineWidth + '" stroke-linecap="round" ' +
             'stroke-linejoin="round">');
  for (var i = 0; i < polys.length; i++) {
    var pts = polys[i].points;
    if (pts.length < 2) continue;
    var d = ["M", (pts[0][0] * g.sx).toFixed(2) + "," +
                  (pts[0][1] * g.sy).toFixed(2)];
    for (var j = 1; j < pts.length; j++) {
      d.push("L", (pts[j][0] * g.sx).toFixed(2) + "," +
                  (pts[j][1] * g.sy).toFixed(2));
    }
    if (polys[i].closed) d.push("Z");
    parts.push('<path d="' + d.join(" ") + '"/>');
  }
  parts.push("</g>");
  parts.push(annotationsSvg(opts.annotations));
  parts.push("</svg>");
  return parts.join("\n");
}

/* ------------------------------------------------------------
 * 5cg：centerline 骨架化三件組（純函式；OpenCV.js 標準版無
 * ximgproc.thinning，自刻 Zhang-Suen——品質優於 erode 迴圈法）
 * ------------------------------------------------------------ */

/** Zhang-Suen 細線化。bin：0/1 Uint8Array（不改動原陣列），
 *  回傳 1px 寬骨架（0/1）。maxIter 為保險上限。 */
function zhangSuenThin(bin, w, h, maxIter) {
  maxIter = maxIter || 500;
  var img = Uint8Array.from(bin);
  var kill = [];
  for (var iter = 0; iter < maxIter; iter++) {
    var changed = false;
    for (var step = 0; step < 2; step++) {
      kill.length = 0;
      for (var y = 1; y < h - 1; y++) {
        for (var x = 1; x < w - 1; x++) {
          var c = y * w + x;
          if (!img[c]) continue;
          var p2 = img[c - w],     p3 = img[c - w + 1],
              p4 = img[c + 1],     p5 = img[c + w + 1],
              p6 = img[c + w],     p7 = img[c + w - 1],
              p8 = img[c - 1],     p9 = img[c - w - 1];
          var B = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9;
          if (B < 2 || B > 6) continue;
          var A = ((p2 === 0 && p3 === 1) ? 1 : 0) +
                  ((p3 === 0 && p4 === 1) ? 1 : 0) +
                  ((p4 === 0 && p5 === 1) ? 1 : 0) +
                  ((p5 === 0 && p6 === 1) ? 1 : 0) +
                  ((p6 === 0 && p7 === 1) ? 1 : 0) +
                  ((p7 === 0 && p8 === 1) ? 1 : 0) +
                  ((p8 === 0 && p9 === 1) ? 1 : 0) +
                  ((p9 === 0 && p2 === 1) ? 1 : 0);
          if (A !== 1) continue;
          if (step === 0) {
            if (p2 * p4 * p6 !== 0 || p4 * p6 * p8 !== 0) continue;
          } else {
            if (p2 * p4 * p8 !== 0 || p2 * p6 * p8 !== 0) continue;
          }
          kill.push(c);
        }
      }
      if (kill.length) {
        changed = true;
        for (var i = 0; i < kill.length; i++) img[kill[i]] = 0;
      }
    }
    if (!changed) break;
  }
  return img;
}

/** 1px 骨架 → 折線集合（圖論版）。
 *
 *  兩個關鍵：
 *  1. **對角修剪**：對角鄰接若存在正交「墊腳石」（同列或同行的
 *     中繼像素）即為冗餘邊——不剪會在轉角/階梯處製造假交叉點，
 *     把一條線碎成多段還畫出重複段。
 *  2. **邊訪問**：以「邊」為訪問單位（而非像素），天然去重；
 *     deg≠2 的節點（端點/交叉點）為路徑斷點，殘餘未訪問邊
 *     即純環。
 *
 *  回傳 [[[x,y],…], …]；環的首尾同點。 */
function traceCenterlines(skel, w, h) {
  var N = w * h;
  var adj = new Array(N);                 // c → [鄰居 c…]（修剪後）
  var y, x, c, k;
  for (y = 0; y < h; y++) {
    for (x = 0; x < w; x++) {
      c = y * w + x;
      if (!skel[c]) continue;
      var lst = [];
      for (var dy = -1; dy <= 1; dy++) {
        for (var dx = -1; dx <= 1; dx++) {
          if (!dx && !dy) continue;
          var nx = x + dx, ny = y + dy;
          if (nx < 0 || nx >= w || ny < 0 || ny >= h) continue;
          if (!skel[ny * w + nx]) continue;
          if (dx && dy) {                  // 對角：有墊腳石就修剪
            if (skel[y * w + nx] || skel[ny * w + x]) continue;
          }
          lst.push(ny * w + nx);
        }
      }
      adj[c] = lst;
    }
  }
  var seen = new Set();                    // 邊 key：min*N + max
  function ekey(a, b) { return a < b ? a * N + b : b * N + a; }
  function toXY(cc) { return [cc % w, (cc / w) | 0]; }

  function walk(start, next) {
    var pts = [toXY(start), toXY(next)];
    seen.add(ekey(start, next));
    var prev = start, cur = next;
    while (adj[cur].length === 2) {
      var nxt = adj[cur][0] === prev ? adj[cur][1] : adj[cur][0];
      if (seen.has(ekey(cur, nxt))) break; // 環回到起點
      seen.add(ekey(cur, nxt));
      pts.push(toXY(nxt));
      prev = cur; cur = nxt;
    }
    return pts;
  }

  var paths = [];
  // Pass 1：從端點/交叉點（deg≠2）出發
  for (c = 0; c < N; c++) {
    if (!adj[c] || adj[c].length === 2) continue;
    for (k = 0; k < adj[c].length; k++) {
      if (seen.has(ekey(c, adj[c][k]))) continue;
      paths.push(walk(c, adj[c][k]));
    }
  }
  // Pass 2：純環（全 deg==2、邊未訪問）
  for (c = 0; c < N; c++) {
    if (!adj[c] || adj[c].length !== 2) continue;
    if (seen.has(ekey(c, adj[c][0])) && seen.has(ekey(c, adj[c][1]))) {
      continue;
    }
    var nb = seen.has(ekey(c, adj[c][0])) ? adj[c][1] : adj[c][0];
    var loop = walk(c, nb);
    if (loop.length >= 3) {
      loop.push(toXY(c));                  // 閉合回起點
      paths.push(loop);
    }
  }
  return paths;
}

/** 純 JS Ramer–Douglas–Peucker 折線簡化（迭代式，避免深遞迴）。 */
function rdpSimplify(pts, eps) {
  if (eps <= 0 || pts.length < 3) return pts;
  var keep = new Uint8Array(pts.length);
  keep[0] = 1; keep[pts.length - 1] = 1;
  var stack = [[0, pts.length - 1]];
  while (stack.length) {
    var seg = stack.pop();
    var s = seg[0], e = seg[1];
    var ax = pts[s][0], ay = pts[s][1];
    var bx = pts[e][0], by = pts[e][1];
    var dx = bx - ax, dy = by - ay;
    var len = Math.sqrt(dx * dx + dy * dy) || 1e-12;
    var maxD = -1, maxI = -1;
    for (var i = s + 1; i < e; i++) {
      var d = Math.abs(dy * pts[i][0] - dx * pts[i][1] +
                       bx * ay - by * ax) / len;
      if (d > maxD) { maxD = d; maxI = i; }
    }
    if (maxD > eps) {
      keep[maxI] = 1;
      stack.push([s, maxI], [maxI, e]);
    }
  }
  var out = [];
  for (var j = 0; j < pts.length; j++) if (keep[j]) out.push(pts[j]);
  return out;
}

/* ------------------------------------------------------------
 * 瀏覽器 adapter：File → 解碼 → auto_crop → 縮圖 → 核心管線
 * ------------------------------------------------------------ */

var _cache = {file: null, bitmap: null, gray: null, w: 0, h: 0};

function _makeCanvas(w, h) {
  if (typeof OffscreenCanvas !== "undefined") return new OffscreenCanvas(w, h);
  var c = document.createElement("canvas");
  c.width = w; c.height = h;
  return c;
}

async function _decode(file) {
  if (_cache.file === file && _cache.bitmap && _cache.gray) return _cache;
  var bitmap = (_cache.file === file && _cache.bitmap)
    ? _cache.bitmap : await createImageBitmap(file);
  var w = bitmap.width, h = bitmap.height;
  var ctx = _makeCanvas(w, h).getContext("2d", {willReadFrequently: true});
  ctx.fillStyle = "#fff";                 // RGBA 壓平到白底
  ctx.fillRect(0, 0, w, h);
  ctx.drawImage(bitmap, 0, 0);
  var rgba = ctx.getImageData(0, 0, w, h).data;
  _cache = {file: file, bitmap: bitmap,
            gray: grayscale(rgba, w, h), w: w, h: h};
  return _cache;
}

/** 裁切＋縮圖到 maxSide，回傳 {imageData, w, h}（白底壓平）。
 *
 *  5ci 快徑：未勾自動裁切時，直接把 bitmap 縮到目標大小——
 *  跳過全解析度 getImageData（4000px 照片＝64MB buffer）與
 *  16M 像素灰階迴圈，大照片省數秒且不佔記憶體。 */
async function _cropAndScale(file, opts, maxSide) {
  var needCrop = !!opts.autoCropWhitespace || !!opts.autoCropBorder;
  var box, srcW, srcH, bitmap;
  if (needCrop) {
    var dec = await _decode(file);
    bitmap = dec.bitmap;
    box = autoCropBox(dec.gray, dec.w, dec.h,
                      !!opts.autoCropWhitespace, !!opts.autoCropBorder);
  } else {
    bitmap = (_cache.file === file && _cache.bitmap)
      ? _cache.bitmap : await createImageBitmap(file);
    if (_cache.file !== file) {
      _cache = {file: file, bitmap: bitmap, gray: null,
                w: bitmap.width, h: bitmap.height};
    }
    box = [0, 0, bitmap.width, bitmap.height];
  }
  var cw = box[2] - box[0], ch = box[3] - box[1];
  var scale = maxSide / Math.max(cw, ch);
  var tw = cw, th = ch;
  if (scale < 1.0) { tw = Math.trunc(cw * scale); th = Math.trunc(ch * scale); }
  var ctx = _makeCanvas(tw, th).getContext("2d", {willReadFrequently: true});
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";     // 近似 LANCZOS
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, tw, th);
  ctx.drawImage(bitmap, box[0], box[1], cw, ch, 0, 0, tw, th);
  return {imageData: ctx.getImageData(0, 0, tw, th), w: tw, h: th};
}

/** browser 引擎主入口。opts 對齊 /api/doodle 的表單欄位。 */
async function renderInBrowser(file, opts) {
  var t0 = performance.now();
  var s = await _cropAndScale(file, opts, opts.maxSidePx || 200);
  var gray = autocontrast(grayscale(s.imageData.data, s.w, s.h), 2);
  var svg = buildDoodleSvg(gray, s.w, s.h, {
    canvasWidthMm: opts.canvasWidthMm,
    threshold: opts.threshold,
    lineColor: opts.lineColor,
    lineWidth: opts.lineWidth,
    annotations: opts.annotations,
  });
  return {svg: svg, ms: performance.now() - t0};
}

/* ------------------------------------------------------------
 * 5cb：OpenCV.js 引擎（CDN 惰性載入）
 * ------------------------------------------------------------ */

// 5ch：4.10.0 路徑實測 404（5cb pin 錯，引擎從未成功載入——三層
// 降級把它掩蓋成「還能用」）。改 pin 實測存在的 4.9.0，並以 4.x
// （官方最新）作備援，逐一重試。
// 5cj：使用者校網實測 docs.opencv.org 被防火牆靜默丟包（連
// onerror 都等不到）——首位改「同源」：本伺服器 /vendor/opencv.js
// 代抓＋快取，使用者連得上本站就載得到引擎；外部 CDN 降為備援。
// 5cl：第二位加 jsDelivr 鏡像——@techstark/opencv-js 的
// dist/opencv.js 是官方 4.9.0 原檔；校網擋 docs.opencv.org 時
// cdn.jsdelivr.net 常是放行的。
// 5cm：同源位址「絕對化」——相對路徑在 blob/巢狀 worker 的
// base URL 解析不可靠（blob 基底直接 SyntaxError），且實機解剖
// 顯示正式 worker 內相對路徑 importScripts 無限懸掛、絕對 URL
// 3/3 成功。node（無 location）維持相對字串。
var _ORIGIN = (typeof location !== "undefined" && location.origin &&
               location.origin !== "null") ? location.origin : "";
// 5da：4.9.0-release.3 的 WASM runtime init 在新版 Chrome（149
// 家用機實測）永久懸掛——importScripts 數百 ms 完成、cv Promise
// 永不 resolve；微型 WASM 同機秒過＝非 WASM 封鎖；4.11.0-release.1
// 同機同管道 759ms 完整就緒。先前「受管理電腦環境層懸掛」的判定
// 極可能一直就是這個版本不相容。pin 升 4.11（同源 /vendor 由
// 伺服器端同步升級，快取檔名帶版本自動失效舊檔）。
// docs.opencv.org 退出清單：實測只掛 4.9.0/4.13.0（4.11.0 回
// 404）、校網又靜默丟包——同源＋jsDelivr 已足。
// 5db：同源 URL 帶版本 query——5da 部署驗收抓到第三層快取：
// /vendor/opencv.js 有 max-age=604800，瀏覽器 HTTP 快取的舊
// 4.9 回應在 pin 升級後仍命中（no-store 實測伺服器已 serve
// 4.11、裸 URL 仍回 4.9 舊 bytes；帶 query 343ms 就緒）。
// query 版本與 server 的 _OPENCV_CACHE_FNAME 同步升級。
var OPENCV_CDN_URLS = [
  _ORIGIN + "/vendor/opencv.js?v=4.11.0",
  "https://cdn.jsdelivr.net/npm/@techstark/opencv-js@4.11.0-release.1" +
    "/dist/opencv.js",
];
var OPENCV_CDN_URL = OPENCV_CDN_URLS[0];   // 向後相容（測試引用）
var _cvPromise = null;

/** cv 物件初始化收尾（promise 型／onRuntimeInitialized 型皆相容）。 */
function _resolveCv(resolve, reject) {
  var cv = root.cv;
  if (cv && typeof cv.then === "function") {
    cv.then(function (m) { root.cv = m; resolve(m); }, reject);
  } else if (cv && cv.Mat) {
    resolve(cv);
  } else if (cv) {
    cv.onRuntimeInitialized = function () { resolve(cv); };
  } else {
    reject(new Error("OpenCV.js 載入後未取得 cv 物件"));
  }
}

/* 5cm：worker 端下載改 fetch——importScripts 是同步阻塞、
 * 無法逾時，遇到防火牆「靜默丟包」（連錯誤都不回）就是永久
 * 懸掛；且實機解剖顯示正式 worker 內它對本檔莫名卡死。
 * fetch 可設 chunk 間隔逾時、可回報下載進度（MB）。 */
var OPENCV_FETCH_STALL_MS = 15000;   // 相鄰 chunk 間隔上限

async function _fetchScript(url, onStatus) {
  var ctrl = new AbortController();
  var stall = null;
  function bump() {
    if (stall) clearTimeout(stall);
    stall = setTimeout(function () { ctrl.abort(); },
                       OPENCV_FETCH_STALL_MS);
  }
  bump();
  try {
    var resp = await fetch(url, {signal: ctrl.signal});
    if (!resp.ok) throw new Error("HTTP " + resp.status + ": " + url);
    if (!resp.body || !resp.body.getReader) {
      var txt = await resp.text();
      clearTimeout(stall);
      return txt;
    }
    var reader = resp.body.getReader();
    var chunks = [], got = 0, lastMb = 0;
    for (;;) {
      var r = await reader.read();
      if (r.done) break;
      bump();
      chunks.push(r.value);
      got += r.value.length;
      var mb = (got / (1 << 20)) | 0;
      if (onStatus && mb > lastMb) {
        lastMb = mb;
        onStatus("下載 OpenCV.js… " + mb + " MB");
      }
    }
    clearTimeout(stall);
    var buf = new Uint8Array(got), off = 0;
    for (var i = 0; i < chunks.length; i++) {
      buf.set(chunks[i], off);
      off += chunks[i].length;
    }
    return new TextDecoder("utf-8").decode(buf);
  } catch (e) {
    if (stall) clearTimeout(stall);
    throw e;
  }
}

/** 惰性載入 OpenCV.js（僅載一次；相容 promise 型與
 *  onRuntimeInitialized 型兩種官方初始化介面）。
 *  5cf：Worker 與主執行緒分流；5cm：Worker 走 fetch＋間接 eval
 *  （全域作用域，UMD 設 globalThis.cv），主執行緒 script tag
 *  加 20s 逾時（silent-drop 防火牆下 onerror 永不觸發）。 */
function _loadCvFromUrl(url, onStatus) {
  return new Promise(function (resolve, reject) {
    if (onStatus) {
      // 5ci：講清楚「會等多久」——首次下載＋WASM 編譯視網速
      // 可達數十秒，沒有這句就是「無回應」體感
      onStatus("下載＋編譯 OpenCV.js（首次約 10MB，之後走快取）… " + url);
    }
    if (typeof document === "undefined") {           // Worker（5cf/5cm/5co）
      // 5co：fetch 只當「看門狗＋進度＋HTTP 快取暖身」（可逾時、
      // 可觀察；擋掉 silent-drop 防火牆的永久懸掛），實際執行改回
      // importScripts(絕對 URL)——5cm 的 10MB 間接 eval 在引擎情境
      // 實測會 CPU 懸掛（Chrome 解剖：同字串 inline eval 216ms、
      // 引擎內直跑無限卡；absolute importScripts 全日 4/4 穩定）。
      // fetch 成功後 importScripts 讀同 URL＝快取命中，不再碰網路。
      _fetchScript(url, onStatus).then(function (code) {
        try {
          if (code.length < 1_000_000) {
            throw new Error("opencv.js 過小：" + code.length);
          }
          if (onStatus) onStatus("編譯 OpenCV.js（WASM 初始化）…");
          importScripts(url);
          _resolveCv(resolve, reject);
        } catch (e) { reject(e); }
      }, reject);
      return;
    }
    var tag = document.createElement("script");
    var timer = setTimeout(function () {             // 5cm：逾時保險
      tag.onload = tag.onerror = null;
      reject(new Error("OpenCV.js 載入逾時（20s）：" + url));
    }, 20000);
    tag.src = url;
    tag.async = true;
    tag.onerror = function () {
      clearTimeout(timer);
      reject(new Error("OpenCV.js 載入失敗：" + url));
    };
    tag.onload = function () {
      clearTimeout(timer);
      _resolveCv(resolve, reject);
    };
    document.head.appendChild(tag);
  });
}

function loadOpenCV(onStatus) {
  if (_cvPromise) return _cvPromise;
  _cvPromise = (async function () {
    var lastErr = null;
    for (var i = 0; i < OPENCV_CDN_URLS.length; i++) {
      try {
        return await _loadCvFromUrl(OPENCV_CDN_URLS[i], onStatus);
      } catch (e) {
        lastErr = e;
        if (typeof console !== "undefined") {
          console.warn("OpenCV.js CDN 失敗，換下一個來源:", e);
        }
      }
    }
    _cvPromise = null;                              // 全滅：下次可重試
    throw lastErr || new Error("OpenCV.js 所有 CDN 來源皆載入失敗");
  })();
  return _cvPromise;
}

/** opencv 引擎主入口。cvOpts：
 *  mode("outline"|"canny") / blockSize / c / invert /
 *  simplifyPx / minArea / maxProcSide */
async function renderInOpenCV(file, opts) {
  var t0 = performance.now();
  var cv = await loadOpenCV(opts.onStatus);
  var cvo = opts.cv || {};
  var mode = cvo.mode || "outline";
  var maxProcSide = cvo.maxProcSide || 1000;
  if (opts.onStatus) opts.onStatus("解碼與縮圖…");
  var s = await _cropAndScale(file, opts, maxProcSide);
  if (opts.onStatus) opts.onStatus("二值化與輪廓抽取…");

  var src = cv.matFromImageData(s.imageData);
  var gray = new cv.Mat();
  var bin = new cv.Mat();
  var contours = new cv.MatVector();
  var hierarchy = new cv.Mat();
  var kernel = null;
  try {
    cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);
    cv.GaussianBlur(gray, gray, new cv.Size(3, 3), 0);   // 輕度降噪

    if (mode === "canny") {
      var thr = opts.threshold === undefined ? 50 : opts.threshold;
      cv.Canny(gray, bin, thr, thr * 3);
    } else {
      var bs = Math.max(3, (cvo.blockSize || 25) | 1);   // 強制奇數
      var C = cvo.c === undefined ? 10 : cvo.c;
      cv.adaptiveThreshold(
        gray, bin, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C,
        cvo.invert ? cv.THRESH_BINARY : cv.THRESH_BINARY_INV, bs, C);
      kernel = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(3, 3));
      cv.morphologyEx(bin, bin, cv.MORPH_OPEN, kernel);  // 去斑
    }

    if (mode === "centerline") {
      // 5cg：骨架化中心線——雷射每條線只走一次（outline 會沿筆畫
      // 兩側各切一刀）。Zhang-Suen 在高解析下計算量大，由 5cf 的
      // Worker 承接；這裡照樣回報進度。
      if (opts.onStatus) opts.onStatus("骨架化中…（中心線模式）");
      var b01 = new Uint8Array(s.w * s.h);
      var bd = bin.data;
      for (var bi = 0; bi < b01.length; bi++) b01[bi] = bd[bi] ? 1 : 0;
      var skel = zhangSuenThin(b01, s.w, s.h);
      var traced = traceCenterlines(skel, s.w, s.h);
      var minLen = cvo.minArea === undefined ? 30 : cvo.minArea;
      var eps2 = cvo.simplifyPx === undefined ? 1.5 : cvo.simplifyPx;
      var cpolys = [];
      for (var ti = 0; ti < traced.length; ti++) {
        var tp = traced[ti];
        if (tp.length < 2 || tp.length < minLen) continue;
        cpolys.push({points: eps2 > 0 ? rdpSimplify(tp, eps2) : tp,
                     closed: false});
      }
      var csvg = contoursToSvg(cpolys, s.w, s.h, {
        canvasWidthMm: opts.canvasWidthMm,
        lineColor: opts.lineColor,
        lineWidth: opts.lineWidth,
        annotations: opts.annotations,
      });
      return {svg: csvg, ms: performance.now() - t0};
    }

    cv.findContours(bin, contours, hierarchy,
                    cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE);

    var closed = mode !== "canny";
    var minArea = cvo.minArea === undefined ? 30 : cvo.minArea;
    var eps = cvo.simplifyPx === undefined ? 1.5 : cvo.simplifyPx;
    var polys = [];
    for (var i = 0; i < contours.size(); i++) {
      var cnt = contours.get(i);
      var keep = closed
        ? cv.contourArea(cnt) >= minArea
        : cv.arcLength(cnt, false) >= minArea;   // canny：以長度濾雜訊
      if (keep) {
        var use = cnt;
        var approx = null;
        if (eps > 0) {
          approx = new cv.Mat();
          cv.approxPolyDP(cnt, approx, eps, closed);
          use = approx;
        }
        var pts = [];
        for (var j = 0; j < use.data32S.length; j += 2) {
          pts.push([use.data32S[j], use.data32S[j + 1]]);
        }
        if (pts.length >= 2) polys.push({points: pts, closed: closed});
        if (approx) approx.delete();
      }
      cnt.delete();
    }
    if (opts.onStatus) {
      opts.onStatus("組裝 SVG（" + polys.length + " 條路徑）…");
    }
    var svg = contoursToSvg(polys, s.w, s.h, {
      canvasWidthMm: opts.canvasWidthMm,
      lineColor: opts.lineColor,
      lineWidth: opts.lineWidth,
      annotations: opts.annotations,
    });
    return {svg: svg, ms: performance.now() - t0, paths: polys.length};
  } finally {
    src.delete(); gray.delete(); bin.delete();
    contours.delete(); hierarchy.delete();
    if (kernel) kernel.delete();
  }
}

/* ------------------------------------------------------------
 * 引擎表
 * ------------------------------------------------------------ */

var DoodleEngines = {
  browser: {
    id: "browser",
    label: "瀏覽器（即時預覽）",
    live: true,
    available: function () {
      return typeof createImageBitmap !== "undefined";
    },
    render: renderInBrowser,
  },
  opencv: {
    id: "opencv",
    label: "OpenCV（輪廓向量化）",
    live: true,
    available: function () {
      // 5cf：主執行緒（有 document）或 Worker（有 importScripts）皆可
      return (typeof document !== "undefined" ||
              typeof importScripts === "function") &&
             typeof createImageBitmap !== "undefined";
    },
    render: renderInOpenCV,
  },
  server: {
    id: "server",
    label: "伺服器",
    live: false,
    available: function () { return true; },
    render: async function (file, opts) {
      var t0 = performance.now();
      var fd = new FormData();
      fd.append("image", file);
      fd.append("canvas_width_mm", opts.canvasWidthMm);
      fd.append("max_side_px", opts.maxSidePx);
      fd.append("threshold", opts.threshold);
      fd.append("line_color", opts.lineColor);
      fd.append("line_width", opts.lineWidth);
      fd.append("auto_crop_whitespace", opts.autoCropWhitespace ? "true" : "false");
      fd.append("auto_crop_border", opts.autoCropBorder ? "true" : "false");
      fd.append("annotations_json", JSON.stringify(opts.annotations || []));
      var r = await fetch(opts.apiBase + "/api/doodle",
                          {method: "POST", body: fd});
      if (!r.ok) {
        var err = await r.json().catch(function () {
          return {detail: r.statusText};
        });
        throw new Error(err.detail || ("HTTP " + r.status));
      }
      return {svg: await r.text(), ms: performance.now() - t0};
    },
  },
};

/* ------------------------------------------------------------
 * 5cf：Web Worker 卸載 —— renderVia() 統一入口
 *
 * 降級階梯：Worker 可用 → worker 跑（主執行緒零卡頓）；
 * Worker 建立/執行失敗 → 主執行緒直跑（5ca/5cb 引擎原地可用）；
 * 前端引擎整組失敗 → UI 層再退伺服器（既有 fallback）。
 * ------------------------------------------------------------ */

var WORKER_URL = "/static/doodle_worker.js?v=161";   // 5db cache-bust
var _worker = null;
var _workerBroken = false;
var _msgSeq = 0;
var _pending = new Map();

function workerSupported() {
  return !_workerBroken &&
         typeof Worker !== "undefined" &&
         typeof OffscreenCanvas !== "undefined" &&
         typeof document !== "undefined";     // 只在主執行緒開 worker
}

function _getWorker() {
  if (_worker) return _worker;
  _worker = new Worker(WORKER_URL);
  _worker.onmessage = function (ev) {
    var m = ev.data || {};
    var p = _pending.get(m.id);
    if (!p) return;
    if (m.status !== undefined) {              // 進度轉發（如 opencv 載入）
      if (p.bump) p.bump();                    // 5cm：有進度＝還活著
      if (p.onStatus) p.onStatus(m.status);
      return;
    }
    if (p.clearStall) p.clearStall();          // 5cm：收尾解除看門狗
    _pending.delete(m.id);
    if (m.ok) {
      p.resolve({svg: m.svg, ms: m.ms, paths: m.paths, via: "worker"});
    } else {
      p.reject(new Error(m.error || "worker render failed"));
    }
  };
  _worker.onerror = function (e) {
    _workerBroken = true;                      // 之後一律主執行緒直跑
    _pending.forEach(function (p) {
      if (p.clearStall) p.clearStall();        // 5cm
      p.reject(new Error("worker error: " + (e && e.message || e)));
    });
    _pending.clear();
    try { _worker.terminate(); } catch (_e) { /* noop */ }
    _worker = null;
  };
  return _worker;
}

/** 統一渲染入口：優先 Worker，失敗回主執行緒。
 *  回傳 {svg, ms, via: "worker"|"main"}。 */
async function renderVia(engineId, file, opts) {
  var eng = DoodleEngines[engineId];
  if (!eng) throw new Error("unknown doodle engine: " + engineId);
  if (engineId !== "server" && workerSupported()) {
    try {
      var id = ++_msgSeq;
      var w = _getWorker();
      return await new Promise(function (resolve, reject) {
        // 5cm：進度看門狗——沒有任何訊息（進度或收尾）就視為 worker
        // 懸掛（實測校網 silent-drop／受管理電腦環境層會讓執行端永久
        // 卡住而無例外），terminate 後回主執行緒降級。每收到一則訊息
        // 重計時。5cp：90s → 30s（正常各階段間隔實測 < 3s，30s 已是
        // 極保守；受管理電腦上使用者不該等超過半分鐘）。
        var stall = null;
        function bump() {
          if (stall) clearTimeout(stall);
          stall = setTimeout(function () {
            _pending.delete(id);
            _workerBroken = true;
            try { _worker && _worker.terminate(); } catch (e2) { /* noop */ }
            _worker = null;
            reject(new Error("worker 逾時無回應（30s）"));
          }, 30000);
        }
        function clearStall() { if (stall) clearTimeout(stall); }
        bump();
        _pending.set(id, {resolve: resolve, reject: reject,
                          onStatus: opts.onStatus,
                          bump: bump, clearStall: clearStall});
        var send = {};                         // function 欄位不可 clone
        for (var k in opts) {
          if (typeof opts[k] !== "function") send[k] = opts[k];
        }
        w.postMessage({id: id, engine: engineId, file: file, opts: send});
      });
    } catch (e) {
      if (typeof console !== "undefined") {
        console.warn("doodle worker fallback to main thread:", e);
      }
      if (engineId === "opencv") {
        // 5cr：opencv 不退主執行緒——會讓 worker 懸掛的機器
        // （環境層卡大型腳本執行），主執行緒執行同樣懸掛；而主
        // 執行緒一凍，timer 全停、看門狗無效，等於整頁凍死
        // （使用者本機伺服器實測「網頁無回應」）。直接把錯誤
        // 拋給 UI 層退伺服器引擎＋記 sessionStorage 失敗記憶。
        throw e;
      }
    }
  }
  var direct = await eng.render(file, opts);
  direct.via = "main";
  return direct;
}

var api = {
  DoodleEngines: DoodleEngines,
  OPENCV_CDN_URL: OPENCV_CDN_URL,
  WORKER_URL: WORKER_URL,
  loadOpenCV: loadOpenCV,
  renderVia: renderVia,
  workerSupported: workerSupported,
  // 純函式核心（node parity／單元測試用）
  grayscale: grayscale,
  autocontrast: autocontrast,
  findEdges: findEdges,
  rleRows: rleRows,
  contentBbox: contentBbox,
  peelBorder: peelBorder,
  autoCropBox: autoCropBox,
  buildDoodleSvg: buildDoodleSvg,
  contoursToSvg: contoursToSvg,
  canvasGeom: canvasGeom,
  // 5cg centerline 三件組
  zhangSuenThin: zhangSuenThin,
  traceCenterlines: traceCenterlines,
  rdpSimplify: rdpSimplify,
};

if (typeof module !== "undefined" && module.exports) {
  module.exports = api;               // node（parity 驗證）
} else {
  root.DoodleEngine = api;            // 瀏覽器
}
})(typeof self !== "undefined" ? self : this);
