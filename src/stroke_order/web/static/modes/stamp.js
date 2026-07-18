// ============================================================
// 印章模式 (Phase 5ay) — laser engraving on wood
// ============================================================
const STAMP = {
  decorations: [],   // [{svg_content, x_mm, y_mm, w_mm, h_mm}, ...]
  // 12m-7 r29: 圓戳章內框向量圖（user 上傳的 SVG 文字內容；產生預覽時
  // 自動計算 bbox 後 push 到 decorations array 一起送 backend）
  innerDecoSvg: null,
};

function stampInit() {
  const $ = id => document.getElementById(id);
  if (!$("st-render")) return;
  $("st-render").onclick   = () => stampRender();
  $("st-dl-svg").onclick   = () => stampDownload("svg");
  $("st-dl-pdf").onclick   = () => stampDownload("pdf");
  $("st-dl-gcode").onclick = () => stampDownload("gcode");
  $("st-dl-dxf").onclick   = () => stampDownload("dxf");   // 5bs
  $("st-deco-add").onclick = stampAddDecoration;
  // 12m-1 patch r5: applyDefaults 必須先於 capacity 註冊到 st-preset.change
  // 否則 capacity 拿 stale w/h 發 fetch，跟 applyDefaults 末尾 call 的 fetch
  // race；網路抖動時 stale response 後到會 overwrite UI。
  $("st-preset").addEventListener("change", stampApplyPresetDefaults);
  // Capacity hint live-updates — st-preset 不放這裡（applyDefaults 末尾會 call）
  // st-pad / st-double-border 影響 oval inner area，必須觸發 refresh
  ["st-w", "st-h", "st-charsize", "st-text",
   "st-pad", "st-double-border"].forEach(id => {
    const el = $(id);
    if (!el) return;
    el.addEventListener("change", stampUpdateCapacity);
    el.addEventListener("input", stampUpdateCapacity);
  });
  // 12g: 每字位移微調 — text 變動時更新 row 數
  $("st-text").addEventListener("input", stampUpdateCharOffsetsUI);
  // 12l: 公司章短列 checkbox group — 隨字數切換 3-col / 4-col / 隱藏
  ["st-text", "st-preset"].forEach(id => {
    $(id).addEventListener("input", stampUpdateOfficialShortColUI);
    $(id).addEventListener("change", stampUpdateOfficialShortColUI);
  });
  stampUpdateOfficialShortColUI();
  // 12m-1: oval 結構化欄位 — preset=oval 時顯示 5 欄 + 隱藏單一 text
  $("st-preset").addEventListener("change", stampUpdateOvalFieldsUI);
  stampUpdateOvalFieldsUI();
  // 12m-7 r39: 職名章 (rectangle_title) 左欄 1/2 行 toggle
  const rectLeft2Rows = $("st-rect-left-2rows");
  const rectLeftLine2Row = $("st-rect-left-line2-row");
  if (rectLeft2Rows && rectLeftLine2Row) {
    const syncRectLeft2Rows = () => {
      rectLeftLine2Row.style.display = rectLeft2Rows.checked
        ? "flex" : "none";
    };
    rectLeft2Rows.addEventListener("change", syncRectLeft2Rows);
    syncRectLeft2Rows();
  }
  // 12m-1 patch r17: oval-show-inner ↔ double-border 雙向同步
  const ovalShowInner = $("st-oval-show-inner");
  if (ovalShowInner) {
    ovalShowInner.addEventListener("change", stampOvalShowInnerSync);
  }
  // 12m-7 r29: 圓戳章內框向量圖上傳 + 清除
  const innerDecoFile = $("st-round-inner-deco-file");
  if (innerDecoFile) {
    innerDecoFile.addEventListener("change", async (e) => {
      STAMP.innerDecoOnlySlot2Pos = null;  // r31: 換檔重置 case 4 prompt 選擇
      const f = e.target.files[0];
      if (!f) {
        STAMP.innerDecoSvg = null;
        $("st-round-inner-deco-status").textContent =
          "自動置中：依中央 1/2/3 是否填寫決定 image+text 比例配置";
        return;
      }
      try {
        STAMP.innerDecoSvg = await f.text();
        $("st-round-inner-deco-status").textContent =
          `已載入 ${f.name}（${(f.size / 1024).toFixed(1)} KB）`;
      } catch (err) {
        STAMP.innerDecoSvg = null;
        alert("讀取 SVG 檔失敗：" + err.message);
      }
    });
  }
  const innerDecoClear = $("st-round-inner-deco-clear");
  if (innerDecoClear) {
    innerDecoClear.addEventListener("click", () => {
      STAMP.innerDecoSvg = null;
      STAMP.innerDecoOnlySlot2Pos = null;  // r31
      if (innerDecoFile) innerDecoFile.value = "";
      $("st-round-inner-deco-status").textContent =
        "自動置中：依中央 1/2/3 是否填寫決定 image+text 比例配置";
    });
  }
  // 12m-1 patch r6: 姓名章專用排列（2 字 / 5 字 layout）— preset ∈
  // {square_name, round_name} 時顯示，跟 oval-fields pattern 對齊。
  $("st-preset").addEventListener("change", stampUpdateNameFieldsUI);
  stampUpdateNameFieldsUI();
  // 12m-1 patch r9: 3 字自動補字僅 square_name；每字位移微調僅
  // square_name / round_name / square_official 適用。
  $("st-preset").addEventListener("change", stampUpdateAutofillUI);
  $("st-preset").addEventListener("change", stampUpdateCharOffsetsVisibilityUI);
  stampUpdateAutofillUI();
  stampUpdateCharOffsetsVisibilityUI();
  // 12m-1 patch r3: 初次載入也套用 preset defaults（含雙線外框 ON for oval）。
  // 過去 stampApplyPresetDefaults 只 hook 在 change，初始狀態靠 HTML 寫死，
  // 結果使用者第一次選 oval 時若 cached JS 沒 4-element default，雙框沒生效。
  // 改成 init 時就跑一次 → 任何 preset 進站都同步到正確 default 狀態。
  stampApplyPresetDefaults();
  const offsetsReset = $("st-char-offsets-reset");
  if (offsetsReset) {
    offsetsReset.addEventListener("click", () => {
      document.querySelectorAll("#st-char-offsets-body input").forEach(
        el => { el.value = "0"; }
      );
    });
  }
  stampUpdateCharOffsetsUI();
  // 12b-1: 業界 8 級尺寸 quick-pick — 套用後同步 w/h
  $("st-size-preset").addEventListener("change", stampApplySizePreset);
  // 12b-1: 手動改 w/h → quick-pick 切到「自訂尺寸」
  ["st-w", "st-h"].forEach(id => {
    $(id).addEventListener("input", stampSyncSizePreset);
  });
  stampUpdateCapacity();
  stampRefreshDecoList();
}

