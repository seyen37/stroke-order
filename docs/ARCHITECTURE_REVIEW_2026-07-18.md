# stroke_order 全程式架構健檢報告

日期：2026-07-18　基準版本：0.14.221（commit 3ca813d）
方法：4 個分面深入審查（後端架構／效能／前端／測試與部署）＋沙箱實測＋人工交叉驗證關鍵主張。

---

## 一、總評

架構骨架是健康的：`ir → sources → exporters → web` 分層方向乾淨、核心層零反向依賴；「幾何收集器＋多發射器」模式在 stamp／patch／stencil／grid 已確實兌現；gallery 的安全實作（參數化查詢、token hash、magic-link 一次性消耗）是全 repo 的模範層。34 章 PRINCIPLES 顯示原則意識很強。

真正的問題是：**執行的一致性落後於自訂原則**。最有價值的下一步不是重寫，而是「把已寫下的鐵則掃全體套齊」——最典型的就是 §9.1（async def 內同步 I/O 是全站級災難）只修了 sutra／stencil 四條路由，其餘 12+ 條重渲染路由仍是 `async def`，正是 §13.1「新鐵則要追溯掃全體」的反例。

技術債集中在四個熱點：`server.py`（4,693 行、`create_app()` 單函式 3,858 行、零 APIRouter）、`index.html`（單一 inline script 7,622 行）、`mandala.py`（G-code 靠反解析 SVG 字串，collector 模式最大破口）、CI 覆蓋缺口（node 測試無閘門、字型測試 CI 全 skip 假綠）。

---

## 二、規模基線

| 項目 | 數值 |
|---|---|
| Python（src） | 約 32,900 行；server.py 4,693／stamp.py 2,778／mandala.py 2,098 |
| 路由 | 85 條，全部定義在 `create_app()` closure 內，零 `APIRouter` |
| 前端 | index.html 10,852 行（單一 inline script 區塊 7,622 行、230 個函式共用頂層 scope） |
| 測試 | 97 檔（86 py＋11 mjs）約 26,500 行；pytest 函式 1,708、node test 257 |
| 資料 | data/ 580K（g0v_cache 已入庫 124 字）；samples/ 14M；.git 7.9M |
| 部署 | Render free tier 單 worker；CI 存在（ci.yml）但覆蓋不完整 |

---

## 三、P0：正確性與可用性風險（低工作量、高效益，建議最先做）

### P0-1　12+ 條 CPU-bound 渲染路由仍是 `async def`——單 worker 下任一重請求凍全站
`server.py`：notebook(1154)、notebook_post(1313)、letter(1433)、manuscript(1747)、wordart(1981)、mandala(2293)、doodle(2615)、grid(2695)、export(2831)、patch_post(3246)、patch_get(3322)、stamp_post(3398)、stamp_get(3528)，另 gallery 頭像上傳（4400，內含同步 Pillow resize）。這些函式體內直接跑字型載入＋幾何運算＋SVG 產生，無任何 `await`／`to_thread`。FastAPI 只有 sync `def` 路由會自動進 threadpool——`sutra_post/sutra_get/sutra_pdf/api_stencil` 在 5dp 已刻意改對，同型未擴散。

**修法**：逐一刪掉 `async` 關鍵字（body 不變），與 5dp 對齊。工作量：小。效益：並發下不再全站排隊；也消除 P0-2 的 event-loop 凍結面。
**回歸注意**：依 5ck 教訓，建議加一條 inspect 回歸鎖（掃 create_app 內所有重渲染端點必須 sync def），一次鎖死全體。

### P0-2　字元載入主幹在請求路徑內同步打外網（timeout 10s×N 字）
`sources/g0v.py:118`（`urllib.request.urlopen`，timeout 10s）；`AutoSource` 預設 primary 就是 `G0VSource(allow_network=True)`。kanjivg.py:102、mmh.py:209 同型（mmh 首用會同步下載 30MB）。快取字集內的字沒事；**字集外任一字**就會在（目前是 async 的）路由內同步網路往返——校內使用情境學生輸入罕字即觸發。

