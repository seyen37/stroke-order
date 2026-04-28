# 2026-04-28：Phase A Backend Foundation（VISION.md 落地第一步）

> 範圍：依 VISION.md Phase A 規劃，落地組件覆蓋分析器的 backend 基礎建設（不含 API、不含 UI）。
>
> 起點：VISION.md 戰略 + 808 實證已就緒，但 codebase 完全沒有「組件」相關模組。
> 終點：`stroke_order.components` 子套件含 4 個模組（ids / decompose / coverset / algorithm）+ 43 條測試全綠 + 既有測試無回歸。
>
> 對應 commits（待提交）：
> - `feat(components): Phase A backend foundation — IDS, decompose, coverset, greedy`
>
> Tasks: 6b-1 ~ 6b-4

---

## 決策 1：5 個架構決策一次定案（vs. 邊做邊改）

**情境**：Phase A 涉及多個架構選擇——資料源、儲存位置、模組分割、API 形狀、UI 整合策略。每個都有合理的兩三條路。

**選項**：
- A. 邊寫邊決定（每個檔案開工時再選）
- B. 動工前一次擺出所有決策，請使用者點頭再做

**決定**：B。

**5 個關鍵決策**（使用者已確認）：

| 編號 | 決策 | 理由 |
|---|---|---|
| A1 | cjkvi-ids 為主、KanjiVG 為輔 | Phase A 只需結構不需軌跡，IDS 88K 字覆蓋極廣 |
| A2 | 個人覆蓋追蹤用 IndexedDB（非 SQLite）| 與 5d PSD 同站，避免新增 server-side state |
| A3 | 新建 `components/` 子套件 + 4 模組 | 命名空間清楚，與既有 `decomposition.py`（朱邦復 5000 字）區隔 |
| A4 | 4 個 API endpoints | components / coverset×2 / coverage |
| A5 | 整合到現有 5d 控制面板（不開新分頁）| 使用者不需切換 context |

**考量**：使用者偏好的工作模式是「3 步以上先計畫、確認後再做」。一次提綱挈領的好處：(a) 對齊期待 (b) 避免實作中半路改方向 (c) 決策變成 commit message 的素材，未來人讀懂為何這樣做。

**教訓**：架構決策上桌一次比邊做邊改省時間。實作 2 小時的工作，前 15 分鐘規劃可省後段 1 小時的反覆。

---

## 決策 2：ids.txt（2 MB）bundle 進 package vs. 不 bundle

**情境**：cjkvi-ids 的 ids.txt 是 2 MB 文字檔，分析器跑起來必備。

**選項**：
- A. Bundle 進 package（commit 進 git，pip install 就有）
- B. 寫下載腳本，第一次執行時抓
- C. 抽取相關 subset bundle 進 package（例如只 808 + 5000 + closure）

**決定**：A。

**考量**：
1. **既有先例**：專案內 `data/5000_wuqian.txt`（590 KB）就 commit 在 repo 裡且打包進 package
2. **使用體驗**：B 方案要求第一次 import 時打網路，會在離線環境失敗——對打包/部署不友善
3. **Repo 大小**：git repo 整體已 ~50 MB（含 cache、SVG、JSON），多 2 MB 文字無感
4. **資料更新頻率**：cjkvi-ids 一年發布 1-2 次更新；commit 本身就是版本鎖定機制
5. **C 方案複雜度**：subset 萃取要寫額外工具 + 維護兩份資料源，得不償失

**實作**：
- Path：`src/stroke_order/components/data/ids.txt`
- `pyproject.toml` 加 `"stroke_order.components" = ["data/*.txt", "coversets/*.json"]`
- `ids.py` 用 `importlib.resources.files()` 跨環境取路徑（`pip install -e` / `pip install` 都對）

**教訓**：「2 MB 是大還是小」要看 context。對個人專案 + 內含書法資料的工具，2 MB 是 acceptable cost；對 web app js bundle，2 MB 就災難。判斷時看 repo 已有的尺度而非絕對值。

---

## 決策 3：葉組件遞迴深度——「校」應該分解到第幾層？

**情境**：寫 `test_recommend_first_pick_maximizes_gain` 時，假設「校 = ⿰木交」分解出 2 個葉組件（木、交）。實際跑出 6 個（木 + 交遞迴到 一、丿、丶、八、…）。

**問題**：演算法是錯了還是測試錯了？

**選項**：
- A. 限制 decompose 深度為 1（只取直接子組件）
- B. 完全遞迴到原子層（包含 stroke-level 組件如 一、丿、丶）
- C. 中間層（停在「能用 KanjiVG 對齊出軌跡」的層次）

**決定**：B（完全遞迴），改測試而非改演算法。

**考量**：
1. **VISION.md 要求**：使用者寫了一個字，系統自動切出**能用組件**作為訓練素材。「組件」一詞涵蓋從部首到單筆——演算法不該人為砍層
2. **A 方案問題**：「交」這層在 KanjiVG 上往往沒有對應的部件（不是 214 部首），停在這層反而失去更深的對齊機會
3. **C 方案問題**：「能用 KanjiVG 對齊出軌跡」是 Phase B 才會碰的問題；在 Phase A 不該為它留接口
4. **B 的好處**：演算法產出最完整的覆蓋資訊；上層想做粒度過濾的話，再寫一個 `decompose_to_depth(char, depth)` wrapper 即可

**實作差異**：把測試 `assert recs[0].gain == 2` 改為 `assert recs[0].gain > 2 and recs[0].char == "校"`，並加註解說明為何 leaves 比想像中多。

