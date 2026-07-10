# stroke-order 整體規劃建議書（主檔）— 2026-07-05

> **本檔取代 `PROJECT_PLAN_2026-06-19.md` 成為新主檔**（舊檔保留為歷史盤點，頂部已標 superseded）。
> 盤點基準：**v0.14.133**｜1511 passed / 49 skipped / 0 failed｜21 exporters｜12 資料源｜~50 web 端點｜5 cover-sets｜68 決策日誌
> 狀態：**草案**。§6「戰略選項」與 §7「推薦決定」屬 QODA 第 2-3 步，**待你 sign-off 才動工**；§8 起的步驟指引在 sign-off 後即為執行藍圖。
> 對焦紀錄（2026-07-05）：新檔取代舊主檔｜戰略重新開放評估（不預設 6/19 的 Path 1）｜投入節奏＝每週數個 session｜交付＝Markdown 進 repo。

---

## 0. 文件定位與修訂方式

本檔是三合一：**(1) 現況與架構分析**（§1-§4）、**(2) 戰略建議**（§5-§7）、**(3) 執行指引與修訂原則**（§8-§11）。

**未來修訂 SOP**：遇下列任一觸發即重開本檔（另存 `PROJECT_PLAN_YYYY-MM-DD.md`、舊檔標 superseded、不原地重寫歷史）：

1. 任一 Stage 的 kill criteria 被觸發（§8）
2. 戰略假設被推翻（例：spike 證明對齊器不可行、或出現真實使用者需求）
3. 外部機會出現（合作邀約、社群需求、學術發表窗口）
4. 超過一季未動工，現況快照已失真

修訂時必遵循 §10 的九條策略原則——那一節就是寫給未來修訂者（未來的你＋AI 協作者）的憲章。

---

## 1. 現況快照（2026-07-05）

| 面向 | 狀態 |
|---|---|
| 版本 / 測試 | v0.14.133；1511 passed / 49 skipped / 0 failed |
| 核心 pipeline | Phase 1-4 完成：IR → 分類 → 平滑 → hook policy → 多格式輸出（SVG/G-code/JSON/GIF/ODP） |
| 資料源 | 12 源、auto-fallback 串聯（UserDict → g0v → MMH → Punctuation → CNS Kai）＋4 種字型風格 |
| 組件子系統（Phase A）| ✅ 完成：IDS parser、greedy set cover、5 個 cover-sets（808/4808/5000/本土6792/國小5021）、覆蓋率實證 200-248 組件 |
| 5d 手寫蒐集 | MVP 完成：IndexedDB PSD（軌跡＋時間戳＋筆壓＋tilt）、匯出 JSON/SVG/ZIP |
| Phase B/C/D（主線）| ✗ **全部未動工**。主線自 4/28 Phase A 後停擺 68 天 |
| Line B 設計工具 | 廣度過剩（14/21 exporters）；zentangle 6z 視覺驗證仍是 dangling thread |
| Line C 部署 | Render free tier（冷啟動 ~30s）＋GitHub Pages 文件站＋雙遠端備份＋CI |
| 治理 | PRINCIPLES.md 7 章、決策日誌三件套、§3.10 嚴格 default-deny git workflow——成熟且運作中 |

**與 6/19 盤點的差異**：quick win #2（README badge）已閉合；zentangle 視覺驗證與戰略拍板兩項懸置至今。期間 0 commit——這 16 天的靜止本身就是資訊：**沒有拍板的推薦不會自己執行**，本檔的步驟切法（§8）直接回應這一點。

---

## 2. 架構分析：優勢與結構性風險

### 2.1 值得保留的架構優勢

1. **IR 中心化**：所有源匯入統一中間表示，exporter 只認 IR——加源、加輸出互不干擾，這是 12 源 × 21 exporters 沒有失控的原因。
2. **Source abstraction + auto-fallback**：罕用字自動降級到 CNS，UserDict 最高優先，使用者可自救。
3. **測試密度**：1511 條全綠＋視覺驗證 SOP，重構安全網厚。
4. **決策可追溯**：68 篇決策日誌＋PRINCIPLES 索引，任何「當初為什麼這樣做」都答得出來——bus factor = 1 的最佳緩解。
5. **Cover-set 實證**：「200-250 組件覆蓋常用字空間」有三源交叉驗證，VISION 的數學地基是實測不是猜想。

### 2.2 結構性風險與債（按影響排序）

