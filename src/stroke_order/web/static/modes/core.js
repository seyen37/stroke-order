// W4-R2 次批：顯式跨檔邊（原全域相依 → import/export 網）
import { renderCnsDecomposition } from "./fonts.js?v=__V__";

// ==== Wakeup overlay controller (Render free-tier cold-start UX) ====
// 包一層 window.fetch：第一個 fetch 超過 3 秒未回應就顯示 overlay。
// 同 session 喚醒過後不再觸發（用 sessionStorage 標記）。
// 多個 fetch 同時 in-flight 時只計第一個 + 最後一個。
(function installWakeupOverlay() {
  const SHOW_DELAY = 3000;   // ms — 超過這時間才顯示
  const STAGE_2_AT = 7000;   // ms — overlay 顯示後再過這時間切 stage 2 (10s 總計)
  const STAGE_3_AT = 27000;  // ms — overlay 顯示後再過這時間切 stage 3 (30s 總計)

  const overlay = document.getElementById('wakeup-overlay');
  if (!overlay) return;  // safety: should never happen

  const originalFetch = window.fetch.bind(window);
  let inFlight = 0;
  let showTimer = null, stage2Timer = null, stage3Timer = null;

  function isAwake() {
    try { return sessionStorage.getItem('wakeupSeen') === '1'; }
    catch (e) { return false; }
  }
  function markAwake() {
    try { sessionStorage.setItem('wakeupSeen', '1'); } catch (e) {}
  }

  function showOverlay() {
    overlay.classList.remove('stage-2', 'stage-3');
    overlay.classList.add('show');
    overlay.setAttribute('aria-hidden', 'false');
    stage2Timer = setTimeout(() => overlay.classList.add('stage-2'), STAGE_2_AT);
    stage3Timer = setTimeout(() => overlay.classList.add('stage-3'), STAGE_3_AT);
  }
  function hideOverlay() {
    overlay.classList.remove('show', 'stage-2', 'stage-3');
    overlay.setAttribute('aria-hidden', 'true');
    clearTimeout(showTimer); clearTimeout(stage2Timer); clearTimeout(stage3Timer);
    showTimer = stage2Timer = stage3Timer = null;
  }

  window.fetch = function(...args) {
    if (isAwake()) return originalFetch(...args);

    if (inFlight === 0) {
      // 第一個請求 — 啟動延遲顯示計時
      showTimer = setTimeout(showOverlay, SHOW_DELAY);
    }
    inFlight++;

    return originalFetch(...args).finally(() => {
      inFlight--;
      if (inFlight === 0) {
        hideOverlay();
        markAwake();  // 第一輪 fetch 全結束 → 視為已喚醒
      }
    });
  };
})();

const API_BASE = "";  // same origin

let currentWriter = null;
let currentChar = null;
let currentMeta = null;

function qparams() {
  const src  = document.getElementById("source").value;
  const hook = document.getElementById("hook").value;
  const mode = document.getElementById("mode").value;
  const cs   = document.getElementById("char_size").value;
  const fr   = document.getElementById("feed_rate").value;
  return {
    source: src, hook_policy: hook, mode: mode,
    char_size: cs, feed_rate: fr,
  };
}

async function load() {
  const char = document.getElementById("char").value.trim();
  if (!char || char.length !== 1) {
    alert("請輸入恰好一個中文字");
    return;
  }
  currentChar = char;
  const p = qparams();
  const qs = new URLSearchParams({
    source: p.source, hook_policy: p.hook_policy,
  }).toString();

  // 1. Load hanzi-writer-formatted data for preview
  try {
    const dataResp = await fetch(`${API_BASE}/api/character/${encodeURIComponent(char)}?${qs}`);
    if (!dataResp.ok) {
      const err = await dataResp.json().catch(() => ({detail: dataResp.statusText}));
      throw new Error(err.detail || "unknown error");
    }
    const data = await dataResp.json();

    // 2. Load meta for diagnostics
    const metaResp = await fetch(`${API_BASE}/api/meta/${encodeURIComponent(char)}?${qs}`);
    currentMeta = await metaResp.json();
    renderDiagnostics(currentMeta);

    // 3. Set up hanzi-writer preview
    renderPreview(char, data);

    // 4. Populate download links
    renderDownloads(char, p);

    // 5. Render decomposition section (5000.TXT + CNS 部件)
    renderDecomposition(currentMeta);
    renderCnsDecomposition(char);
  } catch (e) {
    document.getElementById("diagnostics").textContent = `載入失敗：${e.message}`;
    document.getElementById("diag-badges").innerHTML =
      `<span class="badge error">ERROR</span>`;
  }
}

