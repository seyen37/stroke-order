# 決策紀錄 2026-07-13：注音 v2 全線（5cv→5cz）＋ OpenCV 懸案破案（5da）

對應 PRINCIPLES §11。版本 0.14.161 → 0.14.167，tests 1647 → 1659。

---

## D1. 注音資料源：QODA 選 C「治本」（5cw）

**問題**：pinyin-pro 是大陸讀音體系，字帖注音欄會印出與教育部
審定音不符的注音（垃圾→ㄌㄚㄐㄧ）。

**選項**：
- A. 衝突字覆寫表（30~60 常用字，逐字驗證）——80/20，快
- B. 完整審定表資料檔（8000+ 字）進前端——工程大、條件音無解
- C. 換台灣體系資料源（McBopomofo 資料）——治本、要重寫轉換層

**決定**：AI 推薦 A，**使用者選 C**。事後看 C 全面優於預期：
McBopomofo 的 BPMFBase（21,786 字）＋heterophony 優先序一次
解掉「台灣音」與「破音字預設讀音」兩個問題，而且值直接是注音
——命中字連拼音轉換層都不用走，pinyin-pro 反而降級成缺字
fallback。5cx 破音字下拉 UI 的資料（次音欄位）也是 C 案免費
附送的。

**教訓**：80/20 推薦是基於「治本成本高」的假設；當治本方案
存在高品質開源資料源時，成本假設要重新估。使用者的直覺
（換資料源）贏過 AI 的漸進主義。

## D2. 衍生檔入 repo、格式為「排序＋逐行」（5cw）

執行期/部署期零外網（5cq vendor 燒入哲學延伸到資料檔）；排序
逐行讓 diff 穩定、且截斷立即可偵測（沙箱掛載事故的防禦性設計
——搭配測試的全庫規模門檻）。再生腳本入 repo、手動執行，
fetch 失敗 graceful 保留舊檔。

## D3. 幾何收集器＋多發射器：`_zhuyin_layout`（5cy）

注音欄幾何原本只活在 `_zhuyin_strip`（SVG 字串生成）內。G-code
要用同一套幾何時有兩條路：複製數學、或抽收集器。選抽——
理由是 5cv 剛發生過「調號位置修正」：若兩端各持一份數學，這類
修正必然漂移。收集器回傳純資料（placements/tone_tracks/
tone_dot），SVG 與 G-code 各自發射。5cz 的 page 型 strip 成為
第三個消費者，零改動接上。

同輪教訓：placements 一開始只帶 Character 物件，測試 stand-in
曝露「G-code 註解標了錯的符號名」——收集器的輸出要**自帶語意
標籤**（原符號字），不能倚賴消費端從物件反推。

## D4. page 型注音欄＝「加寬格寬」而非「改版面引擎」（5cz）

notebook/letter 的 flow/分頁/容量全繫在 `char_width_mm` 一個
參數上。把 pair（2:1）映射成 `char_width = 1.5 × line_height`，
layouts.py 零改動、所有下游計算自動正確；渲染端把字形壓回左側
方格、右掛 strip。對照組是「教 flow 引擎認識 pair cell」——
侵入五個函式、直向橫向兩套。**當版面引擎的抽象剛好有一個總開
關參數時，寧可在參數上做文章，不要教引擎新概念。**

## D5. OpenCV 懸案結案：版本不相容，不是環境層（5da）

**背景**：5cb 起 OpenCV 引擎「產生中…」懸掛，經五層根因
（死 CDN→校網丟包→docs 403→event loop 凍結→「受管理電腦
環境層」），最終 5cp/5cr 以 UX 保底收場，「環境層」為當時
結論。

**本輪對照實驗鏈**（Chrome MCP，家用機）：
1. jsDelivr 暢通＝非校網
2. 前景分頁（排除背景節流）仍卡 WASM init
3. blob 對照組：importScripts 342ms 完成、`await cv` 永不
   resolve——卡點精準到 WASM runtime init
4. 微型 WASM 秒過＝非 WASM 封鎖
5. A/B：4.9.0-release.3 卡死、4.11.0-release.1 同機 759ms 就緒

**結論**：@techstark/opencv-js 4.9.0 build 與新版 Chrome
（149）不相容。舊「環境層」判定極可能一直就是這個——當時的
blob「成功」樣本未驗到 cv ready 這一層。

**修法決策**：
- pin 升 4.11、版本常數單一事實源
- **快取檔名帶版本**：無版本檔名（opencv.js）會讓 pin 升級後
  舊快取永遠命中——Render 燒入檔與本機快取都中。檔名即版本
  ＝升級自動失效，舊檔閒置無害
- docs.opencv.org 整個退出清單：4.11 實測 404（只掛 4.9/
  4.13）、對資料中心 403、校網靜默丟包——三種環境三種死法的
  源不配當備援；同源＋jsDelivr＋unpkg 已足

**留白**：校網機複測待下次到校——若 4.11 在校網機也通，
「環境層」假說正式退役，5cp 的「實驗性」標籤可評估拿掉。

## D6. 流程面：badge 疏漏與沙箱重套紀律

- README **version badge 連兩輪漏更新**（5cy/5cz 只改 tests
  badge）——收工檢查的 badge 核對是「兩顆都對」，不是「有改
  就好」。bat 提醒詞已涵蓋，人（AI）的 checklist 也要涵蓋
- 沙箱 verify 樹重套兩次踩 anchor 雷：短 anchor 首現非目標
  （capacity 端點誤植）、行尾註解漏抄致 count=0。規則：重套
  anchor 一律含「呼叫頭部或函式簽名」等長上下文，且 rep()
  的 count 斷言（非靜默替換）是抓誤植的最後防線——兩次都是
  它抓下來的