| # | 問題 | 影響 | 對策（§8 對應） |
|---|---|---|---|
| R1 | **蓄水通路實質未通**：gallery SMTP 未開（dev mode 印 console）、Render free tier 無持久碟——SQLite 每次 redeploy 歸零 | Phase B/C/D 的燃料（真實手寫資料）只能靠自己寫；「使用者上傳」目前是裝飾 | Stage 4 蓄水 sprint；短期內誠實接受「資料自產」 |
| R2 | **零使用數據儀表**：無任何 endpoint 計數 / 訪問統計 | 所有「要不要投推廣」的判斷都在盲飛 | Stage 0 最小儀表（半天工作） |
| R3 | `web/server.py` 4,087 行單檔、~50 端點集中 | 改動半徑大、AI session 讀檔成本高 | 凍結 Line B 後自然止血；Phase B 新端點另開 router，**不擴大單檔** |
| R4 | repo root 堆置 ~200 顆樣本 PNG/SVG | 門面雜亂、clone 變重、AI 勘查噪音 | Stage 0 歸檔（機械性工作） |
| R5 | 資料授權混合：g0v 教育合理使用、KanjiVG CC BY-SA、MMH LGPL | 若走商業路線，g0v 依賴是地雷 | §10-P7 授權邊界原則；Phase B 對齊器以 KanjiVG/MMH 為準 |
| R6 | 冷啟動 ~30s（Render free） | 任何推廣的第一印象殺手 | 蓄水 sprint 前必先解（付費 tier 或 keep-alive） |
| R7 | zentangle 6z 視覺驗證懸置 59 天 | 心理負債＋違反自家「閉環」原則 | Stage 0 第一項，30 分鐘內閉合 |

**一句話診斷（延續 6/19、加重語氣）**：能量配置與戰略價值倒掛未解——而且多了一層：**決策懸置比錯誤決策的成本更高**。6/19 產出了正確的地圖，卻因為推薦停在「待拍板」而 16 天零進度。本檔的解法是把拍板點縮小（只拍 Stage 0＋Stage 1 spike，兩者合計 3-4 sessions），把大決策移到 spike 之後用數據拍（§8 Stage 2 checkpoint）。

---

## 3. 目標與運作模式回顧

**存在理由（VISION 不變）**：世界第一個「真實手寫軌跡 × 組件化字型 × 個人風格生成」三維交集開源系統。使用者寫 600-1000 字 → 覆蓋 200-250 組件 → 組合演算法生成 3500+ 字個人字庫。

**運作模式（實然）**：solo 開發者 ＋ AI 協作 session、間歇到每週數次的節奏、§3.10 嚴格治理、決策日誌完整。這個模式的強項是**可中斷可恢復**（文件密度讓任何 session 都能冷啟動），弱項是**大 phase 容易懸置**（Phase B 估 2-3 週，在 session 制下若不切小步就永遠「還沒開始」）。

**因此本檔的核心設計決定**：所有步驟切成**單 session 可閉合**的粒度，每步有明確驗收標準——這不是形式主義，是配合實際運作模式的生存設計。

---

## 4. 可行性分析（主線 Phase B/C/D ＋ 替代路線）

### 4.1 Phase B 組件級切割——技術風險拆解

核心任務：使用者整字手寫軌跡 vs 標準軌跡（KanjiVG `kvg:element` / MMH medians）比對 → 切成組件級樣本。

| 子問題 | 風險 | 評估 |
|---|---|---|
| 筆畫數一致時的 stroke-index 對映 | 低 | KanjiVG 每筆已標註所屬組件；使用者按標準筆順寫 → 直接按筆畫索引分組，**不需要幾何比對** |
| 使用者筆順偏離標準 | 中 | 可用筆畫幾何特徵（起點象限、方向、長度）做匈牙利對映；spike 先不解，偵測到偏離就標記「低信心」跳過 |
| 連筆（一筆寫多畫）| 中高 | 5d 有時間戳＋筆壓，可偵測筆畫數不符；同上，先標記不切 |
| 組件邊界歧義（「必」）| 低（工程上）| 以 KanjiVG 標註為準、IDS 補充；爭議字列 skip-list，學術爭議不擋工程 |
| 簡繁 / 區域變體 | 低 | 5d 蒐集時已知目標字與源，切割用同源標準軌跡 |

**結論**：Phase B 的「保守版」（只處理筆畫數吻合＋筆順標準的樣本）風險是低的，而且這個保守版就足以解鎖組件庫與覆蓋率閉環——因為 5d 練習場景本來就引導使用者按標準筆順寫。**Spike 的目標從「證明對齊器可行」修正為「量測保守版的命中率」**：拿 10-20 個自寫樣本，量測多少 % 能直接按筆畫索引切割成功。命中率 > 70% 即值得全量投入。