function stampApplyPresetDefaults() {
  const $ = id => document.getElementById(id);
  // Layout preset 切換時的預設尺寸：對齊業界 8 級制（個人章 4 分、
  // 公司章 8 分；圓 / 橢圓 / 長方非 8 級制業界少見，保持原邏輯）。
  // 第 4 個值（可選）= double_border 預設（12m-1 patch：橢圓章預設雙框，
  // 業界橢圓章絕大多數含 inner ellipse；其他 preset 維持單框）。
  const defaults = {
    square_name:      [12, 12, 5,  false],
    round_name:       [12, 12, 5,  false],
    square_official:  [24, 24, 8,  false],
    round:            [24, 24, 8,  true],   // 12m-7 r25: 圓戳章預設雙框（內圓+外圓 ring band）
    oval:             [50, 35, 9,  true],   // 12m-1 patch r2: 1.43:1 比例（業界常見），預設雙框
    tax_invoice:      [45, 40, 8,  true],   // 12m-7 r7: 統一發票章「電視章」改 45×40 (4.5×4.0 cm) 給更多 vertical 空間（plum 跟 char 同寬時不擠）
    rectangle_title:  [28, 8,  6, false],   // 12m-7 r39: 職名章預設 28×8
  };
  const d = defaults[$("st-preset").value];
  if (!d) return;
  $("st-w").value = d[0];
  $("st-h").value = d[1];
  $("st-charsize").value = d[2];
  if (d.length >= 4 && $("st-double-border")) {
    $("st-double-border").checked = !!d[3];
    // 12m-1 patch r17: sync oval-show-inner from preset default
    const innerCb = $("st-oval-show-inner");
    if (innerCb) innerCb.checked = !!d[3];
  }
  // 同步 size quick-pick 顯示
  stampSyncSizePreset();
  stampUpdateCapacity();
}

// 12b-1: 點業界尺寸 quick-pick → 同步填 w/h（方/圓共用）
function stampApplySizePreset() {
  const $ = id => document.getElementById(id);
  const v = $("st-size-preset").value;
  if (!v) return;  // 「自訂尺寸」不動 w/h
  $("st-w").value = v;
  $("st-h").value = v;
  stampUpdateCapacity();
}

// 12b-1: 手動改 w/h 時，quick-pick 切到「自訂尺寸」（除非剛好等於某級）
function stampSyncSizePreset() {
  const $ = id => document.getElementById(id);
  const w = $("st-w").value, h = $("st-h").value;
  // 方章：w === h 且符合 8 級 → 切到對應 option；否則切「自訂」
  const standard = ["10", "12", "15", "18", "21", "24", "27", "30"];
  const sel = $("st-size-preset");
  if (w === h && standard.includes(w)) {
    sel.value = w;
  } else {
    sel.value = "";
  }
}

