// ======================================================================
// card/main.js — 手寫卡片模式（5et）編輯器接線層。
//
// 單向資料流：state 變更 → scheduleRender()（rAF 合批）→ innerHTML 重繪
// edit SVG → pointer 事件（事件委派讀 data-box-id）改 state。畫面與匯出
// 共用 render.js 同一條字串渲染路徑。
// ======================================================================

import { CARD_PRESETS, normalizeBox, marqueeRect, faceFoldEdge } from './geometry.js';
import {
  newCard, newTextBox, newKaomojiBox, newArtBox,
  resolvePreset, saveDraft, loadDraft, serialize,
} from './model.js';
import { KAOMOJI_CATEGORIES } from './kaomoji.js';
import { sanitizeSvgText } from './svgimport.js';
import { renderFaceSvg, renderSheetSvg, renderPrintSvg } from './render.js';
import { createGlyphRegistry } from './glyphs.js';

const $ = (id) => document.getElementById(id);

// ---- state -----------------------------------------------------------

let card = loadDraft() ?? newCard();
let activeFace = 0;
let selectedId = null;
let drag = null; // {mode:'move'|'resize', boxId, startMm:{x,y}, orig:{...}}
// R3b 框選插入：{kind:'text'|'doodle'|'svg'} → 拖矩形 →（檔案）→ 插入
let pendingInsert = null;
let marqueeDrag = null; // {start:{x,y}, cur:{x,y}}

const glyphs = createGlyphRegistry({ requestRender: scheduleRender });

// ---- render（rAF 合批） ----------------------------------------------

let rafId = null;

function scheduleRender() {
  if (rafId) return;
  rafId = requestAnimationFrame(() => { rafId = null; render(); });
}

function preset() {
  return resolvePreset(card.preset, card.custom, card.portrait);
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
  const mq = marqueeDrag ? marqueeRect(marqueeDrag.start, marqueeDrag.cur, 0.5) : null;
  $('card-stage').innerHTML = renderFaceSvg(face(), boxes(), {
    mode: 'edit',
    selectedId,
    glyphProvider: glyphs.provider,
    showGuides: $('card-guides').checked,
    marquee: mq,
    foldEdge: faceFoldEdge(p, face().key),
    showRuler: $('card-ruler').checked,
  });
  // R3b：直式切換僅單面卡型有意義；面翻轉設定僅對折卡型顯示
  $('card-portrait-wrap').style.display = p.sheet ? 'none' : '';
  $('card-portrait').checked = !!card.portrait;
  $('card-face-rotate-wrap').style.display = p.sheet ? '' : 'none';
  if (p.sheet) $('card-face-rotate').checked = !!card.faceRotate[face().key];
  $('card-stage').style.cursor = pendingInsert ? 'crosshair' : '';
  renderPanel();
  saveDraft(card);
}

function renderPanel() {
  const box = selectedBox();
  $('card-box-panel').style.display = box ? '' : 'none';
  if (!box) return;
  const isText = box.kind === 'text';
  const isKao = box.kind === 'kaomoji';
  const isArt = box.kind === 'art';
  $('card-text-row').style.display = isArt ? 'none' : '';
  $('card-size-row').style.display = isArt ? 'none' : '';
  $('card-glyph-row').style.display = isText ? '' : 'none';
  $('card-vertical').parentElement.style.display = isText ? '' : 'none';
  $('card-art-row').style.display = isArt ? '' : 'none';
  if (isArt) {
    $('card-art-label').textContent = box.art.label || '（圖案）';
  } else {
    if (document.activeElement !== $('card-text')) $('card-text').value = box.text;
    $('card-size').value = box.sizeMm;
  }
  if (isKao) $('card-text').setAttribute('rows', '1');
  else $('card-text').removeAttribute('rows');
  if (isText) {
    $('card-vertical').checked = box.vertical;
    $('card-glyph-source').value = box.glyph.source;
    $('card-glyph-style').value = box.glyph.style;
    $('card-glyph-style').style.display = box.glyph.source === 'style' ? '' : 'none';
    $('card-font-row').style.display = box.glyph.source === 'userfont' ? '' : 'none';
  } else {
    $('card-font-row').style.display = 'none';
  }
  // R4：外框樣式（全部 kind 適用）
  const fr = box.frame ?? { style: 'none', strokeMm: 0.5, padMm: 3 };
  $('card-frame-style').value = fr.style;
  $('card-frame-stroke').value = fr.strokeMm;
  $('card-frame-pad').value = fr.padMm;
  $('card-frame-detail').style.display = fr.style === 'none' ? 'none' : '';
}