### 4.2 Phase C / D / spinoffs

- **Phase C 規則式組合**（估 8-12 sessions）：IDS parser 已存在（`components/ids.py`），變形規則庫（左旁壓窄、上部矮化等）是可枚舉的工程；美學上限存在但「七成像本人」的驗收不苛刻。可行，排在 Phase B 後。
- **Phase D 神經組合**：需 5000 字級樣本。在 R1（蓄水未通）解決前**不具備啟動條件**，維持遠期。
- **tinyhanzi**：依賴 Phase B 的組件資料成熟，維持凍結觸發條件不變。

### 4.3 蓄水路線的誠實評估

當前狀態等於**還沒開始經營使用者**：SMTP 未開＝無法真實註冊、無持久碟＝資料會消失、無儀表＝不知道有沒有人來、冷啟動 30s＝來了也可能走。蓄水不是「推廣」問題，是四個基礎設施缺口。好消息：四個缺口都是小工程（各 0.5-1 session）；壞消息：補完之後仍需要內容與通路經營，那是持續性投入而非一次工程。你的教育現場身分是天然通路（國小書法/生字簿場景、資訊教育社群），但通路經營應該等產品有「寫 100 字看到自己的組件庫」這個 aha moment（＝Phase B 產出）再啟動，否則留不住人。

---

## 5. 需要改進的地方（彙總清單）

- **技術債**：R3 單檔 server（止血即可，不急拆）；front-end 無 build system（凍結廣度後可接受）。
- **文件債**：無（6/19 已清 README badge；本檔取代舊主檔後文件鏈完整）。
- **結構債**：R4 root 樣本歸檔。
- **產品債**：R1 蓄水四缺口、R7 zentangle 閉環、Line B 凍結未正式公告（README 仍以 Line B 功能為主敘事，與 VISION 主線敘事失衡）。
- **流程債**：大 phase 懸置模式（§2.2 診斷）——用 §8 的 session-sized 切步＋縮小拍板點解。

---

## 6. 戰略選項（QODA Step 2 — 重新開放評估）

四條路徑，按「治理穩健度」排序（不確定性最先被壓住的排前面）：

| 路徑 | 內容 | 優點 | 缺點 / 風險 |
|---|---|---|---|
| **★ Option 1：閘門式主線推進** | Stage 0 閉合舊債（1-2 sessions）→ Phase B spike 量測命中率（1-2 sessions）→ **checkpoint 用數據拍大板** → 全量 Phase B 或轉向 | 先花 3-4 sessions 把最大技術不確定性變成數字，大決策不再憑感覺；每步單 session 可閉合，杜絕懸置；spike 失敗也只損失 2 sessions 且留下量測工具 | 主線見效仍需 Stage 3 全量（4-6 sessions）；期間蓄水維持現狀 |
| Option 2：蓄水優先 | 先補四缺口（SMTP/持久化/儀表/冷啟動）＋5d UX 打磨，Phase B 延後 | 替 Phase B/D 累積真實資料；基礎設施反正遲早要補 | 沒有 aha moment 的產品，通了管線也留不住人；主線繼續停擺，離「存在理由」更遠 |
| Option 3：雙軌交錯 | Phase B 為主、每 2-3 sessions 插一個蓄水 quick win | 兩頭都動 | 在間歇 session 制下，雙軌＝雙倍 context 切換成本；歷史證據（5 月）顯示這個模式會讓硬工程被軟工程擠掉 |
| Option 4：降速維護 | 全面凍結、只修 bug，等外部觸發 | 零投入 | VISION 窗口不等人（組件化＋手寫資料是 open niche）；治理慣性一旦斷，重啟成本高 |

**淘汰說明**：6/19 的「Path 2 續攻 Line B 廣度」不再列入——廣度過剩已是兩份主檔的共同診斷，維持淘汰。

---

## 7. 推薦決定（QODA Step 3 — 一段話）

**推薦 Option 1（閘門式主線推進），並把「最小儀表」併入 Stage 0。** 理由：專案的存在理由是三維交集系統，其中唯一還沒被工程驗證的環節就是組件級切割——Phase B spike 用 2 sessions 把它變成命中率數字，之後的大決策（全量投入 vs 轉蓄水）就有 ground truth 可拍，不再重演 6/19「推薦懸置 16 天」的模式。蓄水四缺口不是不做，是**排在 aha moment 之後**（Stage 4），因為沒有「看到自己的組件庫長出來」這個核心體驗前，通了管線也留不住使用者；唯一例外是儀表——它半天可完成、服務所有路徑的決策品質，所以進 Stage 0。Option 3 的雙軌在間歇 session 制下有實證的擠出效應，不推薦當主軸。

