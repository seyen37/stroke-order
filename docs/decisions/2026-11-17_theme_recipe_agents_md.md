# ADR — 主題配方＋元件使用時機表＋AGENTS.md

- 日期：2026-11-17
- 版本：0.14.303 → **0.14.304**
- 狀態：已實作（純文件＋守門測試，無執行期改動）
- 相關：DESIGN.md §9、§10.4、§11（本輪新立）；ADR `2026-11-16_teacher_theme.md`

## 脈絡

使用者轉貼 Meta 開源設計系統 Astryx 的介紹（2026-06 開源、MIT、Beta、
React 19＋StyleX、150+ 元件、七套主題、附 AGENTS.md／CLAUDE.md 與 CLI 文件）。
評估結論：**不導入**——本站是原生 HTML/JS、無打包，DESIGN.md 明訂不引框架，
Render 免費層也不宜加前端建置；且它仍是 Beta。可借鏡的是兩個做法：
主題＝一組自訂屬性覆寫；設計文件寫成人與 AI 都能照做的形式。

## 決策（QODA，使用者選定）

1. **主題：只寫做法，不加新主題**（不選「做投影高對比主題」——目前沒有
   老師反映需求，Blueprint 原則 1 證據先於建設）。
   - DESIGN.md 新增 §11「新增一套主題的做法」九步：先有證據→選前綴→
     單一主題檔→語意→顏色表→對比→元件表→守門測試→頁面。
   - `tests/test_design_md.py` 的教師主題測試改成 `THEMES` 登記表＋
     `pytest.mark.parametrize`：新主題登記一筆，七項守門測試自動套上。
2. **AI 文件：§10.4 使用時機表＋根目錄 AGENTS.md**。
   - §10.4：教師主題 23 個 `.t-` class 各寫用途／什麼時候用／不要用在。
   - 雙向同步鎖：theme.css 有、表沒列 → 紅燈；表列了、CSS 沒有 → 紅燈
     （mutation 驗過兩個方向都會抓）。
   - `AGENTS.md`：只指路（先讀什麼、怎麼驗證、專案慣例、交付流程、
     部署驗證只讀），不重複內容。`tests/test_agents_md.py` 檢查它提到的
     路徑都存在，避免檔案搬家後帶錯路。

## 為什麼 AGENTS.md 刻意很短

內容若和 DESIGN.md／PRINCIPLES 重複，兩邊遲早不一致。所以它只放「去哪裡
看」和幾條違反就會出事的慣例（不 commit/push、部署驗證不打計數端點、
CC BY-ND 不改寫），細節一律連回原檔。

## 驗證

- `tests/test_design_md.py` 17 項全綠（含新 component_table、recipe 兩項）；
  mutation：刪掉 `.t-badge` 列 → 紅；表加不存在的 `.t-ghost-x` → 紅。
- `tests/test_agents_md.py` 2 項；全套 pytest 2,232 passed、node 344/344。