// 12l: 公司章短列 UI 切換 — 依字數顯示 3-col / 4-col checkbox 或隱藏整列
// 12m-1: oval preset 切換時顯示橢圓章 5 欄位 + 隱藏單一 text 欄
// 12m-6: tax_invoice 共用 oval-fields，但語意 / 預設值 / label 不同：
//   上弧文=公司名稱、中央 1=統一編號（標題固定「統一編號」）、
//   中央 2=負責人、中央 3=電話、下弧文=地址
function stampUpdateOvalFieldsUI() {
  const $ = id => document.getElementById(id);
  const presetEl = $("st-preset");
  const textRow = $("st-text-row");
  const ovalFields = $("st-oval-fields");
  if (!presetEl || !textRow || !ovalFields) return;
  const v = presetEl.value;
  const isOval = v === "oval";
  const isTaxInvoice = v === "tax_invoice";
  const isRound = v === "round";   // 12m-7 r25: 圓戳章共用 oval 結構化 layout
  const showFields = isOval || isTaxInvoice || isRound;
  textRow.style.display = showFields ? "none" : "";
  ovalFields.style.display = showFields ? "flex" : "none";
  // 12m-1 patch r17: oval-like 時隱藏標準雙線外框 row（被 oval-fields 內的
  // 「顯示內框」checkbox 取代），同步雙向 state。
  const dbLabel = $("st-double-border-label");
  if (dbLabel) dbLabel.style.display = showFields ? "none" : "";
  // 12m-1 patch r18: 鋸齒外框 checkbox 在 oval-like 顯示
  const sawLabel = $("st-sawtooth-label");
  if (sawLabel) sawLabel.style.display = showFields ? "" : "none";
  // 12m-7 r26: 圓戳章單圓周排列 checkbox 僅 round preset 顯示
  const rcaLabel = $("st-round-cont-arc-label");
  if (rcaLabel) rcaLabel.style.display = isRound ? "" : "none";
  // 12m-7 r28: 圓戳章不顯示中央 1/2「加粗」checkbox（user 要求簡化版面）
  const bold1Label = $("st-oval-body-1-bold-label");
  const bold2Label = $("st-oval-body-2-bold-label");
  const showBold = isOval || isTaxInvoice;
  if (bold1Label) bold1Label.style.display = showBold ? "" : "none";
  if (bold2Label) bold2Label.style.display = showBold ? "" : "none";
  // 12m-7 r29: 圓戳章專用內框向量圖上傳 row
  const innerDecoRow = $("st-round-inner-deco-row");
  if (innerDecoRow) innerDecoRow.style.display = isRound ? "flex" : "none";
  // 12m-7 r39: 職名章 (rectangle_title) 結構化欄位
  const isRect = (v === "rectangle_title");
  const rectFields = $("st-rect-fields");
  if (rectFields) rectFields.style.display = isRect ? "flex" : "none";
  // 職名章 mode 時也要 hide 單一 text 欄（用 rect-fields 取代）
  if (isRect && textRow) textRow.style.display = "none";
  // Sync 內外狀態：oval-show-inner ↔ st-double-border
  const innerCb = $("st-oval-show-inner");
  const dbCb = $("st-double-border");
  if (showFields && innerCb && dbCb) {
    // 從 oval-show-inner 同步到 double-border（雙線外框 backend flag）
    dbCb.checked = innerCb.checked;
  }
  // 12m-7: tax_invoice 額外欄位（上方標題 / 縣市 / 縣市位置）
  const taxinvExtra = $("st-taxinv-extra");
  if (taxinvExtra) {
    taxinvExtra.style.display = isTaxInvoice ? "flex" : "none";
  }
  // 12m-6: tax_invoice 切換 oval-fields label / placeholder / default 文字
  // 對齊「電視章」用途。Oval 改回原 placeholder。
  const lblBody1 = ovalFields.querySelector('label[for="st-oval-body-1"]')
    || ovalFields.querySelectorAll('div > label')[1]; // 中央 1 row label
  // 透過 id 直接抓 input
  const txTitle = ovalFields.querySelector('[style*="font-weight:600"]');
  const inpArcTop = $("st-oval-arc-top");
  const inpBody1 = $("st-oval-body-1");
  const inpBody2 = $("st-oval-body-2");
  const inpBody3 = $("st-oval-body-3");
  const inpArcBot = $("st-oval-arc-bottom");
  if (isTaxInvoice) {
    if (txTitle) {
      txTitle.innerHTML = '統一發票章「電視章」欄位'
        + '<span style="color:var(--muted);font-weight:normal;font-size:11px;'
        + 'margin-left:6px;">公司名稱 + 統一編號（固定標題）+ 負責人 + 電話 + 地址</span>';
    }
    if (inpArcTop) inpArcTop.placeholder = "公司名稱 / 商號";
    if (inpBody1) inpBody1.placeholder = "統一編號（8 位數字）";
    if (inpBody2) inpBody2.placeholder = "負責人姓名";
    if (inpBody3) inpBody3.placeholder = "電話";
    if (inpArcBot) inpArcBot.placeholder = "公司地址";
    // 套用 tax_invoice 預設文字（只在欄位空 / 是 oval default 時填）
    const ovalDefaults = new Set([
      "測試文件股份有限公司", "收發章", "電話:02-2234567",
      "測試市測試區測試路1段2巷3弄4號5樓之一",
      "測試市測試區測試路1段2巷3弄4號5樓之ㄧ",  // legacy（zhuyin ㄧ）
      "試題市試題區測試路1段2巷3弄4號之ㄧ56號7樓",  // legacy 舊預設
      "",
    ]);
    if (inpArcTop && ovalDefaults.has(inpArcTop.value))
      inpArcTop.value = "測試發票股份有限公司";
    if (inpBody1 && ovalDefaults.has(inpBody1.value))
      inpBody1.value = "12345678";
    if (inpBody2 && ovalDefaults.has(inpBody2.value))
      inpBody2.value = "王大同";
    if (inpBody3 && ovalDefaults.has(inpBody3.value))
      inpBody3.value = "02-23456789";
    if (inpArcBot && ovalDefaults.has(inpArcBot.value))
      inpArcBot.value = "台北市中正區測試路100號";
  } else if (isOval) {
    if (txTitle) {
      txTitle.innerHTML = '橢圓章欄位（業界格式）'
        + '<span style="color:var(--muted);font-weight:normal;font-size:11px;'
        + 'margin-left:6px;">上弧文 + 中央 1-3 行 + 下弧文（任一空白即略過）</span>';
    }
    if (inpArcTop) inpArcTop.placeholder = "公司名稱 / 單位名稱";
    if (inpBody1) inpBody1.placeholder = "單位名稱 / 電話 / 統一編號";
    if (inpBody2) inpBody2.placeholder = "單位名稱 / 電話 / 統編號碼";
    if (inpBody3) inpBody3.placeholder = "電話 / 傳真";
    if (inpArcBot) inpArcBot.placeholder = "地址 / 分店名稱";
  }
}

