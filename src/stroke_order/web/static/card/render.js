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

import { faceGuides, sheetGuides, layoutTextBox, EM } from './geometry.js';

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

//: 文字框內容（不含編輯框線）。
export function boxContentMarkup(box, glyphProvider) {
  const cells = layoutTextBox(
    box,
    box.text,
    { sizeMm: box.sizeMm, vertical: box.vertical },
  );
  const inner = cells.map((c) => cellMarkup(c, box.glyph, glyphProvider)).join('');
  return `<g data-box-id="${esc(box.id)}" fill="#1a1a1a">${inner}</g>`;
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
  const { mode = 'export', selectedId = null, glyphProvider = null, showGuides = false } = opts;
  const parts = [];
  parts.push(`<rect x="0" y="0" width="${face.w}" height="${face.h}" fill="#ffffff"/>`);
  if (mode === 'edit' && showGuides) parts.push(guidesMarkup(face));
  for (const box of boxes) {
    parts.push(boxContentMarkup(box, glyphProvider));
    if (mode === 'edit') parts.push(boxChromeMarkup(box, box.id === selectedId));
  }
  return (
    `<svg xmlns="${XMLNS}" width="${face.w}mm" height="${face.h}mm"` +
    ` viewBox="0 0 ${face.w} ${face.h}">${parts.join('')}</svg>`
  );
}

//: 展開列印版（對折卡）：各面依 placement 擺入，rotate180 面旋轉。
export function renderSheetSvg(preset, boxesByFace, opts = {}) {
  const sheet = preset.sheet;
  if (!sheet) return null;
  const { glyphProvider = null, showFoldLine = true } = opts;
  const parts = [];
  parts.push(`<rect x="0" y="0" width="${sheet.w}" height="${sheet.h}" fill="#ffffff"/>`);
  for (const place of sheet.placement) {
    const face = preset.faces.find((f) => f.key === place.face);
    const boxes = boxesByFace[place.face] ?? [];
    const inner = boxes.map((b) => boxContentMarkup(b, glyphProvider)).join('');
    const rot = place.rotate180
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