交叉驗證修正：`data/g0v_cache` 已有 124 個常用字 JSON 隨 repo 部署（心經前段 48 唯一字覆蓋 46），所以日常 demo 不會踩到；但 Render 檔案系統是暫時性的，執行期新抓的字每次 deploy／喚醒即蒸發，重複付冷成本。沙箱實測冷路徑整頁 82 秒 vs 暖路徑 48ms（1,700 倍差）。

**修法**（三段式）：
1. 擴充入庫字集：把常用教學字集（如 5000_wuqian 高頻段）預抓進 `data/g0v_cache` 隨 repo 部署（一次性腳本）。
2. 生產環境的網路抓取移出請求熱路徑：P0-1 改 sync def 後至少不凍 event loop；進一步可將「快取未命中」改為明確 4xx 提示＋背景補抓，或縮短 timeout 至 2~3s。
3. render.yaml 掛 persistent disk（或啟動預熱腳本）保住執行期快取。
工作量：小～中。效益：極高（消除線上最壞延遲與 502 主因）。

### P0-3　無 GZipMiddleware——大 SVG／JSON 全裸傳
實測：10 字字帖 SVG 246KB、心經單頁 1.25MB、zhuyin_tw.json 454KB。SVG/JSON gzip 通常壓到 10~15%。修法：`app.add_middleware(GZipMiddleware, minimum_size=1024)` 兩行。順帶對 `/static` 大 JSON 補長效 `Cache-Control`。工作量：極小。效益：傳輸量降約 85%，校網體感明顯。

### P0-4　零跨請求快取：同參數每次全部重算
`_load` 管線（validate→classify→hook→smooth→decomp→radical）只有單一請求內的 memoize；渲染端點無 ETag／Cache-Control。實測暖字型下同 10 字重載仍 95ms／請求。修法：(a) `_load` 結果加 `lru_cache`（key=char+source+hook+style，Character 唯讀）；(b) 高成本 GET 端點依 query 算 ETag 回 304。工作量：中。效益：熱門字帖近乎免費。

### P0-5　CI 兩個覆蓋缺口——「綠燈假象」
(a) 11 檔 .mjs／257 個 node 測試沒有任何自動閘門（ci.yml 與收工檢查.bat 都只跑 pytest）——這正是歷史上「node 測試被漏跑」多次應驗的根因；補一行 `node --test tests/*.mjs` 進 ci.yml 與收工檢查.bat。(b) CI 不抓字型，57 個字型測試在 CI 永遠 skip，實質守門只剩本機收工檢查.bat；建議 CI 加 fonts job（快取 GitHub Release 字型）或至少對 skip 數設門檻告警。工作量：小／中。

---

## 四、P1：維護性結構債

### 後端
1. **`create_app()` 單函式 3,858 行、零 APIRouter**。天然切線清楚：`/api/sutra/*`（~430 行）、`/api/gallery/*`（~360 行）、`/api/user-dict/*`、字型狀態群、`/vendor/*`——先抽這 5 群成 `routers/*.py`，`create_app` 只 `include_router`。可分批、每群一 commit。工作量：大（但漸進）。
2. **loader closure 複製 13 處**（`_load→_upgrade_to_sung→…→_apply_cns_mode` 串在 635/666/892/1206/…/4121 逐字重複）。抽 `make_char_loader(source, hook_policy, style, cns_mode)` 工廠，13 處改一行。工作量：中。
3. **SVG header＋mm 尺寸契約 11 個 exporter 各自手寫**，格式已漂移（`:.2f`／`:.3f`／不格式化並存）——違反 §27 單一真相源，也是 5bt「mm width＝viewBox 跨度」契約的散布風險。抽 `exporters/_svg_common.py: svg_header()`。工作量：小。
4. **樣板重複**：7 個 capacity 端點同骨架（可用共用 Depends）；下載檔名／Content-Disposition／X-* header 68 處（抽 `svg_response()` helper）。工作量：小～中。
5. **gallery/service.py 1,181 行多職責**（auth 橋接＋uploads＋likes＋avatar 影像處理），拆 uploads/social/avatars。f-string 組 SQL（701-724）目前安全（僅伺服器端常量），加註解鎖定不變式即可。工作量：中／小。

