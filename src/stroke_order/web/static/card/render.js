// ======================================================================
// card/render.js — 手寫卡片模式（5et）SVG 渲染層。
//
// 全部輸出「SVG 字串」：編輯器以 innerHTML 掛載、下載直接成檔——單一
// 渲染路徑，畫面所見即匯出（避免雙軌漂移）。mm 契約：width/height mm
// ＝ viewBox 跨度（5bt 全站契約，tests 有鎖）。
//
// 字形來源（R2）：glyphProvider(char, glyphSpec) → SVG 片段字串
// （2048 EM 座標、原點左上）或 null（fallback 系統字型 <text>）。
// ======================================================================

import { faceGuides, sheetGuides, layoutTextBox, contentRect, EM } from './geometry.js';
import { fitTextLength } from './kaomoji.js';

const XMLNS = 'http://www.w3.org/2000/svg';

export function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

//: 單一 cell 的字形標記。provider 命中→EM 群組縮放；否則系統字型。
function cellMarkup(cell, glyph, glyphProvider) {
  const frag = glyphProvider ? glyphProvider(cell.char, glyph) : null;
  if (frag) {
    const s = cell.size / EM;
    return `<g transform="translate(${round(cell.x)},${round(cell.y)}) scale(${s.toFixed(6)})">${frag}</g>`;
  }
  // 系統字型 fallback：以 cell 中心定位（text-anchor 置中）
  const cx = cell.x + cell.size / 2;
  const y = cell.y + cell.size * 0.82; // 近似 CJK baseline
  return (
    `<text x="${round(cx)}" y="${round(y)}" font-size="${round(cell.size * 0.92)}"` +
    ` text-anchor="middle" font-family="'Kaiti TC','DFKai-SB','BiauKai','Noto Serif TC',serif">` +
    `${esc(cell.char)}</text>`
  );
}

function round(v) {
  return Math.round(v * 1000) / 1000;
}

//: 框內容（不含編輯框線）——R4：先畫裝飾外框，內容排進 contentRect。
export function boxContentMarkup(box, glyphProvider) {
  const rect = contentRect(box);
  const inner = { ...box, ...rect };
  let content;
  if (box.kind === 'kaomoji') {
    content = kaomojiMarkup(inner);
  } else if (box.kind === 'art') {
    content = artMarkup(inner);
  } else {
    const cells = layoutTextBox(
      inner,
      box.text,
      { sizeMm: box.sizeMm, vertical: box.vertical },
    );
    content = cells.map((c) => cellMarkup(c, box.glyph, glyphProvider)).join('');
  }
  return (
    `<g data-box-id="${esc(box.id)}" fill="#1a1a1a">` +
    `${frameMarkup(box)}${content}</g>`
  );
}

//: R4 裝飾外框（匯出內容的一部分，非編輯 chrome）。
export function frameMarkup(box) {
  const f = box.frame;
  if (!f || f.style === 'none') return '';
  const sw = f.strokeMm;
  const base = ` fill="none" stroke="#1a1a1a" stroke-width="${sw}"`;
  const inset = sw / 2; // 框線畫在框界內
  const x = r3(box.x + inset);
  const y = r3(box.y + inset);
  const w = r3(box.w - sw);
  const h = r3(box.h - sw);
  switch (f.style) {
    case 'solid':
      return `<rect x="${x}" y="${y}" width="${w}" height="${h}"${base}/>`;
    case 'rounded': {
      const rx = r3(Math.min(box.w, box.h) * 0.12);
      return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}"${base}/>`;
    }
    case 'dashed':
      return `<rect x="${x}" y="${y}" width="${w}" height="${h}"${base} stroke-dasharray="2.2 1.4"/>`;
    case 'double': {
      const gap = Math.max(sw * 2, 1.2);
      const x2 = r3(box.x + inset + gap);
      const y2 = r3(box.y + inset + gap);
      const w2 = r3(box.w - sw - 2 * gap);
      const h2 = r3(box.h - sw - 2 * gap);
      return (
        `<rect x="${x}" y="${y}" width="${w}" height="${h}"${base}/>` +
        `<rect x="${x2}" y="${y2}" width="${w2}" height="${h2}"${base}/>`
      );
    }
    case 'ellipse': {
      const cx = r3(box.x + box.w / 2);
      const cy = r3(box.y + box.h / 2);
      return (
        `<ellipse cx="${cx}" cy="${cy}" rx="${r3(box.w / 2 - inset)}"` +
        ` ry="${r3(box.h / 2 - inset)}"${base}/>`
      );
    }
    default:
      return '';
  }
}

