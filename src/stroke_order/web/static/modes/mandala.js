// ============================================================
// Mandala (曼陀羅) mode — Phase 5b r4
// ============================================================

// ===== Phase 5b r27: 曼陀羅檔案匯出/匯入（純前端，不上伺服器） =====
// schema = stroke-order-mandala-v1（與 stroke-order-psd-v1 命名對齊）
// 兩 tier:
//   1. .mandala.md  : YAML frontmatter (機器解析) + auto prose body (AI/人類)
//   2. SVG <metadata><mandala-config> : SVG 內嵌 JSON，1 檔即視覺 + 設定
const MD_SCHEMA = "stroke-order-mandala-v1";
window._mandalaSessionMeta = window._mandalaSessionMeta || null;

const MD_MIGRATIONS = {
  "stroke-order-mandala-v1": (data) => data,  // identity
  // 未來 v2 從此加：
  // "stroke-order-mandala-v2": (data) => { ...migrate from v1... },
};

function _mandalaGenerateUuid() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function _mandalaTitleToPinyin(title) {
  if (!title) return "";
  // pinyin-pro 全域：window.pinyinPro
  if (typeof window.pinyinPro !== "undefined" && window.pinyinPro.pinyin) {
    try {
      const p = window.pinyinPro.pinyin(title, {
        toneType: "none", separator: "-", nonZh: "consecutive",
      });
      return p.toLowerCase()
        .replace(/[^a-z0-9-]+/g, "-")
        .replace(/-+/g, "-")
        .replace(/^-|-$/g, "");
    } catch (e) { console.warn("pinyin convert failed:", e); }
  }
  // Fallback：純 ASCII 過濾
  return (title || "").toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/-+/g, "-").replace(/^-|-$/g, "");
}

function _mandalaCurrentMetadata() {
  const title = (document.getElementById("md-title")?.value || "").trim();
  const designNote = (document.getElementById("md-design-note")?.value || "").trim();
  const now = new Date().toISOString();
  if (!window._mandalaSessionMeta) {
    window._mandalaSessionMeta = {
      id: _mandalaGenerateUuid(),
      created_at: now,
    };
  }
  return {
    id: window._mandalaSessionMeta.id,
    title: title,
    title_pinyin: _mandalaTitleToPinyin(title),
    design_note: designNote,
    author: "",  // r28 上 gallery 時填寫
    created_at: window._mandalaSessionMeta.created_at,
    modified_at: now,
  };
}

// ---- State builder：UI inputs → state object ----
function mandalaBuildState() {
  const g = id => document.getElementById(id)?.value;
  const checked = id => document.getElementById(id)?.checked;
  const centerType = (document.querySelector('input[name="md-center-type"]:checked') || {}).value || "char";
  const nFoldVal = (g("md-n-fold") || "").trim();
  const layers = [];
  document.querySelectorAll("#md-rings-container .md-ring-section").forEach(section => {
    const ringIdx = parseInt(section.dataset.ring, 10) || 0;
    section.querySelectorAll(".md-layer-row").forEach(row => {
      const style = row.querySelector(".md-layer-style").value;
      const layer = {
        ring: ringIdx,
        style: style,
        n_fold: parseInt(row.querySelector(".md-layer-n").value, 10) || 18,
        r_mm: parseFloat(row.querySelector(".md-layer-r-mm").value) || 0,
        color: row.querySelector(".md-layer-color")?.value || "#000000",
        visible: row.querySelector(".md-layer-visible")?.checked !== false,
      };
      // polymorphic params 從 len/width inputs
      _mandalaApplyStyleSpecificParams(layer, style,
        parseFloat(row.querySelector(".md-layer-len").value),
        parseFloat(row.querySelector(".md-layer-width").value));
      layers.push(layer);
    });
  });
  return {
    schema: MD_SCHEMA,
    canvas: {
      size_mm: parseFloat(g("md-size")) || 140,
      page_width_mm: parseFloat(g("md-pw")) || 210,
      page_height_mm: parseFloat(g("md-ph")) || 297,
    },
    center: {
      type: centerType,
      text: g("md-center-text") || "",
      size_mm: parseFloat(g("md-center-size")) || 24,
      line_color: g("md-char-color") || "#000000",
      icon_style: g("md-icon-style") || "lotus_petal",
      icon_n: parseInt(g("md-icon-n"), 10) || 8,
      icon_size_mm: parseFloat(g("md-icon-size")) || 12,
    },
    ring: {
      text: g("md-ring-text") || "",
      size_mm: parseFloat(g("md-ring-size")) || 10,
      spacing: parseFloat(g("md-char-spacing")) || 2.0,
      orientation: g("md-orient") || "bottom_to_center",
      auto_shrink: !!checked("md-auto-shrink"),
      shrink_safety_margin: parseFloat(g("md-shrink-margin")) || 0.85,
      protect_chars: !!checked("md-protect-chars"),
      protect_radius_factor: parseFloat(g("md-protect-radius")) || 0.55,
      line_color: g("md-char-color") || "#000000",
    },
    mandala: {
      style: g("md-style-primitive") || "interlocking_arcs",
      composition_scheme: g("md-comp-scheme") || "vesica",
      n_fold: nFoldVal === "" ? null : parseInt(nFoldVal, 10),
      show: !!checked("md-show-mandala"),
      overlap_ratio: parseFloat(g("md-overlap")) || 1.25,
      lotus_length_ratio: parseFloat(g("md-lotus-len")) || 1.25,
      lotus_width_ratio: parseFloat(g("md-lotus-width")) || 0.6,
      rays_length_ratio: parseFloat(g("md-rays-len")) || 1.25,
      inscribed_padding_factor: parseFloat(g("md-inscribed-pad")) || 0.7,
      r_ring_ratio: parseFloat(g("md-r-ring")) || 0.45,
      r_band_ratio: parseFloat(g("md-r-band")) || 0.78,
      stroke_width: parseFloat(g("md-stroke")) || 0.6,
      line_color: g("md-mandala-color") || "#000000",
    },
    extra_layers: layers,
    style: {
      font: g("md-style") || "kaishu",
      cns_outline_mode: g("md-cns-mode") || "skip",
      source: g("md-source") || "auto",
    },
  };
}

// ---- Auto prose body：從 state 渲染人類/AI 可讀摘要 ----
function _mandalaRenderProseBody(state) {
  const lines = [];
  const m = state.metadata || {};
  const title = m.title || "未命名曼陀羅";
  lines.push(`# ${title}`);
  lines.push("");
  lines.push(`> 由 stroke-order ${state.generator?.version || ""} 匯出。`);
  lines.push("");
  lines.push("## 視覺概觀（自動生成，下次匯出會被覆蓋）");
  lines.push("");
  const c = state.canvas || {};
  lines.push(`- 畫布：${c.size_mm} mm 直徑 / 頁面 ${c.page_width_mm}×${c.page_height_mm} mm`);
  const ce = state.center || {};
  if (ce.type === "char") {
    lines.push(`- 中心字：「${ce.text}」（${ce.size_mm} mm，${ce.line_color}）`);
  } else if (ce.type === "icon") {
    lines.push(`- 中心圖：${ce.icon_style}（N=${ce.icon_n}，${ce.icon_size_mm} mm）`);
  } else {
    lines.push(`- 中心：空`);
  }
  const r = state.ring || {};
  if (r.text) {
    lines.push(`- 字環：「${r.text}」共 ${r.text.length} 字（${r.size_mm} mm，${r.orientation}）`);
  }
  const md = state.mandala || {};
  lines.push(`- 主 mandala：${md.style}，scheme = ${md.composition_scheme}，N = ${md.n_fold ?? "auto"}，色 ${md.line_color}`);
  if (state.extra_layers?.length) {
    lines.push(`- 裝飾層共 ${state.extra_layers.length} 層：`);
    for (const layer of state.extra_layers) {
      const v = layer.visible === false ? " (隱藏)" : "";
      lines.push(`  - 環 ${layer.ring}：${layer.style} N=${layer.n_fold} r=${layer.r_mm}mm 色 ${layer.color}${v}`);
    }
  }
  lines.push("");
  lines.push("## 設計意圖");
  lines.push("");
  lines.push(m.design_note || "（無）");
  lines.push("");
  return lines.join("\n");
}