### 前端
6. **7,622 行單一 script、230 函式共用頂層 scope**。好消息：repo 內已有兩個現成範本——`handwriting/` 與 `gallery/` 都是乾淨 ES modules，且在無 build step 下已正常運作，證明拆分可行。且新模式（PATCH/STAMP/SUTRA/SW/FONT_STATUS）已是物件命名空間、內聚良好，可直接外移；舊模式（grid/nb/lt/ms/dd/wa/md）是裸前綴散函式，需先收斂再外移。
7. **`?v=` cache-busting 22 處手動同步**（zentangle 一族要同步 14 處、doodle 3 處）。以 pyproject version 為單一事實源：server 吐 HTML 時把 `?v=__VER__` 佔位符 replace 成 `app.version`。工作量：中。這是歷史上多次「三處同步」痛點的根治。
8. **su-/st- 前綴撞名是結構性 bug 溫床**（5en 事故已實證；模式名與前綴全面錯位：sutra→su、stamp→st、stencil→sc、patch→pt）。趁模式外移成獨立檔時把 id 前綴改全稱（sutra-/stamp-/stencil-），根除。
9. **重複樣板**：blob 下載樣板 8 份（且無一處 `revokeObjectURL`，潛在洩漏）；`!r.ok` fetch 錯誤處理 15+ 份；`const g=(id)=>…` 複製 8 份且 `g` 一名三義。抽 common/dom.js、net.js、download.js。工作量：小。

### 測試
10. **TestClient fixture 散落 56 檔**（conftest 僅 15 行）——上收 conftest 為共用 fixture。工作量：中（機械化）。
11. **186 個寫死長度斷言**（`assert len(...)==N`）是「改預設值→大面積紅掉」教訓的結構根因——資料集筆數、registry 長度收斂為 src/ 內常數，測試引用同源。工作量：中～大（漸進即可）。
12. **無快慢分層**（零 markers）：1,708 測試只能全量跑。引入 `@pytest.mark.slow`＋`-m "not slow"` 快層，開發迴圈受益（也緩解沙箱 45 秒上限分批問題）。工作量：中。

---

## 五、P2：值得排程但不急

1. **mandala.py 是 collector 模式最大破口**：`render_mandala_gcode(svg_str)` 用 ElementTree 反解析 SVG 字串還原 polylines，導致字 outline 丟棄、缺 DXF、解析脆弱。根因是 20+ 個 `*_band_svg` 直接回傳 SVG 字串。重構為 `_mandala_polylines()` collector。工作量：大——建議等有 mandala 功能需求時順勢做。
2. **zentangle.py 繞層**：唯一直接 import `..sources.*` 私有函式的 exporter；至少把 `_outline_to_polylines` 升為公開 API。工作量：中。
3. **演算法熱點**：engrave scanline O(掃描線×全邊數) 無 active-edge-table（雷雕重字可提速數倍）；zhang_suen 骨架化每字重跑可對 (font,char,mode) lru_cache，dense 偵測應「先驗門檻提前降級」而非跑爆才 except（5ea 現況成本已付）；stencil `_dilate` 逐像素步進。工作量：各中／低。
4. **巨檔拆分**：stamp.py 2,778 行——裝飾幾何（oval flower/star/sawtooth）抽 `stamp_decorations.py`。
5. **部署細節**：pyproject 三份 extras 幾乎重複（web/all/dev 各自重列，CI 用 dev、Render 用 web，易漂移）→ extras 自引用收斂；README 正文數字 stale（41 行寫 0.14.172、387 行寫 666 測試，與 badge/pyproject 三方不一致）→ 版本改 `importlib.metadata` 讀取、正文移除硬編數字；render.yaml 字型 graceful failure 會靜默缺字部署 → build 後加「字型清點」step；`components/data/ids.txt`(2.1M)、大 coversets 是否必需隨 wheel 打包，值得評估。

