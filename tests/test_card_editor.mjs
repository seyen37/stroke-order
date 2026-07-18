// ======================================================================
// test_card_editor.mjs — 手寫卡片模式（5et）純函式層測試。
// 執行：node --test tests/test_card_editor.mjs（收工檢查.bat / CI 皆納入）
// ======================================================================
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  CARD_PRESETS, customPreset, faceGuides, sheetGuides,
  layoutTextBox, overflowCount, normalizeBox, cellTransform,
  SAFE_MARGIN_MM, EM,
} from '../src/stroke_order/web/static/card/geometry.js';
import {
  newCard, newTextBox, serialize, deserialize, sanitizeGlyph, SCHEMA,
} from '../src/stroke_order/web/static/card/model.js';
import {
  renderFaceSvg, renderSheetSvg, esc,
} from '../src/stroke_order/web/static/card/render.js';
import {
  outlineToPathD, outlineFragment, traceFragment,
} from '../src/stroke_order/web/static/card/glyphs.js';

// ---- geometry --------------------------------------------------------

test('presets: 名片 90×52 預設單面；A6 對折兩面 148×105', () => {
  assert.equal(CARD_PRESETS.business.faces[0].w, 90);
  assert.equal(CARD_PRESETS.business.faces[0].h, 52);
  const a6 = CARD_PRESETS.a6_fold;
  assert.equal(a6.faces.length, 2);
  for (const f of a6.faces) {
    assert.equal(f.w, 148);
    assert.equal(f.h, 105);
  }
});

test('A6 對折 sheet＝A5 直式 148×210、水平摺線 y=105、封面 rotate180', () => {
  const s = CARD_PRESETS.a6_fold.sheet;
  assert.equal(s.w, 148);
  assert.equal(s.h, 210);
  assert.deepEqual(s.fold, { axis: 'h', at: 105 });
  const cover = s.placement.find((p) => p.face === 'cover');
  assert.equal(cover.rotate180, true);
  const line = sheetGuides(s);
  assert.deepEqual(line, { x1: 0, y1: 105, x2: 148, y2: 105 });
});

test('customPreset 夾在 30–420mm（尺規調整契約）', () => {
  assert.equal(customPreset(10, 9999).faces[0].w, 30);
  assert.equal(customPreset(10, 9999).faces[0].h, 420);
  assert.equal(customPreset('148', '105').faces[0].w, 148);
});

test('faceGuides 安全邊界置中內縮', () => {
  const g = faceGuides({ w: 90, h: 52 });
  assert.equal(g.safe.x, SAFE_MARGIN_MM);
  assert.equal(g.safe.w, 90 - 2 * SAFE_MARGIN_MM);
});

test('layoutTextBox 橫書換行：框寬 3 字，第 4 字落第二行', () => {
  const box = { x: 10, y: 10, w: 26.4, h: 30 }; // size 8, gap .8 → 3 字/行
  const cells = layoutTextBox(box, '新年快樂', { sizeMm: 8 });
  assert.equal(cells.length, 4);
  assert.equal(cells[3].line, 1);
  assert.equal(cells[0].x, 10);
  assert.equal(cells[3].y > cells[0].y, true);
});

test('layoutTextBox 直書：主軸向下、行軸右→左', () => {
  const box = { x: 0, y: 0, w: 30, h: 26.4 };
  const cells = layoutTextBox(box, '賀年', { sizeMm: 8, vertical: true });
  assert.equal(cells[1].y > cells[0].y, true);        // 第二字在下
  assert.equal(cells[0].x, 30 - 8);                   // 首行靠右
});

test('layoutTextBox 換行符強制斷行、溢出截斷有計數', () => {
  const box = { x: 0, y: 0, w: 50, h: 20 }; // 兩行容量（pitchLine=10）
  const cells = layoutTextBox(box, '一\n二', { sizeMm: 8 });
  assert.equal(cells[1].line, 1);
  const tiny = { x: 0, y: 0, w: 8, h: 8 };
  assert.equal(overflowCount(tiny, '春夏秋冬', { sizeMm: 8 }) > 0, true);
});

test('normalizeBox 夾回面內＋最小尺寸', () => {
  const f = { w: 90, h: 52 };
  const b = normalizeBox({ x: 80, y: -5, w: 200, h: 2 }, f);
  assert.equal(b.w, 90);
  assert.equal(b.h, 8);
  assert.equal(b.x, 0);
  assert.equal(b.y, 0);
});

test('cellTransform：EM→cell 縮放', () => {
  const t = cellTransform({ x: 5, y: 7, size: 10.24 });
  assert.deepEqual(t.translate, [5, 7]);
  assert.equal(Math.abs(t.scale - 10.24 / EM) < 1e-9, true);
});