// 12m-1 patch r17: 「顯示內框」checkbox change → sync to st-double-border
// + trigger capacity refresh
function stampOvalShowInnerSync() {
  const innerCb = document.getElementById("st-oval-show-inner");
  const dbCb = document.getElementById("st-double-border");
  if (!innerCb || !dbCb) return;
  dbCb.checked = innerCb.checked;
  if (typeof stampUpdateCapacity === "function") stampUpdateCapacity();
}

// 12m-1 patch r6: 姓名章專用排列選項（2 字 / 5 字 layout）。preset ∈
// {square_name, round_name} 時顯示。其他 preset（公司章 / 圓章 / 橢圓 /
// 長方）不適用，整個區塊隱藏避免 UI 雜訊。
function stampUpdateNameFieldsUI() {
  const presetEl = document.getElementById("st-preset");
  const nameFields = document.getElementById("st-name-fields");
  if (!presetEl || !nameFields) return;
  const isPersonalName = presetEl.value === "square_name"
                       || presetEl.value === "round_name";
  nameFields.style.display = isPersonalName ? "" : "none";
}

// 12m-1 patch r9: 3 字自動補字僅 square_name 慣例（個人姓名章 4 格 2×2
// 補「印」），其他 preset 沒此邏輯需求 → 整 row 隱藏。
function stampUpdateAutofillUI() {
  const presetEl = document.getElementById("st-preset");
  const row = document.getElementById("st-autofill-row");
  if (!presetEl || !row) return;
  row.style.display = (presetEl.value === "square_name") ? "" : "none";
}

// 12m-1 patch r9: 每字位移微調僅 square_name / round_name / square_official
// 適用（這 3 個 preset 是 grid-based，每字有獨立 cell 可位移）。橢圓 /
// 圓戳章 / 職名章 layout 是 arc 或固定 stretch，per-char offset 沒意義。
function stampUpdateCharOffsetsVisibilityUI() {
  const presetEl = document.getElementById("st-preset");
  const det = document.getElementById("st-char-offsets");
  if (!presetEl || !det) return;
  const allowed = ["square_name", "round_name", "square_official"];
  det.style.display = allowed.includes(presetEl.value) ? "" : "none";
}

function stampUpdateOfficialShortColUI() {
  const presetEl = document.getElementById("st-preset");
  const textEl = document.getElementById("st-text");
  const row = document.getElementById("st-off-shortcol-row");
  if (!row || !presetEl || !textEl) return;
  const preset = presetEl.value;
  const cleanText = (textEl.value || "").replace(/\s+/g, "");
  const charCount = Array.from(cleanText).length;
  const isOfficial = preset === "square_official";
  const needsShort = isOfficial && (
    (charCount >= 7 && charCount <= 8) ||
    (charCount >= 10 && charCount <= 11) ||
    (charCount >= 13 && charCount <= 15)
  );
  // 字數 9 / 12 / 16 是 perfect grid，沒短列；1-6 不適用 multi-col layout
  row.style.display = needsShort ? "" : "none";
  if (!needsShort) return;
  const use4Col = charCount >= 13 && charCount <= 15;
  document.querySelectorAll(".st-off-3col").forEach(el => {
    el.style.display = use4Col ? "none" : "";
  });
  document.querySelectorAll(".st-off-4col").forEach(el => {
    el.style.display = use4Col ? "" : "none";
  });
}

// 12m-1 patch r5: stampUpdateCapacity 帶 sequence guard 防 async race。
// 多次併發 fetch 時，舊的 response 可能後到 overwrite 最新 UI；用單調遞增
// 序號 token，return 時比對最新 token，stale 直接 drop。
let _capacityReqSeq = 0;
async function stampUpdateCapacity() {
  const $ = id => document.getElementById(id).value;
  const $$ = id => document.getElementById(id);
  const myReq = ++_capacityReqSeq;
  // 12m-1 patch r4: 帶 double_border + border_padding 給 backend，否則 oval
  // 雙框時 inner area 跟 capacity 算錯（差 0.8mm × 2 = 1.6mm 影響弧長 cap）。
  const params = new URLSearchParams({
    preset: $("st-preset"),
    stamp_width_mm: $("st-w"),
    stamp_height_mm: $("st-h"),
    char_size_mm: $("st-charsize"),
    border_padding_mm: $("st-pad") || "0.8",
    double_border: $$("st-double-border")?.checked ? "true" : "false",
  });
  try {
    const r = await fetch(`${API_BASE}/api/stamp/capacity?${params}`);
    if (!r.ok) return;
    const d = await r.json();
    // 12m-1 patch r5: stale response → drop (newer request already inflight/done)
    if (myReq !== _capacityReqSeq) return;
    const sizeStr = `<b>${d.inner_size_mm[0]}×${d.inner_size_mm[1]}</b> mm`;
    let hint;
    if ((d.preset === "oval" || d.preset === "tax_invoice") && d.oval_caps) {
      // 12m-1 patch r4 / 12m-6: oval-like 結構化 hint — 弧文 / body 各自 cap
      const c = d.oval_caps;
      hint = `章面內框 ${sizeStr} ｜ 弧文每行 ≤ <b>${c.arc_top_max}</b> 字、中央每行 ≤ <b>${c.body_per_line_max}</b> 字（自動縮放至 ${c.min_legible_mm}mm 為下限）`;
    } else {
      hint = `章面內框 ${sizeStr} ｜ 建議文字 ≤ <b>${d.max_chars}</b> 字`;
    }
    $$("st-capacity").innerHTML = hint;
  } catch (_) {}
  stampUpdateSizeHint();
}

