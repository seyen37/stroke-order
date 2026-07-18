// ======================================================================
// card/main.js — 手寫卡片模式（5et）編輯器接線層。
//
// 單向資料流：state 變更 → scheduleRender()（rAF 合批）→ innerHTML 重繪
// edit SVG → pointer 事件（事件委派讀 data-box-id）改 state。畫面與匯出
// 共用 render.js 同一條字串渲染路徑。
// ======================================================================

import { CARD_PRESETS, normalizeBox } from './geometry.js';
import {
  newCard, newTextBox, resolvePreset, saveDraft, loadDraft, serialize,
} from './model.js';
import { renderFaceSvg, renderSheetSvg } from './render.js';
import { createGlyphRegistry } from './glyphs.js';

const $ = (id) => document.getElementById(id);

// ---- state -----------------------------------------------------------

let card = loadDraft() ?? newCard();
let activeFace = 0;
let selectedId = null;
let drag = null; // {mode:'move'|'resize', boxId, startMm:{x,y}, orig:{...}}

const glyphs = createGlyphRegistry({ requestRender: scheduleRender });

// ---- render（rAF 合批） ----------------------------------------------

let rafId = null;

function scheduleRender() {
  if (rafId) return;
  rafId = requestAnimationFrame(() => { rafId = null; render(); });
}

function preset() {
  return resolvePreset(card.preset, card.custom);
}

function face() {
  const p = preset();
  return p.faces[Math.min(activeFace, p.faces.length - 1)];
}

function boxes() {
  return card.boxes[face().key] ?? [];
}

function selectedBox() {
  return boxes().find((b) => b.id === selectedId) ?? null;
}

function render() {
  const p = preset();
  // 面籤
  const tabs = $('card-face-tabs');
  tabs.innerHTML = p.faces
    .map((f, i) => `<button data-face="${i}" class="${i === activeFace ? 'on' : ''}">${f.label}</button>`)
    .join('');
  tabs.style.display = p.faces.length > 1 ? '' : 'none';
  // 卡面
  $('card-stage').innerHTML = renderFaceSvg(face(), boxes(), {
    mode: 'edit',
    selectedId,
    glyphProvider: glyphs.provider,
    showGuides: $('card-guides').checked,
  });
  renderPanel();
  saveDraft(card);
}

function renderPanel() {
  const box = selectedBox();
  $('card-box-panel').style.display = box ? '' : 'none';
  if (!box) return;
  if (document.activeElement !== $('card-text')) $('card-text').value = box.text;
  $('card-size').value = box.sizeMm;
  $('card-vertical').checked = box.vertical;
  $('card-glyph-source').value = box.glyph.source;
  $('card-glyph-style').value = box.glyph.style;
  $('card-glyph-style').style.display = box.glyph.source === 'style' ? '' : 'none';
  $('card-font-row').style.display = box.glyph.source === 'userfont' ? '' : 'none';
}

// ---- 座標換算：clientX/Y → 面 mm ------------------------------------

function toMm(evt) {
  const svg = $('card-stage').querySelector('svg');
  const pt = new DOMPoint(evt.clientX, evt.clientY);
  const m = svg.getScreenCTM();
  if (!m) return { x: 0, y: 0 };
  const p = pt.matrixTransform(m.inverse());
  return { x: p.x, y: p.y };
}

// ---- pointer 互動：選取 / 拖移 / 右下把手縮放 ------------------------

function onPointerDown(evt) {
  const t = evt.target;
  const boxId = t.getAttribute && t.getAttribute('data-box-id');
  const mm = toMm(evt);
  if (t.classList?.contains('card-handle')) {
    const orig = boxes().find((b) => b.id === boxId);
    drag = { mode: 'resize', boxId, startMm: mm, orig: { ...orig } };
  } else if (boxId) {
    selectedId = boxId;
    const orig = boxes().find((b) => b.id === boxId);
    drag = { mode: 'move', boxId, startMm: mm, orig: { ...orig } };
  } else {
    // 命中內容群組的字也算選取該框
    const g = t.closest ? t.closest('g[data-box-id]') : null;
    const gid = g?.getAttribute('data-box-id');
    if (gid) {
      selectedId = gid;
      const orig = boxes().find((b) => b.id === gid);
      drag = { mode: 'move', boxId: gid, startMm: mm, orig: { ...orig } };
    } else {
      selectedId = null;
      drag = null;
    }
  }
  if (drag) $('card-stage').setPointerCapture?.(evt.pointerId);
  scheduleRender();
}