function renderPreview(char, data) {
  const target = document.getElementById("preview");
  target.innerHTML = "";
  if (currentWriter) { currentWriter.cancelQuiz?.(); }
  currentWriter = HanziWriter.create(target, char, {
    width: 280, height: 280, padding: 6,
    strokeAnimationSpeed: 1.2,
    delayBetweenStrokes: 120,
    showCharacter: true,
    charDataLoader: (_c, onComplete) => onComplete(data),
  });
}

function renderDecomposition(meta) {
  const elem = document.getElementById("decomposition");
  const d = meta.decomposition;
  const rad = meta.radical_category;
  // If neither decomposition nor radical classification, show empty state.
  if (!d && !rad) {
    elem.innerHTML = `<em style="color:var(--muted);">
      （${meta.character} 不在朱邦復資料庫中）</em>`;
    return;
  }
  // Radical category badge (Phase 4 — 2018 四大類)
  let radBadge = "";
  if (rad) {
    const [cat, sub] = rad.split("/");
    const palette = {
      "本存": "#c7e7c7",  // greenish — natural
      "人造": "#d4d4f7",  // purplish — manufactured
      "規範": "#f7e0c7",  // orange — abstract
      "應用": "#f7c7d4",  // pink — relational
    };
    const bg = palette[cat] || "#eee";
    radBadge = `<span class="badge" style="background:${bg};color:#333;">部首 ${rad}</span>`;
  }
  // If no decomposition but we have radical, render minimal
  if (!d) {
    elem.innerHTML = `<div>${radBadge}
      <span style="color:var(--muted);margin-left:6px;">
      (不在 5000 會意字資料庫)</span></div>`;
    return;
  }
  const partBox = (label, root, role, def) => {
    if (!root) return "";
    const roleText = role ? ` <span class="badge ok">${role}</span>` : "";
    return `<div style="margin:4px 0;">
        <b>${label}：</b>「${root}」${roleText}
        <span style="color:var(--muted);">${def}</span></div>`;
  };
  const atomBadge = d.is_atom
    ? `<span class="badge ok">${d.category}</span>`
    : `<span class="badge fix">${d.category}</span>`;
  const formBadge = d.earliest_form
    ? `<span class="badge warn">${d.earliest_form}</span>` : "";
  elem.innerHTML = `
    <div style="margin-bottom:6px;">${atomBadge} ${formBadge} ${radBadge}
      <span style="color:var(--muted);">${d.concept || ''}</span></div>
    ${partBox("字首", d.head_root, d.head_role, d.head_def)}
    ${partBox("字尾", d.tail_root, d.tail_role, d.tail_def)}
  `;
}

function renderDiagnostics(meta) {
  const badges = [];
  const v = meta.validation || {};
  if (v.is_valid)  badges.push(`<span class="badge ok">VALID</span>`);
  else             badges.push(`<span class="badge error">INVALID</span>`);
  if (v.fix_was_applied) badges.push(`<span class="badge fix">已自動修復</span>`);
  (v.warnings || []).forEach(w =>
    badges.push(`<span class="badge warn">warn</span>`));
  badges.push(`<span class="badge ok">source: ${meta.source}</span>`);
  document.getElementById("diag-badges").innerHTML = badges.join(" ");

  const lines = [
    `character:   ${meta.character}  ${meta.unicode}`,
    `strokes:     ${meta.stroke_count}`,
    `signature:   ${meta.signature}`,
    `bbox:        ${meta.bbox.join(", ")}`,
    `source:      ${meta.source}`,
    "",
    "每筆畫:",
    ...meta.strokes.map((s, i) =>
      `  #${i+1}  kind=${s.kind_code}(${s.kind_name})  hook=${s.has_hook}  ${s.track.length} 點`
    ),
  ];
  if (v.warnings && v.warnings.length) {
    lines.push("", "警告:");
    v.warnings.forEach(w => lines.push(`  ⚠ ${w}`));
  }
  if (v.errors && v.errors.length) {
    lines.push("", "錯誤:");
    v.errors.forEach(e => lines.push(`  ✗ ${e}`));
  }
  if (v.fix_was_applied) {
    lines.push("", `✓ 自動修復: ${v.fix_description}`);
  }
  document.getElementById("diagnostics").textContent = lines.join("\n");
}

