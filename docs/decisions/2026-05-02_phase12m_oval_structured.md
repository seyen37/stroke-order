# 2026-05-02 — Phase 12m-1 橢圓章結構化 + T-02 業界 layout（5 round）

<!-- retrofit 2026-05-02：原檔名 2026-05-04_phase12m_oval_structured.md，內部日期 5-04。git commit 5-02 02:45-04:08 (+0800)，align commit date 後重命名。 -->

> 把橢圓章從「單一 text 字串平均分 1-2 行 horizontal」重構成業界橢圓章標準格式：上弧文 + 中央 1-3 行水平 body + 下弧文。User 上傳 8 張業界範例圖驅動，連續 5 個 patch round（r0-r3）做出貼近 T-02 復刻效果。**這次新增最多的 architecture decisions** — 結構化 vs separator / 弧文方向 / 弧長均分 / UI default init time / oval 比例。

**版號變化**：0.14.17 → 0.14.21（連 5 個 bump）
**Commits**：63be79f / eb30c42 / 55ebd13 + r3 pending
**對話 / 工作期間**：5 個 patch round across 同一 day session

---

## 整體脈絡

12l 結束後 user 上傳 8 張業界橢圓章範例圖（T-01 ~ T-06、TT-01 ~ TT-06 系列、可調日期 A-D）要求對齊。原本的 oval preset 只把單一 text 拆 1-2 行水平 — 跟業界差太遠：
- 沒有上下弧文
- 沒有中央 multi-line body 階層（標題大 / 聯絡小）
- 沒有雙框
- 沒有裝飾元素

從 8 張圖萃取共識 anatomy → 拆 5 個 phase（12m-1 ~ 12m-5），先做 12m-1 核心 layout，後續 phase 累進。

整個 12m-1 連續 5 round（r0 + 4 patches），每 round user 看 PNG/截圖 → 提具體反饋 → 我做小改動 → 部署再驗。最終貼近 T-02 reference。

---

## 決策 1：結構化 input vs separator hack

**觸發**：oval 從單一 `text` 字串升級到 5 個語意獨立欄位（上弧 / 中央 1/2/3 / 下弧），API 怎麼接？

**選項**：

| 編號 | 方案 | 範例 |
|---|---|---|
| A | 結構化欄位（5 個獨立 input） | `oval_arc_top: str`、`oval_body_lines: list[str]`、`oval_arc_bottom: str` |
| B | Single text + separator hack | `text="紅棠文化\|收發章\|電話:...\|新北市..."` |

**考慮的因素**：
- User 心智模型清晰度
- API field 自我文件化
- empty / optional 欄位處理（不需 escape separator）
- 未來擴充性（如 per-arc font size）
- API surface area 增加

**選擇**：☑ A 結構化

**理由**：

A 的 user mental model 直接（5 個 input 對齊 5 個語意）。B 雖然 backward compat 容易（沿用既有 `text` field）但需要 user 學 separator 規則 + 處理 escape + 限制未來擴充（加新欄位 break separator schema）。**結構化 schema 一直是 long-term 對的選擇**，多 3-5 個 fields 不算大代價。

向後兼容：當 `oval_*` 全空 + 用既有 `text` 時，fallback 到舊 1-2 行 horizontal layout（不破既有 oval test）。

**後續驗證 / 結果**：✅ T-02 復刻成功，user 看 UI 5 欄位即懂使用。Backward compat tests 全綠。

---

## 決策 2：弧文 char rotation（朝外 vs 朝上 vs 切軸）

**r0 + r1 兩輪迭代決策。**

**觸發**：弧文 char 沿曲線，rotation 該怎麼定？

**選項**：

| 編號 | 上弧 rotation | 下弧 rotation | 視覺 |
|---|---|---|---|
| A 全朝外 | θ + 90° | θ + 90° | 上弧頭朝上正立、下弧頭朝下倒立（user 看要轉頭讀）|
| B 上朝外下朝外 | θ + 90° | θ − 90° | 上弧頭朝上、下弧頭朝上（**腳**朝下朝外）— 兩弧都正讀 |
| C 全朝上 | θ + 90° (top), 0 (bottom) | 兩弧字都直立 | 下弧字身跟弧 baseline 不貼合 |

**r0 選 A**（user 原話「頂部朝外」）。
**r1 改 B**（user 反饋「下弧字身倒立讀不通，改正立」）。

**理由（r1 修正）**：

