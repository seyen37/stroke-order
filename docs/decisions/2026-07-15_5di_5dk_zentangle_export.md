# 決策紀錄 2026-07-15（禪繞引擎重構弧）：5di 互動修正 → 5dj 引擎 → 5dk 匯出

對應 PRINCIPLES §15。0.14.179 → 0.14.186，pytest 1680（不動、全屬
前端），node 129 → 257。七輪：5di（驗收回饋）＋5dj-1~5（禪繞引擎
五子輪）＋5dk（匯出擴充）。QODA 六回（5di 一案／5dj-1~3 各三案／
5dj-4 三案／5dj-5 三案／5dk 三案），全數 A 案定案。

## D1. 使用者理念 → 分層正交架構（5dj-1）

使用者給的是禪繞畫「理念」（iCSO 五筆劃＋七延伸技法），不是規格。
把它翻成三層正交模型：基本符號（registry `category`）／延伸技法
（後處理 spec 的純函式）／資料（region.enhancers）。關鍵決策＝
延伸層是「吃 spec 列 → 回傳 spec 列」的純函式，與 tangle builder
完全解耦——既有 8 圖樣一行不改就降為 classic、與 5 基本符號共用
同一條 `orientSpecs`／`renderTangleSpecs`。理念的「五 × 七」乘法
結構直接落成程式的兩個正交維度。

## D2. 同一 spec 管線同時餵渲染與匯出（5dj-4）

禪繞的幾何全在前端 spec。匯出不另寫幾何——`collectExportPaths`
呼叫的是 `buildTangleOriented → applyEnhancers`，與 `drawRegionLayer`
**同一條管線**。所以畫面上看到什麼、匯出就是什麼，含全部延伸技法、
含每區段的朝向與參數。若在後端 Python 重寫一套幾何＝雙軌維護、
必然漂移。單一真相源不只省事，是正確性的保證。

## D3. 近似先落地、精確有觸發才升級（5dj-4 → 5dj-5）

5dj-4 的裁切用「折線細分＋中點取樣」——可測、夠用、當輪就交付
價值（雷切/寫字機拿得到裁好的線）。精確版（evenodd 真裁切）不是
一開始就做，而是等到有明確觸發（使用者要「比取樣更精確」）才升級。
5dj-5 換成精確交點分割，邊界落字形邊、無 px 鋸齒、折線更少更長。
先交付近似、保留升級路徑＝每輪都有可驗收的價值，不為一次到位
拖延交付。

## D4. 能力邊界誠實，不適用就略過或降級（5dj-2/3）

延伸技法對不適用的 spec **不硬套**：Coffering 只認完整 orb（弧與
非 orb 略過，金庫效應需封閉幾何）；Sparkle 對 s_shape 首版 MVP
維持原樣（renderer 自算控制點、不易穩定切分），5dj-3 才用攤平法
補上；Rounding 從端點小圓近似升級成真銳角三角、但直角不填、孤立
端點仍圓化。每個「做不到／暫不做」都在註解誠實標注、留升級路徑，
不假裝全能、也不硬塞出怪幾何。

## D5. 管線順序＝混搭正確性的載體（5dj-2）

七技法自由多勾＝任意子集，順序保證「不炸」。但「不炸」不夠——
E2E 抓到 Coffering＋Sparkle 同開時 Coffering **靜默失效**（Sparkle
先把 orb 切成弧、Coffering 找不到完整圓）。修法是把 Coffering 排到
Sparkle 前，並補回歸鎖測試。凡「後處理疊後處理」的固定管線，順序
本身就是規格：要用實際組合（不只單技法）驗證，把「先誰後誰」的
依賴寫進測試。

## D6. registry／單一事實源長出多消費者（5dj-1~3、5dk）

同一份宣告式清單餵多個 UI 與邏輯：`TANGLES` registry → 縮圖鈕
（縮圖直接跑生產 builder，圖示與輸出同源）；`ENHANCERS` 陣列 →
中排 toggle；`COMBOS` → 快捷鈕；`ENHANCER_PARAM_DEFS` → 滑桿；
`DXF_LAYER_COLORS` → DXF 層。新增一個技法/組合/參數＝改一處清單、
UI 自動長出，永不漂移。

## D7. 前端復刻後端格式，靠既有實作當規格（5dk）

DXF 匯出要在前端（禪繞全前端），但格式規格不憑空發明——直接復刻
`exporters/dxf.py` 的 R12 writer（POLYLINE/VERTEX/SEQEND、LAYER
table、CUT/ENGRAVE/WRITE 顏色、flip_y）。既有 Python 實作就是規格
文件，JS 版逐項對齊＝與印章/鏤空字的 DXF 一致、雷切軟體同樣認得。
跨語言復刻時，先讀既有實作、對齊慣例，勝過各寫各的。

## D8. 三層語意分工＝一份幾何餵不同機器（5dk）

匯出不是一坨線。`collectExportPaths` 分 strokes/fills/outline，DXF
據此組 CUT（字框輪廓，雷切走）／ENGRAVE（圖樣線＋掃描填充，雷雕
走）／WRITE（圖樣線，寫字機描）。ENGRAVE 與 WRITE 內容刻意重疊
（圖樣線）——同一份幾何按機器類型分層，使用者在雷切軟體選要處理
哪層。填色形狀三態（輪廓/掃描/略過）也是同理：一份形狀、按輸出
目的（檢視/雷雕/筆繪）換表現。

## D9. 雲端工作階段的檔案紀律（本弧全程）

雲端沙箱與本機權威檔是兩個檔案系統，跨越時的紀律（詳 §15.6）：
①開工 `git reset --hard` 前確認前輪已 push，否則清掉未 commit 工作
（用 `/root/out` 副本還原）②寫回一律 `device_commit_files` ＋ stage
回讀驗證（uploads 快取殘影＝以 stage bytes 或新檔名/clone 對照，
不信 `device_bash` 讀值）③`收工檢查.bat` 取最高編號 msg，要兩筆
分開就分兩輪交付、之間讓使用者收工一次。
