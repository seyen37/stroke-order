# 決策紀錄 2026-07-18（5ef~5ep）：切割風格 registry × 中心線平滑 UI × styled 逐字手寫範字

對應 PRINCIPLES §28–§33。承 5dm（STENCIL_CUTTING_STYLES.md §4/§5 藍圖）＋
5ed（Chaikin 骨架平滑）＋5dw/5dx（逐字手寫）。本日 11 弧全收全推
（origin＋backup），版號 0.14.209→0.14.220，期末 pytest 1756 passed /
62 skipped。commit：5ef `910c0ed`、5eg `e44eed6`、5eh `35cd599`、5ei
`0b22eb3`、5ej `e402bdd`、5ek `cebb835`、5el `72211d4`、5em `326b4ea`、
5en `f3050a6`、5eo `4d73642`、5ep `cc26585`。

---

## 整體脈絡

三條線並行：（A）把字模「切割策略」從散落的函式引數收斂成宣告式
registry，再沿同一 seam 長出四個切割功能；（B）把 5ed 的骨架平滑移植成
JS，並把「平滑度／簡化度」開成塗鴉與字帖對稱的使用者旋鈕；（C）修一個
實機回報的 styled 範字 bug（抄經選篆書、逐字手寫範字卻是楷書），並在修
第二版時揪出「用注入 mock 測導致假性通過」的方法論漏洞。

本批同時記錄**兩個明確擱置的幾何延伸**（完整 R1、bridge_axis curve_normal），
兩者都是沙箱實測後判定「現況已夠好／局部量測繞不開骨架」而刻意不做。

---

## 決策 1：切割 registry 要「先純重構立 seam，再沿 seam 加功能」（5ef，§28）

**觸發**：下弧候選點名「切割風格 registry 重構（承 5dm）」。當時 stencil.py
實際只有一種策略（全連派 `connect_depth=full`、殘腔 0），參數散在函式引數
與模組常數。

**選項**：

| 編號 | 方案 | 優點 | 缺點 |
|---|---|---|---|
| A | 純 registry 重構、行為逐位元保存，第二風格另弧 | seam 與新行為分離、每步可驗零回歸 | registry 只有 1 entry＝暫時像過度抽象 |
| B | 重構同時把 envelope 第二風格一起做 | 一次到位 | 重構 bug 與新演算法 bug 混在一起難分 |
| C | 暫緩 | — | 藍圖擱著、參數持續散落 |

**選擇**：☑ A

**理由**：registry 只有 1 entry 本身確實是 YAGNI 警訊，但使用者點名此弧、
文件是刻意留的藍圖、第二風格已設計好——這把它從「臆測」變「已規劃」。更關鍵
的是**把重構與加功能分成兩個 commit**：5ef 只搬家、逐位元保存（既有 stencil
測試全綠即證），5eg 才引入新演算法。若混做，一旦鏤空幾何出錯，無法一眼判斷
是搬家搬壞還是新演算法本身錯。

**後續驗證**：✅ 5ef 純重構零回歸；5eg~5eo 四個功能都沿這條 seam 乾淨長出，
每個都是小 diff。

---

## 決策 2：孔巢狀深度用 Jordan「min 穿牆」量、不用形態學層剝（5eg，§29）

**觸發**：envelope（方正簡潔）要「只斷最外框、留深層 counter（如國/圖 內件）
成島」，需要一個「這個孔被幾層墨包住」的深度定義。

**選項**：

| 編號 | 方案 | 優點 | 缺點 |
|---|---|---|---|
| A | 軸向射線的**最小穿牆數**＝巢狀深度（Jordan 曲線定理保證） | 對單一 blob 正確、O(邊長) | 需想清楚「取四軸 min」 |
| B | 形態學層剝（erode 幾次到消失＝深度） | 直覺 | **ink 常是單一連通 blob，層剝量的是到 blob 邊界的距離、非巢狀層數** → 錯 |

**選擇**：☑ A（`_hole_depths`：四軸向射線、取最小穿牆數）

**理由**：被 d 層 loop 包住的孔，任一射線出界至少穿 d 次牆，而**最小**的那個
方向恰等於 d（Jordan）。形態學層剝的致命錯在於它假設「深度＝可被剝掉的層數」，
但漢字墨跡幾乎總是單一連通 blob，剝的是 blob 半徑不是包覆層數。

**後續驗證**：✅ 三層巢狀（1/2/3）→ envelope_depth 1/2/3 分別鑿到第幾層，島
留存正確。此決策的**反面教材**見決策 6（R1 局部量測同樣栽在 blob-leak）。

---

## 決策 3：切割方向↔牆是對偶，keep_primary 用「懲罰切主幹方向的射線」實作（5ei/5eo，§30）