---

## 六、效能實測數據（沙箱，pip install -e ".[web]" 後）

| 場景 | 耗時 | 輸出 |
|---|---|---|
| 單字「永」grid（暖） | 載入 1.6ms＋渲染 0.4ms | 9.7KB |
| 10 字 grid（冷字型） | 3,716ms | 246KB |
| 同 10 字二次載入（暖、無跨請求快取） | 95ms | — |
| 心經一頁 260 字位（冷 g0v，字集外） | **82,306ms** | 1.25MB |
| 心經一頁（暖＋memoized） | **48ms** | — |

解讀：渲染本身極快，瓶頸幾乎全在「逐字首次載入」與「無跨請求快取」。P0-2＋P0-4 是投報率最高的兩件事；P0-3（gzip）則直接把 1.25MB 壓到約 150KB。

---

## 七、分階段改造路線圖

每一波都能獨立收工（符合現行收工 SOP：全綠才 commit），不破壞對外 API 形態與既有測試。

**Wave 1｜速效止血（1~2 個工作輪）**
async→sync def 批次修（P0-1，含 inspect 回歸鎖）→ GZipMiddleware＋靜態 Cache-Control（P0-3）→ CI 補 node step＋字型 job／skip 門檻（P0-5）→ g0v 常用字集預抓入庫＋timeout 縮短（P0-2 前半）。全部小工作量，效益立現。

**Wave 2｜快取與單一事實源（2~3 輪）**
`_load` lru_cache＋GET 端點 ETag（P0-4）→ `?v=` 版本注入（P1-7）→ render.yaml persistent disk 或啟動預熱（P0-2 後半）→ pyproject extras 收斂＋README 數字自動化（P2-5）→ conftest 上收 client fixture（P1-10）。

**Wave 3｜後端結構收斂（3~5 輪，可分批）**
APIRouter 5 群拆分（每群一 commit）→ `make_char_loader` 工廠（13 處收斂）→ `svg_header()`／`svg_response()` helpers → capacity 共用 Depends → gallery/service 拆分。斷言常數化（P1-11）隨手漸進。

**Wave 4｜前端拆分與大重構（依需求排程）**
前端四階段：抽 common 工具層（dom/net/download）→ 已物件化模式外移成 module（順帶根除 su-/st- 前綴）→ 裸前綴舊模式逐一收斂外移 → 面板資料驅動化。mandala collector 化與演算法熱點（P2-1/3）等有對應功能需求時順勢做。

**明確不建議做的事**（避免 over-engineering）：不引入前端 build step（ES modules 無 build 已被 handwriting/ 驗證可行）；不換 Web 框架；不動 gallery 安全層（現況是模範）；不為了「架構純度」一次性大爆改——每一波守住「全綠收工、可獨立回滾」。

---

## 八、與 PRINCIPLES 的對照（後設觀察）

本次發現的最大宗不是「新問題」，而是「已知鐵則未掃全體」：§9.1（async 同步 I/O）修了 4 條漏 12 條、§13.1（新鐵則追溯掃全體）本身成為反例、§27（跨層契約單一真相源）在 SVG header 與 `?v=` 兩處失守、「改預設值 grep 全部測試」教訓的根因（186 個寫死斷言）一直沒有結構性解。建議把「立新鐵則時同輪掃全體＋加回歸鎖」正式寫進收工 SOP——這一條做到了，上面一半的 P0/P1 未來不會再長回來。