//: R3 顏文字：整串單行置中；近似寬度超框時用 textLength 擠壓。
export function kaomojiMarkup(box) {
  const size = box.sizeMm ?? 8;
  const cx = box.x + box.w / 2;
  const y = box.y + box.h / 2 + size * 0.32;
  const tl = fitTextLength(box.text, size, box.w);
  const squeeze = tl !== null
    ? ` textLength="${Math.round(tl * 100) / 100}" lengthAdjust="spacingAndGlyphs"`
    : '';
  return (
    `<text x="${Math.round(cx * 1000) / 1000}" y="${Math.round(y * 1000) / 1000}"` +
    ` font-size="${size}" text-anchor="middle"` +
    ` font-family="'Noto Sans TC','Segoe UI Symbol',system-ui,sans-serif"${squeeze}>` +
    `${esc(box.text)}</text>`
  );
}

//: R3 塗鴉/SVG：等比縮放置中嵌入（frag 已經 svgimport 淨化，唯一合法來源）。
export function artMarkup(box) {
  const a = box.art;
  if (!a || !a.frag) return '';
  const s = Math.min(box.w / a.vw, box.h / a.vh);
  const tx = box.x + (box.w - a.vw * s) / 2 - a.vx * s;
  const ty = box.y + (box.h - a.vh * s) / 2 - a.vy * s;
  return (
    `<g transform="translate(${r3(tx)},${r3(ty)}) scale(${s.toFixed(6)})">${a.frag}</g>`
  );
}

function r3(v) {
  return Math.round(v * 1000) / 1000;
}

//: 編輯層附加物：框線＋縮放把手（匯出時不含）。
export function boxChromeMarkup(box, selected) {
  const stroke = selected ? '#1976d2' : '#b8c4d0';
  const handles = selected
    ? `<rect class="card-handle" data-box-id="${esc(box.id)}" x="${round(box.x + box.w - 2.5)}" y="${round(box.y + box.h - 2.5)}" width="5" height="5" fill="#1976d2"/>`
    : '';
  return (
    `<rect class="card-box-frame" data-box-id="${esc(box.id)}" x="${round(box.x)}" y="${round(box.y)}"` +
    ` width="${round(box.w)}" height="${round(box.h)}" fill="none" stroke="${stroke}"` +
    ` stroke-width="0.35" stroke-dasharray="1.2 1" vector-effect="non-scaling-stroke"/>` + handles
  );
}

//: 導引層（安全邊界；編輯顯示、匯出可選）。
export function guidesMarkup(face) {
  const g = faceGuides(face);
  return (
    `<rect x="${round(g.safe.x)}" y="${round(g.safe.y)}" width="${round(g.safe.w)}"` +
    ` height="${round(g.safe.h)}" fill="none" stroke="#7fd4c1" stroke-width="0.25"` +
    ` stroke-dasharray="2 1.5"/>`
  );
}

//: 單面 SVG。mode: 'edit'（含框線/導引/選取）| 'export'（純內容）。
export function renderFaceSvg(face, boxes, opts = {}) {
  const {
    mode = 'export', selectedId = null, glyphProvider = null,
    showGuides = false, marquee = null,
  } = opts;
  const parts = [];
  parts.push(`<rect x="0" y="0" width="${face.w}" height="${face.h}" fill="#ffffff"/>`);
  if (mode === 'edit' && showGuides) parts.push(guidesMarkup(face));
  for (const box of boxes) {
    parts.push(boxContentMarkup(box, glyphProvider));
    if (mode === 'edit') parts.push(boxChromeMarkup(box, box.id === selectedId));
  }
  if (mode === 'edit' && marquee) {
    parts.push(
      `<rect x="${marquee.x}" y="${marquee.y}" width="${marquee.w}" height="${marquee.h}"` +
      ` fill="rgba(25,118,210,0.08)" stroke="#1976d2" stroke-width="0.3"` +
      ` stroke-dasharray="1.5 1"/>`,
    );
  }
  return (
    `<svg xmlns="${XMLNS}" width="${face.w}mm" height="${face.h}mm"` +
    ` viewBox="0 0 ${face.w} ${face.h}">${parts.join('')}</svg>`
  );
}