function renderDownloads(char, p) {
  const base = `${API_BASE}/api/export/${encodeURIComponent(char)}`;
  const linksConf = [
    { fmt: "svg",   params: `mode=${p.mode}&show_numbers=true`,
      label: "SVG (描邊+軌跡)" },
    { fmt: "svg",   params: `mode=track&rainbow=true&show_numbers=true`,
      label: "SVG (彩虹筆順)" },
    { fmt: "gcode", params: `char_size=${p.char_size}&feed_rate=${p.feed_rate}`,
      label: `G-code (${p.char_size}mm)` },
    { fmt: "json",  params: "", label: "JSON polyline" },
  ];
  const common = `source=${p.source}&hook_policy=${p.hook_policy}`;
  const html = linksConf.map(({fmt, params, label}) => {
    const url = `${base}?format=${fmt}&${common}${params ? '&' + params : ''}`;
    return `<a href="${url}" download>⤓ ${label}</a>`;
  }).join("");
  document.getElementById("downloads").innerHTML = html;
}

// preview control buttons
document.getElementById("btn-animate").onclick = () => {
  if (!currentWriter) return;
  currentWriter.animateCharacter();
};
document.getElementById("btn-quiz").onclick = () => {
  if (!currentWriter) return;
  currentWriter.quiz();
};
document.getElementById("btn-reset").onclick = () => {
  if (!currentWriter) return;
  currentWriter.showCharacter();
};

// hotkey: Enter in input triggers load
document.getElementById("char").addEventListener("keydown", e => {
  if (e.key === "Enter") load();
});
document.getElementById("load").onclick = load;
// Only change listeners on selects INSIDE the single-view (not grid)
document.querySelectorAll("#single-view select").forEach(
  el => el.addEventListener("change", load)
);

// ============================================================
// Mode toggle (單字 / 字帖 / 筆記 / 信紙 / 塗鴉)
// ============================================================
const views = {
  single:     document.getElementById("single-view"),
  grid:       document.getElementById("grid-view"),
  notebook:   document.getElementById("notebook-view"),
  letter:     document.getElementById("letter-view"),
  manuscript: document.getElementById("manuscript-view"),
  doodle:     document.getElementById("doodle-view"),
  patch:      document.getElementById("patch-view"),     // Phase 5ax
  stamp:      document.getElementById("stamp-view"),     // Phase 5ay
  stencil:    document.getElementById("stencil-view"),   // Phase 5dc
  sutra:      document.getElementById("sutra-view"),     // Phase 5az
  wordart:    document.getElementById("wordart-view"),
  mandala:    document.getElementById("mandala-view"),  // Phase 5b r4
  zentangle:  document.getElementById("zentangle-view"),  // Phase 6z-1
};
document.querySelectorAll('input[name="mode"]').forEach(r =>
  r.addEventListener("change", () => {
    const mode = document.querySelector('input[name="mode"]:checked').value;
    for (const [name, el] of Object.entries(views)) {
      el.style.display = (name === mode) ? "grid" : "none";
    }
  })
);

// ── U2 資訊架構：模式群 tab（書寫/製造/藝術）顯隱＋隨 radio 自動跟隨 ──
// radio 與 value 不變（模式面板切換仍由上方 views 邏輯處理）；tab 只控制
// 選擇器可見群，並在模式變更時自動跟到該模式所屬的群。
const MODE_GROUP = {
  single: "write", grid: "write", manuscript: "write", notebook: "write",
  letter: "write", sutra: "write",
  doodle: "make", patch: "make", stamp: "make", stencil: "make",
  wordart: "art", mandala: "art", zentangle: "art",
};
function showModeGroup(g) {
  document.querySelectorAll(".mode-group").forEach(
    el => el.classList.toggle("show", el.dataset.g === g));
  document.querySelectorAll(".mode-tab").forEach(
    t => t.classList.toggle("active", t.dataset.g === g));
}
document.querySelectorAll(".mode-tab").forEach(
  t => t.addEventListener("click", () => showModeGroup(t.dataset.g)));
document.querySelectorAll('input[name="mode"]').forEach(
  r => r.addEventListener("change", () => {
    if (r.checked && MODE_GROUP[r.value]) showModeGroup(MODE_GROUP[r.value]);
  }));
{
  const _chk = document.querySelector('input[name="mode"]:checked');
  if (_chk && MODE_GROUP[_chk.value]) showModeGroup(MODE_GROUP[_chk.value]);
}

// W4-R2：跨檔邊匯出（消費端見 import 網）
export { API_BASE, load };
