// W4-R2 次批：顯式跨檔邊（原全域相依 → import/export 網）
import { API_BASE } from "./core.js?v=__V__";
import { sutraRender } from "./sutra.js?v=__V__";
// 5ew-R3：共用儲存層（練習史雙寫＋轉換器）——與筆順練習頁同一模組
import { saveTrace, uuid, swStrokesToTraceStrokes }
  from "../handwriting/storage.js?v=__V__";

// ============================================================
// 逐字手寫 (Phase 5dt) — 點抄經預覽格子 → 手寫自己的字 → 存 user-dict
// ============================================================
const SW = {
  positions: [],     // [{char, pos}] in reading order (from cellmap)
  index: 0,          // current position in `positions`
  strokes: [],       // [[ [x,y], ... ], ...] canvas-pixel coords
  active: null,
  dirty: false,      // any successful write this session → refresh preview
  hadSaved: false,   // 5dy: current char had a saved user-dict entry on open
                     // → clearing + submit deletes it (reverts to 描紅範本)
  anim: null,        // 5eb: requestAnimationFrame handle while replaying 筆順
  demoWriter: null,  // 5ec: hanzi-writer instance while showing 標準筆順示範
  refImg: null,      // 5en: styled 範字 image (篆/隸 etc.) for the current char,
                     // built from the preview's rendered glyph so the popup
                     // reference matches the selected 字型風格 (not a system font)
};

// 5en: build a faint reference-glyph <img> for the current cell from the
// ALREADY-RENDERED 抄經 preview, cropped to that cell's bbox. This makes the
// popup 範字 match the selected 字型風格 (篆書/隸書/宋…) instead of the browser
// system font that ctx.fillText would draw. Returns a loaded Image, or null
// (缺字 / no preview / error) → swDrawBase falls back to fillText.
async function swBuildRefImg(cur) {
  try {
    // 5ep 修：抄經預覽是 #su-preview（su-＝sutra）；5en 誤用 #st-preview
    // （st-＝印章 stamp）→ production 查無、回 null、fallback 系統字型楷書。
    const previewEl = document.getElementById("su-preview");
    if (!previewEl) return null;
    const rect = previewEl.querySelector(
      `#sutra-cellmap rect[data-pos="${cur.pos}"]`);
    const svg = previewEl.querySelector("svg");
    if (!rect || !svg) return null;
    const bb = rect.getBBox();               // cell bbox in SVG user units
    if (!bb || bb.width <= 0 || bb.height <= 0) return null;
    const NS = "http://www.w3.org/2000/svg";
    const out = document.createElementNS(NS, "svg");
    out.setAttribute("xmlns", NS);
    out.setAttribute("viewBox", `${bb.x} ${bb.y} ${bb.width} ${bb.height}`);
    out.setAttribute("width", "360");
    out.setAttribute("height", "360");
    // 5eq: use the FILLED letterform (reference / trace) as the popup 範字 — a
    // clean, thin seal/kaishu shape matching the grid 描紅. The skeleton layer
    // (sutra-trace-skeleton) is a thick 12%-of-char_size centreline drawing kept
    // at 0.03 opacity in the preview; 5en forced ALL layers to opacity 1 and
    // stacked them, so 篆/隸 turned into a heavy, merged blob whose round-cap
    // strokes also overran the glyph bbox (實機回報：太粗、筆畫重疊、比例偏大).
    // Clone ONLY the filled layer(s) when present; fall back to the skeleton
    // centreline only when no filled letterform exists (rare).
    // NOT the user handwriting, marks or cellmap. Recolour to a clearly-visible
    // light grey (print layers use very low opacity that would be invisible).
    let has = false;
    const _filledIds = ["sutra-glyph-reference", "sutra-trace"];
    const _useIds = _filledIds.some(id => svg.querySelector("#" + id))
      ? _filledIds
      : ["sutra-trace-skeleton"];
    for (const id of _useIds) {
      const g = svg.querySelector("#" + id);
      if (!g) continue;
      const clone = g.cloneNode(true);
      clone.removeAttribute("id");
      clone.setAttribute("opacity", "1");
      const f = clone.getAttribute("fill");
      const s = clone.getAttribute("stroke");
      if (f && f !== "none") clone.setAttribute("fill", "#c8c8c8");
      if (s && s !== "none") clone.setAttribute("stroke", "#c8c8c8");
      out.appendChild(clone);
      has = true;
    }
    if (!has) return null;
    const xml = new XMLSerializer().serializeToString(out);
    const url = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml);
    return await new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = url;
    });
  } catch (e) {
    console.warn("swBuildRefImg failed", e);
    return null;
  }
}

