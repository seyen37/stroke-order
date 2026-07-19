// ======================================================================
// storage.js — IndexedDB wrapper for handwriting traces (PSD).
//
// Schema v1:
//   DB:    stroke-order-practice
//   Store: traces    keyPath=id, indices: char | style | ts
//   Store: settings  keyPath=key
//
// All public functions return Promises. Failures reject, so callers can
// `try/catch` around their IDB work without dealing with raw IDBRequests.
// ======================================================================

const DB_NAME       = 'stroke-order-practice';
const DB_VERSION    = 1;
const STORE_TRACES  = 'traces';
const STORE_SETS    = 'settings';

let _dbPromise = null;

function openDb() {
  if (_dbPromise) return _dbPromise;
  _dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_TRACES)) {
        const s = db.createObjectStore(STORE_TRACES, {keyPath: 'id'});
        s.createIndex('char',  'char',  {unique: false});
        s.createIndex('style', 'style', {unique: false});
        s.createIndex('ts',    'ts',    {unique: false});
      }
      if (!db.objectStoreNames.contains(STORE_SETS)) {
        db.createObjectStore(STORE_SETS, {keyPath: 'key'});
      }
    };
    req.onerror   = () => reject(req.error);
    req.onsuccess = () => resolve(req.result);
  });
  return _dbPromise;
}

// Generic IDBRequest wrapper. `fn(store)` must return a single IDBRequest.
function reqOnStore(storeName, mode, fn) {
  return openDb().then(db => new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, mode);
    const req = fn(tx.objectStore(storeName));
    tx.oncomplete = () => resolve(req.result);
    tx.onerror    = () => reject(tx.error);
    tx.onabort    = () => reject(tx.error || new Error('tx aborted'));
  }));
}

// --------------------------------------------------------------- traces

export async function saveTrace(trace) {
  if (!trace || !trace.id) throw new Error('trace.id required');
  return reqOnStore(STORE_TRACES, 'readwrite', s => s.put(trace));
}

export async function getTrace(id) {
  return reqOnStore(STORE_TRACES, 'readonly', s => s.get(id));
}

export async function listAllTraces() {
  return reqOnStore(STORE_TRACES, 'readonly', s => s.getAll());
}

export async function deleteTrace(id) {
  return reqOnStore(STORE_TRACES, 'readwrite', s => s.delete(id));
}

export async function clearAllTraces() {
  return reqOnStore(STORE_TRACES, 'readwrite', s => s.clear());
}

export async function countTraces() {
  return reqOnStore(STORE_TRACES, 'readonly', s => s.count());
}

// Unique chars covered. Cursor walks the `char` index keys.
export async function listUniqueChars() {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_TRACES, 'readonly');
    const idx = tx.objectStore(STORE_TRACES).index('char');
    const out = new Set();
    const cur = idx.openKeyCursor();
    cur.onsuccess = (e) => {
      const c = e.target.result;
      if (!c) return;
      out.add(c.key);
      c.continue();
    };
    tx.oncomplete = () => resolve(Array.from(out));
    tx.onerror    = () => reject(tx.error);
  });
}

// --------------------------------------------------------------- settings

export async function getSetting(key) {
  const row = await reqOnStore(STORE_SETS, 'readonly', s => s.get(key));
  return row?.value;
}

export async function setSetting(key, value) {
  return reqOnStore(STORE_SETS, 'readwrite', s => s.put({key, value}));
}

// --------------------------------------------------------------- helpers

// RFC 4122 v4 UUID. Uses crypto.randomUUID when available; falls back
// for older Safari versions.
export function uuid() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, ch => {
    const r = (Math.random() * 16) | 0;
    const v = ch === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// Return aggregate stats useful for the dashboard.
export async function getDbStats() {
  const [count, uniqueChars] = await Promise.all([
    countTraces(),
    listUniqueChars(),
  ]);
  return {
    count,
    unique_chars: uniqueChars.length,
  };
}

// ======================================================================
// 5ew-R3：共用儲存層雙寫——筆順練習（進階版）×逐字手寫（簡潔版）整合
//
// 本模組升格為兩介面共用的儲存層：
//   IndexedDB traces＝完整練習史（EM 2048 六元組點列：x,y,t,壓力,tilt）
//   server user-dict＝渲染字庫（各模式渲染吃它；純 [x,y] 折線）
// 進階版 COMMIT：存練習史＋（預設勾選、可取消）同步渲染字庫；
// 簡潔版 送出：照舊寫渲染字庫＋（新增）補寫練習史。
// 轉換器是純函式——node --test 直測（tests/test_practice_store.mjs）。
// ======================================================================

export const TRACE_EM = 2048;

/** trace strokes（六元組點列）→ user-dict handwriting 折線（純 [x,y]）。 */
export function traceStrokesToUserDict(traceStrokes) {
  return (traceStrokes || [])
    .map(s => (s.points || []).map(p => [p[0], p[1]]))
    .filter(s => s.length >= 2);
}

/**
 * SW 簡潔版畫布筆畫（canvas 像素 [x,y]）→ trace strokes（EM 2048）。
 * 簡潔版不採時間/壓力——t=0、壓力 0.5（誠實降階，不捏造時序）。
 */
export function swStrokesToTraceStrokes(strokes, canvasW, canvasH) {
  const sx = TRACE_EM / (canvasW || TRACE_EM);
  const sy = TRACE_EM / (canvasH || TRACE_EM);
  return (strokes || [])
    .filter(s => s && s.length >= 2)
    .map(s => {
      const points = s.map(([x, y]) =>
        [Math.max(0, Math.min(TRACE_EM, x * sx)),
         Math.max(0, Math.min(TRACE_EM, y * sy)), 0, 0.5, 0, 0]);
      return {
        points,
        duration_ms: 0,
        pen_down_at: [points[0][0], points[0][1]],
        pen_up_at: [points[points.length - 1][0], points[points.length - 1][1]],
        device: 'unknown',
      };
    });
}

/** 練習史 trace → 渲染字庫（POST /api/user-dict，canvas 空間＝EM 2048）。 */
export async function syncTraceToUserDict(char, traceStrokes) {
  const strokes = traceStrokesToUserDict(traceStrokes);
  if (!strokes.length) return { ok: false, detail: 'no strokes' };
  const r = await fetch('/api/user-dict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      char,
      format: 'handwriting',
      handwriting: { strokes, canvas_width: TRACE_EM,
                     canvas_height: TRACE_EM },
    }),
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: r.statusText }));
    return { ok: false, detail: e.detail || `HTTP ${r.status}` };
  }
  return { ok: true };
}

/**
 * 雙寫入口：存練習史（IndexedDB）＋（可選）同步渲染字庫。
 * user-dict 失敗不影響練習史已存的事實——回傳分項結果讓 UI 個別提示。
 */
export async function saveDual(record, { toUserDict = false } = {}) {
  await saveTrace(record);
  let synced = null;
  if (toUserDict) {
    try {
      synced = await syncTraceToUserDict(record.char, record.strokes);
    } catch (e) {
      synced = { ok: false, detail: String(e && e.message || e) };
    }
  }
  return { saved: true, synced };
}
