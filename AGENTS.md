# AGENTS.md — 給 AI 代理的入口

> 本檔只指路，不重複內容。細節以各連結檔為準；與連結檔衝突時以連結檔為準。
> 同步鎖：`tests/test_agents_md.py` 會檢查本檔提到的路徑都真的存在。

## 這是什麼

stroke-order：筆順練習紙產生器（FastAPI 單體＋原生 HTML/JS，無前端框架、
無打包）。線上部署在 Render（origin `main` 推上去自動部署）。

## 動手前先讀

1. `DESIGN.md`——UI 唯一設計事實源。先看 §9「AI 代理提示指引」；教師頁看
   §10（元件使用時機表 §10.4），要加主題看 §11。
2. `docs/PRINCIPLES.md`——工程原則（編號引用，如 §61 終局測試）。
3. `docs/BLUEPRINT.md`——路線圖與「證據先於建設」原則。
4. `docs/decisions/`——ADR；做非小事決策前先找有沒有前例。

## 怎麼驗證

- Python：`python -m pytest -q`（`tests/`）。
- 前端純邏輯：`node --test tests/*.mjs`。
- 改 UI：截圖目視（桌機＋375px 手機寬），確認無橫向捲動、無 console error。

## 專案慣例（違反會紅燈）

- 版本：只改 `pyproject.toml` 的 `version`；README 徽章由收工腳本自動同步。
- 頁面：靜態檔放 `src/stroke_order/web/static/`，路由在
  `src/stroke_order/web/routes/pages.py` 用 `_versioned_page`；HTML 內引用
  一律帶 `?v=__V__`（伺服器注入版本，破快取）。
- 新路由：同步更新 `tests/test_route_snapshot.py`；要計數就在
  `src/stroke_order/web/server.py` 的計數桶登記。
- 色彩與元件：照 `DESIGN.md`，改顏色變數時文件與 CSS 同一批改
  （`tests/test_design_md.py`）。
- 教育部辭典資料是 CC BY-ND：原文呈現、不改寫。

## 交付流程

- 代理**不 commit、不 push**。改好的檔案交給維護者；commit 由維護者在本機
  跑 `收工檢查.bat`（全測試綠才 commit），訊息檔放
  `docs/_commit_msg/YYYY-MM-DD_NN.txt`（台北日期，腳本用最新一份）。
- 每輪留紀錄：`docs/WORK_LOG_YYYY-MM-DD.md`；決策寫 ADR 到 `docs/decisions/`。
- 部署驗證**只讀**：不要對正式站送寫入請求，也不要打會計數的頁面或 API
  （會汙染使用量數據）；用 `/static/...` 檔案內容或 `/api/metrics` 判斷。
