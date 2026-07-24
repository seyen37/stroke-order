# DESIGN.md — stroke-order 設計真理源

> 本檔是 stroke-order 全站 UI 的**單一設計事實源**（格式參照
> VoltAgent/awesome-design-md 慣例）。任何 AI 或人類要寫/改前端介面，
> **先讀本檔再動手**；與本檔衝突的產出視為缺陷。
> 內容萃取自 2026-07 UX 稽核弧（5fp~5fu）實戰定案——不是願望清單，
> 是已上線並有測試鎖著的既有語言。
> 同步鎖：`tests/test_design_md.py` 會比對本檔色碼與實際 CSS——
> **改 token 時文件與程式碼要同一批改**，否則紅燈。

---

## 1. 視覺氣質（Visual Theme）

**「安靜的紙，清楚的墨。」** 這是給老師與學生用的書法/字帖工具站：

- 介面是「紙」：淺灰紙面、白色卡片、細邊框、幾乎無陰影——UI chrome
  退位，讓使用者產生的**字帖/SVG 預覽（墨）成為畫面主角**。
- 工具型資訊密度：設定項多但以卡片分區、`<details>` 收合進階項收納；
  不追求留白極簡，追求「找得到、看得懂」。
- 樸素勝於華麗：無漸層、無大圓角、無裝飾動畫；hover 只做輕微變暗、
  互動回饋靠明確的文字狀態（「✓ 完成」「產生中…」）。
- 語言：繁體中文（台灣用語）；emoji 僅作功能圖示（🚨/⚑/📌/↓），
  不作裝飾。

## 2. 色彩語意（Color Palette & Roles）

**鐵則：藍＝主要動作；紅＝破壞性專用。**（5fq 定案）
紅色按鈕永遠不是「送出」；主要動作永遠不是紅色。

同一套色值在三個頁面作用域各有前綴（主頁 `--*`／筆順練習 `--hw-*`／
分享庫 `--gl-*`）——**同義異名、值必須鎖同**：

| 角色 | Token | 色值 | 定義處 |
|---|---|---|---|
| 紙面背景 | `--bg` | `#fafafa` | `src/stroke_order/web/static/index.html` |
| 卡片表面 | `--surface` | `#fff` | `src/stroke_order/web/static/index.html` |
| 墨（主文字） | `--fg` | `#222` | `src/stroke_order/web/static/index.html` |
| 輔助文字 | `--muted` | `#666` | `src/stroke_order/web/static/index.html` |
| 邊線（主頁） | `--border` | `#ddd` | `src/stroke_order/web/static/index.html` |
| **主要動作藍** | `--primary` | `#2c5cb8` | `src/stroke_order/web/static/index.html` |
| 主要動作字色 | `--primary-ink` | `#fff` | `src/stroke_order/web/static/index.html` |
| **破壞性紅** | `--accent` | `#c33` | `src/stroke_order/web/static/index.html` |
| 鍵盤焦點圈 | `--focus` | `#7aa7ff` | `src/stroke_order/web/static/index.html` |
| 資訊提示框底 | `--info-bg` | `#f0f7ff` | `src/stroke_order/web/static/index.html` |
| 資訊提示框字 | `--info-fg` | `#235` | `src/stroke_order/web/static/index.html` |
| 主要動作藍（手寫） | `--hw-accent` | `#2c5cb8` | `src/stroke_order/web/static/handwriting/handwriting.css` |
| 邊線（手寫/分享庫） | `--hw-line` | `#e0e0e0` | `src/stroke_order/web/static/handwriting/handwriting.css` |
| 主要動作藍（分享庫） | `--gl-accent` | `#2c5cb8` | `src/stroke_order/web/static/gallery/gallery.css` |
| 破壞性紅（分享庫） | `--gl-danger` | `#c33` | `src/stroke_order/web/static/gallery/gallery.css` |
| 資訊底/字/框 | `--gl-info-bg` 等 | `#e8f3ff` / `#1a4480` / `#b3d4f5` | `src/stroke_order/web/static/gallery/gallery.css` |
| 警示底/字 | `--gl-warn-bg` 等 | `#fff8e0` / `#704000` | `src/stroke_order/web/static/gallery/gallery.css` |
| 成功綠 | `--gl-success` | `#1d6b3a` | `src/stroke_order/web/static/gallery/gallery.css` |
| 隱藏標章底 | `--gl-flag-bg` | `#fbe9e7` | `src/stroke_order/web/static/gallery/gallery.css` |
| 隱藏標章字 | `--gl-flag-fg` | `#c62828` | `src/stroke_order/web/static/gallery/gallery.css` |
| 隱藏標章框 | `--gl-flag-border` | `#f2c1bc` | `src/stroke_order/web/static/gallery/gallery.css` |

衍生：`--danger: var(--accent)`；`--info-accent: var(--primary)`（資訊
提示框左緣線——5gb 把原 `#46a`/`#4a90c2`/`#69a`/`#6998d9` 四種雜藍歸一
到主要動作藍）。內容渲染色（折線紅 `#c62828`/谷折藍
`#1565c0`/中線綠 `#149046`、禪繞/字帖描紅灰階）屬**輸出品語意**，
不受 UI 色盤約束。

## 3. 字體（Typography）