**觸發**：使用者要「直豎筆畫別從中切開」，鏤空缺口盡量落在橫筆。

**選項**：A 顯式偵測每根筆畫朝向再避讓（需筆畫切分＝骨架，重）；★B 用方向↔牆
對偶的啟發式（`_escape_score` 對水平射線＝切豎筆的方向 ×BIAS(1.6) 懲罰）。

**選擇**：☑ B（`keep_primary="vertical_first"`）

**理由**：關鍵洞察是**射線方向與它切的牆正交**——水平射線切的是豎筆、垂直
射線切的是橫筆。所以「保豎」＝「懲罰水平射線」，不需要知道每根筆畫在哪，只需
在逃逸評分裡給方向加權。這避開了 A 的骨架切分（見決策 6 為何骨架路線這弧不走）。
5eo 把 physical 也從 thinnest_wall 改成 vertical_first，兩風格統一保豎。

**後續驗證**：✅ 沙箱 noto_hei 渲染→cairosvg→PNG 視覺複驗，缺口落橫筆。實機
待驗收清單 ⑦⑪。

---

## 決策 4：連筋深度是 runtime 旋鈕、不是 style 欄位（5ej，§30）

**觸發**：使用者要「envelope 深度可調，連到第幾層自己決定」。

**選擇**：☑ 加 `envelope_depth` 為 `stencil_geometry()` 執行期參數＋
`/api/stencil?envelope_depth=`，**不**在 CuttingStyle dataclass 加欄位。

**理由**：CuttingStyle 定義的是「風格身份」（envelope vs physical），深度是
使用者當下的旋鈕值——把旋鈕塞進身份欄位會逼出「envelope-1／envelope-2…」
一堆偽風格。runtime 參數覆蓋風格預設（envelope 預設 1、physical 恆全連）
才是正交分解。§30 一併涵蓋此點。

**後續驗證**：✅ 三層巢狀字 1→2 內件由留島轉連通。

---

## 決策 5：同源演算法改進要套「所有」消費點，tuning 參數必須進 cache key（5eh/5ek/5el/5em，§31）

**觸發**：5ed 的 Chaikin 只用在骨架描紅。塗鴉中心線與字帖自訂字型都在畫
polyline，同樣受益於平滑；且使用者要能自己調平滑/簡化強度。

**選擇**：☑ `chaikinSmooth` 掛 JS api 匯出，套塗鴉 centerline＋字帖 grid；
再把 chaikinIters（塗鴉）、gf-smooth＋gf-simplify（字帖 RDP）開成對稱 UI 旋鈕。

**理由**：一個平滑演算法有多個等價消費點（骨架／塗鴉／字帖），改進要一次套齊
否則體驗分裂。踩到的坑：`fontCharTracks` 有快取，**cache key 必須併入
iters+eps**，否則使用者調旋鈕會拿到舊軌跡（快取沒失效）——這是 §15.8「快取
破壞要涵蓋整個依賴」的再驗。純 JS 靜態檔改動記得 bump `?v=`（5eh 有；5ek/5el/5em
只改 index.html 免 bump）。

**後續驗證**：✅ node 實測 Chaikin 最大轉角 90°→26.6°；塗鴉與字帖 UI 對稱。

---

## 決策 6：瀏覽器無 styled 字型時 reuse 伺服器 SVG 字形，別 canvas fillText（5en，§32）

**觸發**：實機回報——抄經選篆書，逐字手寫視窗範字顯示系統楷書「觀」非篆書。

**根因**：`swDrawBase` 用 `ctx.fillText` 畫範字，但篆/隸字形是**伺服器渲染的
SVG**、瀏覽器本地沒有這些字型，fillText 只會落回系統 sans/楷。

**選擇**：☑ `swBuildRefImg` 從抄經預覽已渲染的 SVG，clone 範字圖層
（sutra-glyph-reference/trace/trace-skeleton，**排除** user/marks/cellmap）、
裁到該格 cellmap rect bbox、recolor #c8c8c8、載成 Image；swDrawBase 有 refImg
就 drawImage、缺才 fillText fallback（缺字→範字空白＝誠實）。

**理由**：要顯示 styled 字形而瀏覽器無該字型時，**伺服器早已把正確字形渲進
預覽 SVG 了**——reuse 它（clone＋裁＋recolor）遠比想辦法在前端重畫可靠。

**後續驗證**：⚠ v1 有接線 bug，見決策 7。

---

## 決策 7：修「JS 讀 DOM 元素」的 bug，e2e 必須對真實渲染的元素跑（5en→5ep，§33）

**觸發**：5en 部署後使用者**重報同一 bug**——篆書範字仍是楷書。

