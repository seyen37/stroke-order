# ADR — P2 `/myfont`「寫你的名字→得到字型」三步驟頁

- 日期：2026-10-19
- 版本：0.14.298 → **0.14.299**
- 狀態：已實作（個人化線 QODA A 三輪收官）
- 相關：P0 `2026-10-19_p0_user_dict_readonly.md`、P1 `2026-10-19_p1_handfont_post.md`、
  Blueprint §8 Phase 2 第 7 項、DESIGN.md（按鈕四階／動詞規範）、§67（ES module ?v=）

## 決策

1. **流程三步＋選做一步**：①輸入名字（最多 6 個不同的字；去重、去空白、
   surrogate pair 正確）②逐字寫（米字格＋淡灰範字可關、復原一筆、清除、
   上一字回看＝新增 `WritingCanvas.loadStrokes`、空白不給過）③產生字型
   （粗細三檔、著作權具名可關）→ 頁內以 FontFace 即時預覽＋可打字試＋
   ↓ 下載 TTF（成功前 disabled）＋三平台安裝說明 ④再多寫幾個字（總數
   ≤100，與伺服器上限 parity 鎖）。
2. **資料只在瀏覽器**：每寫好一字存進練習紀錄（IndexedDB，與筆順練習頁
   同一個 store，tags=`myfont`）；開頁換名字時自動帶入之前寫過的字（最新
   一筆，可重寫）。只呼叫 `POST /api/handfont`，**不碰** `/api/user-dict`
   （測試鎖）。
3. **送出前點距精簡**（6 EM 單位，約字寬 0.3%）：指標取樣每筆數百點，100 字
   原始點數會超過伺服器 20 萬點上限；精簡只作用於請求，練習紀錄保留原始取樣。
4. **純邏輯抽 `static/myfont/core.mjs`**（node 直測），頁面只接線；匯入鏈全帶
   `?v=__V__`。
5. **誠實措辭**：「伺服器不保存」「只有你寫過的字」「沒寫過的字會由電腦改用
   內建字型顯示（這是字型的正常行為）」「換裝置不會跟著走」「iPad／手機需另外
   的 App」——皆鎖成測試。`/guide` 第 4 節舊說法（「手寫練習寫過的字一鍵打包」，
   P0 後公開站不成立）改為導向 `/myfont`。
6. **計數**：頁面瀏覽記 `myfont_page`；產生字型記既有 `handfont`（gate）。

## 驗證

- `tests/test_myfont_page.py` 10 項＋`tests/test_myfont_core.mjs` 8 項。
- Playwright 端到端（公開站設定 WRITABLE=false）：名字「王 小王」→ 拆成 王、小
  （去重）→ 滑鼠實寫兩字 → 空白攔截「還沒寫，先寫一筆」→ 產生字型 ✓ 2 字、
  FontFace loaded、下載檔頭 `00 01 00 00`、檔名 `王小王_手寫字型.ttf` → 回上一字
  筆畫重現 → IndexedDB 兩筆 tags=myfont → 重新整理換名「小明」自動帶入「小✓」；
  無 pageerror；伺服器端字庫目錄未建立；計數 myfont_page/handfont 正確。
- 桌機與 375px 手機截圖目視；手機首版書寫格超出卡片內距（86vw 未扣 padding）
  → 改 `min(100%, 360px)` 後落在卡片內、無橫向捲動。修掉一個小瑕疵：名字中的
  空白原會進著作權欄。