- UI 一律系統字疊：`-apple-system, "Noto Sans TC", "PingFang TC",
  "Microsoft JhengHei", sans-serif`（**不引外部 webfont**——免費層
  資源天花板＋離線可用）。
- 等寬（代碼/座標/G-code）：`ui-monospace, "SF Mono", Menlo, Consolas`。
- 書法字型（教育部楷/宋/隸、崇羲篆、思源黑）只出現在**內容渲染**
  （字帖預覽/SVG 輸出），永不用於 UI chrome。
- 層級：頁標題 22px；區塊標 14px、`uppercase`、`--muted`、字距 .5px
  ——刻意低調，讓內容區為主；正文 14px／行高 1.5；hint 13px `--muted`。

## 4. 元件（Component Styling）

**按鈕四階**（padding 7px 16px、radius 4px、hover `brightness(.96)`、
disabled `opacity:.5`、focus-visible `2px solid var(--focus)`）：

- `btn-primary`：藍實底白字、600 字重——每個表單**恰一顆**主要動作。
- `btn-secondary`：白底灰框——次要動作與下載。
- `btn-ghost`：透明無框 `--muted`——低調輔助。
- `btn-danger`：**白底紅字紅框**（不給紅實底——降低誤觸吸引力），
  且不可復原操作**必配二次確認**（E2E 要實測「攔得住」）。

慣例元件：卡片（白底 1px 邊、radius 8、shadow `0 1px 2px rgba(0,0,0,.04)`）；
空狀態句 `.preview-empty`——「（輸入◯◯後按「產生◯◯」以顯示）」句式
全站統一；產生成功前**下載鈕一律 disabled**；狀態列文字回饋
（「✓ 完成（點格子可逐字手寫）」）；隱藏標章（`--gl-flag-*` 三件組，
淺紅底深紅字）；資訊提示框（`--info-bg` 底＋`--info-accent` 左緣線
＋`--info-fg` 字）。

**動詞規範**：觸發產出的按鈕一律「產生◯◯」（不用「載入」「重繪」）；
下載鈕「↓ 下載 ◯◯」帶格式名。

## 5. 版面（Layout Principles）

- 間距刻度：`--space-1..6` ＝ 4/8/12/16/24px；表單列距 12px。
- 主頁：960px 置中、雙欄 grid（設定 vs 預覽），640px 以下折單欄。
- action-bar 三區：導覽｜主要動作（`margin-left:auto` 靠右跳出）｜
  下載（次要階）。
- **共用控制列鐵序**（5fu 定案）：字型風格 → 罕用字 → 資料源——
  全站同名、同序、相鄰；**不硬搬絕對位置**（尊重各表單語意分組）。
- 進階/少用參數收 `<details><summary>◯◯▾</summary>`；長表單的產生列
  可 `position:sticky` 貼底。

## 6. 深度與層級（Depth & Elevation）

只有三層，不玩 elevation 系統：紙面（`--bg`）→ 卡片（1px 邊＋極輕
shadow）→ `<dialog>`（原生遮罩）。分享庫卡片 shadow
`0 1px 3px rgba(0,0,0,.08)`、radius 4px。

## 7. 設計護欄（Guardrails — Do / Don't）

- ✅ 每個獨立 CSS 檔開頭帶 `[hidden]{display:none!important}` guard。
- ✅ 版本標籤一律注入（空殼＋JS 讀資產 `?v=`），**永不手刻版號**。
- ✅ 新分類/選項白名單只存單一事實源（service `ALLOWED_KINDS`／
  `hash.mjs`），route 與元件不重複持有清單。
- ✅ 訊息文字會換行——佈局測試用元素 id 錨定、幾何斷言留換行餘裕。
- ✅ HTML/CSS/JS 自包含單檔或本站模組；靜態資產 import 帶 `?v=`。
- ❌ 不引 CSS 框架、webfont、UI 元件庫（Bootstrap/Tailwind 等一律不用）。
- ❌ 不用紅色做肯定/送出動作；不做無確認的不可復原操作。
- ❌ 不手寫十六進位色值散在元件裡——一律引用 token；新色先進本檔
  色表再使用。
- ❌ localStorage 以外不落任何本機儲存新機制（草稿既有慣例除外）。

## 8. 響應式（Responsive Behavior）

- 主斷點 640px：雙欄折單欄；工具列 `flex-wrap: wrap` 自然換行。
- 觸控目標：按鈕最小 7px 垂直 padding；分享庫卡片整卡可點區明確。
- 行動版不得隱藏主要動作；下載群可換行但不收合。

## 9. AI 代理提示指引（Agent Prompt Guide）

開任何 UI 工作前：

1. 讀本檔＋`docs/PRINCIPLES.md` 相關節（§54/§57/§61/§62/§71~§74）。
2. 改色 → 查 §2 token 表；同值三前綴（`--primary`/`--hw-accent`/
   `--gl-accent`）要一起動；文件與 CSS **同一批 commit**
   （`tests/test_design_md.py` 同步鎖會驗）。
3. 新按鈕 → 先問「這是主要/次要/幽靈/破壞哪一階」；新預覽區 → 配
   空狀態句＋產生前 disable 下載。
4. 新頁面 checklist：`_versioned_page` 注入、`[hidden]` guard、
   系統字疊、640px 斷點、回主頁導覽。
5. 佈局變更 → 更新終局測試（§61），斷言用 id 錨定。