// 12g: 每字位移微調 UI — 字數變動時動態生成 row（保留既有值）
function stampUpdateCharOffsetsUI() {
  const text = document.getElementById("st-text").value || "";
  // square_name max 5（後端 hard-cap），其他 preset 也限 5 簡化 UX
  const n = Math.min([...text].length, 5);
  const body = document.getElementById("st-char-offsets-body");
  if (!body) return;
  // 保留既有值（避免 user 改字時打掉微調）
  const oldRows = body.querySelectorAll(".char-offset-row");
  const oldValues = Array.from(oldRows).map(row => ({
    dx: parseFloat(row.querySelector(".char-dx").value) || 0,
    dy: parseFloat(row.querySelector(".char-dy").value) || 0,
  }));
  body.innerHTML = "";
  if (n === 0) {
    body.innerHTML = '<span style="color:var(--muted);">輸入文字後顯示</span>';
    return;
  }
  for (let i = 0; i < n; i++) {
    const old = oldValues[i] || { dx: 0, dy: 0 };
    const charPreview = [...text][i] || "?";
    const row = document.createElement("div");
    row.className = "char-offset-row";
    row.dataset.i = String(i);
    row.style.cssText = "display:flex;align-items:center;gap:6px;margin:2px 0;";
    row.innerHTML = `
      <span style="min-width:50px;">第 ${i + 1} 字（${charPreview}）</span>
      <span title="正值往右、負值往左">左右 X</span>
      <input type="number" class="char-dx" value="${old.dx}"
             step="0.1" min="-5" max="5" style="width:55px;"
             title="正值往右、負值往左">
      <span title="正值往下、負值往上">上下 Y</span>
      <input type="number" class="char-dy" value="${old.dy}"
             step="0.1" min="-5" max="5" style="width:55px;"
             title="正值往下、負值往上">
      mm
    `;
    body.appendChild(row);
  }
}

// 12b-2 + 12b-3: 小尺寸警示 + 字數推薦尺寸
// 業界規範（8 張範例圖共識）：
//   1 字  → 1.0–1.5 cm   2 字  → 1.0–1.8 cm
//   3 字  → 1.2–2.1 cm   4 字  → 1.5–2.4 cm
//   5+ 字 → 2.4–3.0 cm（公司章常見）
// 小尺寸警示：邊長 ≤ 1.5 cm AND 字數 ≥ 3 → 提示筆劃可能相連
function stampUpdateSizeHint() {
  const $ = id => document.getElementById(id);
  // 12m-7 r28: 圓戳章使用 oval-fields 結構化欄位，st-text 字數非實際內容，
  // 推薦尺寸 hint 不適用 → 隱藏。
  const presetVal = $("st-preset").value;
  if (presetVal === "round") {
    $("st-size-hint").style.display = "none";
    return;
  }
  const w = parseFloat($("st-w").value) || 0;
  const text = $("st-text").value || "";
  // 用 [...str] 正確處理中文字元 / 表情 / 多碼點
  const n = [...text].length;

  const recommendations = {
    1: "1.0–1.5 cm",
    2: "1.0–1.8 cm",
    3: "1.2–2.1 cm",
    4: "1.5–2.4 cm",
    5: "2.4–3.0 cm（公司章常見）",
  };
  // 12e: square_name 最多 5 字（業界慣例 + 後端 layout 對齊）
  const preset = $("st-preset").value;
  const isSquareName = preset === "square_name";
  const rec = recommendations[n];

  const parts = [];
  // 12e: square_name 6+ 字超過上限 → 紅色警示
  if (isSquareName && n > 5) {
    parts.push(`⚠ 正方形姓名章最多 5 字，超過部分（第 6 字以後共 ${n - 5} 字）將不顯示`);
  }
  // 警示：4 分 1.2cm 以下 + 3 字以上 → 筆劃相連風險
  else if (w <= 12 && n >= 3) {
    parts.push("⚠ 1.2 cm 以下尺寸 + 3 字以上時筆劃可能相連，建議先試印確認");
  } else if (w <= 15 && n >= 4) {
    parts.push("⚠ 1.5 cm 以下尺寸 + 4 字以上時筆劃可能相連，建議放大尺寸或減少字數");
  }
  // 字數推薦尺寸（純資訊）
  if (rec && n > 0 && n <= 5) {
    parts.push(`業界 ${n} 字推薦尺寸：${rec}`);
  } else if (n > 5 && !isSquareName) {
    // 非 square_name 的多字（公司章 9 字、抄經...）保留
    parts.push(`業界 ${n} 字推薦尺寸：2.4–3.0 cm（公司章常見）`);
  }

  const hintEl = $("st-size-hint");
  if (parts.length === 0) {
    hintEl.style.display = "none";
  } else {
    hintEl.innerHTML = parts.join(" · ");
    hintEl.style.display = "block";
    // 12e: 6+ 字超過上限 → 紅色警示樣式（區別黃色一般提示）
    const isOverLimit = isSquareName && n > 5;
    if (isOverLimit) {
      hintEl.style.background = "#fef2f2";
      hintEl.style.borderLeftColor = "#c33";
      hintEl.style.color = "#9b2c2c";
    } else {
      hintEl.style.background = "#fff8e6";
      hintEl.style.borderLeftColor = "#e0a020";
      hintEl.style.color = "#7a5500";
    }
  }
}

