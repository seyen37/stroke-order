// ======================================================================
// card/geometry.js — 手寫卡片模式（5et）純幾何層：卡型 presets、面結構、
// 導引線、文字框內逐字格排版。零 DOM 依賴，node --test 可直測。
//
// 座標契約：全部 mm（與全站 SVG mm 契約一致，見 PRINCIPLES §27 / 5bt）。
// ======================================================================

//: 卡型 presets。faces 每面獨立編輯；sheet 描述整張列印展開版。
//: A6 對折（使用者定案：公制 A6 為基準）＝ A5 直式 148×210 沿水平中線
//: 對折（tent fold）→ 上下兩面各為 A6 橫式 148×105，上半面列印時旋轉 180°。
export const CARD_PRESETS = {
  business: {
    key: 'business',
    label: '名片卡 9×5.2cm',
    faces: [{ key: 'front', label: '正面', w: 90, h: 52 }],
    sheet: null, // 單面卡無展開版
  },
  a6_fold: {
    key: 'a6_fold',
    label: 'A6 橫式對折卡（A5 展開）',
    faces: [
      { key: 'cover', label: '封面', w: 148, h: 105 },
      { key: 'inside', label: '內頁', w: 148, h: 105 },
    ],
    sheet: {
      w: 148,
      h: 210,
      fold: { axis: 'h', at: 105 }, // 水平摺線 y=105
      // 列印慣例：tent fold 上半面（封面）旋轉 180°，下半面（內頁）正放
      placement: [
        { face: 'cover', x: 0, y: 0, rotate180: true },
        { face: 'inside', x: 0, y: 105, rotate180: false },
      ],
    },
  },
};

export const DEFAULT_PRESET = 'business';
export const SAFE_MARGIN_MM = 5;   // 安全邊界（參考：賀卡慣例 3–6mm）
export const BLEED_MM = 3;         // 出血（R4 印刷 PDF 才消費，先入模型）
export const MIN_BOX_MM = 8;       // 框最小邊長
export const EM = 2048;            // 全站字形 EM 座標

// 自訂尺寸（使用者定案：以尺規方式調整）——夾在合理範圍。
export function customPreset(wMm, hMm) {
  const w = clamp(Number(wMm) || 0, 30, 420);
  const h = clamp(Number(hMm) || 0, 30, 420);
  return {
    key: 'custom',
    label: `自訂 ${w}×${h}mm`,
    faces: [{ key: 'front', label: '正面', w, h }],
    sheet: null,
  };
}

export function clamp(v, lo, hi) {
  return Math.min(hi, Math.max(lo, v));
}

//: 面的導引線（編輯層顯示；匯出時可選）。
export function faceGuides(face, safeMm = SAFE_MARGIN_MM) {
  const m = clamp(safeMm, 0, Math.min(face.w, face.h) / 2 - 1);
  return {
    safe: { x: m, y: m, w: face.w - 2 * m, h: face.h - 2 * m },
  };
}

//: 展開版導引線（摺線）。
export function sheetGuides(sheet) {
  if (!sheet || !sheet.fold) return null;
  const f = sheet.fold;
  return f.axis === 'h'
    ? { x1: 0, y1: f.at, x2: sheet.w, y2: f.at }
    : { x1: f.at, y1: 0, x2: f.at, y2: sheet.h };
}

// ----------------------------------------------------------------------
// 文字框逐字格排版：與全站慣例一致，每字一個正方 cell（2048 EM 映射），
// 由框寬自動換行。回傳每字的 cell 幾何（mm，相對「面」左上角）。
// ----------------------------------------------------------------------

//: opts: { sizeMm 字高, gapMm 字距, lineGapMm 行距, vertical 直書 }
export function layoutTextBox(box, text, opts = {}) {
  const size = clamp(opts.sizeMm ?? 8, 3, 100);
  const gap = opts.gapMm ?? size * 0.1;
  const lineGap = opts.lineGapMm ?? size * 0.25;
  const vertical = !!opts.vertical;
  const cells = [];
  const chars = [...String(text ?? '')];
  if (!chars.length) return cells;

  const pitchMain = size + gap;       // 行內前進
  const pitchLine = size + lineGap;   // 換行前進
  // 橫書：主軸=x、行軸=y；直書：主軸=y（上→下）、行軸=x（右→左，傳統）
  const mainSpan = vertical ? box.h : box.w;
  const lineSpan = vertical ? box.w : box.h;
  const perLine = Math.max(1, Math.floor((mainSpan + gap) / pitchMain));
  const maxLines = Math.max(1, Math.floor((lineSpan + lineGap) / pitchLine));

  let line = 0;
  let idx = 0;
  for (const ch of chars) {
    if (ch === '\n') { line += 1; idx = 0; continue; }
    if (idx >= perLine) { line += 1; idx = 0; }
    if (line >= maxLines) break; // 溢出截斷（UI 另行警示）
    const main = idx * pitchMain;
    const lineOff = line * pitchLine;
    const x = vertical ? box.x + box.w - size - lineOff : box.x + main;
    const y = vertical ? box.y + main : box.y + lineOff;
    cells.push({ char: ch, x, y, size, line, index: idx });
    idx += 1;
  }
  return cells;
}

//: 溢出檢查：回傳被截斷的字數（0＝全放得下）。
export function overflowCount(box, text, opts = {}) {
  const placed = layoutTextBox(box, text, opts).length;
  const visible = [...String(text ?? '')].filter((c) => c !== '\n').length;
  return Math.max(0, visible - placed);
}

//: 拖拉/縮放後的框正規化：夾在面內、保最小尺寸。
export function normalizeBox(box, face) {
  const w = clamp(box.w, MIN_BOX_MM, face.w);
  const h = clamp(box.h, MIN_BOX_MM, face.h);
  const x = clamp(box.x, 0, face.w - w);
  const y = clamp(box.y, 0, face.h - h);
  return { ...box, x, y, w, h };
}

//: EM 字形 → cell 的 transform 參數（SVG: translate + scale）。
export function cellTransform(cell) {
  const s = cell.size / EM;
  return { translate: [cell.x, cell.y], scale: s };
}
