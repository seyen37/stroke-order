# 決策紀錄：covert clobber 善後＋5fo → 全站 UX 稽核 → 5fp~5fu（2026-07-23，QODA 重放）

對應 PRINCIPLES §69–§74。版本 0.14.264 → 0.14.270；tests 1855 → 1870。
工作日誌：`WORK_LOG_2026-07-23.md` 第二場；稽核報告：`UX_AUDIT_2026-07-23.md`。

---

## D1. 跨會話 covert clobber 善後：修復策略選「前進修復」不選「回滾」

**Question**：舊沙箱寫回把裝置 repo 版本退回（0.14.263→0.14.255）、刪掉
`scipy>=1.10`、且 commit `a1dcf3c` 訊息張冠李戴（撿到已消費的 licenses 訊息檔），
而且已 push origin。怎麼善後？

**Options**：
- A. `git revert`／force-push 回滾 a1dcf3c —— 歷史乾淨，但 force-push 動遠端
  歷史（backup remote 也要同步動）、且 a1dcf3c 裡混有**正確的 gallery 修正**，
  整筆回滾會把好東西也退掉。
- B. ★ **前進修復**：新 commit 把版本推到 0.14.264（高於一切殘影）、scipy 逐位元
  復原、訊息檔 `_53` 內文補述 a1dcf3c 的真實內容——歷史留疤但可讀，不動遠端歷史。

**Decision**：B。公開 repo 不 force-push 是既有紀律；「訊息錯的 commit」用下一筆
的訊息補述即可追溯。版本號選 0.14.264 而非退回 0.14.263 再 bump，確保任何快取／
部署比對都單調遞增。

**執行**：`6d487b5`；backup remote 落後一併補推。教訓固化為「開工三步對表」
（→ §69）：① sandbox `git fetch origin` 對 log ② device 端 `grep version
pyproject.toml`＋`ls docs/_commit_msg | tail` 對現值 ③ phase 代號 grep 近期
log 防撞名（本輪即因此把 5fm 改名 5fo）。

---

## D2. /gallery 手刻版本標籤：修一頁 vs 掃全類

**Question**：/gallery 版本標籤手刻 `v0.13.0`（§57 注入紀律的漏網頁）。只修這頁？

**Options**：
- A. 只把 /gallery 改成注入——最小 diff，但 §57 當時就是「以為修完了」才漏掉
  這頁；下次再新增獨立頁還會再犯。
- B. ★ 修這頁＋**回歸鎖掃全類**：`test_no_hardcoded_version_labels_on_disk`
  掃全部 HTML 的 `>vX.Y.Z<` 字面，未來任何頁手刻版本直接紅燈。

**Decision**：B。同類病（手刻、複本、漏 guard）的修法從來不是「再修一處」，
而是「掃出全類＋機器鎖」（→ §70，承 §59 兄弟實作）。同款案例同輪重演：
`[hidden]` guard 在 handwriting.css、index.css 修過兩次後，5fr 又在 gallery.css
第三現——結論一樣：**每個獨立 CSS 檔都要自帶 guard**，不能假設「修過了」。

---

## D3. UX 稽核工作法：稽核與施工分離、分級 sign-off、環境限制先聲明

**Question**：使用者要「初次使用者觀點全站體驗＋測試報告＋整體改善建議」。
直接邊測邊修？還是先出報告？

**Options**：
- A. 邊稽核邊修——快，但發現與決策混在一起，使用者失去取捨權；且稽核中的
  誤讀（見 D5）會直接變成錯誤施工。
- B. ★ **僅稽核不動程式**：13 模式＋3 頁全實走（Playwright「進入→輸入→產生→
  檢視」）、35 張截圖佐證、分級 P0（互動缺陷）／P1（一致性）／P2（打磨），
  報告言明「未經 sign-off 前不會實作」，等使用者逐級放行。

**Decision**：B。實際流程：使用者「先做 P0 一輪」→「P1」→「P2」→「共用控制列
固定位」（P2 遺留專門輪），一輪一 commit 一部署驗收——稽核發現≠工單（→ §71）。

**環境限制聲明**：沙箱缺教育部字型、hanzi-writer CDN 不可達——受影響觀察逐條
標註〔環境〕，「缺字型時的錯誤呈現方式」仍是有效體驗觀察，但「載入失敗」本身
不判 bug。沒有這層標註，稽核報告會把環境問題誤報成產品回歸。

---

## D4. 5fq 色彩語意：藍＝主要動作的基準從哪來

**Question**：全站「主要動作」色不一（紅／藍混用），統一成哪個？

**Options**：
- A. 以主頁現行紅（--accent）為準——改動最少，但紅與「破壞性」的通用直覺相衝
  （稽核實據：逐字手寫「送出並關閉」紅色被誤讀為危險鈕）。
- B. ★ 以 /handwriting 的藍（--hw-accent `#2c5cb8`）為準，新增 `--primary`；
  紅（--accent/--danger）收斂為破壞性專用。

**Decision**：B。「藍＝行動、紅＝破壞」符合平台慣例；/handwriting 是使用頻率
最高的獨立頁，向它對齊遷移成本最低。同輪配套：動詞統一「產生◯◯」、空狀態句
全站化 `.preview-empty`、破壞性按鈕隔離列——四件都是「同一心智模型」的不同面。