// ---- Serialize：state → MD 字串（frontmatter manual 保留拼音註解 + body） ----
function serializeMandalaMd(state) {
  state.generator = state.generator || { app: "stroke-order", version: "0.14.106" };
  const m = state.metadata;
  // metadata 區段用 manual template 保留中文/拼音 inline 註解
  const escY = (s) => jsyaml.dump(s == null ? "" : s, { lineWidth: -1 }).trim();
  const head = [
    `schema: ${state.schema}`,
    `exported_at: ${m.modified_at}`,
    `generator:`,
    `  app: stroke-order`,
    `  version: "${state.generator.version}"`,
    ``,
    `metadata:`,
    `  # 中文標題 + 拼音對照（拼音用於檔名 slug，import 時系統讀中文 title）`,
    `  title: ${escY(m.title)}     # 拼音: ${m.title_pinyin || "(空)"}`,
    `  title_pinyin: ${escY(m.title_pinyin)}`,
    `  design_note: ${escY(m.design_note)}`,
    `  author: ${escY(m.author)}     # r28 gallery 上傳時填寫`,
    `  id: ${m.id}`,
    `  created_at: ${m.created_at}`,
    `  modified_at: ${m.modified_at}`,
    ``,
  ].join("\n");
  // 其餘 sections 用 js-yaml.dump 自動序列化
  const rest = {
    canvas: state.canvas,
    center: state.center,
    ring: state.ring,
    mandala: state.mandala,
    extra_layers: state.extra_layers,
    style: state.style,
  };
  const restYaml = jsyaml.dump(rest, { indent: 2, lineWidth: -1, noRefs: true });
  return `---\n${head}${restYaml}---\n\n${_mandalaRenderProseBody(state)}\n`;
}

// ---- Parse：MD 字串 → state（含 schema validation + migration） ----
function parseMandalaMd(text) {
  const m = text.match(/^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$/);
  if (!m) throw new Error("檔案缺少 YAML frontmatter（--- ... --- 區塊）");
  let parsed;
  try { parsed = jsyaml.load(m[1]); }
  catch (e) { throw new Error("YAML 解析失敗：" + (e.message || e)); }
  if (!parsed || typeof parsed !== "object") {
    throw new Error("Frontmatter 不是有效 YAML 物件");
  }
  return _mandalaMigrateState(parsed);
}

function _mandalaMigrateState(state) {
  const sch = state.schema;
  const migrator = MD_MIGRATIONS[sch];
  if (!migrator) {
    throw new Error(`不支援的 schema：${sch || "(空)"}（已知：${Object.keys(MD_MIGRATIONS).join(", ")}）`);
  }
  return migrator(state);
}

// ---- Tier 2: SVG metadata 嵌入/萃取 ----
function _mandalaInjectSvgMetadata(svgStr, state) {
  const json = JSON.stringify(state);
  // CDATA 防護：JSON 中真出現 ]]> (極罕) 時 escape
  const cdataSafe = json.replace(/]]>/g, "]]]]><![CDATA[>");
  const block = `<metadata><mandala-config xmlns="https://stroke-order.local/mandala">` +
                `<![CDATA[${cdataSafe}]]></mandala-config></metadata>`;
  // 在第一個 <svg ...> 開標籤後注入
  return svgStr.replace(/<svg([^>]*)>/, `<svg$1>${block}`);
}

function _mandalaExtractSvgMetadata(svgStr) {
  const m = svgStr.match(
    /<mandala-config[^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/mandala-config>/);
  if (!m) return null;
  let json = m[1].replace(/\]\]\]\]><!\[CDATA\[>/g, "]]>");
  let parsed;
  try { parsed = JSON.parse(json); }
  catch (e) { throw new Error("SVG metadata JSON 解析失敗：" + e.message); }
  return _mandalaMigrateState(parsed);
}

