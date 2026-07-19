# 5ew 手寫整合弧：五輪 QODA 重放（點字手寫全站擴散）

- **日期**：2026-07-19（第三階段）
- **版本**：0.14.234 → 0.14.239（44a09a1 → eea1f6a，五筆主 commit）
- **對應原則**：§46–§49
- **狀態**：全輪上線驗收 PASS（含 handwrite.js ?v 注入後 md5 逐位元等價）

## 背景

使用者五項需求：卡片入口移位、筆順練習（進階版）×抄經逐字手寫
（簡潔版）整合互切＋資料整合、預載省 render、預覽分段載入＋進度條、
「點字→手寫視窗＋手寫字匯入」擴散到全部文字/藝術模式。拆五輪，
每輪 QODA。

## R2：預覽分段載入——「空白格先出＋分批填字」vs 其他

**Options**：A 骨架屏（假格線佔位）；B SSE/串流；★C 空白格先出＋
分批填字（glyph_chars 參數）。

**定案 C 的理由**：A 的骨架與真版面有落差（句讀/格式樣要真算）；
B 引入新傳輸模型、快取層（5eu 只蓋 GET）與重試語意全要重做；C 重用
既有 POST 端點，後端只加一個 Optional 參數，且「空白版」不是假畫面
——格線/句讀/cellmap 全真，逐字手寫立刻可點。

**關鍵語意設計**：glyph_chars 三態——None＝完整（下載/PDF 零變更）；
""＝零載入純版面；字集＝loader 包「集合外→None」。第三態刻意重用
「loader 回 None＝缺字跳過」的既有語意，渲染器零新分支；data-missing
由前端隨批修正。

**等價性驗證**（非近似宣稱）：分段合併後每個具名圖層 children 數
＝一次性渲染（258=258）、缺字數相等（2=2），真 DOM 解析比對。

## R3：資料整合——擴充 storage.js vs 新共用模組

**Options**：★A 擴充 handwriting/storage.js 為共用層（兩介面同一
模組）；B 新開 shared/practice_store.js。

**定案 A**：storage.js 已擁有 IndexedDB schema 與 settings store，
新模組會製造兩份 DB 開啟邏輯與版本遷移點。轉換器做成純函式
（六元組↔[x,y]），node 直測不需瀏覽器。

**誠實降階原則**：SW 簡潔版沒有時序/筆壓——swStrokesToTraceStrokes
填 t=0、壓力 0.5，**不捏造漸變時序**；資料消費端（機器人訓練）可由
t=0 辨識降階紀錄。tags/source 帶 `${mode}-sw` 標記提交來源。

**同步方向**：進階版預設勾選「同步到渲染字庫」（可取消——練壞不蓋
好字）；簡潔版必寫練習史（fire-and-forget，失敗不影響 user-dict
已存事實、分項回報）。

## R4：overlay 泛化——adapter 參數化 vs 複製 vs 後端 cellmap

**Options**：★A SW.adapter 介面參數化（單一 overlay）；B 各模式
複製輕量 overlay；C 後端為四模式補 sutra 式 rect cellmap。

**定案 A**：B 是四份重複維護、R5 再加三份；C 多此一舉——grid.py
（5cn）與 page.py（5ct）早已埋 `<g data-char>` 錨點，後端零改動。
adapter 收斂五個耦合點：refresh 回呼、style/source select id、
collect（收集可點格）、buildRefImg（範字建構）。

**狀態綁定教訓（§46）**：adapter 與字集若綁「掛載當下」（模組級
SW.positions 直寫），使用者切換模式後點舊預覽會拿錯 adapter/字集。
改為 collect 閉包持有自己的 positions，**點擊當下**才寫入 SW——
單例 overlay 服務多來源的正確形。

**通用命中/範字**：`<g>` 命中區只有筆墨——注入透明滿格矩形
（格內皆 EM2048 局部座標，grid 平移、page 型平移＋縮放、wordart
旋轉全成立）；範字＝複製該格「即時」內容轉灰（自訂字型注入後
點格，所見即所得）。

**附帶根因修（§49）**：E2E console 出現 `d="Z"` path error——追根
是 grid.py 對 track-only 筆畫（user-dict 手寫字/標點）硬轉 outline
path：空 outline 得垃圾 path **且該筆畫完全不顯示**。page.py 5ai
早已「拆 outline/track 兩群、track-only 折線 fallback」，grid.py
是漏掃的兄弟實作——補齊同語意＋回歸測試。若無此修，R4 的字帖
手寫字在臨摹列全部隱形。

## R5：藝術模式——混合式 vs 全 overlay vs 全按鈕

**Options**：★A 混合式；B 三模式全 overlay；C 三模式全按鈕。

**定案 A**：文字藝術與曼陀羅共用 `_place_char_svg`——加一個
data-char 純屬性（§48，5cn/5ct 前例第三度復用）雙模式生效，R4
adapter 原樣沿用。禪繞字畫在 canvas、演算法吃 outline（手寫字
track-only 本質用不上）——B 是高成本做一個沒有下游價值的入口；
改「✍ 進階練習↗」深連結 /handwriting?char=X&from=zentangle，
限制誠實對應而非硬湊一致性。

## E2E 隔離制度化（§47）

R3 教訓：Playwright E2E 寫沙箱**真實** user-dict（2 筆手寫「永」蓋
掉標準 5 筆）→ 8 個 pytest 連鎖紅。「事後清理」依賴記得清、清得全；
R4/R5 改為 uvicorn 帶 `STROKE_ORDER_USER_DICT_DIR=/tmp/rNud` 啟動
——副作用進獨立資料目錄，驗收後確認正式字典零檔案。有伺服器側
副作用的 E2E，隔離要靠環境而非紀律。

## 結果

七模式（抄經/字帖/筆記/信紙/稿紙/文字藝術/曼陀羅）點字開窗、寫完
重繪即見手寫字（UserDictSource 載字鏈頂端）＋禪繞字跳板；練習史與
渲染字庫雙寫互通；抄經預覽感知延遲 11s→1.2s；筆順練習換字零等待。
擴散邊際成本：四模式各 ~5 行、藝術雙模式後端 1 處。