---

## D5. 稽核發現在施工輪要現場再驗證：「↻ 全部歸零」案例

**Question**：稽核報告建議印章「↻ 全部歸零」加二次確認（比照清空慣例）。照做？

**Decision**：**不照做**——施工時實測發現它只歸零「位移微調」，不是清空資料，
是可隨手按的低風險操作；加確認反而礙事。正確修法是**正名**「↻ 位移全部歸零」
消除誤會。原則：稽核是遠觀，施工輪要現場再驗證每條建議，稽核誤讀要訂正而非
照單全收（→ §71）。同型案例：「單字模式三空區」實測部分容器已有舊短句，
建議從「補空狀態」修正為「統一句式」。

---

## D6. 5fs 卡片「逐字手寫」：新開介面 vs 重用深連結參數路

**Question**：手寫卡片文字框要加「逐字手寫」。在 /card 內嵌手寫視窗？還是跳轉？

**Options**：
- A. /card 內嵌 sw-overlay——體驗不跳頁，但要把整套手寫視窗（儲存層、筆跡
  資料庫、字框渲染）搬進卡片頁，重複實作一份。
- B. ★ 重用 5fd 深連結：`/handwriting?char=<文字框字串>&from=card`——參數路
  本來就吃多字字串；只加一顆鈕＋`_fromLabels.card`＋返回鈕分流 `/card`。

**Decision**：B。零新 API、零新頁面、手寫資料天然進同一個資料庫。這是「參數路
用寬鬆型別（字串而非單字）」在設計當下多花五分鐘、日後重複回本的複利案例
（→ §74，承 §26）。

---

## D7. 5ft 分享庫新分類：改 API vs registry 派遣

**Question**：分享庫要加「立體字」分類。上傳／列表／下載 API 要不要動？

**Options**：
- A. API 加 popup 專用分支（if kind == "popup"…）——直觀，但每加一類都要再開
  一刀，驗證邏輯散在 route 層。
- B. ★ **registry 派遣**：`ALLOWED_KINDS` 加 `KIND_POPUP`、
  `VALIDATORS["popup"]`／`SUMMARIZERS["popup"]` 註冊各自的純函式——route 層
  一行不動（僅 ext_map 補 `.svg`）。

**Decision**：B。5b r28 立的 registry 在此第一次驗證「新增分類零 API 改動」
成立（→ §74）。驗證憑據設計：popup SVG 產出時**內嵌**
`<metadata><popup-config><![CDATA[{json}]]></popup-config></metadata>`
（schema `stroke-order-popup-v1`）——檔案自帶憑據，上傳端認 metadata 而非
猜測檔案內容；uploader 前端同一 schema 字串分流。測試 monkeypatch
`generate_popup` 免字型，round-trip（產出→validator）驗收。

---

## D8. 5fu 共用控制列統一：統一到什麼程度

**Question**：使用者 sign-off「共用控制列固定位」。三共用控制項（字型風格／
罕用字／資料源）在 13 模式散布不一——統一到「絕對同位」嗎？

**Options**：
- A. 全模式搬到同一絕對位置（表單第一列固定三件）——最「一致」，但破壞各表單
  的語意分組（就近原則），且 grid/notebook/letter/manuscript 等多數模式三件
  本已相鄰、順序正確，硬搬是為統一而統一。
- B. ★ **三層次**：同名（「資料源」「字型風格」全站同物同名）→ 同序（字型風格→
  罕用字→資料源）→ 相鄰聚攏（只搬散落的 wordart／mandala）；不動絕對位置。

**Decision**：B。跨模式一致的心智模型由「同名＋同序＋相鄰」即可達成；絕對同位
的邊際收益低於語意分組的損失（→ §73）。執行紀律：**統一前先全模式盤點現況**，
以多數派為準只搬少數；id 全保留、JS 零改動；E2E 除幾何（同列 top 差 <8px、
左→右順序、各 id 恰一次防搬移殘留）外，**動過的模式改值後實測產生成功**——
搬 DOM 的輪必驗功能面。

---

## 附：本弧 E2E 方法學三則（→ §72）

1. 閉合 `<details>` 內元素 `getBoundingClientRect` 仍回幾何（Chromium
   content-visibility）——判可見用 `el.checkVisibility()`。
2. 佈局順序斷言別用「字串首現位置」（「基本符號」等字樣多處出現會誤中）——
   用元素 id 錨定。
3. 訊息會換行——「同一行」幾何斷言改「錨點下方 N px 帶內」。

## 附：流程事故兩則（→ §69 姊妹律）

1. 沙箱有未推 commit（5fs `c6ce453`）時誤跑 `git reset --hard origin/main`
   洗掉，reflog 撈回。鐵則：reset 前先 `git log origin/main..HEAD`。
2. 5fs＋5ft 兩輪堆疊未收工，收工檢查.bat 一筆 commit 吃兩輪、訊息只寫 5ft
   ——多輪堆疊時訊息檔要寫**累積式**（bat 依名稱取最新一檔）。
