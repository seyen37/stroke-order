// ======================================================================
// materials.js — Source of practice characters.
//
// Four types:
//   sutra     — fetch /api/sutra/text/:preset, iterate real glyphs
//   input     — typed string from #hw-input-string
//   upload    — .txt file via FileReader
//   freehand  — no source; user writes whatever they like (label later)
//
// Common interface (`MaterialIterator`):
//   .chars              array of single chars to practise (excl. punct/space
//                        for sutra/upload/input; empty for freehand)
//   .index              current position within `chars`
//   .total              chars.length
//   .currentChar()      char at .index, or '' for freehand / out-of-range
//   .next() / .prev()   move pointer (clamped). returns currentChar().
//   .reset()            back to start
//   .progress()         { index, total, percent }
// ======================================================================

// Match the same regex the backend uses for "real glyph" — Letters / Numbers.
// We avoid Unicode property escapes for older browser compat; CJK ranges
// covered by Letter category in modern engines anyway. Accepts any
// single non-whitespace, non-punctuation char.
const _REAL_GLYPH_RE = /^[^\s\p{P}]$/u;
function _isRealGlyph(ch) {
  if (!ch) return false;
  // Fallback for engines without /u flag support: just exclude common
  // ASCII whitespace/punct.
  try { return _REAL_GLYPH_RE.test(ch); }
  catch (_) { return /\S/.test(ch) && !/[\,\.\!\?;:'"]/.test(ch); }
}

function _stringToChars(text) {
  return Array.from(text || '').filter(_isRealGlyph);
}

// ---------------------------------------------------------------- iterator

class MaterialIterator {
  constructor(chars, meta) {
    this.chars = chars || [];
    this.index = 0;
    this.meta  = meta || {};
  }
  get total() { return this.chars.length; }
  currentChar() {
    if (this.chars.length === 0) return '';
    if (this.index < 0 || this.index >= this.chars.length) return '';
    return this.chars[this.index];
  }
  next() {
    if (this.index < this.chars.length - 1) this.index++;
    return this.currentChar();
  }
  prev() {
    if (this.index > 0) this.index--;
    return this.currentChar();
  }
  reset() { this.index = 0; return this.currentChar(); }
  progress() {
    return {
      index:   this.index,
      total:   this.total,
      percent: this.total === 0 ? 0
              : Math.round((this.index + 1) / this.total * 100),
    };
  }
}

// ---------------------------------------------------------------- sources

/** Load a sutra preset's text via the backend. */
export async function loadSutraMaterial(preset) {
  const r = await fetch(`/api/sutra/text/${encodeURIComponent(preset)}`);
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `sutra '${preset}' load failed (${r.status})`);
  }
  const data = await r.json();
  return new MaterialIterator(_stringToChars(data.text), {
    type:    'sutra',
    preset:  preset,
    title:   data.title || preset,
  });
}

/** Build an iterator from a literal string. */
export function loadInputMaterial(text) {
  return new MaterialIterator(_stringToChars(text), {
    type: 'input',
  });
}

/** Read a .txt File object and build an iterator. */
export async function loadUploadMaterial(file) {
  const text = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file, 'utf-8');
  });
  return new MaterialIterator(_stringToChars(text), {
    type:     'upload',
    filename: file.name,
  });
}

/** Empty iterator — freehand mode has no preset chars. */
export function loadFreehandMaterial() {
  return new MaterialIterator([], { type: 'freehand' });
}

// ----------------------------------------------- preset list (for dropdown)

/** Fetch the flat list of available sutra presets (for the <select>). */
export async function fetchSutraPresets() {
  const r = await fetch('/api/sutra/presets');
  if (!r.ok) throw new Error(`presets fetch failed (${r.status})`);
  const data = await r.json();
  // Each item: { key, title, ready, ... }
  return (data.presets || []).filter(p => p.ready);
}

export { MaterialIterator };
