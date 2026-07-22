# 決策紀錄 2026-07-22（5et-R5）：手寫卡片模式加尺規＋卡緣摺邊虛線；子模組 import 快取缺口根治

對應 PRINCIPLES §67（ES 子模組相對 import 也要帶 ?v= 快取鍵）。承 5et（手寫卡片模式
R1~R4）、§27（單一事實源）、§57（版本注入不手刻）。commit：`9362d80`（功能, 0.14.261）／
`6dc8d9f`（快取回歸修復, 0.14.262）。

---

## 整體脈絡

使用者請求卡片編輯器（/card）兩件事：加尺規以量測上下左右範圍距離；卡緣設為直線、
對折卡中間的摺線改虛線並隨面籤切換上下/左右位置。功能如期實作、沙箱 Playwright 四對折
面實測通過、上線 0.14.261——但線上出現白畫回歸：卡型下拉空、卡面空白。根因不在功能
本身，而在卡片子系統的 ES module 內部 import 沒帶版本查詢，撞上瀏覽器快取。

---

## 決策 1：尺規＝邊尺刻度＋選取框距四邊讀數（兩者都做、預設關）

**觸發**：「加尺規量測上下左右範圍距離」有多種解讀（邊尺刻度／選取框距讀數）。

**選項**：A 邊尺刻度（上/左緣 mm 尺）／B 選取框四邊距離讀數／C 兩者。

**選擇**：☑ C（AskUserQuestion 使用者選「兩者都做」、預設關可勾選）。

**理由**：邊尺提供隨處可讀的絕對刻度、讀數提供選取框對四邊的相對距離，兩者互補才是完整
「量測」。預設關避免畫面雜訊（比照安全邊界為工具型開關）。

**後續驗證**：✅ Playwright 名片卡插入文字框後讀數 上15.9/下21.1/左18.0/右18.0 mm。

---

## 決策 2：摺邊由「展開版佈局」推導，不吃 rotate180

**觸發**：對折卡要把摺邊畫成虛線、隨面籤切換位置。

**根因/取捨**：面在展開版（sheet.placement）的哪半邊、摺線（fold.at）就落在它貼著中線的
那一邊。`rotate180` 只是 tent-fold 列印慣例，與「編輯面上摺邊指示」無關——若吃 rotate180
會讓封面/內頁摺邊都算到同一邊，違反使用者「切換上下位置」的直覺。

**選擇**：☑ 依 placement＋fold 幾何推導（faceFoldEdge），忽略 rotate180。

**理由**：符合使用者心智模型（展開版：封面上半→摺邊在下、內頁下半→摺邊在上；左右對折
封面右半→左、封底左半→右）。四種面 Playwright 實測位置全對。

**後續驗證**：✅ 上下對折下/上、左右對折左/右皆正確；非對折卡四邊實線。

---

## 決策 3：白畫回歸——子模組 import 快取缺口，根治整類而非只補 card（§67）

**觸發**：0.14.261 上線，/card 卡型下拉空、卡面白（新 card.html 的「尺規」核取方塊有出現
＝HTML 已更新、是 JS 初始化中斷）。沙箱全新瀏覽器的 Playwright 測不出。

**根因**：card 子系統 ES module 內部 import 用相對路徑但**沒帶 `?v=__V__`**
（`import './geometry.js'`）。`/static` 未帶 `?v=` 只快取 1 小時；本輪在 geometry.js 新增
`export faceFoldEdge`，瀏覽器仍載 1 小時內快取的舊 geometry.js（無此 export）→ 新 main.js
的 named import link 失敗 → 整頁初始化中斷。入口 `card.html` 以 `?v=__V__` 載 main.js
（每次破快取），但**子 import 沒有＝「半破快取」**；modes/* 子系統早有 `?v=__V__`，
card/handwriting/gallery 三個漏了。

**選項**：

| 編號 | 方案 | 優點 | 缺點 |
|---|---|---|---|
| A | 只補 card 的 import | scope 最小 | handwriting/gallery 同缺口未除，下次改它們的 export 再中招 |
| B | 全 static 子系統相對 import 補 ?v=__V__ ＋掃全 static 守門測試 | 根治整類、機器防回潮 | 動 12 處、跨三子系統 |

**選擇**：☑ B

**理由**：根因是「子模組 import 缺版本快取鍵」這一類，不是 card 單點。只補 card 等於留三顆
同型地雷（handwriting/gallery）。B 一次補齊 12 處＋守門測試（掃全 static，任何相對 .js
import 缺 ?v=__V__ 即紅燈），把「半破快取」這類 bug 從「回訪使用者才中、CI 測不出」變成
「靜態守門擋下」。

**後續驗證**：✅ node card 41 綠；TestClient 確認 main.js import 已改寫成 ?v=0.14.x；全
static 52 個相對 import 全數版本化（0 缺）；Playwright 全新瀏覽器 /card 正常。使用者當下
Ctrl+F5 解 0.14.261，0.14.262 部署後所有人自動修復。

---

## 沒做的決策（明確擱置）

- **尺規讀數常駐/更密刻度**：先做「選取才顯示讀數、每 5/10mm 刻度」；若使用者要常駐或更密
  再調，不預先過度設計。
- **匯出（本面 SVG/PDF）也畫卡緣/尺規**：卡緣與尺規僅 edit 模式畫，export 維持純內容——
  雷雕/寫字機工作流不能混入編輯輔助線。

---

## 學到的規則（→ PRINCIPLES §67）

**版本破快取的紀律要覆蓋「整條 import 圖」，不是只有 HTML 引的第一層**：所有 static ES
module 的相對 .js import 一律帶 `?v=__V__`（讓 versioning 中介層改寫成版號、與入口同步破
快取），配掃全 static 的守門測試。附帶（驗收盲點）：這類「半破快取」bug 全新瀏覽器/CI 測
不出（無舊快取），只中「1 小時內回訪」的使用者——別以為「Playwright 測過就沒事」；要嘛靠
靜態守門，要嘛實機帶快取回訪重現。

---

## 相關檔案

- 功能：`src/stroke_order/web/static/card/geometry.js`（faceFoldEdge）、`card/render.js`
  （boundaryMarkup/rulerMarkup）、`card/main.js`（接線）、`card.html`（尺規核取方塊）
- 快取修復：`card/main.js`、`card/model.js`、`card/render.js`、`handwriting/exporter.js`、
  `gallery/gallery.js`（相對 import 補 ?v=__V__）
- 測試：`tests/test_card_editor.mjs`（+4 R5）、`tests/test_web_layering.py`
  （`test_static_js_relative_imports_carry_version_query` 守門）
- 工作紀錄：`docs/WORK_LOG_2026-07-22.md`（5et-R5 節）
- 原則：`docs/PRINCIPLES.md` §67
