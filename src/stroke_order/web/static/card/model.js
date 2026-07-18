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
//   box = { id, kind: "text", x, y, w, h,          // mm
//           text, sizeMm, vertical,
//           glyph: { source: "system"|"handwriting"|"userfont"|"style",
//                    style: "kaishu"|... } }        // R2 消費
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
      .filter((b) => b && b.kind === 'text' && typeof b.id === 'string')
      .map((b) => normalizeBox(
        {
          id: b.id,
          kind: 'text',
          x: Number(b.x) || 0,
          y: Number(b.y) || 0,
          w: Number(b.w) || 10,
          h: Number(b.h) || 10,
          text: String(b.text ?? ''),
          sizeMm: Number(b.sizeMm) || 8,
          vertical: !!b.vertical,
          glyph: sanitizeGlyph(b.glyph),
        },
        f,
      ));
  }
  return card;
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