function swInit() {
  const $ = id => document.getElementById(id);
  if (!$("sw-overlay")) return;
  $("sw-close").onclick   = swClose;
  $("sw-undo").onclick    = () => { swStopAnim(); swHideDemo(); SW.strokes.pop(); swRedraw(); swInfo(); };
  $("sw-clear").onclick   = () => { swStopAnim(); swHideDemo(); SW.strokes = []; swRedraw(); swInfo(); };
  $("sw-play").onclick    = swPlayStrokes;   // 5eb: 重播你寫的筆順
  $("sw-demo-btn").onclick = swShowDemo;     // 5ec: 標準正確筆順示範
  $("sw-demo").onclick    = swHideDemo;      // 5ec: 點示範疊層收起回手寫
  $("sw-show-ref").onchange = swRedraw;
  $("sw-prev").onclick    = () => swNav(-1);
  $("sw-next").onclick    = () => swNav(1);
  $("sw-skip").onclick    = () => swNav(1, /*noSubmit=*/true);
  // 5ew-R3：進階練習——另開筆順練習頁練此字（完整軌跡/筆壓/練習史；
  // 該頁存檔預設同步回渲染字庫，回抄經重新產生預覽即見）
  $("sw-advanced").onclick = () => {
    const cur = SW.positions[SW.index];
    if (!cur) return;
    window.open(
      `/handwriting?char=${encodeURIComponent(cur.char)}&from=sutra`,
      "_blank", "noopener");
  };
  $("sw-submit").onclick  = swSubmitAndClose;
  $("sw-export").onclick  = () => {
    // 5dz: name the handwriting ZIP after the current 字型風格 —
    // {風格}_手寫字.zip (server maps the style code to its label).
    const style = (document.getElementById("su-style") || {}).value || "";
    const q = style ? `?style=${encodeURIComponent(style)}` : "";
    window.location.href = `${API_BASE}/api/user-dict/export${q}`;
  };
  $("sw-import").onclick  = () => $("sw-import-file").click();
  $("sw-import-file").addEventListener("change", swImport);
  $("sw-overlay").addEventListener("click", (e) => {
    if (e.target.id === "sw-overlay") swClose();
  });
  swBindCanvas();
}

// Wire clickable cells after each preview render (called by sutraRender).
function swAttachPreviewClicks(previewEl) {
  const rects = [...previewEl.querySelectorAll("#sutra-cellmap rect[data-char]")];
  // Build the reading-order position list (sorted by data-pos).
  SW.positions = rects
    .map(r => ({ char: r.getAttribute("data-char"),
                 pos: parseInt(r.getAttribute("data-pos"), 10),
                 missing: r.hasAttribute("data-missing") }))
    .sort((a, b) => a.pos - b.pos);
  rects.forEach(r => {
    r.style.cursor = "pointer";
    // faint hover highlight
    r.addEventListener("mouseenter", () => { r.setAttribute("fill", "rgba(80,140,255,.12)"); });
    r.addEventListener("mouseleave", () => { r.setAttribute("fill", "transparent"); });
    if (r.hasAttribute("data-missing")) {
      // subtle dashed outline so 缺字 cells read as "writable"
      r.setAttribute("stroke", "#e0a94f");
      r.setAttribute("stroke-width", "0.3");
      r.setAttribute("stroke-dasharray", "1,1");
    }
    r.addEventListener("click", () => {
      const p = parseInt(r.getAttribute("data-pos"), 10);
      const idx = SW.positions.findIndex(q => q.pos === p);
      swOpen(idx >= 0 ? idx : 0);
    });
  });
}

