// ======================================================================
// card/model.js — 手寫卡片模式（5et）資料模型：卡片狀態、序列化、
// localStorage 自動存檔。純資料層零 DOM，node --test 可直測。
//
// schema v1：
//   {
//     schema: "stroke-order-card-v1",
//     preset: "business" | "a6_fold" | "custom",
//     custom: {w, h} | null,
//     boxes: { <faceKey>: [ <box>, ... ] },
//   }
//   box（共同欄位）= { id, kind, x, y, w, h }               // mm
//   kind="text"    ＋ text, sizeMm, vertical,
//                    glyph: { source: "system"|"handwriting"|"userfont"|"style",
//                             style: "kaishu"|... }        // R2 消費
//   kind="kaomoji" ＋ text, sizeMm                          // R3：單行置中
//   kind="art"     ＋ art: { frag, vx, vy, vw, vh, label }  // R3：塗鴉/SVG
//                    （frag 僅能來自 svgimport.sanitizeSvgText 的輸出）
// ======================================================================

import { CARD_PRESETS, DEFAULT_PRESET, customPreset, normalizeBox } from './geometry.js';

export const SCHEMA = 'stroke-order-card-v1';
export const STORAGE_KEY = 'card:draft';

let _seq = 0;

export function newCard(presetKey = DEFAULT_PRESET, custom = null) {
  const preset = resolvePreset(presetKey, custom);
  const boxes = {};
  for (const f of preset.faces) boxes[f.key] = [];
  return { schema: SCHEMA, preset: presetKey, custom, boxes };
}

export function resolvePreset(presetKey, custom = null) {
  if (presetKey === 'custom') return customPreset(custom?.w, custom?.h);
  return CARD_PRESETS[presetKey] ?? CARD_PRESETS[DEFAULT_PRESET];
}

export function newTextBox(face, init = {}) {
  _seq += 1;
  const box = normalizeBox(
    {
      id: `b${Date.now().toString(36)}${_seq}`,
      kind: 'text',
      x: init.x ?? face.w * 0.15,
      y: init.y ?? face.h * 0.3,
      w: init.w ?? face.w * 0.6,
      h: init.h ?? Math.min(face.h * 0.3, 30),
      text: init.text ?? '',
      sizeMm: init.sizeMm ?? 8,
      vertical: !!init.vertical,
      glyph: init.glyph ?? { source: 'system', style: 'kaishu' },
    },
    face,
  );
  return box;
}

export function newKaomojiBox(face, init = {}) {
  _seq += 1;
  return normalizeBox(
    {
      id: `k${Date.now().toString(36)}${_seq}`,
      kind: 'kaomoji',
      x: init.x ?? face.w * 0.2,
      y: init.y ?? face.h * 0.4,
      w: init.w ?? Math.min(face.w * 0.5, 60),
      h: init.h ?? 12,
      text: init.text ?? '(＾▽＾)',
      sizeMm: init.sizeMm ?? 8,
    },
    face,
  );
}

export function newArtBox(face, art, init = {}) {
  _seq += 1;
  // 依圖案長寬比給預設框（最長邊 = 面寬 40%）
  const long = Math.min(face.w, face.h) * 0.5;
  const ratio = art.vh / art.vw;
  const w = init.w ?? (ratio > 1 ? long / ratio : long);
  const h = init.h ?? (ratio > 1 ? long : long * ratio);
  return normalizeBox(
    {
      id: `a${Date.now().toString(36)}${_seq}`,
      kind: 'art',
      x: init.x ?? face.w * 0.3,
      y: init.y ?? face.h * 0.25,
      w,
      h,
      art: {
        frag: String(art.frag),
        vx: Number(art.vx) || 0,
        vy: Number(art.vy) || 0,
        vw: Number(art.vw),
        vh: Number(art.vh),
        label: String(art.label ?? ''),
      },
    },
    face,
  );
}

// ---- 序列化 / 驗證 ---------------------------------------------------

export function serialize(card) {
  return JSON.stringify(card);
}

//: 寬鬆載入：schema 不符或壞資料回 null（呼叫端 fallback 新卡）。
export function deserialize(json) {
  let obj;
  try {
    obj = JSON.parse(json);
  } catch {
    return null;
  }
  if (!obj || obj.schema !== SCHEMA) return null;
  const preset = resolvePreset(obj.preset, obj.custom);
  const card = newCard(obj.preset in CARD_PRESETS || obj.preset === 'custom' ? obj.preset : DEFAULT_PRESET, obj.custom ?? null);
  for (const f of preset.faces) {
    const list = Array.isArray(obj.boxes?.[f.key]) ? obj.boxes[f.key] : [];
    card.boxes[f.key] = list
      .filter((b) => b && typeof b.id === 'string' && BOX_KINDS.has(b.kind))
      .map((b) => reviveBox(b, f))
      .filter(Boolean);
  }
  return card;
}

const BOX_KINDS = new Set(['text', 'kaomoji', 'art']);

//: 逐 box 復原＋驗證；壞資料回 null 丟棄（寬鬆載入原則）。
function reviveBox(b, face) {
  const base = {
    id: b.id,
    kind: b.kind,
    x: Number(b.x) || 0,
    y: Number(b.y) || 0,
    w: Number(b.w) || 10,
    h: Number(b.h) || 10,
  };
  if (b.kind === 'text') {
    return normalizeBox({
      ...base,
      text: String(b.text ?? ''),
      sizeMm: Number(b.sizeMm) || 8,
      vertical: !!b.vertical,
      glyph: sanitizeGlyph(b.glyph),
    }, face);
  }
  if (b.kind === 'kaomoji') {
    return normalizeBox({
      ...base,
      text: String(b.text ?? ''),
      sizeMm: Number(b.sizeMm) || 8,
    }, face);
  }
  // art：frag 必須是字串、尺寸有效，否則整框丟棄
  const a = b.art;
  if (!a || typeof a.frag !== 'string' || !a.frag.trim()) return null;
  const vw = Number(a.vw);
  const vh = Number(a.vh);
  if (!Number.isFinite(vw) || !Number.isFinite(vh) || vw <= 0 || vh <= 0) return null;
  return normalizeBox({
    ...base,
    art: {
      frag: a.frag,
      vx: Number(a.vx) || 0,
      vy: Number(a.vy) || 0,
      vw,
      vh,
      label: String(a.label ?? ''),
    },
  }, face);
}

const GLYPH_SOURCES = new Set(['system', 'handwriting', 'userfont', 'style']);

export function sanitizeGlyph(g) {
  const source = GLYPH_SOURCES.has(g?.source) ? g.source : 'system';
  const style = typeof g?.style === 'string' ? g.style : 'kaishu';
  return { source, style };
}

// ---- localStorage 自動存檔（DOM 環境才有 window；node 測試跳過） ----

export function saveDraft(card, storage = globalThis.localStorage) {
  if (!storage) return false;
  try {
    storage.setItem(STORAGE_KEY, serialize(card));
    return true;
  } catch {
    return false;
  }
}

export function loadDraft(storage = globalThis.localStorage) {
  if (!storage) return null;
  try {
    const raw = storage.getItem(STORAGE_KEY);
    return raw ? deserialize(raw) : null;
  } catch {
    return null;
  }
}