// ---- R3：顏文字選盤 / 塗鴉插入 / SVG 匯入 ----------------------------

function buildKaomojiPicker() {
  const host = $('card-kaomoji-panel');
  host.innerHTML = KAOMOJI_CATEGORIES.map((cat) =>
    `<div class="kao-cat"><div class="kao-cat-label">${cat.label}</div>` +
    cat.items.map((k) =>
      `<button type="button" class="kao-item" data-kao="${k.replace(/"/g, '&quot;')}">${k
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')}</button>`).join('') +
    '</div>').join('');
  host.addEventListener('click', (e) => {
    const k = e.target.getAttribute?.('data-kao');
    if (!k) return;
    const box = newKaomojiBox(face(), { text: k });
    boxes().push(box);
    selectedId = box.id;
    host.style.display = 'none';
    scheduleRender();
  });
}

function setInsertStatus(msg) {
  $('card-insert-status').textContent = msg ?? '';
}

async function insertDoodleFromImage(file) {
  setInsertStatus(`線稿轉換中…（${file.name}）`);
  try {
    const fd = new FormData();
    fd.append('image', file);
    fd.append('canvas_width_mm', '100');
    fd.append('auto_crop_whitespace', 'true');
    const r = await fetch('/api/doodle', { method: 'POST', body: fd });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    const svgText = await r.text();
    const clean = sanitizeSvgText(svgText, { dropBackgroundRect: true });
    if (clean.error) throw new Error(clean.error);
    const box = newArtBox(face(), { ...clean, label: `線稿：${file.name}` }, pendingRect ?? {});
    pendingRect = null;
    boxes().push(box);
    selectedId = box.id;
    setInsertStatus(`✓ 已插入線稿（${file.name}）`);
    scheduleRender();
  } catch (err) {
    setInsertStatus(`線稿轉換失敗：${err.message}`);
  }
}

async function insertSvgFile(file) {
  try {
    const text = await file.text();
    const clean = sanitizeSvgText(text);
    if (clean.error) throw new Error(clean.error);
    const box = newArtBox(face(), { ...clean, label: `SVG：${file.name}` }, pendingRect ?? {});
    pendingRect = null;
    boxes().push(box);
    selectedId = box.id;
    setInsertStatus(`✓ 已匯入 ${file.name}（外部連結/腳本已淨化移除）`);
    scheduleRender();
  } catch (err) {
    setInsertStatus(`SVG 匯入失敗：${err.message}`);
  }
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
  if (pendingInsert) {
    const mm = toMm(evt);
    marqueeDrag = { start: mm, cur: mm };
    $('card-stage').setPointerCapture?.(evt.pointerId);
    scheduleRender();
    return;
  }
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
  if (marqueeDrag) {
    marqueeDrag.cur = toMm(evt);
    scheduleRender();
    return;
  }
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
  if (marqueeDrag && pendingInsert) {
    const rect = marqueeRect(marqueeDrag.start, marqueeDrag.cur)
      ?? defaultRectAt(marqueeDrag.start);
    const insert = pendingInsert;
    marqueeDrag = null;
    pendingInsert = null;
    finishInsert(insert.kind, rect);
    scheduleRender();
    return;
  }
  marqueeDrag = null;
  drag = null;
}

//: 點一下（沒拖）→ 以點擊處為中心的預設大小矩形
function defaultRectAt(pt) {
  const f = face();
  return {
    x: pt.x - f.w * 0.3, y: pt.y - 7.5,
    w: f.w * 0.6, h: 15,
  };
}

function armInsert(kind, hint) {
  pendingInsert = { kind };
  setInsertStatus(hint);
  scheduleRender();
}

function finishInsert(kind, rect) {
  const f = face();
  if (kind === 'text') {
    const box = newTextBox(f, { ...rect, text: '寫點什麼' });
    boxes().push(box);
    selectedId = box.id;
    setInsertStatus('');
  } else {
    // doodle / svg：先記住框，選完檔案再插入
    pendingRect = rect;
    if (kind === 'doodle') $('card-doodle-file').click();
    else $('card-svg-file').click();
  }
}

let pendingRect = null;

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
  const svg = renderSheetSvg(preset(), card.boxes, {
    glyphProvider: glyphs.provider,
    faceRotate: card.faceRotate,
  });
  if (!svg) return;
  downloadBlob(new Blob([svg], { type: 'image/svg+xml' }), `card_${card.preset}_sheet.svg`);
}