A 對 top arc OK（頭朝上 = 自然 reading direction），但下弧頭朝下意味著 user 看視覺要倒轉腦袋 — 業界橢圓章 majority 是下弧字身正立（如 T-02 reference 顯然如此）。改 B 只需要改 `rot_offset = -90.0` 一行。

C 字身直立但腳不貼弧 baseline，視覺上 chars 會看起來「漂浮」不貼曲線，業界沒看到這種設計。

**後續驗證 / 結果**：✅ r1 PNG 顯示下弧「試題市試題區...」chars 正立讀左→右，user 確認對齊 reference。

---

## 決策 3：弧文字距 — 角度均分 vs 弧長均分（r2 重要）

**觸發**：r1 PNG 顯示「中央字距比邊緣字距寬」。User 要求修正。

**選項**：

| 編號 | 方案 | 字距特性 |
|---|---|---|
| A 角度均分（既有）| 每字 t = i / (n-1) × span，cos/sin 取點 | 字距隨橢圓曲率變化（apex 寬、sides 窄） |
| B 弧長均分 | 數值積分 ds/dt = √(a²sin²t + b²cos²t)，反查 t | 等視覺距離 |
| C 取捨折衷（hybrid） | 部分 angular 部分 arc-length 加權 | 複雜、無明顯好處 |

**選擇**：☑ B 弧長均分

**理由**：

A 的數學原因：橢圓 ds/dt 在 a≠b 時隨 t 變化，apex（短軸方向）每角度步進對應更長弧長 → 字看起來分得開。在 a:b = 1.43:1 (50×35) 的橢圓上，這個差異視覺明顯。

B 用 200 樣本 trapezoidal numerical integrate 建 (t, cumulative arc length) lookup table，反查每字的 target arc length 對應的 t。Performance：每張章 1-2 次 call，每次 ~0.3ms（compared to network RTT 10-100ms 完全 negligible）。

C 沒明顯優勢，捨棄。

**後續驗證 / 結果**：✅ 11 字均分後 pairwise Euclidean distances max/min ratio = **1.007**（接近完美等距，was 視覺明顯不均）。**新加 2 個 uniform-spacing 測試**驗證 ratio < 1.05。

---

## 決策 4：UI default 套用時機 — change-only vs init-time

**r3 的關鍵 fix。**

**觸發**：r1 設了 `oval default = double_border ON` 但 user 截圖顯示 checkbox 沒勾。

**選項**：

| 編號 | 方案 | 行為 |
|---|---|---|
| A change-only hook（既有）| `$("st-preset").addEventListener("change", stampApplyPresetDefaults)` | user 切換 preset 才套 default，初次載入維持 HTML 寫死 default |
| B 改 HTML 預設勾選 | `<input type="checkbox" checked>` 寫死 | 但其他 preset (square_*) 不該勾，會出現 wrong default |
| C init-time + change | 既有 listener + `stampApplyPresetDefaults()` 收尾呼叫 | 初次載入也跑一次 default |

**選擇**：☑ C init + change

**理由**：

A 的問題：user 第一次進站 preset 已停在 oval 但沒 fire change → JS 不跑 → checkbox 維持 HTML 預設（unchecked）。**這是 first-time UX 的常見 bug pattern**。

B 雖簡單但會 break 其他 preset（square_name 不該勾雙框）。

C 在 `stampInit()` 結尾加一行 `stampApplyPresetDefaults()` 即可，覆蓋兩種觸發路徑（init 跟 change），最 robust。

**後續驗證 / 結果**：⏳ pending — r3 commit 因 cross-session git index.lock 卡住未 push，user 端執行才能驗證。後端邏輯（`render_stamp_svg` with `double_border=true` 出 2 個 border path）已 confirmed 正確。

---

## 決策 5：橢圓比例 50×30 (1.67:1) → 50×35 (1.43:1)

**r2 的次要決策。**

**觸發**：user 要求「調整橢圓曲率，參考範例比例」。

**選項**：

| 編號 | 比例 | 業界對應 |
|---|---|---|
| A | 50×30 (1.67:1)（既有）| 較扁，5×3 cm 公司用章 |
| B | 50×35 (1.43:1)（新）| 4-6 cm 級橢圓章常見 |
| C | 50×40 (1.25:1) | 較圓，少見 |

**選擇**：☑ B 50×35

**理由**：

User 的 reference 圖目測長寬比 ~1.4:1，最接近 B。B 也是台灣業界 4.5×3.0 / 5×3.5 cm 級橢圓章常見比例。A 偏扁，C 偏圓不像常見業界橢圓。

**後續驗證 / 結果**：✅ 視覺對比 50×30 vs 50×35，B 明顯更接近 reference。