async function stampAddDecoration() {
  const $ = id => document.getElementById(id);
  const file = $("st-deco-file").files[0];
  let svg_content = $("st-deco-paste").value.trim();
  if (file) svg_content = await file.text();
  if (!svg_content) {
    alert("請選擇 SVG 檔或貼上 SVG 內容");
    return;
  }
  STAMP.decorations.push({
    svg_content,
    x_mm: parseFloat($("st-deco-x").value),
    y_mm: parseFloat($("st-deco-y").value),
    w_mm: parseFloat($("st-deco-w").value),
    h_mm: parseFloat($("st-deco-h").value),
  });
  $("st-deco-file").value = "";
  $("st-deco-paste").value = "";
  stampRefreshDecoList();
}

function stampRefreshDecoList() {
  const list = document.getElementById("st-deco-list");
  if (!list) return;
  if (STAMP.decorations.length === 0) {
    list.innerHTML = "（尚未加入裝飾。可選 SVG 檔或貼上後按「+ 加入」）";
    return;
  }
  list.innerHTML = STAMP.decorations.map((d, i) =>
    `<div style="margin:2px 0;">
       #${i + 1} 位置(${d.x_mm},${d.y_mm}) 大小 ${d.w_mm}×${d.h_mm} mm
       (${d.svg_content.length} 字元)
       <button data-idx="${i}" class="st-deco-del"
               style="background:none;border:none;color:var(--accent);cursor:pointer;">✕</button>
     </div>`
  ).join("");
  list.querySelectorAll(".st-deco-del").forEach(b =>
    b.addEventListener("click", () => {
      STAMP.decorations.splice(parseInt(b.dataset.idx), 1);
      stampRefreshDecoList();
    }));
}

// 12m-7 r31: 圓戳章內框圖 + body 動態 layout — 7 case (% of inner V):
//   全空    → image 100%
//   只 1    → text 上 33%   / image 下 33%
//   1+2     → text 上 60% (split 30+30) / image 下 40%
//   1+3     → text 上 30% + 下 30%      / image 中 40%
//   只 2    → user 選擇圖在上方 or 下方  / 50-50 split
//   2+3     → image 上 40%  / text 下 60% (split 30+30)
//   只 3    → image 上 33%  / text 下 33%
//   全 3 填 → 無 image
function stampComputeRoundInnerLayout() {
  const $ = id => document.getElementById(id);
  if (!STAMP.innerDecoSvg) return null;
  const preset = $("st-preset")?.value;
  if (preset !== "round") return null;
  const has1 = !!($("st-oval-body-1")?.value || "").trim();
  const has2 = !!($("st-oval-body-2")?.value || "").trim();
  const has3 = !!($("st-oval-body-3")?.value || "").trim();
  const w = parseFloat($("st-w")?.value) || 24;
  const h = parseFloat($("st-h")?.value) || 24;
  const padding = parseFloat($("st-pad")?.value) || 0.8;
  const cx = w / 2, cy = h / 2;
  const halfA = w / 2, halfB = h / 2;
  const dOffset = 0.30 * Math.min(halfA, halfB);
  const innerA = halfA - dOffset, innerB = halfB - dOffset;
  const innerHRatioDenom = h - 2 * padding;
  const innerV = 2 * innerB;
  const margin = 0.6;
  // 12m-7 r33: 在 inner ellipse top/bot 邊緣的 slot 自動加 SAFETY margin
  // 12m-7 r36: 改用 explicit gap allocation 策略 — slot 之間留 2-3% gap
  // region 由 case 配置直接設定，不用 fill ratio 收縮 char。FILL_RATIO 從
  // 0.85 → 0.92（char 更貼合 slot），imgMargin 1.0 → 0（image 不再收縮，
  // gap 由 case % allocation 提供）。整體效果：字體跟圖都更大、填滿內框。
  const SAFETY = 0.04;
  const FILL_RATIO = 0.92;
  const slotOverride = (rStart, rEnd) => {
    const rs = rStart < 0.01 ? SAFETY : rStart;
    const re = rEnd > 0.99 ? (1 - SAFETY) : rEnd;
    const yTop = cy - innerB + rs * innerV;
    const yBot = cy - innerB + re * innerV;
    const yCtr = (yTop + yBot) / 2;
    const maxH = (yBot - yTop) * FILL_RATIO;
    return [(yCtr - cy) / innerHRatioDenom, maxH / innerHRatioDenom];
  };
  // 12m-7 r36: imgMargin 0（gap by explicit case allocation）
  const imgMargin = 0;
  const imgBbox = (rStart, rEnd) => {
    const yTop = cy - innerB + rStart * innerV + imgMargin;
    const yBot = cy - innerB + rEnd * innerV - imgMargin;
    if (yBot <= yTop) return null;
    const imgCy = (yTop + yBot) / 2;
    const imgDy = Math.abs(imgCy - cy);
    const rByEllipse = Math.min(innerA, innerB - imgDy);
    if (rByEllipse <= 0) return null;
    const r = Math.min(rByEllipse, (yBot - yTop) / 2);
    if (r < 0.5) return null;
    return {x: cx - r, y: imgCy - r, w: r * 2, h: r * 2};
  };
  let bbox = null;
  const overrides = {};
  // 12m-7 r37: 進一步減少空白 — 全空 image 推到 0.02..0.98（最大化）；
  // 1+2/2+3 中央 2 (slot_1) 加大、中央 1/3 (slot_0/slot_2) 略小且更靠
  // border；只 2 text+image 都靠 border。
  if (!has1 && !has2 && !has3) {
    // 全空 → image 96% (0.02..0.98) 推到極限
    bbox = imgBbox(0.02, 0.98);
  } else if (has1 && !has2 && !has3) {
    // 只 1 → slot_0 30% + gap 3% + image 59%（r36 維持）
    overrides.slot_0 = slotOverride(0.04, 0.34);
    bbox = imgBbox(0.37, 0.96);
  } else if (has1 && has2 && !has3) {
    // 1+2 (r37): slot_0 27% (略小, 靠 top) + gap 2% + slot_1 33% (大, 中) +
    // gap 3% + image 29% (靠 bot)
    overrides.slot_0 = slotOverride(0.03, 0.30);
    overrides.slot_1 = slotOverride(0.32, 0.65);
    bbox = imgBbox(0.68, 0.97);
  } else if (has1 && !has2 && has3) {
    // 1+3 → slot_0 + image + slot_2（r36 維持）
    overrides.slot_0 = slotOverride(0.04, 0.30);
    overrides.slot_2 = slotOverride(0.70, 0.96);
    bbox = imgBbox(0.33, 0.67);
  } else if (!has1 && has2 && !has3) {
    // 只 2 (r37): text 跟 image 各 45-46% 推到 border（gap 3% 中間）
    const sel = $("st-round-inner-deco-only2-pos");
    const pos = (sel?.value === "up") ? "up" : "down";
    if (pos === "up") {
      bbox = imgBbox(0.03, 0.49);
      overrides.slot_1 = slotOverride(0.52, 0.97);
    } else {
      overrides.slot_1 = slotOverride(0.03, 0.48);
      bbox = imgBbox(0.51, 0.97);
    }
  } else if (!has1 && has2 && has3) {
    // 2+3 (r37): image 29% (靠 top) + gap 3% + slot_1 33% (大, 中) +
    // gap 2% + slot_2 27% (略小, 靠 bot)
    bbox = imgBbox(0.03, 0.32);
    overrides.slot_1 = slotOverride(0.35, 0.68);
    overrides.slot_2 = slotOverride(0.70, 0.97);
  } else if (!has1 && !has2 && has3) {
    // 只 3 → image 61% + gap 3% + slot_2 28%（r36 維持）
    bbox = imgBbox(0.04, 0.65);
    overrides.slot_2 = slotOverride(0.68, 0.96);
  }
  return {bbox, overrides};
}