**根因（一詞之差）**：`swBuildRefImg` 寫 `getElementById("st-preview")`，但
`st-`＝**印章 stamp**（st-render→stampRender）、抄經是 `su-`
（su-render→sutraRender、`#su-preview`）。production 抓到印章預覽（抄經模式
下無 cellmap）→查無→回 null→fallback 楷書。

**為何 5en 測試沒抓到（真正的教訓）**：5en 的 e2e 用**注入的 mock st-preview**
（還把它搬到 body 讓 getBBox 生效）、pytest 只鎖字串 wiring——**沒有一個測試
對真實 sutraRender 產出的 su-preview 跑**。mock 遷就了「元素叫 st-preview」
這個錯誤假設，於是假性通過。

**修法**：`st-preview`→`su-preview`（一詞）；pytest 斷言改切 swBuildRefImg
函式體比對（須含 su-preview、不得含 st-preview——st-preview 是印章模式合法用法
不能全域禁）；新增 `e2e_5ep` 對**真實 sutraRender** 跑：切抄經→產生預覽→等真
`#su-preview #sutra-cellmap` 渲染→swOpen→驗 `SW.refImg` 為已載入
HTMLImageElement。

**選擇**：☑ 一詞修正＋補真實渲染 e2e。

**後續驗證**：✅ e2e_5ep 全綠、1756 passed；實機待使用者確認 v2 生效（清單 ⑫）。

---

## 沒做的決策（明確擱置，勿重試）

- **完整 R1（keep_primary=structural，局部牆延伸量測）**：試作後 revert，**未
  提交**。沙箱「寬橫條＋寬孔」實測 structural 切掉長橫主幹。根因＝交接處量垂直
  run 會 blob-leak 進相連筆畫→量到墨團尺寸非筆畫長度→退化成長寬比≈vertical_first。
  結論：R1 局部量測繞不開筆畫切分（＝骨架，B 案帶 5ea 的 OOM 風險）。除非罕見
  橫主幹字實機證明需要，否則不做。與決策 2 同源教訓：**單一 blob 上的局部幾何
  量測會 leak。**
- **bridge_axis curve_normal（拉丁曲線法線切點）**：評估後零改動。沙箱實測常見
  正體拉丁已正確——O/Q/8 偵測 0 轉角→十字 fallback、`bridge_count=2` 得上下
  極點（殘腔 0）；碗形 B/D/P/R 交接處有轉角→走轉角路徑。curve_normal 只救非
  軸向曲線 niche，真出現破字再做。

---

## 學到的規則 / pattern（→ PRINCIPLES §28–§33）

- **§28**：宣告式 registry／清單，先做「純重構立 seam、逐位元保存」一個 commit，
  再沿 seam 加功能——別把搬家與新演算法混在同一 diff。
- **§29**：單一連通 blob 上，巢狀深度用 Jordan 軸向射線最小穿牆數，別用形態學
  層剝；更廣義——**單一 blob 上的局部幾何量測會 leak，先問「這個量測會不會漏進
  相連結構」**。
- **§30**：切割射線方向與它切的牆正交（水平射線切豎筆）；「保某方向筆畫」＝
  「懲罰切它的射線方向」，免骨架。可調量是 runtime 旋鈕、非風格身份欄位。
- **§31**：同源演算法有多消費點時改進要一次套齊；帶快取的消費點，tuning 參數
  必須進 cache key（否則調值回舊結果）。
- **§32**：要顯示 styled 字形而瀏覽器無該字型時，reuse 伺服器已渲進預覽的 SVG
  字形（clone＋裁＋recolor），別 canvas fillText 系統字型。
- **§33**：修「JS 讀哪個 DOM 元素」的 bug，端到端測必須對**真實渲染的元素**跑；
  注入 mock 會遷就錯誤假設而假性通過（mock 驗邏輯、真實渲染驗接線，缺一不可）。
  附記憶點：抄經＝`su-`（sutra）、印章＝`st-`（stamp），易混。

---

## 相關檔案

- 工作紀錄：`docs/WORK_LOG_2026-07-18.md`（5ea~5ep 各弧＋收工總結節）
- 切割規格：`docs/STENCIL_CUTTING_STYLES.md`（§4 表已更新 physical=vertical_first、
  frame_strategy=nearest_edge_spoke）
- 原則：`docs/PRINCIPLES.md` §28–§33
- 程式碼異動：`src/stroke_order/exporters/stencil.py`（registry／_hole_depths／
  _escape_score／_connect_to_frame）、`src/stroke_order/web/server.py`
  （/api/stencil style＋envelope_depth）、`src/stroke_order/web/static/index.html`
  （中心線 UI＋swBuildRefImg）、`src/stroke_order/web/static/doodle_engine.js`
  （chaikinSmooth）、`tests/test_stencil.py`／`test_web_grid.py`／
  `test_doodle_engine.py`／`test_sutra.py`