> **QODA Step 4：本檔 sign-off 範圍 = Stage 0 ＋ Stage 1（合計 3-4 sessions）＋ Line B 正式凍結。** Stage 3 之後的投入由 Stage 2 checkpoint 的數據另行拍板——你現在不需要承諾 2-3 週的 Phase B，只需要承諾一次量測。

---

## 8. 實行步驟指引（sign-off 後的執行藍圖）

每步＝1 session 內可閉合；標【驗收】與【kill】。順序即優先序。

### Stage 0 — 閉合與地基（1-2 sessions）

| # | 步驟 | 驗收 | 備註 |
|---|---|---|---|
| 0.1 | zentangle 6z 視覺驗證：開 demo 看 4 條 curve 軸 → confirm 或退回 | dangling thread 閉合，決策日誌記結論 | 30 分鐘 |
| 0.2 | Line B 正式凍結公告：README 加「維護狀態」段、本檔連結 | README 敘事重心移到 VISION 主線 | 凍結＝只修 bug，非刪除 |
| 0.3 | root 樣本歸檔到 `samples/` / `docs/gallery/` | repo root 只剩程式與設定檔 | 機械性；.gitattributes 確認 LFS 不受影響 |
| 0.4 | 最小儀表：SQLite 計數表（endpoint × 日期 × count），middleware 一個、查詢端點一個，不記 IP 不記個資 | `/api/stats` 能回答「過去 N 天各模式被用幾次」 | 半天；為所有未來決策供數 |

### Stage 1 — Phase B spike：切割命中率量測（1-2 sessions）

- 建 `components/aligner.py` 最小原型：輸入（整字 PSD 軌跡＋字元），流程＝筆畫數比對 → KanjiVG per-stroke 組件標註分組 → 輸出組件級樣本（含所屬字/位置/筆畫範圍 metadata）。
- 自寫 15-20 字測試集（覆蓋左右/上下/包圍結構），跑命中率報告。
- 【驗收】「明」→ 自動切出日/月樣本；命中率報告產出（成功切割 % ＋ 失敗原因分類）。
- 【kill】命中率 < 50% 且失敗原因無明確工程解 → 停 Phase B，改走 Option 2，本檔重開修訂。
- 【續行門檻】命中率 ≥ 70% → Stage 3 直接排程；50-70% → Stage 2 討論失敗分類後再拍。

### Stage 2 — Checkpoint（QODA，半 session）

用 spike 數據拍板：全量 Phase B（→ Stage 3）或轉蓄水（→ Stage 4 提前）。寫決策日誌。

### Stage 3 — Phase B 全量（4-6 sessions，每步可獨立閉合）

1. `ComponentSample` schema（IndexedDB＋匯出格式；遵循既有 schema versioning 原則：版本字串＋migration table）
2. 對齊器強化（筆順偏離的幾何對映、連筆偵測標記）
3. 5d UI「我的組件庫」頁（按組件瀏覽自己的樣本）
4. 覆蓋率儀表板整合（「你已覆蓋 M 組件、可組合 ~K 字」進度曲線——VISION §五的 aha moment 落地）
5. 【驗收】寫 100 字 → 自動產生 ~250 組件樣本、組件庫可瀏覽。

### Stage 4 — 蓄水 sprint（2-3 sessions，Phase B 驗收後啟動）

1. 持久化：Render 付費 tier 或遷移（SQLite → 持久碟；或 gallery DB 換託管 Postgres）
2. SMTP 開通＋冷啟動緩解（keep-alive ping 或付費 tier 順帶解決）
3. 5d 引導流程打磨：新使用者 10 分鐘內體驗「寫字 → 組件長出來」
4. 通路試水：教育現場（書法課/生字簿場景）小規模試用，用 Stage 0.4 的儀表量測留存
5. 【驗收】一位非本人使用者完整走完註冊 → 寫 20 字 → 看到組件庫。

### Stage 5 — Phase C 組合引擎（8-12 sessions，另開設計 doc）

依 PRINCIPLES §6.1：大 phase 先寫 design doc。IDS 結構樹 → 位置變形規則庫 → 軌跡黏合 → `/api/compose/{char}`。【驗收】寫完 cover-set 的使用者能合成沒寫過的字，視覺七成像本人。

### Stage 6 — 遠期觸發（不排程，只列觸發條件）