// ---- Apply state → UI inputs ----
function applyMandalaState(state) {
  const setVal = (id, v) => {
    const el = document.getElementById(id);
    if (el && v != null) el.value = String(v);
  };
  const setCheck = (id, v) => {
    const el = document.getElementById(id);
    if (el && typeof v === "boolean") el.checked = v;
  };
  const setColor = (id, hex) => {
    const el = document.getElementById(id);
    if (el && hex) {
      el.value = hex;
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }
  };
  const m = state.metadata || {};
  setVal("md-title", m.title);
  setVal("md-design-note", m.design_note);
  // 保留 import 來的 id + created_at（後續 export 重用）
  if (m.id && m.created_at) {
    window._mandalaSessionMeta = { id: m.id, created_at: m.created_at };
  }
  const c = state.canvas || {};
  setVal("md-size", c.size_mm);
  setVal("md-pw", c.page_width_mm);
  setVal("md-ph", c.page_height_mm);
  const ce = state.center || {};
  if (ce.type) {
    document.querySelectorAll('input[name="md-center-type"]').forEach(r => {
      r.checked = (r.value === ce.type);
    });
  }
  setVal("md-center-text", ce.text);
  setVal("md-center-size", ce.size_mm);
  setVal("md-icon-style", ce.icon_style);
  setVal("md-icon-n", ce.icon_n);
  setVal("md-icon-size", ce.icon_size_mm);
  setColor("md-char-color", ce.line_color);
  const r = state.ring || {};
  setVal("md-ring-text", r.text);
  setVal("md-ring-size", r.size_mm);
  setVal("md-char-spacing", r.spacing);
  setVal("md-orient", r.orientation);
  setCheck("md-auto-shrink", r.auto_shrink);
  setVal("md-shrink-margin", r.shrink_safety_margin);
  setCheck("md-protect-chars", r.protect_chars);
  setVal("md-protect-radius", r.protect_radius_factor);
  const md = state.mandala || {};
  setVal("md-style-primitive", md.style);
  setVal("md-comp-scheme", md.composition_scheme);
  setVal("md-n-fold", md.n_fold == null ? "" : md.n_fold);
  setCheck("md-show-mandala", md.show);
  setVal("md-overlap", md.overlap_ratio);
  setVal("md-lotus-len", md.lotus_length_ratio);
  setVal("md-lotus-width", md.lotus_width_ratio);
  setVal("md-rays-len", md.rays_length_ratio);
  setVal("md-inscribed-pad", md.inscribed_padding_factor);
  setVal("md-r-ring", md.r_ring_ratio);
  setVal("md-r-band", md.r_band_ratio);
  setVal("md-stroke", md.stroke_width);
  setColor("md-mandala-color", md.line_color);
  // extra_layers — 全清空後 ring 分組重建
  mandalaClearAllLayers();
  const layers = state.extra_layers || [];
  const ringMap = {};
  for (const layer of layers) {
    const ringIdx = Math.max(0, Math.min(MD_RING_MAX - 1,
      parseInt(layer.ring, 10) || 0));
    if (!ringMap[ringIdx]) ringMap[ringIdx] = [];
    ringMap[ringIdx].push(layer);
  }
  if (!ringMap[0]) ringMap[0] = [];
  Object.keys(ringMap).map(k => parseInt(k, 10)).sort((a, b) => a - b)
    .forEach(ringIdx => mandalaAddRing(ringIdx, ringMap[ringIdx]));
  const s = state.style || {};
  setVal("md-style", s.font);
  setVal("md-cns-mode", s.cns_outline_mode);
  setVal("md-source", s.source);
  // 觸發 sync handler 更新 conditional UI
  ["md-style-primitive", "md-comp-scheme", "md-protect-chars"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  const cr = document.querySelector('input[name="md-center-type"]:checked');
  if (cr) cr.dispatchEvent(new Event("change", { bubbles: true }));
}

// ---- Filename slug：拼音 + .mandala.md ----
function _mandalaSlugifyFilename(state) {
  const m = state.metadata || {};
  const slug = m.title_pinyin || _mandalaTitleToPinyin(m.title) || "";
  if (slug) return `${slug}.mandala.md`;
  const idShort = (m.id || "").slice(0, 8);
  return `mandala-${idShort || "untitled"}.mandala.md`;
}

// ---- Export 按鈕 ----
document.getElementById("md-export-btn")?.addEventListener("click", () => {
  try {
    if (typeof jsyaml === "undefined") {
      throw new Error("js-yaml 函式庫未載入（CDN 失敗？）");
    }
    const state = mandalaBuildState();
    state.metadata = _mandalaCurrentMetadata();
    const md = serializeMandalaMd(state);
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = _mandalaSlugifyFilename(state);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (e) {
    alert("匯出失敗：" + (e.message || e));
    console.error(e);
  }
});

// ---- Import 按鈕 + file input ----
document.getElementById("md-import-btn")?.addEventListener("click", () => {
  document.getElementById("md-import-file")?.click();
});
document.getElementById("md-import-file")?.addEventListener("change", async (ev) => {
  const file = ev.target.files?.[0];
  if (!file) return;
  try {
    if (typeof jsyaml === "undefined") {
      throw new Error("js-yaml 函式庫未載入（CDN 失敗？）");
    }
    const text = await file.text();
    let state;
    if (text.trimStart().startsWith("<svg") || file.name.endsWith(".svg")) {
      state = _mandalaExtractSvgMetadata(text);
      if (!state) throw new Error("SVG 內未找到 mandala-config metadata");
    } else {
      state = parseMandalaMd(text);
    }
    applyMandalaState(state);
    // 自動 render preview
    if (typeof renderMandala === "function") renderMandala();
    const t = state.metadata?.title || "(未命名)";
    console.log(`✓ 匯入成功：${t}`);
  } catch (e) {
    alert("匯入失敗：" + (e.message || e));
    console.error(e);
  } finally {
    ev.target.value = "";  // 允許重複匯入同檔
  }
});

// ===== r27 module END =====

// ===== Phase 5b r28: 上傳到 Gallery（公眾分享庫） =====
// 把當前 mandala state 序列化成 .mandala.md 後 POST 到 /api/gallery/uploads。
// 共享 r27 的 mandalaBuildState + serializeMandalaMd（單一真相來源）。
// 需登入：未登入時顯示提示請 user 先到 /gallery 登入再回。
// 5b r28b: 上傳走 SVG path（伺服器自動生成 thumbnail）
// 流程：fetch /api/mandala?format=svg → 注入 metadata → blob → POST kind=mandala
// 比 r28a MD path 慢約 100-300ms（多一個 SVG render request），但換來
// gallery card 有完整視覺縮圖。
// CDN 失敗時 fallback 到 MD path（舊行為）。
document.getElementById("md-gallery-upload-btn")?.addEventListener("click",
  async () => {
    const hasYaml = (typeof jsyaml !== "undefined");
    const titleEl = document.getElementById("md-title");
    const title = (titleEl?.value || "").trim();
    if (!title) {
      alert("請先在「📁 曼陀羅檔案」區塊填上標題後再上傳。\n"
          + "標題會顯示在公眾分享庫，做為作品名稱。");
      titleEl?.focus();
      return;
    }
    const designNote = (document.getElementById("md-design-note")?.value || "").trim();
    const ok = confirm(
      `上傳到公眾分享庫嗎？\n\n` +
      `標題：${title}\n` +
      `設計意圖：${designNote || "（無）"}\n\n` +
      `Gallery 會顯示縮圖預覽（內嵌完整 mandala 設定，可拖回此頁繼續編輯）。\n` +
      `所有上傳皆公開可下載；只有您本人能刪除。\n` +
      `（若尚未登入，會跳到 /gallery 登入頁）`,
    );
    if (!ok) return;

    // 1. 拼 mandala state + metadata（id / created_at 持久化）
    let state;
    try {
      state = mandalaBuildState();
      state.metadata = _mandalaCurrentMetadata();
      state.generator = { app: "stroke-order", version: "0.14.108" };
    } catch (e) {
      alert("組裝 mandala 設定失敗：" + (e.message || e));
      console.error(e);
      return;
    }
    const slugBase = _mandalaSlugifyFilename(state).replace(/\.mandala\.md$/, "");

    // 2. 走 SVG path：fetch render 後 SVG → JS 注入 metadata
    let blob, filename, fdKind;
    try {
      const params = mandalaBuildParams();
      params.set("format", "svg");
      const r = await fetch(`${API_BASE}/api/mandala?` + params);
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${r.status}`);
      }
      const svgText = await r.text();
      // 注入 metadata（同 mandalaDownload 的 svg path 邏輯）
      const enrichedSvg = _mandalaInjectSvgMetadata(svgText, state);
      blob = new Blob([enrichedSvg], { type: "image/svg+xml;charset=utf-8" });
      filename = `${slugBase}.svg`;
      fdKind = "mandala";
    } catch (e) {
      // SVG path 失敗 → fallback 到 MD path（無 thumbnail 但可用）
      console.warn("SVG path 失敗，fallback MD path:", e);
      if (!hasYaml) {
        alert("SVG render 失敗、且 js-yaml 也未載入；無法上傳。請檢查網路。");
        return;
      }
      try {
        const mdText = serializeMandalaMd(state);
        blob = new Blob([mdText], { type: "text/markdown;charset=utf-8" });
        filename = `${slugBase}.mandala.md`;
        fdKind = "mandala";
      } catch (e2) {
        alert("MD 序列化也失敗：" + (e2.message || e2));
        return;
      }
    }

    // 3. POST 到 /api/gallery/uploads
    const fd = new FormData();
    fd.append("file", blob, filename);
    fd.append("title", title);
    fd.append("comment", designNote);
    fd.append("kind", fdKind);
    try {
      const r = await fetch("/api/gallery/uploads", {
        method: "POST",
        body: fd,
        credentials: "same-origin",
      });
      if (r.status === 401 || r.status === 403) {
        if (confirm("尚未登入 Gallery。要前往 /gallery 登入嗎？\n登入後請再回此頁重試上傳。")) {
          window.open("/gallery", "_blank");
        }
        return;
      }
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(data.detail || `HTTP ${r.status}`);
      }
      const id = data.upload?.id;
      if (confirm(`✓ 上傳成功！(id = ${id})\n\n要前往 Gallery 看作品嗎？`)) {
        window.open("/gallery", "_blank");
      }
    } catch (e) {
      alert("上傳失敗：" + (e.message || e));
      console.error(e);
    }
  });
// ===== r28 / r28b upload-to-gallery END =====

function mandalaBuildParams() {
  const g = id => document.getElementById(id).value;
  const $$ = id => document.getElementById(id);
  const params = new URLSearchParams({
    center_text: g("md-center-text") || "咒",
    ring_text: g("md-ring-text") || "臨兵鬥者皆陣列在前",
    size_mm: g("md-size"),
    page_width_mm: g("md-pw"),
    page_height_mm: g("md-ph"),
    char_size_center_mm: g("md-center-size"),
    char_size_ring_mm: g("md-ring-size"),
    r_ring_ratio: g("md-r-ring"),
    r_band_ratio: g("md-r-band"),
    overlap_ratio: g("md-overlap"),
    stroke_width: g("md-stroke"),
    orientation: g("md-orient"),
    style: g("md-style"),
    cns_outline_mode: g("md-cns-mode"),
    source: g("md-source"),
    show_chars: $$("md-show-chars").checked ? "true" : "false",
    show_mandala: $$("md-show-mandala").checked ? "true" : "false",
    show_outline: $$("md-show-outline").checked ? "true" : "false",
    protect_chars: $$("md-protect-chars").checked ? "true" : "false",
    protect_radius_factor: g("md-protect-radius"),
    mandala_style: g("md-style-primitive"),
    lotus_length_ratio: g("md-lotus-len"),
    lotus_width_ratio: g("md-lotus-width"),
    rays_length_ratio: g("md-rays-len"),
    composition_scheme: g("md-comp-scheme"),
    char_spacing: g("md-char-spacing"),
    inscribed_padding_factor: g("md-inscribed-pad"),
    auto_shrink_chars: $$("md-auto-shrink").checked ? "true" : "false",
    shrink_safety_margin: g("md-shrink-margin"),
    extra_layers_json: mandalaBuildExtraLayersJson(),
    center_type: (document.querySelector('input[name="md-center-type"]:checked') || {}).value || "char",
    center_icon_style: g("md-icon-style"),
    center_icon_n: g("md-icon-n"),
    center_icon_size_mm: g("md-icon-size"),
    // 5b r26: 線條顏色（normalize 成 6-digit hex；default black）
    mandala_line_color: g("md-mandala-color") || "#000000",
    char_line_color: g("md-char-color") || "#000000",
  });
  // n_fold 留空 → 後端自動取字環長度（不要傳空字串給 int validator）
  const nfold = g("md-n-fold").trim();
  if (nfold !== "") params.set("n_fold", nfold);
  return params;
}

async function renderMandala() {
  const statusEl = document.getElementById("md-status");
  const previewEl = document.getElementById("md-preview");
  const dlRow = document.getElementById("md-download-row");
  statusEl.textContent = "產生中…";
  if (dlRow) dlRow.style.display = "none";
  const params = mandalaBuildParams();
  try {
    const r = await fetch(`${API_BASE}/api/mandala?` + params);
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: r.statusText}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    const svg = await r.text();
    previewEl.innerHTML = svg;
    const inner = previewEl.querySelector("svg");
    if (inner) { inner.style.maxWidth = "100%"; inner.style.height = "auto"; }
    const placed = r.headers.get("x-mandala-placed") || "?";
    const missing = r.headers.get("x-mandala-missing") || "0";
    const n = r.headers.get("x-mandala-n-fold") || "?";
    let msg = `已放置 ${placed} 字 · N=${n}-fold mandala`;
    if (parseInt(missing, 10) > 0) msg += ` · ⚠ 缺 ${missing} 個無筆跡字`;
    // Phase 5b r9: 自動縮字提示
    if (r.headers.get("x-mandala-char-shrunk") === "1") {
      const orig = r.headers.get("x-mandala-char-size-original-mm") || "?";
      const eff = r.headers.get("x-mandala-char-size-effective-mm") || "?";
      msg += ` · 🔍 字 ${orig} → ${eff} mm（自動縮小避免碰線）`;
    }
    statusEl.textContent = msg;
    // 5b r18: 顯示多格式下載 row
    if (dlRow) dlRow.style.display = "flex";
  } catch (e) {
    statusEl.textContent = "";
    previewEl.innerHTML =
      `<span style="color:var(--accent);">錯誤：${e.message}</span>`;
  }
}
document.getElementById("md-render").onclick = renderMandala;

// Phase 5b r18: 多格式下載（SVG / PNG / PNG透明 / PDF）
async function mandalaDownload(format) {
  const dlStatus = document.getElementById("md-dl-status");
  if (dlStatus) dlStatus.textContent = "產生 " + format + " 中…";
  const params = mandalaBuildParams();
  params.set("format", format);
  if (format === "png" || format === "png_transparent") {
    const sizeSel = document.getElementById("md-png-size");
    if (sizeSel) params.set("png_size_px", sizeSel.value);
  }
  params.set("download", "true");
  try {
    const r = await fetch(`${API_BASE}/api/mandala?` + params);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    let blob = await r.blob();
    // r27 Tier 2: SVG 下載時注入 mandala-config metadata
    if (format === "svg") {
      try {
        const svgText = await blob.text();
        const state = mandalaBuildState();
        state.metadata = _mandalaCurrentMetadata();
        state.generator = { app: "stroke-order", version: "0.14.106" };
        const enriched = _mandalaInjectSvgMetadata(svgText, state);
        blob = new Blob([enriched], { type: "image/svg+xml;charset=utf-8" });
      } catch (e) {
        console.warn("SVG metadata 注入失敗，下載原 SVG：", e);
      }
    }
    const url = URL.createObjectURL(blob);
    // 副檔名
    const extMap = {svg: "svg", png: "png",
                    png_transparent: "png", pdf: "pdf",
                    gcode: "gcode"};
    const ext = extMap[format] || "svg";
    const tag = (format === "png_transparent") ? "-transparent" : "";
    const a = document.createElement("a");
    a.href = url;
    a.download = `mandala${tag}-${Date.now()}.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    if (dlStatus) dlStatus.textContent = `✓ ${format} 已下載`;
  } catch (e) {
    if (dlStatus) dlStatus.textContent = "❌ 失敗：" + e.message;
  }
}
document.getElementById("md-dl-svg")?.addEventListener("click",
  () => mandalaDownload("svg"));
document.getElementById("md-dl-png")?.addEventListener("click",
  () => mandalaDownload("png"));
document.getElementById("md-dl-png-trans")?.addEventListener("click",
  () => mandalaDownload("png_transparent"));
document.getElementById("md-dl-pdf")?.addEventListener("click",
  () => mandalaDownload("pdf"));
document.getElementById("md-dl-gcode")?.addEventListener("click",
  () => mandalaDownload("gcode"));

// Phase 5b r12: Preset 主題 — 一鍵套全部設定
let MANDALA_PRESETS = [];   // populated from /api/mandala/presets

async function mandalaLoadPresets() {
  const sel = document.getElementById("md-preset");
  const desc = document.getElementById("md-preset-desc");
  if (!sel) return;
  try {
    const r = await fetch(`${API_BASE}/api/mandala/presets`);
    if (!r.ok) return;
    const d = await r.json();
    MANDALA_PRESETS = d.presets || [];
    // Populate dropdown
    for (const p of MANDALA_PRESETS) {
      const opt = document.createElement("option");
      opt.value = p.key;
      opt.textContent = p.name;
      sel.appendChild(opt);
    }
  } catch (e) {
    if (desc) desc.textContent = "(preset 載入失敗：" + e.message + ")";
  }
}

function _setIfExists(id, value) {
  const el = document.getElementById(id);
  if (el == null || value == null) return;
  if (el.type === "checkbox") {
    el.checked = !!value;
  } else {
    el.value = String(value);
  }
}

// r25 取代 r14：preset 套用時依每 layer 的 r_mm（或 r_ratio×r_total）分組到對應 ring，
// 透過 mandalaAddRing(ringIdx, layerCfgs) 一次建立 ring + 內部 layers。

function mandalaApplyPreset(key) {
  const desc = document.getElementById("md-preset-desc");
  if (!key) {
    if (desc) desc.textContent =
      "選擇 preset 一鍵套用所有設定（中心字 / 字環 / 主 mandala / extras）";
    return;
  }
  const preset = MANDALA_PRESETS.find(p => p.key === key);
  if (!preset) return;
  if (desc) desc.textContent = preset.description || "";
  const cfg = preset.config || {};

  // 1. 文字
  _setIfExists("md-center-text", cfg.center_text);
  _setIfExists("md-ring-text", cfg.ring_text);

  // 5b r26: 全域線條顏色（preset 可指定，否則 default 黑）— 雙控制 sync 透過 _mandalaWireColorControl 內部處理，這裡直接給值並觸發 input event
  function _setColor(pickerId, presetId, hex) {
    const picker = document.getElementById(pickerId);
    if (picker && hex) {
      picker.value = hex;
      // 觸發 input event 讓 preset select sync
      picker.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }
  _setColor("md-mandala-color", "md-mandala-color-preset",
    cfg.mandala_line_color || "#000000");
  _setColor("md-char-color", "md-char-color-preset",
    cfg.char_line_color || "#000000");

  // 2. 主 mandala
  _setIfExists("md-style-primitive", cfg.mandala_style);
  _setIfExists("md-comp-scheme", cfg.composition_scheme);
  _setIfExists("md-char-spacing", cfg.char_spacing);
  if (cfg.overlap_ratio != null)
    _setIfExists("md-overlap", cfg.overlap_ratio);
  if (cfg.lotus_length_ratio != null)
    _setIfExists("md-lotus-len", cfg.lotus_length_ratio);
  if (cfg.lotus_width_ratio != null)
    _setIfExists("md-lotus-width", cfg.lotus_width_ratio);
  if (cfg.rays_length_ratio != null)
    _setIfExists("md-rays-len", cfg.rays_length_ratio);
  if (cfg.inscribed_padding_factor != null)
    _setIfExists("md-inscribed-pad", cfg.inscribed_padding_factor);

  // 3. auto-shrink
  if (cfg.auto_shrink_chars != null)
    _setIfExists("md-auto-shrink", cfg.auto_shrink_chars);

  // 4. r25: 動態 layers — 清空所有 ring；依 preset extra_layers r_mm 分組到對應 ring
  //    若 preset 用舊 r_ratio，先換算成 r_mm = r_ratio × r_total（依當前 size）
  mandalaClearAllLayers();
  const r_total_est = _mandalaCurrentRTotalMm();
  const layers = cfg.extra_layers || [];
  const ringMap = {};  // ringIdx -> [layerCfg]
  for (const layer of layers) {
    const r_mm = (layer.r_mm != null)
      ? Number(layer.r_mm)
      : (Number(layer.r_ratio) || 0.5) * r_total_est;
    const ringIdx = Math.max(0,
      Math.min(MD_RING_MAX - 1, Math.floor(r_mm / MD_RING_WIDTH_MM)));
    const layerCfg = Object.assign({}, layer, { r_mm: r_mm });
    if (!ringMap[ringIdx]) ringMap[ringIdx] = [];
    ringMap[ringIdx].push(layerCfg);
  }
  // 確保 0 環一定存在（即便 preset 沒給）
  if (!ringMap[0]) ringMap[0] = [];
  Object.keys(ringMap)
    .map(k => parseInt(k, 10))
    .sort((a, b) => a - b)
    .forEach(ringIdx => mandalaAddRing(ringIdx, ringMap[ringIdx]));

  // 5. r15: 中心類型（preset 可指定 char/icon/empty + icon 子配置）
  if (cfg.center_type) {
    document.querySelectorAll('input[name="md-center-type"]').forEach(r => {
      r.checked = (r.value === cfg.center_type);
    });
    if (cfg.center_type === "icon") {
      if (cfg.center_icon_style != null)
        _setIfExists("md-icon-style", cfg.center_icon_style);
      if (cfg.center_icon_n != null)
        _setIfExists("md-icon-n", cfg.center_icon_n);
      if (cfg.center_icon_size_mm != null)
        _setIfExists("md-icon-size", cfg.center_icon_size_mm);
    }
  } else {
    // preset 沒指定 → 默認 char (backward compat)
    document.querySelectorAll('input[name="md-center-type"]').forEach(r => {
      r.checked = (r.value === "char");
    });
  }

  // 6. 觸發 sync handler，更新 row visibility / halo / center type
  ["md-style-primitive", "md-comp-scheme", "md-protect-chars"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.dispatchEvent(new Event("change", {bubbles: true}));
  });
  // center-type radios 觸發 change → 更新 icon controls 顯隱
  const centerRadio = document.querySelector('input[name="md-center-type"]:checked');
  if (centerRadio) centerRadio.dispatchEvent(new Event("change", {bubbles: true}));
}

document.getElementById("md-preset")?.addEventListener("change", (e) => {
  mandalaApplyPreset(e.target.value);
});
mandalaLoadPresets();   // init: fetch 並填 dropdown

// Phase 5b r25: 動態裝飾層 — ring-based UI（11 環 0-10，每環 10mm，每環內最多 10 layer）
// 結構：md-rings-container > .md-ring-section[data-ring=N] > .md-ring-layers > .md-layer-row
// 全域層編號 = ringIdx × 10 + localIdx (1-based)；半徑用 r_mm（mm）為主。
//
// 「len」input 是 polymorphic key — 依 style 對應到不同的 backend param：
//   arcs    → overlap_ratio
//   lotus   → lotus_length_ratio  (+ width input → lotus_width_ratio)
//   rays    → rays_length_ratio
//   dots    → dot_radius_mm
//   triangles → length_ratio (+ width → width_ratio, default pointing 由 r_ratio 推)
//   wave    → amplitude_ratio
//   zigzag  → tooth_height_ratio
//   spiral  → length_ratio (+ width → spin_turns)

// 5b r25: ring-based 結構（11 環 0-10，每環 10mm 寬，每環內最多 10 layers）
// 全域層編號 = ringIdx × 10 + local_idx_in_ring (1-based)
const MD_RING_MAX = 11;          // ring index 0..10（共 11 環）
const MD_RING_WIDTH_MM = 10;     // 每環徑向寬度 mm
const MD_LAYERS_PER_RING = 10;   // 每環內最多 10 layer（避免 numbering 跨環衝突）
// Phase 5b r23: dropdown 重組為 4 群組（user spec 新分類），17 elements
const MD_STYLE_GROUPS = [
  ["核心基礎元素", [
    ["dots", "圓點"],
    ["interlocking_arcs", "圓圈 (rosette)"],
    ["radial_rays", "直線 / 輻射光線"],
    ["wave", "波浪"],
    ["zigzag", "鋸齒"],
  ]],
  ["幾何符號元素", [
    ["triangles", "三角形"],
    ["squares", "方形"],
    ["crosses", "十字架"],
  ]],
  ["自然與生命元素", [
    ["lotus_petal", "花瓣 (蓮花)"],
    ["leaves", "葉片"],
    ["spiral", "螺旋"],
    ["stars", "星星 / 太陽"],
    ["eyes", "眼睛"],
  ]],
  ["裝飾與填充細節", [
    ["teardrops", "淚滴"],
    ["hearts", "心形"],
    ["clouds", "雲朵紋"],
    ["lattice", "網格"],
  ]],
];

// Backward-compat flat list（給其他舊 selector 用，build_optgroup_html 不需要）
const MD_STYLE_OPTIONS = MD_STYLE_GROUPS.flatMap(([_g, items]) => items);

function _mandalaBuildOptgroupHtml(selectedValue) {
  return MD_STYLE_GROUPS.map(([groupLabel, items]) => {
    const opts = items.map(([v, label]) => {
      const sel = (v === selectedValue) ? " selected" : "";
      return `<option value="${v}"${sel}>${label}</option>`;
    }).join("");
    return `<optgroup label="${groupLabel}">${opts}</optgroup>`;
  }).join("");
}

function _mandalaApplyStyleSpecificParams(layer, style, len, width) {
  if (style === "lotus_petal") {
    layer.lotus_length_ratio = len || 0.6;
    layer.lotus_width_ratio = width || 0.5;
  } else if (style === "radial_rays") {
    layer.rays_length_ratio = len || 0.8;
  } else if (style === "dots") {
    layer.dot_radius_mm = len || 1.0;
  } else if (style === "triangles") {
    layer.length_ratio = len || 0.5;
    layer.width_ratio = width || 0.5;
    layer.pointing = (layer.r_ratio >= 0.7) ? "outward" : "inward";
  } else if (style === "wave") {
    layer.amplitude_ratio = len || 0.04;
  } else if (style === "zigzag") {
    layer.tooth_height_ratio = len || 0.04;
  } else if (style === "spiral") {
    layer.length_ratio = len || 1.25;
    layer.spin_turns = (width != null && width > 0) ? width : 0.5;
    layer.direction = "cw";
  } else if (style === "squares") {
    layer.length_ratio = len || 1.0;
    layer.rotation_alignment = (layer.r_ratio >= 0.7) ? "diamond" : "radial";
  } else if (style === "hearts") {
    layer.length_ratio = len || 1.0;
    layer.pointing = (layer.r_ratio >= 0.7) ? "outward" : "inward";
  } else if (style === "teardrops") {
    layer.length_ratio = len || 1.25;
    layer.pointing = (layer.r_ratio >= 0.7) ? "outward" : "inward";
  } else if (style === "leaves") {
    layer.length_ratio = len || 1.4;
    layer.width_ratio = width || 0.5;
    layer.with_vein = true;
  } else if (style === "clouds") {
    layer.length_ratio = len || 1.0;
    layer.lobe_radius_ratio = (width != null && width > 0) ? width : 0.45;
    layer.pointing = (layer.r_ratio >= 0.7) ? "outward" : "inward";
  } else if (style === "crosses") {
    layer.length_ratio = len || 0.8;
    layer.aspect_ratio = (width != null && width > 0) ? width : 1.0;
  } else if (style === "stars") {
    layer.length_ratio = len || 0.8;
    // width input 對應 star_points (整數，範圍 3-12)；> 1.5 視為點數，否則 default 5
    if (width != null && width >= 3 && width <= 12) {
      layer.star_points = Math.round(width);
    } else {
      layer.star_points = 5;
    }
  } else if (style === "eyes") {
    layer.length_ratio = len || 1.0;
    layer.pupil_ratio = (width != null && width > 0) ? width : 0.3;
  } else if (style === "lattice") {
    layer.length_ratio = len || 0.9;
  } else {
    layer.overlap_ratio = len || 1.25;
  }
}

// 5b r25: 估算當前 r_total（mm）— 用於 r_ratio↔r_mm 轉換 + 給 style helper 推 pointing
function _mandalaCurrentRTotalMm() {
  const sizeEl = document.getElementById("md-size");
  const sizeMm = sizeEl ? parseFloat(sizeEl.value) : 140;
  return Math.max((isNaN(sizeMm) ? 140 : sizeMm) / 2.0, 1.0);
}

// 5b r26: 曼陀羅常用色盤（11 色，預設黑色）
const MD_COLOR_PRESETS = [
  ["#000000", "黑"],
  ["#c0392b", "紅"],
  ["#e67e22", "橘"],
  ["#d4af37", "金"],
  ["#f1c40f", "黃"],
  ["#27ae60", "綠"],
  ["#16a085", "青"],
  ["#2980b9", "藍"],
  ["#8e44ad", "紫"],
  ["#e91e63", "粉"],
  ["#8b4513", "棕"],
];

// 5b r26: 共用 helper — 把 color preset <select> 填入 options + 雙向 sync
//   `selectEl` 帶 data-target="<picker_id>" 屬性指向對應 <input type="color">
//   selectEl change → picker.value = selected
//   picker change → selectEl 切到 「自訂」(空 value)
// 同步: 套 attribute selected 到 hex match 的 option（雙控制初值一致）
function _mandalaWireColorControl(selectEl, pickerEl, initHex) {
  if (!selectEl || !pickerEl) return;
  // 建 option list（avoid 重複建：只在尚未填過時）
  if (selectEl.options.length === 0) {
    for (const [hex, label] of MD_COLOR_PRESETS) {
      const opt = document.createElement("option");
      opt.value = hex;
      opt.textContent = label;
      selectEl.appendChild(opt);
    }
    const customOpt = document.createElement("option");
    customOpt.value = "";
    customOpt.textContent = "自訂…";
    selectEl.appendChild(customOpt);
  }
  const setValueBoth = (hex) => {
    pickerEl.value = hex;
    // 找 preset 中 match 的 option，否則切到 「自訂」
    const matched = MD_COLOR_PRESETS.find(([h]) => h.toLowerCase() === hex.toLowerCase());
    selectEl.value = matched ? matched[0] : "";
  };
  setValueBoth(initHex || "#000000");
  selectEl.addEventListener("change", () => {
    if (selectEl.value === "") {
      // 「自訂…」 → 觸發 native picker
      pickerEl.click();
    } else {
      pickerEl.value = selectEl.value;
    }
  });
  pickerEl.addEventListener("input", () => {
    const hex = pickerEl.value;
    const matched = MD_COLOR_PRESETS.find(([h]) => h.toLowerCase() === hex.toLowerCase());
    selectEl.value = matched ? matched[0] : "";
  });
}

// init 主 mandala + 字布局 color controls
(function _mandalaInitGlobalColors() {
  _mandalaWireColorControl(
    document.getElementById("md-mandala-color-preset"),
    document.getElementById("md-mandala-color"),
    "#000000",
  );
  _mandalaWireColorControl(
    document.getElementById("md-char-color-preset"),
    document.getElementById("md-char-color"),
    "#000000",
  );
})();

// 5b r25: 更新 badge "(N 環 / M 層)" + 控制「+ 增加環」上限
// 5b r26: ring 0 唯一存在時顯示警示
function mandalaUpdateExtrasCount() {
  const container = document.getElementById("md-rings-container");
  const ringSections = container ? container.querySelectorAll(".md-ring-section") : [];
  const ringCount = ringSections.length;
  const layerCount = container ? container.querySelectorAll(".md-layer-row").length : 0;
  const badge = document.getElementById("md-extras-count");
  if (badge) badge.textContent = `(${ringCount} 環 / ${layerCount} 層)`;
  const addRingBtn = document.getElementById("md-add-ring");
  if (addRingBtn) {
    addRingBtn.disabled = (ringCount >= MD_RING_MAX);
    addRingBtn.style.opacity = (ringCount >= MD_RING_MAX) ? "0.5" : "1";
  }
  // 5b r26: 警示僅在「ring 數 = 1 且只有 ring 0」時顯示
  const warn = document.getElementById("md-ring0-warning");
  if (warn) {
    const onlyRing0 = (ringCount === 1)
      && (ringSections[0].dataset.ring === "0");
    warn.style.display = onlyRing0 ? "" : "none";
  }
}

// 5b r25: 全域 renumber — 第 X 層 = ringIdx × 10 + localIdx (1-based)
function mandalaRenumber() {
  const container = document.getElementById("md-rings-container");
  if (!container) return;
  container.querySelectorAll(".md-ring-section").forEach(section => {
    const ringIdx = parseInt(section.dataset.ring, 10) || 0;
    section.querySelectorAll(".md-layer-row").forEach((row, localIdx) => {
      const idxEl = row.querySelector(".md-layer-idx");
      if (idxEl) idxEl.textContent = String(ringIdx * 10 + localIdx + 1);
    });
  });
  mandalaUpdateExtrasCount();
}

// 5b r25: 加 layer row 到指定 ring section
function mandalaAddLayerToRing(section, cfg) {
  if (!section) return null;
  const layersDiv = section.querySelector(".md-ring-layers");
  if (!layersDiv) return null;
  if (layersDiv.querySelectorAll(".md-layer-row").length >= MD_LAYERS_PER_RING) return null;
  cfg = cfg || {};
  const ringIdx = parseInt(section.dataset.ring, 10) || 0;

  const style = cfg.style || "lotus_petal";
  const n = cfg.n_fold || 18;
  // r_mm 預設 = ring 內邊（ringIdx × 10 mm）
  const r_mm_default = ringIdx * MD_RING_WIDTH_MM;
  const r_mm = (cfg.r_mm != null) ? cfg.r_mm : r_mm_default;

  // polymorphic len/width 從 layer 推回 input 顯示值
  let len = 0.6, width = 0.5;
  if (style === "lotus_petal") {
    len = cfg.lotus_length_ratio || 0.6;
    width = cfg.lotus_width_ratio || 0.5;
  } else if (style === "radial_rays") {
    len = cfg.rays_length_ratio || 0.8;
  } else if (style === "dots") {
    len = cfg.dot_radius_mm || 1.0;
  } else if (style === "triangles") {
    len = cfg.length_ratio || 0.5;
    width = cfg.width_ratio || 0.5;
  } else if (style === "wave") {
    len = cfg.amplitude_ratio || 0.04;
  } else if (style === "zigzag") {
    len = cfg.tooth_height_ratio || 0.04;
  } else if (style === "spiral") {
    len = cfg.length_ratio || 1.25;
    width = cfg.spin_turns || 0.5;
  } else {
    len = cfg.overlap_ratio || 1.25;
  }

  // 5b r26: layer 顏色（preset + custom 雙控制），預設黑
  const color = (typeof cfg.color === "string" && cfg.color) ? cfg.color : "#000000";

  const row = document.createElement("div");
  row.className = "row md-layer-row";
  row.style.cssText =
    "background:#f8f8fc;border-left:3px solid #999;padding:5px 10px;" +
    "border-radius:3px;align-items:center;gap:6px;flex-wrap:wrap;margin:3px 0 3px 16px;";
  const optsHtml = _mandalaBuildOptgroupHtml(style);
  const visible = (cfg.visible !== false);
  row.innerHTML =
    `<span style="font-size:11px;color:var(--muted);min-width:50px;">第 <b class="md-layer-idx"></b> 層</span>` +
    `<label style="font-size:11px;" title="勾消即隱藏此層線條（保留設定）">` +
    `<input class="md-layer-visible" type="checkbox"${visible ? " checked" : ""}> 顯示</label>` +
    `<select class="md-layer-style" style="font-size:12px;">${optsHtml}</select>` +
    `<label style="font-size:11px;">N</label>` +
    `<input class="md-layer-n" type="number" value="${n}" min="2" max="60" step="1" style="width:55px;">` +
    `<label style="font-size:11px;" title="該層中心半徑，以 mm 為單位">半徑(mm)</label>` +
    `<input class="md-layer-r-mm" type="number" value="${r_mm}" min="0" max="200" step="1" style="width:70px;">` +
    // 5b r26: 顏色 preset + custom（會在 row.appendChild 後 wire 起來）
    `<label style="font-size:11px;" title="該層線條 fill/stroke 顏色">色</label>` +
    `<select class="md-layer-color-preset md-color-preset" style="font-size:11px;"></select>` +
    `<input class="md-layer-color" type="color" value="${color}"
       style="width:28px;height:22px;padding:0;border:1px solid #ccc;border-radius:3px;">` +
    `<label style="font-size:11px;" title="主參數（瓣長/光線長/dot 半徑/三角長/振幅/齒高/螺旋長）">主</label>` +
    `<input class="md-layer-len" type="number" value="${len}" min="0.04" max="2.5" step="0.05" style="width:65px;">` +
    `<label style="font-size:11px;" title="次參數（瓣寬/三角寬/螺旋圈數，僅部分 style 用）">次</label>` +
    `<input class="md-layer-width" type="number" value="${width}" min="0.1" max="3.0" step="0.05" style="width:60px;">` +
    `<button class="md-layer-delete" type="button" title="刪除此層"
       style="margin-left:auto;padding:2px 8px;font-size:14px;line-height:1;
              border:1px solid #c66;border-radius:3px;background:#fff;
              color:#c33;cursor:pointer;">×</button>`;

  row.querySelector(".md-layer-delete").addEventListener("click", () => {
    row.remove();
    mandalaRenumber();
  });
  const visCb = row.querySelector(".md-layer-visible");
  const syncRowOpacity = () => {
    row.style.opacity = visCb.checked ? "1" : "0.45";
  };
  visCb.addEventListener("change", syncRowOpacity);
  syncRowOpacity();

  // 5b r26: wire color preset + picker（preset 填 options + 雙向 sync）
  _mandalaWireColorControl(
    row.querySelector(".md-layer-color-preset"),
    row.querySelector(".md-layer-color"),
    color,
  );

  layersDiv.appendChild(row);
  mandalaRenumber();
  return row;
}

// 5b r25: 加 ring section（ringIdx 不傳 → 自動分配下一個未用 idx）
function mandalaAddRing(ringIdx, layerCfgs) {
  const container = document.getElementById("md-rings-container");
  if (!container) return null;
  if (container.querySelectorAll(".md-ring-section").length >= MD_RING_MAX) return null;

  // 自動 idx：找最大 + 1
  if (ringIdx == null) {
    let maxIdx = -1;
    container.querySelectorAll(".md-ring-section").forEach(s => {
      const idx = parseInt(s.dataset.ring, 10);
      if (!isNaN(idx) && idx > maxIdx) maxIdx = idx;
    });
    ringIdx = maxIdx + 1;
  }
  ringIdx = Math.max(0, Math.min(MD_RING_MAX - 1, parseInt(ringIdx, 10)));
  // 避 dup
  if (container.querySelector(`.md-ring-section[data-ring="${ringIdx}"]`)) return null;

  const innerMm = ringIdx * MD_RING_WIDTH_MM;
  const outerMm = (ringIdx + 1) * MD_RING_WIDTH_MM;
  const isBaseRing = (ringIdx === 0);
  const section = document.createElement("div");
  section.className = "md-ring-section";
  section.dataset.ring = String(ringIdx);
  section.style.cssText =
    "background:#fafafa;border:1px solid #ccc;border-radius:3px;" +
    "padding:6px 8px;margin:4px 0;";
  section.innerHTML =
    `<div class="row md-ring-header" style="align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:2px;">` +
      `<b style="color:#742;font-size:12px;">第 ${ringIdx} 環</b>` +
      `<span style="color:var(--muted);font-size:11px;">(${innerMm} - ${outerMm} mm)</span>` +
      `<button class="md-add-layer-to-ring" type="button"
         style="padding:2px 8px;font-size:11px;border:1px dashed #999;
                border-radius:3px;background:#fff;cursor:pointer;color:#444;">＋ 增加裝飾層</button>` +
      (isBaseRing ? "" :
        `<button class="md-ring-delete" type="button" title="刪除此環（含內部所有裝飾層）"
           style="margin-left:auto;padding:2px 8px;font-size:11px;
                  border:1px solid #c66;border-radius:3px;background:#fff;
                  color:#c33;cursor:pointer;">× 刪除環</button>`) +
    `</div>` +
    `<div class="md-ring-layers"></div>`;

  section.querySelector(".md-add-layer-to-ring").addEventListener("click", () => {
    mandalaAddLayerToRing(section);
  });
  if (!isBaseRing) {
    section.querySelector(".md-ring-delete").addEventListener("click", () => {
      section.remove();
      mandalaRenumber();
    });
  }

  // 依 ring index 排序插入
  const existing = Array.from(container.querySelectorAll(".md-ring-section"));
  let inserted = false;
  for (const s of existing) {
    const sIdx = parseInt(s.dataset.ring, 10);
    if (sIdx > ringIdx) {
      container.insertBefore(section, s);
      inserted = true;
      break;
    }
  }
  if (!inserted) container.appendChild(section);

  // 加入 layer 配置
  const cfgs = layerCfgs || [];
  for (const cfg of cfgs) {
    mandalaAddLayerToRing(section, cfg);
  }
  mandalaRenumber();
  return section;
}

function mandalaClearAllLayers() {
  const container = document.getElementById("md-rings-container");
  if (container) container.innerHTML = "";
  mandalaUpdateExtrasCount();
}

// 5b r25/r26: 輸出 layers JSON — r_mm 為主（後端優先），r_ratio 給 helper 推 pointing 用，
// color 帶入後端套用 stroke/fill。
function mandalaBuildExtraLayersJson() {
  const container = document.getElementById("md-rings-container");
  const layers = [];
  const r_total_est = _mandalaCurrentRTotalMm();
  if (container) {
    container.querySelectorAll(".md-layer-row").forEach(row => {
      const style = row.querySelector(".md-layer-style").value;
      const visCb = row.querySelector(".md-layer-visible");
      const r_mm = parseFloat(row.querySelector(".md-layer-r-mm").value);
      const r_mm_safe = isNaN(r_mm) ? 0 : Math.max(r_mm, 0);
      const colorEl = row.querySelector(".md-layer-color");
      const color = colorEl && colorEl.value ? colorEl.value : "#000000";
      const layer = {
        style: style,
        n_fold: parseInt(row.querySelector(".md-layer-n").value, 10) || 18,
        r_mm: r_mm_safe,
        r_ratio: r_mm_safe / r_total_est,
        visible: visCb ? visCb.checked : true,
        color: color,
      };
      _mandalaApplyStyleSpecificParams(layer, style,
        parseFloat(row.querySelector(".md-layer-len").value),
        parseFloat(row.querySelector(".md-layer-width").value));
      layers.push(layer);
    });
  }
  return JSON.stringify(layers);
}

// 5b r25: 「+ 增加環」按鈕 — 自動分配下一個 ring idx，新環帶 1 個 default layer
document.getElementById("md-add-ring")?.addEventListener("click", () => {
  mandalaAddRing(null, [{}]);
});

// 5b r25: 初始化 — 確保 0 環存在 + 1 個 default layer
(function _mandalaInitRings() {
  const container = document.getElementById("md-rings-container");
  if (container && container.children.length === 0) {
    mandalaAddRing(0, [{}]);
  }
})();
mandalaUpdateExtrasCount();

// Phase 5b r21: 「🚫 隱藏主線條」checkbox 跟 md-show-mandala 雙向同步
function _mandalaSyncMainHide() {
  const hideCb = document.getElementById("md-hide-main");
  const showCb = document.getElementById("md-show-mandala");
  if (!hideCb || !showCb) return;
  // hide=true ↔ show=false
  hideCb.addEventListener("change", () => {
    showCb.checked = !hideCb.checked;
  });
  showCb.addEventListener("change", () => {
    hideCb.checked = !showCb.checked;
  });
  // init: 同步初始 state
  hideCb.checked = !showCb.checked;
}
_mandalaSyncMainHide();

// Phase 5b r15: 中心類型 radio → show/hide icon controls + 中心字 input
function mandalaSyncCenterType() {
  const checked = document.querySelector('input[name="md-center-type"]:checked');
  const type = checked ? checked.value : "char";
  const iconRow = document.getElementById("md-icon-controls");
  const centerTextInput = document.getElementById("md-center-text");
  if (iconRow) iconRow.style.display = (type === "icon") ? "" : "none";
  if (centerTextInput) {
    centerTextInput.disabled = (type !== "char");
    centerTextInput.style.opacity = (type === "char") ? "1" : "0.5";
  }
}
document.querySelectorAll('input[name="md-center-type"]').forEach(r =>
  r.addEventListener("change", mandalaSyncCenterType));
mandalaSyncCenterType();  // init

// Phase 5b r6: Mandala 樣式切換 → show/hide 該樣式的專用參數 row
function mandalaSyncStyleRows() {
  const sel = document.getElementById("md-style-primitive");
  if (!sel) return;
  const style = sel.value;
  const arcsRow = document.getElementById("md-arcs-row");
  const lotusRow = document.getElementById("md-lotus-row");
  const raysRow = document.getElementById("md-rays-row");
  if (arcsRow) arcsRow.style.display = (style === "interlocking_arcs") ? "" : "none";
  if (lotusRow) lotusRow.style.display = (style === "lotus_petal") ? "" : "none";
  if (raysRow) raysRow.style.display = (style === "radial_rays") ? "" : "none";
}
document.getElementById("md-style-primitive")?.addEventListener("change",
  mandalaSyncStyleRows);
mandalaSyncStyleRows();  // init: 套用一次 default state

// Phase 5b r8: composition_scheme 切換 → show/hide r_ring_ratio / char_spacing /
// inscribed_padding rows，並 auto-toggle halo (vesica/inscribed 預設關)
function mandalaSyncSchemeRows() {
  const sel = document.getElementById("md-comp-scheme");
  if (!sel) return;
  const scheme = sel.value;
  // r_ring_ratio 只在 freeform 顯示（vesica/inscribed 用 char_spacing 推算）
  const rRingInput = document.getElementById("md-r-ring");
  if (rRingInput) {
    const lbl = rRingInput.previousElementSibling;
    rRingInput.style.display = (scheme === "freeform") ? "" : "none";
    if (lbl && lbl.tagName === "LABEL") {
      lbl.style.display = (scheme === "freeform") ? "" : "none";
    }
  }
  // inscribed-only padding row
  const inscribedRow = document.getElementById("md-inscribed-row");
  if (inscribedRow) inscribedRow.style.display = (scheme === "inscribed") ? "" : "none";
  // char_spacing 只在 vesica/inscribed 有意義（freeform 顯示但 backend 忽略）
  const cs = document.getElementById("md-char-spacing");
  if (cs) {
    cs.disabled = (scheme === "freeform");
    cs.style.opacity = (scheme === "freeform") ? "0.5" : "1";
  }
  // Auto halo default: vesica/inscribed 字本來就在線內空間，halo 不需要
  // 但保留 user 設定，只在 scheme change 時建議性切（不強制）
  const protectCb = document.getElementById("md-protect-chars");
  if (protectCb && !protectCb.dataset.userTouched) {
    protectCb.checked = (scheme === "freeform");
  }
}
document.getElementById("md-comp-scheme")?.addEventListener("change",
  mandalaSyncSchemeRows);
// 一旦 user 手動勾過 halo，就不再自動切
document.getElementById("md-protect-chars")?.addEventListener("change", (e) => {
  e.target.dataset.userTouched = "1";
});
mandalaSyncSchemeRows();  // init

// Enable/disable the align dropdown based on auto_cycle state
function waUpdateAlignState() {
  const cycleOn = document.getElementById("wa-auto-cycle").checked;
  const sel = document.getElementById("wa-align");
  const hint = document.getElementById("wa-align-hint");
  sel.disabled = cycleOn;
  sel.style.opacity = cycleOn ? "0.5" : "1";
  if (hint) {
    hint.textContent = cycleOn
      ? "(目前自動循環中，對齊設定已略過)"
      : "(字數不足時套用)";
  }
}
document.getElementById("wa-auto-cycle").addEventListener("change", waUpdateAlignState);

// direction dropdown only active for layout=fill
function waUpdateDirectionState() {
  const layout = document.getElementById("wa-layout").value;
  const sel = document.getElementById("wa-direction");
  const hint = document.getElementById("wa-direction-hint");
  const isFill = (layout === "fill");
  sel.disabled = !isFill;
  sel.style.opacity = isFill ? "1" : "0.5";
  if (hint) {
    hint.textContent = isFill
      ? "(fill 佈局生效：直書 = 字上→下、欄右→左)"
      : "(僅 fill 佈局生效，目前佈局已略過)";
  }
}
document.getElementById("wa-layout").addEventListener("change", waUpdateDirectionState);

// autoload initial single-char on first paint + initial capacity computations
document.addEventListener("DOMContentLoaded", () => {
  load();
  scheduleNbCapacity();
  scheduleLtCapacity();
  waUpdatePanels();
  scheduleWaCapacity();
  waUpdateAlignState();
  waUpdateDirectionState();
  udInit();
  swInit();
  cnsInit();
  sealInit();
  lishuInit();
  songInit();
  kaishuInit();
  bindAllFontStyleGates();   // Phase 11a: font-style select 授權 gate
  patchInit();   // Phase 5ax
  stampInit();   // Phase 5ay
  sutraInit();   // Phase 5az
});