//: R4 印刷版：內容外擴出血 bleedMm、四角裁切標記（落在出血邊內）。
//: source: {kind:'face', face, boxes} | {kind:'sheet', preset, boxesByFace}
export function renderPrintSvg(source, opts = {}) {
  const { bleedMm = 3, glyphProvider = null, faceRotate = null } = opts;
  const b = Math.max(0, bleedMm);
  let w;
  let h;
  let content;
  if (source.kind === 'sheet') {
    const inner = renderSheetSvg(source.preset, source.boxesByFace, {
      glyphProvider, faceRotate,
    });
    if (!inner) return null;
    const sheet = source.preset.sheet;
    w = sheet.w;
    h = sheet.h;
    content = stripSvgWrapper(inner);
  } else {
    w = source.face.w;
    h = source.face.h;
    content = stripSvgWrapper(renderFaceSvg(source.face, source.boxes, {
      mode: 'export', glyphProvider,
    }));
  }
  const W = w + 2 * b;
  const H = h + 2 * b;
  const marks = b >= 1.5 ? cropMarks(b, w, h) : '';
  return (
    `<svg xmlns="${XMLNS}" width="${W}mm" height="${H}mm" viewBox="0 0 ${W} ${H}">` +
    `<rect x="0" y="0" width="${W}" height="${H}" fill="#ffffff"/>` +
    `<g transform="translate(${b},${b})">${content}</g>` +
    `${marks}</svg>`
  );
}

//: 去掉外層 <svg …> 包裝，取內容（同渲染路徑產物，結構可信）。
function stripSvgWrapper(svg) {
  return svg.replace(/^<svg[^>]*>/, '').replace(/<\/svg>$/, '');
}

//: 四角裁切標記：8 段短線，沿修裁邊延伸線畫在出血區內、離修裁角 0.5mm。
function cropMarks(b, w, h) {
  const L = b - 0.5; // 線長（不觸及修裁區）
  if (L <= 0) return '';
  const seg = (x1, y1, x2, y2) =>
    `<line x1="${r3(x1)}" y1="${r3(y1)}" x2="${r3(x2)}" y2="${r3(y2)}"` +
    ' stroke="#000" stroke-width="0.2"/>';
  const xs = [b, b + w];
  const ys = [b, b + h];
  const H = 2 * b + h;
  const W = 2 * b + w;
  let out = '';
  for (const x of xs) out += seg(x, 0, x, L) + seg(x, H - L, x, H);
  for (const y of ys) out += seg(0, y, L, y) + seg(W - L, y, W);
  return out;
}

//: 展開列印版（對折卡）：各面依 placement 擺入，rotate180 面旋轉。
export function renderSheetSvg(preset, boxesByFace, opts = {}) {
  const sheet = preset.sheet;
  if (!sheet) return null;
  const { glyphProvider = null, showFoldLine = true, faceRotate = null } = opts;
  const parts = [];
  parts.push(`<rect x="0" y="0" width="${sheet.w}" height="${sheet.h}" fill="#ffffff"/>`);
  for (const place of sheet.placement) {
    const face = preset.faces.find((f) => f.key === place.face);
    const boxes = boxesByFace[place.face] ?? [];
    const inner = boxes.map((b) => boxContentMarkup(b, glyphProvider)).join('');
    // R3b：faceRotate 覆寫優先於 preset 預設
    const doRotate = faceRotate?.[place.face] ?? place.rotate180;
    const rot = doRotate
      ? ` transform="translate(${place.x + face.w},${place.y + face.h}) rotate(180)"`
      : ` transform="translate(${place.x},${place.y})"`;
    parts.push(`<g${rot}>${inner}</g>`);
  }
  if (showFoldLine && sheet.fold) {
    const l = sheetGuides(sheet);
    parts.push(
      `<line x1="${l.x1}" y1="${l.y1}" x2="${l.x2}" y2="${l.y2}"` +
      ` stroke="#c8c8c8" stroke-width="0.2" stroke-dasharray="3 2"/>`,
    );
  }
  return (
    `<svg xmlns="${XMLNS}" width="${sheet.w}mm" height="${sheet.h}mm"` +
    ` viewBox="0 0 ${sheet.w} ${sheet.h}">${parts.join('')}</svg>`
  );
}
