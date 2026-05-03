# 工作日誌 — 2026-05-04

**主軸**：曼陀羅模式 r25–r27（環結構 / 線條顏色 / 檔案匯出匯入）+ 跨 phase 累積工作整理 commit

## Session 概觀

| 階段 | 內容 | 版本 |
|---|---|---|
| r25 | Mandala UI 改用「環」為組織單位（11 環 0–10，每環 10mm） | 0.14.103 → 0.14.104 |
| r26 | 線條顏色（11 色 preset + 自訂）+ G-code 按色分組 + ring 0 警示 | 0.14.104 → 0.14.105 |
| r27 | `.mandala.md` 匯出/匯入（純前端，本機儲存）+ SVG metadata 內嵌 | 0.14.105 → 0.14.106 |
| commit | 整理 5b r1/r3/r4–r26 + 12m-7 r39 累積工作為 4 個 commit | — |

## 重要里程碑

### r25 ring-based 結構重構

裝飾層 UI 從 flat list 改為「環為容器」的兩層樹結構：

```
md-rings-container
└── .md-ring-section[data-ring=N]      # 0–10 共 11 環
    ├── .md-ring-header                 # 環標籤 + 「+ 增加裝飾層」 + 「× 刪除環」
    └── .md-ring-layers
        └── .md-layer-row × N           # 全域層號 = ringIdx × 10 + localIdx
```

半徑單位從 `r_ratio`（0.05–1.0 抽象）改為 `r_mm`（mm 物理單位，0–200）。對寫字機軌跡更直觀，user 心智模型也更貼近實際機器。後端 `render_extra_layer_svg` 加 r_mm 優先 path，舊 r_ratio fallback 維持向後相容（preset 不需改）。

**112 prior + 4 r25 新 = 116 tests pass。**

### r26 三大新功能

1. **線條顏色**：曼陀羅常用 11 色 preset + 自訂 picker，3 處應用（主 mandala / 字布局 / 每 layer）。每處用 `<select>` + `<input type="color">` 雙控制，共用 helper `_mandalaWireColorControl(select, picker, hex)` 雙向 sync。
2. **G-code 按色分組**：`render_mandala_gcode` 改造成 color-aware — SVG walk 時繼承 stroke/fill，每 polyline 帶 color tag，輸出時按色分組（**首次出現順序 stable**，dict 插入順序保證），每 group 前 emit `; ===== COLOR: #xxx =====` 通用 comment。寫字機看 comment 就知道該換筆。
3. **0 環警示 banner**：條件性顯示（ring 0 唯一存在時），不打擾但精準涵蓋 user 痛點（剛打開 mandala 模式時）。

**108 prior + 8 r26 新 = 120 tests pass。**

### r27 純前端檔案匯出/匯入

雙 tier 並行：
- **Tier 1**：`.mandala.md`（YAML frontmatter 機器精確還原 + Markdown body 給人類/AI）
- **Tier 2**：SVG 內嵌 `<metadata><mandala-config><![CDATA[json]]></mandala-config></metadata>`，1 張 SVG = 視覺 + 完整還原資料

中文 + 拼音雙存（user 明確要求）：`metadata.title`（中文）+ `metadata.title_pinyin`（拼音 slug 給檔名）+ inline `# 拼音: xxx` 註解（人類可讀）。`pinyin-pro@3.20.4` CDN 載入。

Schema 命名 `stroke-order-mandala-v1` 對齊既有 `stroke-order-psd-v1`（抄經）— 未來 r28 上 gallery 共用 `gallery.html` + `uploader.js` 既有架構。

**116 prior + 14 r27 schema fixture tests = 130 mandala-related tests，加 wordart/web 共 173 pass。**

### Commit 整理（HEAD = stamp r38b 起）

工作目錄累積了 5b r1/r3/r4–r26 + 12m-7 r39 多 phase 工作從未 commit。處理為 4 個 phase-grouped commit：

```
609289a phase 5b r27: 曼陀羅檔案 .mandala.md 匯出/匯入（純前端，本機儲存）
84fdf2d phase 12m-7 r39: 職名章 (rectangle_title) 2-column 結構化欄位
e035a61 phase 5b r4-r26: mandala mode（從零到色彩 + G-code 分組）
d1f35dd phase 5b r1+r3: polygon consolidation + linear spread cell-centered
```

`server.py` + `index.html` 同時含 mandala (5b r4–r26) + rect_title (12m-7 r39) 改動，未強行 hunk 拆分 — commit message 誠實標註「對應 UI/API 改動已併入前一個 commit」。

## 過程中遇到的問題

### Cowork sandbox 限制

| 問題 | 解法 |
|---|---|
| 0-byte 垃圾檔 `1.5），` rm 失敗 (Operation not permitted) | 用 `mcp__cowork__allow_cowork_file_delete` 授權 |
| `.git/index.lock` stale (前一場 session 留下) | rm + 確認無實際 git process running |
| `git add` 連續多次撞 index corruption (`bad signature 0x00000000`) | rm `.git/index` + `git read-tree HEAD` 重建後改用單一 batched `git add` |
| GitHub SSH key 沒帶進 sandbox → push 撞 `Permission denied (publickey)` | Push 需 user 在自己 terminal 跑 |
| `github-backup` host alias 不在 sandbox SSH config | Backup remote 同樣需 user 處理 |

### 架構抉擇

| 議題 | 決定 |
|---|---|
| 半徑 UI 用 `r_ratio` (0–1) vs `r_mm` (mm) | r_mm 為主（user 心智模型 + 機器物理單位匹配），r_ratio 留 fallback |
| 單環容器 vs 多環樹結構 | 多環樹（user 明確要求 + 提升心智模型清晰度） |
| 全域永久警示 vs 條件性警示 | 條件性（ring 0 唯一時顯示，不打擾） |
| G-code 機器指令 (M6 T<n>) vs comment | comment（通用，不綁特定機器；寫字機可自訂） |
| 跨 phase commit 強行 hunk 拆 vs 誠實註明 | 誠實註明（hunk staging 風險高且耗時） |
| MD vs JSON for AI-friendly export | MD frontmatter + body 雙層（兩世界最佳） |
| 中文檔名 vs 拼音 slug | 雙存（filename 拼音穩，內容中文 AI 讀） |
| Server-side parser 一起做 vs 純前端先做 | 純前端先做（user 強調本機原則；r28 上 gallery 再補 server parser） |

## 統計

- **檔案異動**：5 個 source（mandala.py、wordart.py、server.py、index.html、stamp.py）+ 6 個 docs + 3 個 tests + 1 個 fixture
- **Test 數**：開始 ~108 → 結束 173 mandala/web/wordart 全 pass
- **新測試**：r25 +4 / r26 +8 / r27 +14 = 26 new tests
- **新 docs**：r25 / r26 / r27 三份 decision log + 1 份 session log（本檔）
- **新 memory（共通性原則）**：5 條（見下「共通性原則」section）