function stampMaybeAddInnerDeco(decoArr) {
  const layout = stampComputeRoundInnerLayout();
  if (!layout || !layout.bbox) return decoArr;
  const b = layout.bbox;
  decoArr.push({
    svg_content: STAMP.innerDecoSvg,
    x_mm: b.x, y_mm: b.y, w_mm: b.w, h_mm: b.h,
    clip_circle: true,
  });
  return decoArr;
}

function stampGetBodySlotOverrides() {
  const layout = stampComputeRoundInnerLayout();
  return layout ? layout.overrides : {};
}

function stampBuildBody(format) {
  const $ = id => document.getElementById(id).value;
  const $$ = id => document.getElementById(id);
  // 3 字姓名章 auto-fill：3 字輸入 + checkbox 勾選 → 補一個字湊成 4 字。
  // 用既有 square_name preset 的 2×2 layout（台灣個人章傳統樣式）。
  // 12m-7 r24: 嚴格 gate by preset === "square_name"。其他 preset（圓戳章
  // round、橢圓章 oval、tax_invoice 等）不適用此規則。原本只 hide UI row
  // 但 JS logic 仍會 trigger（checkbox default checked），造成 user 在
  // 圓戳章輸 3 字時被加「印」，layout 跑錯。
  let text = $("st-text");
  const stPreset = $("st-preset");
  if (stPreset === "square_name"
      && text.length === 3
      && $$("st-auto-fill")?.checked) {
    const fillChar = ($("st-auto-fill-char") || "印").trim().slice(0, 1) || "印";
    text = text + fillChar;
  }
  // 12c: 陰刻 / 陽刻
  const engraveRadio = document.querySelector('input[name="st-engrave"]:checked');
  const engraveMode = engraveRadio ? engraveRadio.value : "concave";
  const linePitch = parseFloat($("st-line-pitch")) || 0.1;
  // 12h: 2 字 layout（預設左右排列右起讀；vertical 上下排列）
  const layout2Radio = document.querySelector('input[name="st-2char-layout"]:checked');
  const layout2Char = layout2Radio ? layout2Radio.value : "horizontal";
  // 12l: 公司章短列位置（multi-select checkbox）
  // 字數決定使用 3-col(7/8/10/11) or 4-col(13/14/15) checkbox group。
  // 兩組 checkbox 都讀，後端會過濾掉跟 cols 不符的 name。
  const cleanText = (text || "").replace(/\s+/g, "");
  const charCount = Array.from(cleanText).length;
  const use4Col = charCount >= 13 && charCount <= 15;
  const shortColInputName = use4Col ? "st-off-shortcol-4" : "st-off-shortcol";
  const offShortCol = Array.from(
    document.querySelectorAll(`input[name="${shortColInputName}"]:checked`)
  ).map(el => el.value);
  // 空陣列 → 後端 fallback ["right"]
  // 12e/12f: 5 字 layout（預設 2+3 姓名章；3+2 是職名章變體）
  const layout5Radio = document.querySelector('input[name="st-5char-layout"]:checked');
  const layout5Char = layout5Radio ? layout5Radio.value : "2plus3";
  // 12g: 每字位移微調（list of [dx, dy]，依目前字數 row 數）
  const charOffsets = Array.from(
    document.querySelectorAll("#st-char-offsets-body .char-offset-row")
  ).map(row => [
    parseFloat(row.querySelector(".char-dx").value) || 0,
    parseFloat(row.querySelector(".char-dy").value) || 0,
  ]);
  return {
    text: text,
    preset: $("st-preset"),
    stamp_width_mm: parseFloat($("st-w")),
    stamp_height_mm: parseFloat($("st-h")),
    char_size_mm: parseFloat($("st-charsize")),
    style: $("st-style"),
    source: $("st-source"),
    show_border: $$("st-show-border").checked,
    double_border: $$("st-double-border").checked,
    border_padding_mm: parseFloat($("st-pad")),
    laser_power: parseInt($("st-power")),
    feed: parseFloat($("st-feed")),
    decorations: stampMaybeAddInnerDeco(STAMP.decorations.slice()),
    // 12m-7 r31: 圓戳章內框圖搭配 body 文字時，動態 slot 位置/高度 overrides
    body_slot_overrides: stampGetBodySlotOverrides(),
    format,
    engrave_mode: engraveMode,
    line_pitch_mm: linePitch,
    layout_5char: layout5Char,
    layout_2char: layout2Char,
    layout_official_short_col: offShortCol,
    char_offsets: charOffsets,
    // 12m-1: 橢圓章結構化欄位 — 後端只在 preset=oval 時用，其他 preset 忽略
    oval_arc_top: ($("st-oval-arc-top") || "").trim(),
    oval_arc_bottom: ($("st-oval-arc-bottom") || "").trim(),
    // 12m-1 patch r11: 不 filter empty — slot-based positioning，
    // empty index 對應該 slot 不渲染（保留 positional semantic）。
    oval_body_lines: [
      ($("st-oval-body-1") || "").trim(),
      ($("st-oval-body-2") || "").trim(),
      ($("st-oval-body-3") || "").trim(),
    ],
    // 12m-1 patch r12: 中央 1/2/3 加粗 flags（中央 3 不可加粗，固定 false）
    oval_body_bold: [
      $$("st-oval-body-1-bold")?.checked || false,
      $$("st-oval-body-2-bold")?.checked || false,
      false,
    ],
    // 12m-1 patch r13: 裝飾符號（plum / star / circle / none）
    oval_decoration: $("st-oval-decoration") || "plum",
    // 12m-1 patch r18: 鋸齒外框
    oval_sawtooth: $$("st-oval-sawtooth")?.checked || false,
    // 12m-7: tax_invoice 上方標題 + 縣市 + 縣市位置
    oval_top_title: ($("st-oval-top-title") || "").trim(),
    oval_location: ($("st-oval-location") || "").trim(),
    oval_location_position: (
      $$("st-oval-location-pos-left")?.checked ? "left" : "bottom"
    ),
    // 12m-7 r26: 圓戳章單圓周模式
    round_continuous_arc: $$("st-round-continuous-arc")?.checked || false,
    // 12m-7 r39: 職名章 (rectangle_title) 2-column 結構化欄位
    rect_left_line1: ($("st-rect-left-line1") || "").trim(),
    rect_left_line2: ($("st-rect-left-line2") || "").trim(),
    rect_right: ($("st-rect-right") || "").trim(),
    rect_left_2rows: $$("st-rect-left-2rows")?.checked || false,
  };
}