- **Phase D**：gallery 累積 ≥ 5000 字真實樣本。
- **tinyhanzi**：Phase B 成熟＋（個人 ESP32 需求 或 社群詢問）。
- **KAGE/GlyphWiki 整合**：Phase C 完成後評估。
- **學術發表**：Phase C 有結果＋組件級資料集達 CC BY-SA 發布標準。

---

## 9. 未來發展應用方向

| 方向 | 依賴 | 定位 |
|---|---|---|
| **個人字型生成器**（核心）| Phase B+C | 「寫 1/5 的字，留下全部的字跡」——書法家、教師、長輩字跡保存 |
| **寫字機器人字源** | 現有＋Phase C | AxiDraw / pen plotter 生態的 reference implementation；tinyhanzi 打嵌入式 |
| **教育應用** | 現有 Line B＋5d | 字帖/筆順/生字簿已可用；你的教育現場是零成本試點通路（Stage 4.4） |
| **學術資料集** | Phase B＋蓄水 | 首個「組件結構標註＋真實軌跡＋生成導向」開放資料集，CC BY-SA |
| **文創入口** | 現有（凍結）| 印章/文字雲/曼陀羅當流量入口可以，不再加廣度 |

商業化備註：若未來走商用，資料鏈必須繞開 g0v（教育合理使用）——以 MMH（LGPL）＋CNS（政府開放）＋使用者自有資料為商用鏈。這是 §10-P7 的由來。

---

## 10. 策略原則（未來修訂本檔時的憲章）

- **P1 能量跟著存在理由走**：任何新工作先過「是否推進三維交集」測試；不推進者進 Line B 凍結區或 spinoff 清單。這是 6/19 與本檔共同的最高原則。
- **P2 閘門式推進**：大 phase 先 spike 壓最大不確定性，kill criteria 在動工前白紙黑字。不允許「先做做看再說」進入多週投入。
- **P3 縮小拍板點**：一次只請使用者 sign-off 3-4 sessions 的量；大承諾必須有數據墊底。針對「推薦懸置」的歷史病灶。
- **P4 資料 > 直覺**：推廣/蓄水/砍功能的判斷以儀表數據為準；沒有數據先補儀表再決策。
- **P5 Session-sized 切步**：每步單 session 可閉合＋明確驗收，配合間歇運作模式；不可閉合的步驟要再切。
- **P6 一手資料源**：新資料源先問「能否取得官方一手文件」（Taiwan-variant integrity 前例）。
- **P7 授權邊界**：商用路徑只依賴可商用資料鏈（MMH/CNS/使用者自有）；教育限定源（g0v）標記清楚不混用。
- **P8 治理不變量**：§3.10 default-deny git workflow、QODA、決策日誌三件套、PRINCIPLES 索引——不因趕進度豁免。
- **P9 凍結不是刪除**：Line B 維持可用、只修 bug；解凍需通過 P1 測試＋寫決策日誌。

---

## 11. 風險登錄（供修訂時對照）

| 風險 | 等級 | 緩解 |
|---|---|---|
| Spike 命中率不達標 | 中 | kill criteria 明確，損失上限 2 sessions；失敗報告本身是學術素材 |
| 間歇節奏中斷 Stage 3 | 中 | 每步獨立可閉合；中斷後任一步可單獨恢復 |
| 蓄水後仍無使用者 | 中高 | Stage 4 才投入、且先小規模試點量測留存，不做大推廣 |
| Render free tier 資料消失 | 高（現況既存）| Stage 4.1 前不宣傳 gallery；現有資料視為可拋 |
| bus factor = 1 | 長期 | 文件治理持續＋資料集/格式開放（別人可接手資料再造工具） |
| 授權爭議 | 低 | P7 邊界＋現有 LICENSE 對照表 |

---

## 12. 落地備註（§3.10 git workflow）

sandbox 產檔、不在 sandbox commit。本檔對應 commit-msg：`docs/_commit_msg/2026-07-05_01.txt`。主機端 PowerShell 執行：

```
cd C:\Users\USER\Documents\Cowork\stroke_order
git add docs/PROJECT_PLAN_2026-07-05.md
git add docs/PROJECT_PLAN_2026-06-19.md
git add docs/_commit_msg/2026-07-05_01.txt
git commit -F docs/_commit_msg/2026-07-05_01.txt
git push origin main
git push backup main
```

---

## 修訂歷史

- 2026-07-05：初版。取代 `PROJECT_PLAN_2026-06-19.md`。對焦決議：開放重估戰略、每週數 session 節奏、閘門式推進。sign-off 範圍縮小為 Stage 0＋Stage 1。
