// ======================================================================
// exporter.js — JSON / Plotter SVG / ZIP export + JSON import.
//
// JSON file shape (schema v1):
//   {
//     "schema":     "stroke-order-psd-v1",
//     "exported_at": "ISO 8601",
//     "trace_count": <int>,
//     "traces":      [ <trace>, ... ]   // matches storage.js Trace shape
//   }
//
// Plotter SVG shape (per character):
//   <svg viewBox="0 0 2048 2048" width="50mm" height="50mm">
//     <title>{char}</title>
//     <desc>...</desc>
//     <metadata id="psd-meta">{ JSON … }</metadata>
//     <g stroke="#000" fill="none" stroke-linecap="round"
//        stroke-linejoin="round" stroke-width="40">
//       <polyline points="x,y x,y …"
//                 data-stroke-index="0"
//                 data-duration-ms="320"
//                 data-avg-pressure="0.62"/>
//       …
//     </g>
//   </svg>
//
// The polylines live in EM 2048 (Y-down) — the same coord system the
// existing stroke-order plotter pipeline uses, so these SVGs can be
// fed straight into the writing-robot output stage.
//
// ZIP packaging: minimal STORE-mode encoder (no compression). Plain
// Uint8Array assembly + CRC32 — ~80 lines, no vendor dependency.
// ======================================================================

import {
  listAllTraces, saveTrace, clearAllTraces, getDbStats,
} from './storage.js';

// ============================================================ JSON

const SCHEMA_TAG = 'stroke-order-psd-v1';

/** Trigger a download of the entire IDB as a single JSON file. */
export async function exportAllJson() {
  const traces = await listAllTraces();
  const payload = {
    schema:       SCHEMA_TAG,
    exported_at:  new Date().toISOString(),
    trace_count:  traces.length,
    traces,
  };
  const blob = new Blob(
    [JSON.stringify(payload, null, 2)],
    { type: 'application/json' },
  );
  const ts = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, '');
  triggerDownload(blob, `psd_${ts}.json`);
  return traces.length;
}

/**
 * Read a previously-exported JSON file. Modes:
 *   'merge'    — keep existing IDB entries, add the imported ones with
 *                fresh UUIDs to avoid id collisions.
 *   'replace'  — wipe IDB first, then import.
 * Returns { imported, skipped, mode }.
 */
export async function importJson(file, mode = 'merge') {
  const text = await readFileAsText(file);
  let data;
  try {
    data = JSON.parse(text);
  } catch (e) {
    throw new Error('檔案格式錯誤（JSON 解析失敗）');
  }
  if (!data || data.schema !== SCHEMA_TAG) {
    throw new Error(
      `不支援的檔案版本：${data?.schema || '(無 schema)'}` +
      `；本系統需 ${SCHEMA_TAG}`,
    );
  }
  const incoming = Array.isArray(data.traces) ? data.traces : [];
  if (mode === 'replace') {
    await clearAllTraces();
  }
  let imported = 0;
  let skipped = 0;
  for (const t of incoming) {
    if (!t || !t.char || !Array.isArray(t.strokes)) {
      skipped++;
      continue;
    }
    // On merge mode, regenerate id so we can re-run import safely.
    const record = mode === 'merge'
      ? { ...t, id: crypto.randomUUID?.() || _fallbackUuid() }
      : t;
    try {
      await saveTrace(record);
      imported++;
    } catch (e) {
      console.warn('skipped trace', e, t);
      skipped++;
    }
  }
  return { imported, skipped, mode };
}

// ============================================================ Plotter SVG

const EM_SIZE      = 2048;
const PHYS_MM_SIZE = 50;     // default physical canvas ⇒ 50mm × 50mm
const STROKE_WIDTH = 40;     // EM units ⇒ ~1mm at 50mm — looks like a pen
const STROKE_COLOR = '#000';

