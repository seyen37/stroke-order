/* ============================================================
 * doodle_worker.js — Phase 5cf 塗鴉引擎 Web Worker 殼
 *
 * 在 Worker 內載入 doodle_engine.js（UMD → self.DoodleEngine），
 * 主執行緒經 message 協定委派 browser / opencv 引擎運算：
 *
 *   收：{id, engine, file, opts}
 *   發：{id, status}                （進度，如 OpenCV.js 首次載入）
 *       {id, ok: true, svg, ms}    （成功）
 *       {id, ok: false, error}     （失敗 → 主執行緒回退直跑）
 *
 * OpenCV.js 在 Worker 內由引擎的 loadOpenCV() 以 importScripts
 * 載入（5cf 分支）；OffscreenCanvas／createImageBitmap 皆為
 * Worker 原生能力。
 * ============================================================ */
/* eslint-env worker */
"use strict";

importScripts("/static/doodle_engine.js?v=151");   // 5cj cache-bust

self.onmessage = async function (ev) {
  var m = ev.data || {};
  var opts = m.opts || {};
  opts.onStatus = function (msg) {
    self.postMessage({id: m.id, status: msg});
  };
  try {
    var eng = self.DoodleEngine.DoodleEngines[m.engine];
    if (!eng || !eng.available()) {
      throw new Error("engine unavailable in worker: " + m.engine);
    }
    var res = await eng.render(m.file, opts);
    self.postMessage({id: m.id, ok: true, svg: res.svg, ms: res.ms,
                      paths: res.paths});
  } catch (e) {
    self.postMessage({
      id: m.id, ok: false,
      error: String((e && e.message) || e),
    });
  }
};