function onPointerMove(evt) {
  if (!drag) return;
  const mm = toMm(evt);
  const dx = mm.x - drag.startMm.x;
  const dy = mm.y - drag.startMm.y;
  const list = boxes();
  const i = list.findIndex((b) => b.id === drag.boxId);
  if (i < 0) return;
  const f = face();
  if (drag.mode === 'move') {
    list[i] = normalizeBox({ ...drag.orig, x: drag.orig.x + dx, y: drag.orig.y + dy }, f);
  } else {
    list[i] = normalizeBox({ ...drag.orig, w: drag.orig.w + dx, h: drag.orig.h + dy }, f);
  }
  scheduleRender();
}

function onPointerUp() {
  drag = null;
}

// ---- 下載 ------------------------------------------------------------

function downloadBlob(blob, filename) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

function downloadFaceSvg() {
  const svg = renderFaceSvg(face(), boxes(), { mode: 'export', glyphProvider: glyphs.provider });
  downloadBlob(new Blob([svg], { type: 'image/svg+xml' }), `card_${card.preset}_${face().key}.svg`);
}

function downloadSheetSvg() {
  const svg = renderSheetSvg(preset(), card.boxes, { glyphProvider: glyphs.provider });
  if (!svg) return;
  downloadBlob(new Blob([svg], { type: 'image/svg+xml' }), `card_${card.preset}_sheet.svg`);
}

function downloadJson() {
  downloadBlob(new Blob([serialize(card)], { type: 'application/json' }), 'card_layout.json');
}

// ---- 事件接線 --------------------------------------------------------

function switchPreset(key) {
  const custom = key === 'custom'
    ? { w: Number($('card-w').value) || 148, h: Number($('card-h').value) || 105 }
    : null;
  card = newCard(key, custom);
  activeFace = 0;
  selectedId = null;
  scheduleRender();
}

function mutateSelected(fn) {
  const box = selectedBox();
  if (!box) return;
  fn(box);
  const f = face();
  const list = boxes();
  const i = list.findIndex((b) => b.id === box.id);
  list[i] = normalizeBox(box, f);
  scheduleRender();
}

export function init() {
  // preset 選單
  const sel = $('card-preset');
  sel.innerHTML = [
    ...Object.values(CARD_PRESETS).map((p) => `<option value="${p.key}">${p.label}</option>`),
    '<option value="custom">自訂尺寸（尺規調整）</option>',
  ].join('');
  sel.value = card.preset;
  sel.onchange = () => switchPreset(sel.value);
  $('card-custom-row').style.display = sel.value === 'custom' ? '' : 'none';
  sel.addEventListener('change', () => {
    $('card-custom-row').style.display = sel.value === 'custom' ? '' : 'none';
  });
  $('card-w').onchange = $('card-h').onchange = () => switchPreset('custom');

  $('card-face-tabs').onclick = (e) => {
    const idx = e.target.getAttribute?.('data-face');
    if (idx !== null && idx !== undefined) {
      activeFace = Number(idx);
      selectedId = null;
      scheduleRender();
    }
  };

  $('card-add-text').onclick = () => {
    const box = newTextBox(face(), { text: '寫點什麼' });
    boxes().push(box);
    selectedId = box.id;
    scheduleRender();
  };
  $('card-del-box').onclick = () => {
    const list = boxes();
    const i = list.findIndex((b) => b.id === selectedId);
    if (i >= 0) list.splice(i, 1);
    selectedId = null;
    scheduleRender();
  };

  const stage = $('card-stage');
  stage.addEventListener('pointerdown', onPointerDown);
  stage.addEventListener('pointermove', onPointerMove);
  stage.addEventListener('pointerup', onPointerUp);
  stage.addEventListener('pointercancel', onPointerUp);

  $('card-text').addEventListener('input', () => mutateSelected((b) => { b.text = $('card-text').value; }));
  $('card-size').addEventListener('change', () => mutateSelected((b) => { b.sizeMm = Number($('card-size').value) || 8; }));
  $('card-vertical').addEventListener('change', () => mutateSelected((b) => { b.vertical = $('card-vertical').checked; }));
  $('card-glyph-source').addEventListener('change', () => mutateSelected((b) => { b.glyph.source = $('card-glyph-source').value; }));
  $('card-glyph-style').addEventListener('change', () => mutateSelected((b) => { b.glyph.style = $('card-glyph-style').value; }));
  $('card-font-file').addEventListener('change', async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await glyphs.loadUserFontFile(file);
      $('card-font-status').textContent = `已載入：${file.name}`;
    } catch (err) {
      $('card-font-status').textContent = `字型載入失敗：${err.message}`;
    }
  });
  $('card-guides').addEventListener('change', scheduleRender);

  $('card-dl-svg').onclick = downloadFaceSvg;
  $('card-dl-sheet').onclick = downloadSheetSvg;
  $('card-dl-json').onclick = downloadJson;
  $('card-reset').onclick = () => {
    if (confirm('清空目前卡片？')) switchPreset(card.preset);
  };

  scheduleRender();
}

init();