/** Build the SVG text for a single trace. Pure — no DOM access. */
export function traceToSvg(trace) {
  const meta = {
    char:        trace.char,
    style:       trace.style,
    label_source: trace.label_source,
    tags:        trace.tags || [],
    device:      trace.device,
    ts:          trace.ts,
    em_size:     trace.em_size || EM_SIZE,
    source:      trace.source || null,
    schema:      SCHEMA_TAG,
  };
  const polyEls = (trace.strokes || []).map((s, i) => {
    const pts = (s.points || []).map(p =>
      `${(+p[0]).toFixed(1)},${(+p[1]).toFixed(1)}`).join(' ');
    const avgP = _avgPressure(s.points);
    const dur = (s.duration_ms != null ? s.duration_ms : 0).toFixed(0);
    return (
      `    <polyline points="${pts}"\n` +
      `              data-stroke-index="${i}"\n` +
      `              data-duration-ms="${dur}"\n` +
      `              data-avg-pressure="${avgP.toFixed(3)}"/>`
    );
  }).join('\n');

  // We escape only the metadata block — stroke data is numeric.
  const metaJson = JSON.stringify(meta).replace(/[<&]/g, ch =>
    ch === '<' ? '&lt;' : '&amp;');
  const charSafe = _xmlText(trace.char);
  const desc = `Captured ${meta.ts || ''} via stroke-order PSD.`;

  return (
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<svg xmlns="http://www.w3.org/2000/svg" ` +
    `viewBox="0 0 ${EM_SIZE} ${EM_SIZE}" ` +
    `width="${PHYS_MM_SIZE}mm" height="${PHYS_MM_SIZE}mm">\n` +
    `  <title>${charSafe}</title>\n` +
    `  <desc>${_xmlText(desc)}</desc>\n` +
    `  <metadata id="psd-meta">${metaJson}</metadata>\n` +
    `  <g stroke="${STROKE_COLOR}" fill="none" ` +
    `stroke-linecap="round" stroke-linejoin="round" ` +
    `stroke-width="${STROKE_WIDTH}">\n` +
    `${polyEls}\n` +
    `  </g>\n` +
    `</svg>\n`
  );
}

/** Trigger a download of one trace as a Plotter SVG file. */
export function exportTraceSvg(trace) {
  const svg = traceToSvg(trace);
  const blob = new Blob([svg], { type: 'image/svg+xml' });
  triggerDownload(blob, _safeSvgFilename(trace));
}

/** Bundle every IDB trace as one .zip (STORE mode, no compression). */
export async function exportAllSvgZip() {
  const traces = await listAllTraces();
  if (traces.length === 0) {
    throw new Error('資料庫沒有任何軌跡可匯出');
  }
  const enc = new TextEncoder();
  const files = {};
  for (const t of traces) {
    const fname = _safeSvgFilename(t);
    files[_uniqueName(files, fname)] = enc.encode(traceToSvg(t));
  }
  const blob = makeZip(files);
  const ts = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, '');
  triggerDownload(blob, `psd_svg_${ts}.zip`);
  return traces.length;
}

// ============================================================ filename utils

function _safeSvgFilename(trace) {
  // Encode the char as its hex codepoint so the filename works even on
  // platforms that mangle CJK in zip entries (Windows Explorer in
  // particular has historically been twitchy here).
  const ch = trace.char || '_';
  const hex = Array.from(ch)
    .map(c => c.codePointAt(0).toString(16).padStart(4, '0'))
    .join('');
  const ts = (trace.ts || '').replace(/[-:T]/g, '').slice(0, 14);
  const style = (trace.style || 'kaishu').replace(/[^a-z0-9_-]/gi, '_');
  return `${ch}_${hex}_${style}_${ts}.svg`;
}

function _uniqueName(files, name) {
  if (!(name in files)) return name;
  // shouldn't happen often — same char/style/ts collision — append idx
  let i = 2;
  while ((`${name.replace(/\.svg$/, '')}_${i}.svg`) in files) i++;
  return `${name.replace(/\.svg$/, '')}_${i}.svg`;
}

function _avgPressure(points) {
  if (!points || !points.length) return 0;
  let sum = 0, n = 0;
  for (const p of points) {
    if (p && p.length >= 4 && Number.isFinite(p[3])) {
      sum += p[3]; n++;
    }
  }
  return n === 0 ? 0 : (sum / n);
}

function _xmlText(s) {
  return String(s || '').replace(/[<&>'"]/g, ch => ({
    '<': '&lt;', '&': '&amp;', '>': '&gt;',
    '"': '&quot;', "'": '&apos;',
  })[ch]);
}

// ============================================================ download

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Defer revoke so the browser has a chance to start the download.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file, 'utf-8');
  });
}

function _fallbackUuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, ch => {
    const r = (Math.random() * 16) | 0;
    return (ch === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

// ============================================================ minimal ZIP
//
// STORE-mode (no compression) ZIP encoder. Spec reference:
//   https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT
// Sections used: 4.3.7 (local file header), 4.3.12 (central directory),
// 4.3.16 (end of central directory record).
//
// Limitations (intentional, MVP):
//   - No compression (DEFLATE) — file size = sum of contents + ~46B per
//     entry. Plotter SVGs are small; this is fine.
//   - No ZIP64 — single file > 4 GB will overflow. We're nowhere near.
//   - Filenames must be < 64 KiB UTF-8.
//
// CRC-32 polynomial 0xEDB88320 (IEEE 802.3, used by ZIP / PNG / gzip).
//

const CRC32_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) {
      c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    }
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(bytes) {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < bytes.length; i++) {
    crc = CRC32_TABLE[(crc ^ bytes[i]) & 0xFF] ^ (crc >>> 8);
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

/**
 * Build a ZIP blob from a `{ filename: Uint8Array }` mapping.
 * Returns: Blob('application/zip')
 */
export function makeZip(files) {
  const enc = new TextEncoder();
  const localChunks = [];   // [Uint8Array, ...] — interleaved header + content
  const cdChunks    = [];   // central directory entries
  let offset = 0;

  for (const [name, content] of Object.entries(files)) {
    const nameBytes = enc.encode(name);
    const crc = crc32(content);
    const size = content.length;

    // 4.3.7 Local File Header (30 bytes + filename)
    const lh = new Uint8Array(30 + nameBytes.length);
    const lhv = new DataView(lh.buffer);
    lhv.setUint32(0,  0x04034b50, true);     // signature
    lhv.setUint16(4,  20, true);             // version needed (2.0)
    lhv.setUint16(6,  0x0800, true);         // flags: bit 11 = UTF-8 names
    lhv.setUint16(8,  0, true);              // method: 0 = STORE
    lhv.setUint16(10, 0, true);              // mod time (unused)
    lhv.setUint16(12, 0, true);              // mod date (unused)
    lhv.setUint32(14, crc, true);
    lhv.setUint32(18, size, true);           // compressed size
    lhv.setUint32(22, size, true);           // uncompressed size
    lhv.setUint16(26, nameBytes.length, true);
    lhv.setUint16(28, 0, true);              // extra field length
    lh.set(nameBytes, 30);

    localChunks.push(lh, content);

    // 4.3.12 Central Directory Header (46 bytes + filename)
    const cd = new Uint8Array(46 + nameBytes.length);
    const cv = new DataView(cd.buffer);
    cv.setUint32(0,  0x02014b50, true);     // signature
    cv.setUint16(4,  20, true);             // version made by
    cv.setUint16(6,  20, true);             // version needed
    cv.setUint16(8,  0x0800, true);         // flags: UTF-8
    cv.setUint16(10, 0, true);              // method
    cv.setUint16(12, 0, true);              // mod time
    cv.setUint16(14, 0, true);              // mod date
    cv.setUint32(16, crc, true);
    cv.setUint32(20, size, true);
    cv.setUint32(24, size, true);
    cv.setUint16(28, nameBytes.length, true);
    cv.setUint16(30, 0, true);              // extra field length
    cv.setUint16(32, 0, true);              // file comment length
    cv.setUint16(34, 0, true);              // disk number
    cv.setUint16(36, 0, true);              // internal attrs
    cv.setUint32(38, 0, true);              // external attrs
    cv.setUint32(42, offset, true);         // local header offset
    cd.set(nameBytes, 46);

    cdChunks.push(cd);
    offset += lh.length + content.length;
  }

  // 4.3.16 End of Central Directory Record (22 bytes)
  const cdSize = cdChunks.reduce((a, c) => a + c.length, 0);
  const eocd = new Uint8Array(22);
  const ev = new DataView(eocd.buffer);
  ev.setUint32(0,  0x06054b50, true);
  ev.setUint16(4,  0, true);                // disk number
  ev.setUint16(6,  0, true);                // disk where CD starts
  ev.setUint16(8,  cdChunks.length, true);  // entries on this disk
  ev.setUint16(10, cdChunks.length, true);  // total entries
  ev.setUint32(12, cdSize, true);
  ev.setUint32(16, offset, true);           // offset of CD
  ev.setUint16(20, 0, true);                // comment length

  return new Blob([...localChunks, ...cdChunks, eocd], {
    type: 'application/zip',
  });
}

// Re-export DB summary so handwriting.html can show counts.
export { getDbStats };