---

## 沒做的決策（明確擱置）

- **12m-2 雙框 inner-ellipse-around-body 變體**：既有 `double_border` (concentric ellipse) 已涵蓋 user 對「內框」的需求。如 user 反饋仍想要 inner ellipse 只圈 body 區（body 在 inner、弧文在 inner-outer 之間 ring band）才動。
- **12m-3 ❀ 裝飾花**：拆給後續 phase。本次先驗收核心 layout。
- **12m-4 可調日期紅色欄**：複雜（民國 / 西元、年月日格式），延後。
- **Per-line font size override**：body 各行 char size 已 auto-fit by usable width（短行大、長行小），自然形成階層。不引入手動 override。
- **弧文反向（朝內）**：majority 業界是朝外，朝內是少見變體。如 user 反饋再開 toggle。

---

## 學到的規則 / pattern（適用未來）

### 結構化 input > separator hack

**觸發點**：當功能 input 有多個語意獨立欄位（如 oval 5 段），改成結構化 fields 比 single text + separator 好。Mental model + UX + 未來擴充性都贏。

**反例**：CSS `font` shorthand `"bold 14px/1.5 Arial"` — 多欄位塞 single string，難 parse、難擴充、易 escape bug。後來 modern CSS 自己拆 `font-weight`、`font-size` 等獨立 property。

**正例**（本日 12m-1）：5 個獨立 API field 直觀、可選欄位 empty string 自動 skip、UI 5 個 input 對齊。

→ 寫進 PROJECT_PLAYBOOK §8.13 候選。

### UI default 要 hook init time，不只 change

**觸發點**：UI 控件 default state 依賴 JS 在 dropdown 變動時填入 → 首次載入時 default 不一致。

**症狀**：user 截圖顯示某個依賴 default 的 UI 元素（checkbox / hint / size）跟 expected 不一致。**Likely 不是 deploy 問題，是 init time hook 漏掉**。

**規則**：所有 `xxxApplyDefaults()` 必須在 `xxxInit()` 收尾呼叫一次：

```js
$("preset").addEventListener("change", applyDefaults);
applyDefaults();   // ← 這行不能漏
```

→ 寫進 PROJECT_PLAYBOOK §8.14 候選。

### 弧長均分（domain-specific，記在這）

橢圓 / 任意參數曲線上分布元素，等參數步進 ≠ 等視覺距離。需 numerical integrate `ds/dt` 建 lookup table 反查。

實作 200 樣本 trapezoidal 已夠精細（max/min ratio = 1.007）。Performance 不是問題（每 call ~0.3ms）。

→ 不寫 playbook（太 niche），記在本決策紀錄。

### 多輪 reference-image-driven SOP

跟 §8.7 morning audit + §8.11 prototype SOP 連動：

1. User 提供 reference image / screenshot
2. AI 從 image 萃取 anatomy / 關鍵元素
3. AI 寫 plan + 列關鍵 design question（2-3 個關鍵抉擇）
4. User 二選一答（不需深思就能決定的 design call）
5. AI 動工 + 視覺驗證（render PNG 比對）
6. Bump version 每 round + commit message 對齊
7. 部署 + user screenshot → 下一 round

5 輪做下來，從「平均 1-2 行 horizontal」到「貼近業界 T-02」。每輪 < 30 分鐘 turn-around。

→ 不另立章節，跟 §8.7 / §8.11 連動。

---

## 相關檔案

- 工作紀錄：[`docs/WORK_LOG_2026-05-02_phase12l_12m.md`](../WORK_LOG_2026-05-02_phase12l_12m.md)
- 12l 同日決策：[`docs/decisions/2026-05-02_phase12l_official_multi_short.md`](2026-05-02_phase12l_official_multi_short.md)
- 程式碼異動（5 round 累計）：
  - `src/stroke_order/exporters/stamp.py`：+5 helpers (`_oval_arc_positions` / `_oval_arc_char_size` / `_oval_body_layout` / `_ellipse_arc_length_table` / `_t_at_arc_length`)，oval 分支新 layout
  - `src/stroke_order/web/server.py`：StampPostRequest +3 oval fields，POST/GET plumbing
  - `src/stroke_order/web/static/index.html`：oval 5 欄位 UI block + dynamic show/hide + JS init fix
  - `tests/test_stamp.py`：+18 個 oval 測試 + 2 個 uniform-spacing 測試
- Commits：`63be79f`（r0）、`eb30c42`（r1）、`55ebd13`（r2）、r3 pending
