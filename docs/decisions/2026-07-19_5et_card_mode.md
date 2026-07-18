# 決策紀錄 2026-07-19（5et）：手寫卡片模式弧——五輪 QODA 重放

對應 PRINCIPLES §37–§40（並再應驗 §33/§34）。commits：`545617b`
（R1+R2，0.14.224）→ `ba6f4c1`（R3，0.14.225）→ `d2a4502`（R3b，
0.14.226）→ `c18efef`（R4，0.14.227）。

---

## 整體脈絡

使用者需求：新增手寫卡片模式——名片/對折卡尺寸、框選區域加文字、文字可
換成自寫手寫字或本機字型、顏文字、手繪圖案/SVG 插入、大框包小框。參考
研究（賀卡尺寸慣例、對折卡「面」結構、出血 3–6mm）＋repo 資產盤點後
發現**約七成是組裝既有積木**：handwriting 頁的 IndexedDB 筆跡、5cn
opentype.js、塗鴉引擎、禪繞框選互動、SVG mm 契約、cairosvg PDF 管線。

---

## 決策 1（R1）：獨立頁 /card＋ES modules；SVG DOM 編輯器單一渲染路徑

| 議題 | 選項 | 定案 |
|---|---|---|
| 位置 | A ★ 獨立頁 ES modules（照 handwriting/ 範本）／B 塞 index.html 巨石 | A——健檢 W4 方向，巨石不再+1,500 行 |
| 技術 | A ★ SVG DOM（mm 座標、輸出零轉換）／B Canvas（要再向量化） | A |
| 對折尺寸 | 使用者定案：公制 A6 為基準＋自訂尺規調整（10×7 吋≠A6，兩制不混） | A5 tent fold→A6 橫式面 |

**架構鐵則（§40）**：render.js 全部輸出「SVG 字串」——編輯器 innerHTML
掛載、SVG 下載、印刷版組裝、PDF 轉檔**全走同一條字串渲染路徑**，畫面所見
即匯出，杜絕編輯/匯出雙軌漂移。純函式層（geometry/model/render/glyphs
判定）零 DOM → node --test 直測；互動與 DOM 走訪由 Playwright E2E 驗。

## 決策 2（R2）：glyph provider 三源——同步查快取、async 補、系統字型墊底

handwriting＝直讀 IndexedDB `stroke-order-practice/traces`（EM 2048
polylines、char index 取最新 ts）；userfont＝opentype.js 經 /vendor
同源代理（5cn 慣例：ascender baseY＋advance 置中）；style＝
/api/handwriting/reference（5d-7 既有端點）。

**⚠ 欄位契約事故**：IR outline 的 Q/C 指令是 `{begin:{x,y}, mid, end}`
**巢狀欄位**、非 x1/y1 扁平——首版誤用，單元測試全綠（測試也照錯誤假設
寫），Playwright 真實渲染抓到 NaN 進 path d。§33「mock 驗邏輯、真實渲染
驗接線」第三度應驗；修正＋NaN 回歸鎖；前端解讀 outline 一律參照
handwriting/reference.js `_buildPath2D`。

## 決策 3（R3）：三種插入內容的邊界設計

- 顏文字**不走逐字方格**（會拆成方塊）→ 獨立 kind 單行置中＋textLength
  擠壓；庫收純字元不收 color emoji（列印/寫字機管線吃不到彩色字型）。
- 塗鴉走**伺服器引擎**（5cp 已定為預設、校網免疫），瀏覽器引擎留接點。
- SVG 匯入立**信任邊界（§39）**：`sanitizeSvgText` 是 art fragment 唯一
  合法來源——元素 allowlist（排除 script/foreignObject/image/use/
  animate/filter）＋屬性過濾（on*/href/xlink:href/style 含 url() 拒）＋
  300KB 上限。E2E 以惡意樣本驗五威脅全剝除。**若未來加版面 JSON 匯入，
  載入時必須重跑 sanitize。**

## 決策 4（R3b）：版面自由度——每面翻轉從「寫死慣例」降為「可設定的預設」

使用者回饋輪（直式名片／左右對折／翻轉自主／任意區域插入）。左右對折
QODA 定案**書式**（封面右、封底左、單面列印皆正放）。關鍵重構：preset
`placement.rotate180` 降為**預設值**、實際以 `card.faceRotate` 為準
（round-trip 保留覆寫）——慣例給預設、控制權還使用者。框選插入＝
marqueeRect 純函式＋pendingInsert 兩段式（點一下＝預設大小、Esc 取消）。

## 決策 5（R4）：大框包小框＝每框外框樣式（視覺疊層，非結構群組）

| 選項 | 說明 | 取捨 |
|---|---|---|
| A ★ | 任何框可設裝飾外框（五樣式＋內距），巢狀＝疊放 | 簡單、組合性強、可無限層；內外框拖曳不連動 |
| B | 結構性「框組」型別（外框＋內容槽綁定） | 體驗好但選取/序列化/拖曳全要重做，本輪風險大 |

採 A；B 留作未來需求。內容排進 `contentRect` 內縮矩形（橢圓×0.72 內接
係數防四角出框）。

**兩個實作教訓**：
1. **§37**：`padMm=0` 是合法值——`Number(x) || 預設` 會把 0（falsy）誤換
   成預設，改 `Number.isFinite` 判定；補「0 不可被預設蓋掉」測試。
2. **§38**：`from __future__ import annotations` 之下 FastAPI request
   model **必須定義在模組層**——create_app 內的區域類別型別註記解析不到、
   參數被誤判成 query（全 repo 既有 15 個 model 都在模組層即此因）。

PDF 走伺服器 cairosvg（與抄經 PDF 同管線）：前端 renderPrintSvg 組出血
3mm＋四角 8 段裁切標記，端點 `_CARD_PDF_DENY` 拒 href/url()/script/
image/use（防 SSRF）＋2MB 上限——與前端 sanitize 構成**縱深防禦兩道**。
PNG 走瀏覽器 canvas（8px/mm≈203dpi）零新相依。

---

## 驗收與後續

- 每輪均：沙箱全量 pytest＋node 全綠 → Playwright E2E（種 IndexedDB／
  setInputFiles 餵字型與惡意 SVG／waitForEvent('download') 驗匯出位元組）
  → 寫回 md5 驗證 → 收工檢查.bat → 雙 remote。
- R1~R3b 線上驗收 PASS；R4 部署驗收排程中。
- backlog：文字框預設高一行、顏文字選盤非 modal、PDF 系統字型伺服器端
  替代提示、結構性框組（若使用者要連動拖曳）。