// ---- model -----------------------------------------------------------

test('model: newCard/newTextBox/serialize round-trip', () => {
  const card = newCard('a6_fold');
  const face = CARD_PRESETS.a6_fold.faces[0];
  card.boxes.cover.push(newTextBox(face, { text: '新年快樂', sizeMm: 12 }));
  const back = deserialize(serialize(card));
  assert.equal(back.schema, SCHEMA);
  assert.equal(back.boxes.cover.length, 1);
  assert.equal(back.boxes.cover[0].text, '新年快樂');
  assert.equal(back.boxes.cover[0].sizeMm, 12);
});

test('model: 壞資料寬鬆降級（壞 JSON / 錯 schema / 未知 glyph source）', () => {
  assert.equal(deserialize('not json'), null);
  assert.equal(deserialize('{"schema":"other"}'), null);
  assert.deepEqual(sanitizeGlyph({ source: 'evil', style: 3 }), { source: 'system', style: 'kaishu' });
});

// ---- render（mm 契約鎖，對齊 5bt 全站契約） --------------------------

test('renderFaceSvg export：width mm＝viewBox 跨度、無編輯框線', () => {
  const face = { key: 'front', w: 90, h: 52 };
  const svg = renderFaceSvg(face, [
    { id: 'b1', kind: 'text', x: 10, y: 10, w: 60, h: 20, text: '賀', sizeMm: 10, vertical: false, glyph: { source: 'system' } },
  ]);
  assert.match(svg, /width="90mm" height="52mm"/);
  assert.match(svg, /viewBox="0 0 90 52"/);
  assert.equal(svg.includes('card-box-frame'), false);
  assert.equal(svg.includes('賀'), true);
});

test('renderFaceSvg edit：含框線；選取框有把手', () => {
  const face = { key: 'front', w: 90, h: 52 };
  const box = { id: 'b1', kind: 'text', x: 1, y: 1, w: 20, h: 10, text: '', sizeMm: 8, vertical: false, glyph: { source: 'system' } };
  const svg = renderFaceSvg(face, [box], { mode: 'edit', selectedId: 'b1' });
  assert.equal(svg.includes('card-box-frame'), true);
  assert.equal(svg.includes('card-handle'), true);
});

test('renderSheetSvg：A5 直式、封面 rotate(180)、摺線', () => {
  const preset = CARD_PRESETS.a6_fold;
  const svg = renderSheetSvg(preset, { cover: [], inside: [] });
  assert.match(svg, /width="148mm" height="210mm"/);
  assert.match(svg, /rotate\(180\)/);
  assert.match(svg, /stroke-dasharray="3 2"/);
  assert.equal(renderSheetSvg(CARD_PRESETS.business, {}), null);
});

test('esc: XSS 字元跳脫', () => {
  assert.equal(esc('<s>&"'), '&lt;s&gt;&amp;&quot;');
});

// ---- glyphs 純函式 ---------------------------------------------------

test('outlineToPathD: M/L/Q/C/Z 全指令（IR outline 欄位契約：begin/mid/end）', () => {
  const d = outlineToPathD([
    { type: 'M', x: 1, y: 2 }, { type: 'L', x: 3, y: 4 },
    { type: 'Q', begin: { x: 5, y: 6 }, end: { x: 7, y: 8 } },
    { type: 'C', begin: { x: 1, y: 1 }, mid: { x: 2, y: 2 }, end: { x: 3, y: 3 } },
    { type: 'Z' },
  ]);
  assert.equal(d, 'M1 2L3 4Q5 6 7 8C1 1 2 2 3 3Z');
  assert.equal(outlineToPathD([]), null);
  // 回歸鎖：NaN 不得進 d 字串（5et 首版誤用 x1/y1 扁平欄位踩過）
  assert.equal(d.includes('NaN'), false);
});

test('outlineFragment / traceFragment：空資料回 null、有料出片段', () => {
  assert.equal(outlineFragment([]), null);
  const frag = outlineFragment([{ outline: [{ type: 'M', x: 0, y: 0 }, { type: 'L', x: 9, y: 9 }] }]);
  assert.match(frag, /<path d="M0 0L9 9"\/>/);
  assert.equal(traceFragment({ strokes: [] }), null);
  const tf = traceFragment({ strokes: [{ points: [{ x: 1, y: 2 }, { x: 3, y: 4 }] }] });
  assert.match(tf, /stroke-width="40"/);
  assert.match(tf, /polyline points="1,2 3,4"/);
});
