/* ============================================================
 * doodle_engine.js — Phase 5ca 塗鴉模式前端化
 *
 * 在瀏覽器內復刻 exporters/doodle.py 的完整管線，讓調參即時
 * 預覽、圖片不出本機。核心為純函式（吃 TypedArray），瀏覽器與
 * node 皆可執行 —— node 端用於與 Python 實作做 parity 驗證。
 *
 * 管線（與 Python 一一對應）：
 *   grayscale      ← PIL convert("L")   （Pillow L24 定點公式）
 *   autocontrast   ← ImageOps.autocontrast(cutoff=2)
 *   findEdges      ← ImageFilter.FIND_EDGES（3×3 Laplacian，邊界複製）
 *   rleRows        ← _rle_rows
 *   contentBbox    ← _content_bbox      （auto_crop 去空白）
 *   peelBorder     ← _peel_border       （auto_crop 剝外框）
 *   buildDoodleSvg ← render_doodle_svg  （同結構 SVG，mm 契約一致）
 *
 * 引擎表 DoodleEngines：browser（本檔）/ server（POST /api/doodle）。
 * Phase 5cb 預計掛入 opencv（OpenCV.js WASM，VectorLine 等級品質）。
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

/** render_doodle_svg 的組裝段：吃已備妥的灰階（已 autocontrast），
 *  產出與 Python 同結構的 SVG 字串（mm 實體尺寸契約一致）。 */
function buildDoodleSvg(gray, w, h, opts) {
  var canvasWidthMm = opts.canvasWidthMm || 150.0;
  var threshold = opts.threshold === undefined ? 50 : opts.threshold;
  var lineColor = opts.lineColor || "#222";
  var lineWidth = opts.lineWidth === undefined ? 0.4 : opts.lineWidth;
  var background = opts.background || "white";
  var marginMm = opts.marginMm === undefined ? 10.0 : opts.marginMm;
  var annotations = opts.annotations || [];

  var edges = findEdges(gray, w, h);
  var runs = rleRows(edges, w, h, threshold);

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
  var sx = innerW / w, sy = innerH / h;

  var parts = [
    '<svg xmlns="http://www.w3.org/2000/svg" ' +
    'viewBox="0 0 ' + canvasWidthMm + ' ' + canvasHeightMm + '" ' +
    'width="' + canvasWidthMm + 'mm" height="' + canvasHeightMm + 'mm">'
  ];
  parts.push('<rect x="0" y="0" width="' + canvasWidthMm +
             '" height="' + canvasHeightMm +
             '" fill="' + xmlEscape(background) + '"/>');
  parts.push('<g transform="translate(' + marginMm + ',' + marginMm + ')" ' +
             'stroke="' + xmlEscape(lineColor) + '" fill="none" ' +
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
  if (annotations.length) {
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
    parts.push(ann.join(""));
  } else {
    parts.push("");   // Python 端空註解仍 join 一個空字串
  }
  parts.push("</svg>");
  return parts.join("\n");
}

/* ------------------------------------------------------------
 * 瀏覽器 adapter：File → 解碼 → auto_crop → 縮圖 → 核心管線
 * ------------------------------------------------------------ */

var _cache = {file: null, bitmap: null, gray: null, w: 0, h: 0};

async function _decode(file) {
  if (_cache.file === file && _cache.bitmap) return _cache;
  var bitmap = await createImageBitmap(file);
  var w = bitmap.width, h = bitmap.height;
  var cv = (typeof OffscreenCanvas !== "undefined")
    ? new OffscreenCanvas(w, h)
    : (function () { var c = document.createElement("canvas");
                     c.width = w; c.height = h; return c; })();
  var ctx = cv.getContext("2d", {willReadFrequently: true});
  ctx.fillStyle = "#fff";                 // RGBA 壓平到白底
  ctx.fillRect(0, 0, w, h);
  ctx.drawImage(bitmap, 0, 0);
  var rgba = ctx.getImageData(0, 0, w, h).data;
  _cache = {file: file, bitmap: bitmap,
            gray: grayscale(rgba, w, h), w: w, h: h};
  return _cache;
}

/** 瀏覽器引擎主入口。opts 對齊 /api/doodle 的表單欄位。 */
async function renderInBrowser(file, opts) {
  var t0 = performance.now();
  var dec = await _decode(file);
  var box = autoCropBox(dec.gray, dec.w, dec.h,
                        !!opts.autoCropWhitespace, !!opts.autoCropBorder);
  var cw = box[2] - box[0], ch = box[3] - box[1];

  // 縮圖：int(w*scale)，僅縮不放，與 Python _prepare 一致
  var maxSide = opts.maxSidePx || 200;
  var scale = maxSide / Math.max(cw, ch);
  var tw = cw, th = ch;
  if (scale < 1.0) { tw = Math.trunc(cw * scale); th = Math.trunc(ch * scale); }

  var cv = (typeof OffscreenCanvas !== "undefined")
    ? new OffscreenCanvas(tw, th)
    : (function () { var c = document.createElement("canvas");
                     c.width = tw; c.height = th; return c; })();
  var ctx = cv.getContext("2d", {willReadFrequently: true});
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";     // 近似 LANCZOS
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, tw, th);
  ctx.drawImage(dec.bitmap, box[0], box[1], cw, ch, 0, 0, tw, th);
  var rgba = ctx.getImageData(0, 0, tw, th).data;

  var gray = autocontrast(grayscale(rgba, tw, th), 2);
  var svg = buildDoodleSvg(gray, tw, th, {
    canvasWidthMm: opts.canvasWidthMm,
    threshold: opts.threshold,
    lineColor: opts.lineColor,
    lineWidth: opts.lineWidth,
    annotations: opts.annotations,
  });
  return {svg: svg, ms: performance.now() - t0};
}

/* ------------------------------------------------------------
 * 引擎表（Phase 5cb 將掛入 opencv 引擎）
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

var api = {
  DoodleEngines: DoodleEngines,
  // 純函式核心（node parity 測試用）
  grayscale: grayscale,
  autocontrast: autocontrast,
  findEdges: findEdges,
  rleRows: rleRows,
  contentBbox: contentBbox,
  peelBorder: peelBorder,
  autoCropBox: autoCropBox,
  buildDoodleSvg: buildDoodleSvg,
};

if (typeof module !== "undefined" && module.exports) {
  module.exports = api;               // node（parity 驗證）
} else {
  root.DoodleEngine = api;            // 瀏覽器
}
})(typeof self !== "undefined" ? self : this);
