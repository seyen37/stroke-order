---
layout: default
---

# 決策日誌：2026-06-19 專案重新規劃 + zentangle 缺字型測試修正

**日期**：2026-06-19
**版號變化**：0.14.133 → 0.14.133（無功能變更；文件 + 1 條測試修正）
**對話 / 工作期間**：Cowork session。開工先做 personal-playbook 同步檢查，之後轉到 stroke-order 重新規劃、程式現況檢視、修一條誤判 fail 的測試、更新 README badge。

---

## 整體脈絡

> 本 session 橫跨兩 repo。前段在 personal-playbook 做同步檢查（pull 已最新、backup 0/0 同步，紀錄見該 repo）。主段在 stroke-order：全 repo 唯讀盤點後產出統整主檔 `docs/PROJECT_PLAN_2026-06-19.md`（全貌地圖 + 3 產品線 + 戰略抉擇）、實機把程式跑起來確認健康、修掉一條在開發機誤判 fail 的 zentangle 測試、並更新落後的 README badge。0 產品程式碼變更。

---

## 決策 1：重新規劃用「統整主檔」切角，取代策略草案

**觸發**：使用者反映「專案太多」、要求統整 stroke-order 相關項目並重新規劃。

**選項**：

| 編號 | 方案 | 優點 | 缺點 |
|---|---|---|---|
| A | 純策略型 plan（done/doing/todo + Phase 抉擇）| 聚焦戰略 | 不解「太多」的全貌感 |
| B | 統整主檔：全貌地圖 + 3 產品線收斂 + 戰略抉擇 | 把爆量功能編成可讀地圖、診斷能量倒掛 | 較長 |

**考慮的因素**：
- 「太多」的本質是單一 repo 功能面爆量（21 exporter / 12 源 / ~50 端點），不是專案多
- 需要一張收斂框架讓 sprawl 可讀
- 與既有 VISION 四階段路線對齊

**選擇**：☑ B（取代/合併早先策略草案、同檔覆寫）

**理由**：
> 收斂成 3 條產品線（A VISION 主線 / B 設計工具 / C 社群平台）後，核心診斷浮現：能量配置與戰略價值倒掛——Line B（14/21 exporter）過投但屬周邊，Line A（組件化 Phase B/C/D）才是存在理由卻自 4/28 Phase A 後停擺。這個診斷只有全貌地圖才看得出來。

**後續驗證 / 結果**：✅ `docs/PROJECT_PLAN_2026-06-19.md` 產出並 commit `b0295f4`，雙遠端同步。戰略抉擇（回主線 Phase B）列推薦但待 user sign-off。

---

## 決策 2：zentangle 缺字型測試的修法——deterministic force-missing，不動共用 helper

**觸發**：實機 `pytest` 全套出現 1 fail：`test_outline_endpoint_503_when_font_missing`。

**根因**：該測試以 `skipif(_kaishu_available())` 控制，而 `_kaishu_available()` 只檢查寫死的 sandbox 路徑 `/tmp/moe-kaishu/edukai-5.1_20251208.ttf`。開發機字型裝在預設位置 `~/.stroke-order/kaishu-fonts/`，測試字型不存在 → 測試不被 skip 而執行，但端點用預設路徑找到字型回 200 → 誤判 fail。非產品 bug。

**選項**：

| 編號 | 方案 | 優點 | 缺點 |
|---|---|---|---|
| A | 改 `_kaishu_available()` 也查預設路徑 | 直覺 | **錯**：該 helper 被 3 處共用（正向測試 gate + fixture 釘 env + 缺字型 gate），改它會讓 fixture 把 env 釘到不存在的 /tmp 測試字型、反而打爛 2 個正向測試 |
| B | 不動 helper，把缺字型測試改成自我強制缺字型（monkeypatch env→不存在 + reset 單例 + 自建 client）| deterministic、與機器字型狀態脫鉤、本機/CI 一致 | 改動範圍稍大（1 條測試重寫）|

**考慮的因素**：
- helper 的共用面（先嘗 A 後實測 1 fail 變 2 fail，立刻 revert）
- 測試應 deterministic、不依賴機器字型安裝狀態
- 0 產品程式碼變更

**選擇**：☑ B

**理由**：
> A 方案實測把 1 fail 變 2 fail——因為沒先確認 `_kaishu_available()` 被幾處共用。revert 後改 B：缺字型測試自己 monkeypatch 一個不存在的字型路徑，無論機器有沒有裝字型都能正確測「缺字型→404/503」這條 graceful degradation。本機與 CI/sandbox 行為從此一致。

**後續驗證 / 結果**：✅ 實機 `pytest tests/test_zentangle_server.py -q` → 8 passed / 2 skipped / 0 failed；全套 **1511 passed / 49 skipped / 0 failed**。commit `bb4de5d`。

---

## 決策 3：README 只更新「目前版本」與 badge，歷史段保留不動

**觸發**：README badge（version 0.14.0 / tests 1057）落後實際（0.14.133 / 1511）。

**選擇**：☑ 更新 version badge、tests badge、「目前版本」標題、內文測試數；**保留**開發歷程／git history 段的 `v0.13.0` / `1057`。

**理由**：
> 開發歷程段的 `v0.13.0` / `1057` 描述「首次公開推送 GitHub 時」的狀態，屬歷史事實，改了會失真。只有「目前版本」是真正過時的。最小改動、不誤改歷史。

**後續驗證 / 結果**：✅ commit `f2700c8`，4 處更新、歷史段保留。

---

## 沒做的決策（明確擱置）

- **Phase B KanjiVG 對齊器 spike**：列入 PROJECT_PLAN 推薦，但屬戰略主線動工，待 user sign-off，本 session 不動。
- **zentangle 4 條 curve 軸視覺驗證**：dangling thread，待 user 看 demo 確認，本 session 不動。
- **Line B 維護凍結**：建議寫進 plan，但屬戰略決策、待拍板。

---

## 學到的規則 / pattern（適用未來）

1. **Read 工具直讀 host 比 sandbox bash 新鮮**：host git 操作 / Edit 寫檔後，sandbox mount 會 stale 甚至 torn（讀到半寫入、SyntaxError）。跨邊界驗證一律用 Read 工具讀 host，別信 sandbox 即時讀回。
2. **共用 test helper 改動前先盤呼叫點**：`_kaishu_available()` 被 gate + fixture + 另一 gate 三處共用，盲改連鎖打爛。改測試優先改「特定測試本身」而非共用判準。
3. **環境依賴的 skip guard 改成 deterministic**：缺資源測試用 monkeypatch force-missing，與機器狀態脫鉤，本機/CI 行為一致。
4. **第一版修錯要快 revert + 拿 ground truth 重診**：錯誤訊息裡的實際 font path（`\tmp\moe-kaishu\...`）才揭露 fixture 釘了 env——debug 先看實際值。
5. **stale `index.lock` from Cowork mount**：raw git 前先 `Remove-Item .git\index.lock -Force`；pull.ps1/push.ps1 已內建清除。

---

## 相關檔案

- 工作紀錄：`docs/journal/2026-06-19_session_log.md`
- 規劃主檔：`docs/PROJECT_PLAN_2026-06-19.md`（commit `b0295f4`）
- 測試修正：`tests/test_zentangle_server.py`（commit `bb4de5d`）
- README：`README.md`（commit `f2700c8`）
- 跨 repo：personal-playbook `WORK_LOG_2026-06-19_stroke-order.md` + 同 repo 同步檢查 decision `2026-06-19_sync_check_pull_backup.md`（commit `c9af2ee`）
