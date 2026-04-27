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