//: R4 PNG：同一條渲染路徑的 SVG → Image → canvas（pxPerMm=8 ≈ 203dpi）
function svgToPngBlob(svgStr, wMm, hMm, pxPerMm = 8) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(new Blob([svgStr], { type: 'image/svg+xml' }));
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(wMm * pxPerMm);
      canvas.height = Math.round(hMm * pxPerMm);
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('PNG 轉換失敗'))), 'image/png');
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('SVG 載入失敗')); };
    img.src = url;
  });
}

async function downloadPng() {
  try {
    const f = face();
    const svg = renderFaceSvg(f, boxes(), { mode: 'export', glyphProvider: glyphs.provider });
    const blob = await svgToPngBlob(svg, f.w, f.h);
    downloadBlob(blob, `card_${card.preset}_${f.key}.png`);
  } catch (err) {
    setInsertStatus(`PNG 匯出失敗：${err.message}`);
  }
}

//: R4 印刷 PDF：對折卡＝展開版；單面卡＝本面。出血 3mm＋裁切標記。
async function downloadPrintPdf() {
  const p = preset();
  const source = p.sheet
    ? { kind: 'sheet', preset: p, boxesByFace: card.boxes }
    : { kind: 'face', face: face(), boxes: boxes() };
  const svg = renderPrintSvg(source, {
    glyphProvider: glyphs.provider,
    faceRotate: card.faceRotate,
  });
  if (!svg) return;
  setInsertStatus('PDF 轉檔中…');
  try {
    const r = await fetch('/api/card/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ svg, filename: `card_${card.preset}_print` }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    downloadBlob(await r.blob(), `card_${card.preset}_print.pdf`);
    setInsertStatus('✓ 印刷 PDF 已下載（含 3mm 出血＋裁切標記）');
  } catch (err) {
    setInsertStatus(`PDF 轉檔失敗：${err.message}`);
  }
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

  $('card-add-text').onclick = () =>
    armInsert('text', '在卡面拖出文字框範圍（點一下＝預設大小；Esc 取消）');
  buildKaomojiPicker();
  $('card-add-kaomoji').onclick = () => {
    const host = $('card-kaomoji-panel');
    host.style.display = host.style.display === 'none' ? '' : 'none';
  };
  $('card-add-doodle').onclick = () =>
    armInsert('doodle', '在卡面拖出圖案放置區域，放開後選擇圖片（點一下＝預設大小）');
  $('card-doodle-file').addEventListener('change', (e) => {
    const f = e.target.files?.[0];
    if (f) insertDoodleFromImage(f);
    e.target.value = '';
  });
  $('card-add-svg').onclick = () =>
    armInsert('svg', '在卡面拖出圖案放置區域，放開後選擇 SVG 檔（點一下＝預設大小）');
  $('card-svg-file').addEventListener('change', (e) => {
    const f = e.target.files?.[0];
    if (f) insertSvgFile(f);
    e.target.value = '';
  });
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
  $('card-ruler').addEventListener('change', scheduleRender);
  $('card-portrait').addEventListener('change', () => {
    card.portrait = $('card-portrait').checked;
    // 換方向後既有框重新夾回面內
    const f = face();
    card.boxes[f.key] = (card.boxes[f.key] ?? []).map((b) => normalizeBox(b, f));
    scheduleRender();
  });
  $('card-face-rotate').addEventListener('change', () => {
    card.faceRotate[face().key] = $('card-face-rotate').checked;
    scheduleRender();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && (pendingInsert || marqueeDrag)) {
      pendingInsert = null;
      marqueeDrag = null;
      setInsertStatus('');
      scheduleRender();
    }
  });

  $('card-frame-style').addEventListener('change', () => mutateSelected((b) => {
    b.frame = { ...(b.frame ?? {}), style: $('card-frame-style').value,
      strokeMm: Number($('card-frame-stroke').value) || 0.5,
      padMm: Number($('card-frame-pad').value) || 3 };
  }));
  $('card-frame-stroke').addEventListener('change', () => mutateSelected((b) => {
    b.frame = { ...(b.frame ?? { style: 'none' }), strokeMm: Number($('card-frame-stroke').value) || 0.5 };
  }));
  $('card-frame-pad').addEventListener('change', () => mutateSelected((b) => {
    b.frame = { ...(b.frame ?? { style: 'none' }), padMm: Number($('card-frame-pad').value) || 0 };
  }));

  $('card-dl-svg').onclick = downloadFaceSvg;
  $('card-dl-png').onclick = downloadPng;
  $('card-dl-pdf').onclick = downloadPrintPdf;
  $('card-dl-sheet').onclick = downloadSheetSvg;
  $('card-dl-json').onclick = downloadJson;
  $('card-reset').onclick = () => {
    if (confirm('清空目前卡片？')) switchPreset(card.preset);
  };

  scheduleRender();
}

init();