async function swOpen(index) {
  if (!SW.positions.length) return;
  SW.index = Math.max(0, Math.min(index, SW.positions.length - 1));
  document.getElementById("sw-overlay").style.display = "flex";
  await swLoadCurrent();
}

function swClose() {
  swStopAnim();   // 5eb
  swHideDemo();   // 5ec
  document.getElementById("sw-overlay").style.display = "none";
  if (SW.dirty) {            // reflect newly-written glyphs in the preview
    SW.dirty = false;
    sutraRender();
  }
}

// Load the current position: show char, preload existing user-dict strokes.
async function swLoadCurrent() {
  swStopAnim();          // 5eb: switching char stops any replay
  swHideDemo();          // 5ec: and any 標準示範 overlay
  const cur = SW.positions[SW.index];
  SW.strokes = [];
  SW.hadSaved = false;   // 5dy: reset; set true only if an entry preloads
  SW.refImg = null;      // 5en: rebuild styled 範字 for this char
  document.getElementById("sw-current-char").textContent = cur.char;
  document.getElementById("sw-progress").textContent =
    `第 ${SW.index + 1} / ${SW.positions.length} 字`;
  // 5en: styled reference glyph (篆/隸…) from the preview; drawn faint by
  // swDrawBase so the popup 範字 matches 字型風格. Refresh before first redraw.
  swBuildRefImg(cur).then((img) => {
    if (SW.positions[SW.index] === cur) { SW.refImg = img; swRedraw(); }
  });
  const st = document.getElementById("sw-status");
  st.textContent = ""; st.style.color = "var(--muted)";
  // Preload any handwriting the user already saved for this char (edit mode).
  try {
    const r = await fetch(`${API_BASE}/api/user-dict/${encodeURIComponent(cur.char)}`);
    if (r.ok) {
      const d = await r.json();
      const c = document.getElementById("sw-canvas");
      const W = c.width, H = c.height;
      SW.strokes = d.strokes.map(s => s.track.map(p => [p[0] / 2048 * W, p[1] / 2048 * H]));
      SW.hadSaved = true;   // 5dy: this char has a saved entry → 清空+送出 deletes it
      st.textContent = "（已載入你先前寫的版本；清空後送出會清除此字的手寫）";
    }
  } catch (_) { /* none yet — blank canvas */ }
  swRedraw(); swInfo();
}

