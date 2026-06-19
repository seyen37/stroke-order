# 工作日誌 — 2026-06-19（重新規劃 + 程式現況檢視 + zentangle 測試修正 + README badge）

**主軸**：本 session 橫跨兩 repo。前段在 personal-playbook 做同步檢查（pull 已最新、雙遠端 0/0 同步）。主段在 stroke-order：全 repo 唯讀盤點 → 產出統整主檔 `PROJECT_PLAN_2026-06-19.md`（全貌地圖 + 3 產品線 + 戰略抉擇）→ 實機把程式跑起來確認健康 → 修一條開發機誤判 fail 的 zentangle 測試 → 更新落後的 README badge。0 產品程式碼變更。

> 🔗 **前段同步檢查**：見 personal-playbook `docs/decisions/2026-06-19_sync_check_pull_backup.md`（commit `c9af2ee`）+ `WORK_LOG_2026-06-19_stroke-order.md`。

---

## Session 概觀

| 段 | 內容 | Commit |
|---|---|---|
| personal-playbook 同步檢查 | pull --ff-only（已最新）+ fetch backup 比對 0/0 同步 | (該 repo `c9af2ee` / `12f37ad`) |
| stroke-order 重新規劃 | 全 repo 盤點 → 統整主檔（地圖 + 3 產品線 + 戰略抉擇）| `b0295f4` |
| 程式現況檢視 | sandbox 安裝/CLI/serve/核心測試 + 主機 venv `.[web]` + 全套 pytest | (純驗證) |
| zentangle 測試修正 | 缺字型測試改 deterministic（修開發機誤判 fail）| `bb4de5d` |
| README badge | version 0.14.0→0.14.133、tests 1057→1511 | `f2700c8` |
| 收工三件套 | 本 journal + decision + personal-playbook WORK_LOG | (本 commit) |

**狀態**：local = origin = backup（三方對齊至最後 commit）/ 版本 0.14.133 不變 / 全套 **1511 passed / 49 skipped / 0 failed**。

---

## 今日完成

### A. 重新規劃（PROJECT_PLAN_2026-06-19.md）
全 repo 唯讀盤點（21 exporter / 12 資料源 / ~50 web 端點 / 70 test 檔 / 63 decision）後，把「太多」收斂成 3 條產品線：
- **Line A VISION 主線**（軌跡×組件化×個人風格）：Phase A ✅、B/C/D ✗ — 存在理由卻停擺。
- **Line B 設計工具**（wordart/zentangle/mandala…）：成熟、廣度過剩 → 建議維護凍結。
- **Line C 社群平台**（gallery/部署）：成熟、低成本維運。
核心診斷：能量配置與戰略價值倒掛。推薦回主線 Phase B（待 sign-off）。

### B. 程式現況檢視（健康）
- sandbox：`pip install -e .` 成功；CLI（info/convert svg+gcode）正常、即時抓 g0v；核心測試 93/93。serve 啟動、API 200。
- 主機：venv + `pip install -e ".[web]"` 成功（cairosvg 在 Windows 也裝起來）；CLI/serve/UI 全綠；全套 pytest **1511 passed / 49 skipped**。

### C. zentangle 缺字型測試修正（bb4de5d）
- 根因：測試 `_kaishu_available()` 只查寫死的 `/tmp/moe-kaishu/...`，與端點實際解析 `~/.stroke-order/kaishu-fonts/` 不一致 → 開發機（有字型）誤判 fail。
- 修法：不動共用 helper，改把缺字型測試自我 force-missing（monkeypatch env + reset 單例）→ deterministic。

### D. README badge（f2700c8）
- version 0.14.0→0.14.133、「目前版本」0.13.0→0.14.133、tests 1057→1511；歷史段保留。

---

## 過程要點 / 教訓

- **跨邊界讀寫**：host git/Edit 後 sandbox mount 會 stale/torn（讀到半寫入 SyntaxError）。改用 Read 工具直讀 host 驗證。
- **共用 helper 別亂改**：第一版改 `_kaishu_available()` 把 1 fail 變 2 fail（它被 3 處共用）；立即 revert、改特定測試本身。
- **debug ground truth first**：錯誤訊息裡的實際 font path 才揭露 fixture 釘了 env；先看實際值再修，別盲推。
- **stale index.lock**：raw git 撞鎖 → 先 `Remove-Item .git\index.lock -Force`（pull/push.ps1 已內建）。
- 全程 §3.10：sandbox 0 git-write、commit 由主機端 `-F` 跑；QODA 戰略抉擇等 sign-off。

---

## 待辦 / 後續（依 PROJECT_PLAN 優先序）

1. **zentangle 4 條 curve 軸視覺驗證**（6z dangling thread，看 demo confirm/退回）。
2. **Phase B KanjiVG 對齊器 spike**（主線；驗收：明→切出日/月組件樣本），待 sign-off。
3. **Line B 維護凍結**決策（停止加新廣度，能量回 Line A）。
4. Service Worker offline（Line C 短債，替主線蓄真實手寫資料）。

---

## 產出檔案

- stroke-order：`docs/PROJECT_PLAN_2026-06-19.md`、`tests/test_zentangle_server.py`、`README.md`、本 journal、`docs/decisions/2026-06-19_replan_and_kaishu_test_fix.md`。
- personal-playbook：`WORK_LOG_2026-06-19_stroke-order.md`（同步檢查另見 `docs/decisions/2026-06-19_sync_check_pull_backup.md`）。

---

## 結語

本 session 把 stroke-order 從「功能爆量、戰略主線停擺」盤點成一張可讀的 3 產品線地圖，並順手清掉一條誤判測試與過時 badge——全套 1511 tests 全綠、三方同步。下一步的戰略抉擇（回主線 Phase B vs 續維護廣度）已備好選項，待拍板。

---

*由 Claude 協助整理，seyen37 審閱。*