**教訓**：**測試失敗時，先問「假設錯還是實作錯」**——這次是假設錯。如果直接改演算法以 fit 測試，會傷到 VISION.md 的核心承諾。

延伸教訓：寫測試時，**只測「演算法應該保證的不變量」**（first pick gain 最大、不重複推薦已寫字、零增益不入推薦），不要測「我以為的具體結果值」。

---

## 決策 4：cover-set JSON 從 data/ 搬到 package 內

**情境**：之前（昨天 6a-4）`build_808_dataset.py` 把 808 字單寫到 `data/cjk_common_808.json`。現在要進 package，**保留兩處**還是**單一真實來源**？

**選項**：
- A. 兩處都保留（data/ 給 build script，package 給 runtime）
- B. 只留 package（runtime 唯一來源），build script 直接寫到 package
- C. 只留 data/，package 透過相對路徑讀取

**決定**：B。

**考量**：
- 兩處同步=技術債：一旦 schema 改，要記得手動同步兩份
- C 方案要 `pip install` 後仍能讀 data/——但 pip 安裝後 data/ 不存在
- B 方案讓「跑 build_808_dataset.py」就直接更新 package 真實資料，零中間步驟

**實作**：
- `build_808_dataset.py` 輸出路徑改為 `src/stroke_order/components/coversets/cjk_common_808.json`
- `analyze_808_components.py::load_808()` 改用 `load_coverset("cjk_common_808")`
- 沙箱限制無法直接刪 `data/cjk_common_808.json`——commit 指令含 `git rm` 由使用者執行

**教訓**：當引入 package-level 資料夾時，要確保**所有寫資料的腳本**也指向新位置。否則 N 個月後發現「為什麼 data/ 跟 package 內容不一致」會很頭痛。

---

## 決策 5：寫 4 個 modules 還是合一個大 module

**情境**：Phase A 的 logic 全部塞 `components.py` 一個檔案 vs. 拆 4 個（ids / decompose / coverset / algorithm）。

**決定**：拆 4 個。

**考量**：
1. **單一職責**：每個檔案有清楚的責任邊界，function naming 不會撞
2. **測試 colocate**：`test_components_ids.py` 對 `ids.py`，1:1 對應好導航
3. **未來 Phase B/C 擴展**：軌跡切割（Phase B）、組合引擎（Phase C）會新增 `tracing.py`、`composer.py` 等。今天合在一起，明天還是要拆
4. **檔案大小**：每檔 100-200 行，閱讀無壓力。一個 600 行的 `components.py` 反而難讀

**反面考量**（沒採用）：
- 「拆檔有導入成本」——這是 Python 不是 C 系，import 4 個檔案沒有任何 runtime 成本
- 「太多檔案 navigation 困難」——VS Code 有 `__init__.py` 統一 export，IDE 跳轉無感

**教訓**：模組化的 cost 是**寫的人多花 5 分鐘想分割線**，benefit 是**未來讀的人省 30 分鐘**。對長期專案，拆比合好。

---

## 今日數字

| 維度 | 數字 |
|---|---|
| 新增模組 | 4（ids、decompose、coverset、algorithm）|
| 新增程式碼行數 | ~600 行（src 約 350 + tests 約 250）|
| 新增測試 | 43 條（10 + 12 + 9 + 12）|
| 既有測試無回歸 | 62/62 含 sample 回歸 ✅ |
| Bundled 資料 | ids.txt（2 MB）+ cjk_common_808.json（76 KB）|
| 工作時長 | ~3 小時（含 debug + 測試修正）|

---

## 對 Phase A 後續的影響

完成這個 backend foundation 之後：

1. **6b-5 ~ 6b-7（API 三件套）** 變成「機械操作」——logic 全在 package 裡，FastAPI route 只是 thin wrapper。預估 1.5 小時。
2. **6b-8 ~ 6b-10（UI 整合）** 是純 frontend 工作，後端介面已穩定，可獨立開發。
3. **6b-11（教育部 4808 cover-set）** 只需仿照 808 的方式產 JSON，不需新模組。
4. **6b-12（version bump + 全套回歸）** 是 release 時刻。

整個 Phase A 預估剩餘工作量 5-7 小時，可在下一個工作日完成。

---

## 反思

**做得好的**：
- 5 個架構決策一次擺出來、使用者一次點頭——避免實作中反覆討論
- TDD 反向發揮：測試失敗讓我們重新想「校到底有幾個葉組件」這個哲學問題，倒逼測試表達力升級
- 沒過早優化：演算法用 O(N×M) 的純暴力暫時夠用（808 字 × ~200 組件），Phase A 不需要 trie / hash-based 加速

**可以更好的**：
- regex 字串還是手寫（雖然這次沒踩到 PUA 注入 bug）。下次涉及 unicode range 一律 `chr()` 或 `\uXXXX`
- `data/cjk_common_808.json` 沒被刪（沙箱限制）——應該在動工前先確認檔案系統權限，會有更清楚的 commit 指令給使用者

**可以保留的方法論**：
- 寫 module 之前先寫 module docstring（這次每個檔案都有清楚的「做什麼、不做什麼」）
- 測試先測 invariant（不重複、零增益不入）再測具體值
- 把 phase 的「結束條件」寫進決策日誌，避免 phase 永遠開放

---

## 下一步建議

優先度：

1. **Push 這個 commit** 把 backend foundation 鎖定到 git
2. **下個工作日做 6b-5 ~ 6b-7（API）**——backend 既然 ready，API 化是低風險動作
3. **完整 Phase A 完成後再 bump 0.13.0 → 0.14.0**——依使用者 Q3 決定的 release 節奏