// Submit the current char's strokes to the user dict. Returns true if a
// write happened (or nothing to write is treated as a no-op success).
async function swSubmitCurrent() {
  const valid = SW.strokes.filter(s => s.length >= 2);
  const cur = SW.positions[SW.index];
  // 5dy: empty canvas. If this char had a saved entry (loaded on open), the
  // user cleared it on purpose → DELETE it so the preview reverts to the
  // original 描紅範本. If there was no saved entry, an empty canvas is a
  // plain no-op (don't fire a pointless DELETE).
  if (valid.length === 0) {
    if (!SW.hadSaved) return { ok: true, wrote: false };
    try {
      const r = await fetch(
        `${API_BASE}/api/user-dict/${encodeURIComponent(cur.char)}`,
        { method: "DELETE" });
      if (!r.ok && r.status !== 404) {   // 404 = already gone, treat as done
        const e = await r.json().catch(() => ({ detail: r.statusText }));
        throw new Error(e.detail || `HTTP ${r.status}`);
      }
      SW.hadSaved = false;
      SW.dirty = true;   // preview must refresh — glyph reverts to 描紅
      const st = document.getElementById("sw-status");
      st.textContent = "（已清除此字的手寫，恢復原範本）";
      st.style.color = "#080";
      return { ok: true, wrote: true };
    } catch (e) {
      const st = document.getElementById("sw-status");
      st.textContent = "清除失敗：" + e.message; st.style.color = "var(--accent)";
      return { ok: false, wrote: false };
    }
  }
  const canvas = document.getElementById("sw-canvas");
  try {
    const r = await fetch(`${API_BASE}/api/user-dict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        char: cur.char,
        format: "handwriting",
        handwriting: { strokes: valid, canvas_width: canvas.width,
                       canvas_height: canvas.height },
      }),
    });
    if (!r.ok) {
      const e = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(e.detail || `HTTP ${r.status}`);
    }
    SW.hadSaved = true;   // 5dy: an entry now exists for this char
    SW.dirty = true;
    // 5ew-R3：雙寫練習史（IndexedDB）——簡潔版寫的字也進練習紀錄，
    // 筆順練習頁（進階版）看得到。fire-and-forget：失敗只記 console，
    // 不影響 user-dict 已存的事實。
    try {
      const traceStrokes = swStrokesToTraceStrokes(
        valid, canvas.width, canvas.height);
      saveTrace({
        id: uuid(),
        char: cur.char,
        label_source: "given",
        style: document.getElementById("su-style")?.value || "kaishu",
        tags: ["sutra-sw"],
        device: "unknown",
        ts: new Date().toISOString(),
        canvas_size: [canvas.width, canvas.height],
        em_size: 2048,
        strokes: traceStrokes,
        source: { kind: "sutra-sw" },
      }).catch(e => console.warn("練習史寫入失敗（user-dict 已存）", e));
    } catch (e) {
      console.warn("練習史轉換失敗（user-dict 已存）", e);
    }
    return { ok: true, wrote: true };
  } catch (e) {
    const st = document.getElementById("sw-status");
    st.textContent = "儲存失敗：" + e.message; st.style.color = "var(--accent)";
    return { ok: false, wrote: false };
  }
}

// Navigate: submit current (unless noSubmit) then move by `delta`.
async function swNav(delta, noSubmit) {
  if (!noSubmit) {
    const res = await swSubmitCurrent();
    if (!res.ok) return;   // stay put on save error
  }
  const next = SW.index + delta;
  if (next < 0 || next >= SW.positions.length) {
    const st = document.getElementById("sw-status");
    st.textContent = next < 0 ? "已是第一個字" : "已是最後一個字";
    st.style.color = "var(--muted)";
    return;
  }
  SW.index = next;
  await swLoadCurrent();
}

async function swSubmitAndClose() {
  const res = await swSubmitCurrent();
  if (!res.ok) return;
  swClose();
}

async function swImport(e) {
  const f = e.target.files[0];
  if (!f) return;
  const st = document.getElementById("sw-status");
  st.textContent = "匯入中…"; st.style.color = "var(--muted)";
  try {
    const fd = new FormData();
    fd.append("file", f);
    fd.append("policy", "replace");
    const r = await fetch(`${API_BASE}/api/user-dict/import`, { method: "POST", body: fd });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    st.textContent = `✓ 已匯入（新增 ${d.imported ?? "?"}）`; st.style.color = "#080";
    SW.dirty = true;
    await swLoadCurrent();
  } catch (err) {
    st.textContent = "匯入失敗：" + err.message; st.style.color = "var(--accent)";
  } finally {
    e.target.value = "";
  }
}

// ---- canvas ----
function swBindCanvas() {
  const c = document.getElementById("sw-canvas");
  c.addEventListener("pointerdown", e => {
    swStopAnim();   // 5eb: starting to draw interrupts any 筆順 replay
    swHideDemo();   // 5ec: and dismisses the 標準示範 overlay
    c.setPointerCapture(e.pointerId);
    SW.active = [swPt(e)]; SW.strokes.push(SW.active); swRedraw();
  });
  c.addEventListener("pointermove", e => {
    if (SW.active == null) return;
    SW.active.push(swPt(e)); swRedraw();
  });
  const fin = () => { if (SW.active == null) return; SW.active = null; swInfo(); };
  c.addEventListener("pointerup", fin);
  c.addEventListener("pointercancel", fin);
  c.addEventListener("pointerleave", fin);
}
function swPt(e) {
  const r = e.target.getBoundingClientRect();
  return [e.clientX - r.left, e.clientY - r.top];
}
function swInfo() {
  document.getElementById("sw-canvas-info").textContent =
    `${SW.strokes.filter(s => s.length >= 2).length} 筆畫`;
}
// 5eb: draw the canvas backdrop (faint reference char + 米字格) without ink.
// Shared by swRedraw and the 筆順 replay animation so both look identical.
function swDrawBase(ctx, W, H) {
  ctx.clearRect(0, 0, W, H);
  const cur = SW.positions[SW.index];
  if (cur && document.getElementById("sw-show-ref").checked) {
    if (SW.refImg) {
      // 5en: styled 範字 (篆/隸/宋…) rendered from the preview glyph — matches
      // the selected 字型風格 instead of a system-font fallback.
      ctx.drawImage(SW.refImg, 0, 0, W, H);
    } else {
      // fallback: system font (缺字 / no preview / non-抄經 caller). Approximates
      // kaishu/song; note it will NOT match 篆/隸 — only used when the styled
      // glyph is unavailable.
      ctx.save();
      ctx.fillStyle = "#dcdcdc";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = `${Math.round(H * 0.82)}px 'Noto Sans TC','PingFang TC','Microsoft JhengHei',sans-serif`;
      ctx.fillText(cur.char, W / 2, H / 2 + H * 0.02);
      ctx.restore();
    }
  }
  // 米字格
  ctx.strokeStyle = "#e8e8e8"; ctx.lineWidth = 1;
  ctx.strokeRect(0.5, 0.5, W - 1, H - 1);
  ctx.beginPath();
  ctx.moveTo(0, 0); ctx.lineTo(W, H);
  ctx.moveTo(W, 0); ctx.lineTo(0, H);
  ctx.moveTo(W / 2, 0); ctx.lineTo(W / 2, H);
  ctx.moveTo(0, H / 2); ctx.lineTo(W, H / 2);
  ctx.stroke();
}

function swRedraw() {
  const c = document.getElementById("sw-canvas");
  const ctx = c.getContext("2d");
  const W = c.width, H = c.height;
  swDrawBase(ctx, W, H);
  // ink
  ctx.strokeStyle = "#222"; ctx.lineWidth = 4;
  ctx.lineCap = "round"; ctx.lineJoin = "round";
  for (const s of SW.strokes) {
    if (s.length < 2) continue;
    ctx.beginPath();
    ctx.moveTo(s[0][0], s[0][1]);
    for (let i = 1; i < s.length; i++) ctx.lineTo(s[i][0], s[i][1]);
    ctx.stroke();
  }
}

// 5eb: cancel any in-flight 筆順 replay.
function swStopAnim() {
  if (SW.anim) { cancelAnimationFrame(SW.anim); SW.anim = null; }
}

// 5eb: replay the user's OWN handwriting stroke-by-stroke — progressively
// draw SW.strokes in write order (with a red pen-tip dot at the leading
// edge), paced by total point count. Works for any char since it plays
// back the user's own captured raw_track, not a font.
function swPlayStrokes() {
  const valid = SW.strokes.filter(s => s.length >= 2);
  const st = document.getElementById("sw-status");
  if (!valid.length) {
    st.textContent = "（尚無筆跡可播放，先寫幾筆再播）";
    st.style.color = "var(--muted)";
    return;
  }
  swStopAnim();
  const c = document.getElementById("sw-canvas");
  const ctx = c.getContext("2d");
  const W = c.width, H = c.height;
  const totalPts = valid.reduce((a, s) => a + s.length, 0);
  const DURATION = Math.min(4500, Math.max(1400, totalPts * 14));  // ms
  let t0 = null;
  function frame(now) {
    if (t0 == null) t0 = now;
    const prog = Math.min(1, (now - t0) / DURATION);
    const showN = Math.round(prog * totalPts);
    swDrawBase(ctx, W, H);
    ctx.strokeStyle = "#222"; ctx.lineWidth = 4;
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    let count = 0, tip = null;
    for (const s of valid) {
      if (count >= showN) break;
      const take = Math.min(s.length, showN - count);
      if (take >= 2) {
        ctx.beginPath();
        ctx.moveTo(s[0][0], s[0][1]);
        for (let i = 1; i < take; i++) ctx.lineTo(s[i][0], s[i][1]);
        ctx.stroke();
      }
      if (take >= 1 && take < s.length) tip = s[take - 1];  // pen still on this stroke
      count += s.length;
    }
    if (tip) {
      ctx.save();
      ctx.fillStyle = "#c0392b";
      ctx.beginPath(); ctx.arc(tip[0], tip[1], 5, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    }
    if (prog < 1) {
      SW.anim = requestAnimationFrame(frame);
    } else {
      SW.anim = null;
      swRedraw();   // settle to the clean full-ink state (no pen tip)
    }
  }
  st.textContent = "▶ 播放筆順中…";
  st.style.color = "var(--muted)";
  swHideDemo();   // 5ec: own-stroke replay and 標準示範 are mutually exclusive
  SW.anim = requestAnimationFrame(frame);
}

// 5ec: hide/cancel the 標準筆順 demo overlay (back to the drawing canvas).
function swHideDemo() {
  const demo = document.getElementById("sw-demo");
  if (!demo) return;
  if (SW.demoWriter) {
    try { SW.demoWriter.cancelQuiz && SW.demoWriter.cancelQuiz(); } catch (_) {}
    SW.demoWriter = null;
  }
  demo.style.display = "none";
  demo.innerHTML = "";
}

// 5ec: show the CORRECT stroke order for the current char as a hanzi-writer
// animation overlaid on the 米字格. Data comes from /api/character (the
// project's own g0v/教育部/CNS stroke data — far wider coverage than
// hanzi-writer's default CDN). Chars with no stroke data degrade honestly.
async function swShowDemo() {
  const cur = SW.positions[SW.index];
  if (!cur) return;
  const st = document.getElementById("sw-status");
  const demo = document.getElementById("sw-demo");
  if (typeof HanziWriter === "undefined") {
    st.textContent = "筆順示範元件未載入"; st.style.color = "var(--accent)";
    return;
  }
  st.textContent = "載入標準筆順…"; st.style.color = "var(--muted)";
  const src = (document.getElementById("su-source") || {}).value || "auto";
  const qs = new URLSearchParams({ source: src, hook_policy: "animation" }).toString();
  try {
    const r = await fetch(`${API_BASE}/api/character/${encodeURIComponent(cur.char)}?${qs}`);
    if (!r.ok) throw new Error("no-data");
    const data = await r.json();
    swStopAnim();          // stop own-stroke replay if running
    demo.innerHTML = "";
    demo.style.display = "block";
    SW.demoWriter = HanziWriter.create(demo, cur.char, {
      width: 360, height: 360, padding: 8,
      strokeAnimationSpeed: 1.0,
      delayBetweenStrokes: 220,
      showOutline: true,
      showCharacter: false,   // trace-style: faint outline + animate strokes in order
      strokeColor: "#1565c0",
      radicalColor: "#c0392b",
      charDataLoader: (_c, onComplete) => onComplete(data),
    });
    SW.demoWriter.animateCharacter();
    st.textContent = "標準筆順示範中（點畫布收起回手寫）";
    st.style.color = "var(--muted)";
  } catch (e) {
    swHideDemo();
    st.textContent = "此字無標準筆順資料，無法示範";
    st.style.color = "var(--accent)";
  }
}

// W4-R2：跨檔邊匯出（消費端見 import 網）
export { swAttachPreviewClicks, swInit };