async function stampRender() {
  const status = document.getElementById("st-status");
  const preview = document.getElementById("st-preview");
  status.textContent = "產生中…";
  try {
    const r = await fetch(`${API_BASE}/api/stamp`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(stampBuildBody("svg")),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: r.statusText}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    preview.innerHTML = await r.text();
    const inner = preview.querySelector("svg");
    if (inner) {
      // 5ba-2: 印章 25×25mm 在 96dpi 只有 ~94px；不撐滿就看不到。
      inner.removeAttribute("width");
      inner.removeAttribute("height");
      inner.style.width = "100%";
      inner.style.maxWidth = "400px";
      inner.style.maxHeight = "400px";
      inner.style.height = "auto";
      inner.style.display = "block";
      inner.style.margin = "0 auto";
      inner.style.background = "white";
      // 12c: 陽刻 SVG 已自帶紅底白字（傳統朱印色），不套 tint。
      // 陰刻維持原本灰色 fill 預覽（5ba-5）。
      const engraveR = document.querySelector('input[name="st-engrave"]:checked');
      const isConvex = engraveR && engraveR.value === "convex";
      if (!isConvex) {
        tintPreviewFill(inner);
      }
    }
    status.textContent = "✓ 完成";
    status.style.color = "#080";
  } catch (e) {
    status.textContent = "失敗：" + e.message;
    status.style.color = "var(--accent)";
  }
}

async function stampDownload(format) {
  const status = document.getElementById("st-status");
  status.textContent = "下載中…";
  try {
    const r = await fetch(`${API_BASE}/api/stamp`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(stampBuildBody(format)),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    // 12b-4: format → file extension（svg/pdf/gcode 三選一）
    const ext = format === "svg" ? "svg"
              : format === "pdf" ? "pdf"
              : format === "dxf" ? "dxf"
              : "gcode";
    a.download = `stamp.${ext}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    status.textContent = `✓ 已下載 stamp.${ext}`;
    status.style.color = "#080";
  } catch (e) {
    status.textContent = "下載失敗：" + e.message;
    status.style.color = "var(--accent)";
  }
}

