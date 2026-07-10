# stroke-order 專案統整與重新規劃（主檔）— 2026-06-19

> ⚠️ **SUPERSEDED（2026-07-05）**：本檔已由 [`PROJECT_PLAN_2026-07-05.md`](PROJECT_PLAN_2026-07-05.md) 取代成新主檔。本檔保留為歷史盤點（全貌地圖 + 3 產品線收斂仍有效，戰略抉擇部分以新檔為準）。

> **本檔取代 2026-06-19 早先的策略草案**，合併為單一主檔：全貌地圖 + 化繁為簡分析 + 戰略抉擇 + 下一步。
> 盤點基準：**v0.14.133**｜HEAD = origin/main = backup/main（同步）｜21 exporters｜12 資料源｜~50 web 端點｜70 test 檔（約 1,460 test fn）｜63 決策日誌
> 狀態：**草案**。第 5 節「主線抉擇」屬戰略決策，列了選項與推薦，**待你拍板才動工**（QODA）。

---

## 0. 為什麼做這份 ——「專案太多」的真正成因

你感覺「專案太多」，但 stroke-order 其實是**一個 repo、功能面爆量**：21 個 exporter、12 個資料源、約 50 個 web 端點、15+ 個 web 模式、70 個測試檔、63 篇決策日誌、外加 gallery 社群子系統與一份從 personal-playbook 複製來的治理 playbook。

> 真正的問題不是「專案多」，是**單一專案長出太多平行功能線、缺一張收斂的全貌圖**，導致難以一眼判斷「哪些是核心、哪些已足、下一步該往哪」。

本檔做三件事：**(1) 一頁全貌地圖**把爆量功能編成清單；**(2) 收斂成 3 條產品線**讓 sprawl 變得可讀；**(3) 化繁為簡**標出可凍結/精簡項，把能量導回戰略主線。

---

## 1. 一頁全貌地圖（Inventory）

### 1.1 CLI（4 指令）
`convert`（單字→SVG/G-code/JSON/GIF/ODP）、`info`（診斷）、`grid`（字帖 batch）、`serve`（Web UI）。

### 1.2 Web 模式 / API（~50 端點，分組）
| 群組 | 端點 | 對應 VISION |
|---|---|---|
| **單字 / 組件 / 覆蓋** | `/api/character` `/api/meta` `/api/components` `/api/coverset/*` `/api/coverage/recommend` `/api/decompose` | ★ 主線核心 |
| **手寫蒐集 (5d)** | `/handwriting` `/api/handwriting/reference` | ★ 主線核心（Layer 2 燃料）|
| **字帖 / 機器輸出** | `/api/grid` `/api/export` | ★ 機器軌跡核心 |
| 設計工具家族 | `/api/notebook` `/api/letter` `/api/manuscript` `/api/wordart` `/api/mandala` `/api/zentangle/*` `/api/doodle` `/api/patch` `/api/stamp` `/api/sutra/*` | ○ 周邊廣度 |
| 字源狀態 | `/api/cns-status` `/api/seal-status` `/api/lishu-status` `/api/song-status` `/api/kaishu-status` | 支援 |
| 罕用字字典 | `/api/user-dict/*` | 支援 |
| 公眾分享庫 (5g) | gallery router（auth/upload/likes/profile…）| △ 社群平台 |

### 1.3 資料源（12）
`g0v`、`mmh`、`kanjivg`、`cns_font`、`cns_strokes`、`cns_components`、`moe_kaishu`、`moe_lishu`、`moe_song`、`chongxi_seal`、`punctuation`、`user_dict`。
呼叫順序：`UserDict → g0v → MMH → Punctuation → CNS(Kai)`。

### 1.4 Exporter（21，依「是否服務 VISION 機器軌跡」分兩類）
- **機器軌跡核心（與 VISION 對齊）**：`svg` `gcode` `json_polyline` `gif` `hanzi_writer` `grid` `odp`（7）
- **設計工具廣度（周邊）**：`wordart` `wordcloud` `mandala` `zentangle` `doodle` `manuscript` `letter` `notebook` `sutra` `stamp` `patch` `engrave` `page` `multi_page`（14）

### 1.5 子系統
- **components**（Phase A）：`algorithm` `coverset` `decompose` `ids` + 5 cover-sets（808/4808/5000…）
- **5d handwriting**：IndexedDB PSD 蒐集（真人軌跡 + 壓力 + tilt）
- **gallery**：`auth` `db` `service` `smtp` + email magic-link + SQLite
- **zentangle**：獨立 web app（6z 系列，Pseudo-3D depth×curve）

### 1.6 文件與治理
63 篇 `docs/decisions/`、`PRINCIPLES.md`、journal、work logs；外加 **`docs/PROJECT_PLAYBOOK.md` 是從 personal-playbook 複製來的通用治理模板**（非本專案內容）。跨 repo 關係見 `docs/decisions/2026-04-29_personal-playbook-divergence.md`。

---

## 2. 收斂成 3 條產品線（化繁為簡的核心框架）

把爆量功能歸成 3 條線，sprawl 立刻變可讀：

| 產品線 | 涵蓋 | 成熟度 | 對「存在理由」的關係 | 建議節奏 |
|---|---|---|---|---|
| **Line A — VISION 主線**（軌跡 × 組件化 × 個人風格）| sources、components(Phase A)、ir、decomposition、5d 手寫、機器軌跡 exporter、Phase B/C/D | Phase A ✅，B/C/D ✗ | **這才是專案的存在理由** | **回主線、集中投入** |
| **Line B — 設計工具**（字帖/書法/藝術產生器）| wordart、zentangle、mandala、doodle、manuscript、letter、notebook、sutra、stamp、grid 美化… | 非常成熟、廣度過剩 | 周邊：好用但不推進 VISION | **進維護凍結、停止加新廣度** |
| **Line C — 社群平台**（公眾分享 + 部署）| gallery、auth、Render 部署、文件站 | 成熟 | 替主線蓄真實手寫資料的通路 | **低成本維運、選擇性推廣** |

> **一句話洞察**：Line B 佔了大宗程式碼（14/21 exporter、多數 web 端點），但對 VISION 是周邊；Line A 才是「世界第一個三維交集系統」的本體，**卻自 4/28 Phase A 後停擺**。能量配置與戰略價值倒掛——這就是「太多」的根。

---

## 3. 已完成 / 待繼續 / 尚未開始（按產品線歸類）

### ✅ 已完成
- **Line A**：Phase 1–4 核心 pipeline + 6 大資料源 + Phase A 組件分析器（3 cover-sets、greedy set cover、coverage report）+ 5d 手寫 MVP。
- **Line B**：Phase 5a–5an 全部 UI 家族（筆記/信紙/塗鴉/稿紙/文字雲 11×16×4/直書/多頁/塗鴉區）+ zentangle 6z（depth×curve 五維）。
- **Line C**：gallery（5g）+ Render 線上部署 + GitHub Pages 文件站 + 多帳號備份 + CI + §3.10 嚴格 git workflow。

### 🚧 待繼續（dangling thread）
- **Line B**：zentangle 6z-5b/5c **4 條 curve 軸視覺正確性「待你視覺驗證」**（最後未閉小尾巴）。
- **文件債**：README badge（標 `0.14.0`/`1057`）落後實際（`0.14.133`/~1,460）。
- **治理**：PRINCIPLES §6.8 morning-audit 閉環已連續 close 3 個，無 pending。

### 🔭 尚未開始（戰略主線 + spinoffs）
| 項目 | 線 | 估時 | 解鎖 |
|---|---|---|---|
| **Phase B 組件級 PSD 切割** ★ | A | 2–3 週 | tinyhanzi + Phase C 地基 |
| Phase C 規則式組合引擎 | A | 4–6 週 | 「寫 600 字合成沒寫過的字」核心賣點 |
| Phase D 神經組合模型 | A | 半年（研究級）| 自然度超越規則 |
| Service Worker offline | C | 1–2 週 | 弱網/低階手機；擴大 5d 蓄水 |
| tinyhanzi（嵌入式字庫）| spinoff | — | 卡在 Phase B |
| 組件 glyph cache / KAGE 整合 | spinoff | — | 依 Phase C |

---

## 4. 化繁為簡：可凍結 / 精簡 / 封存候選

| 動作 | 對象 | 理由 |
|---|---|---|
| **維護凍結** | Line B 全體（wordart/zentangle/mandala/…）| 廣度已過剩（wordart 11×16×4、zentangle 五維），邊際報酬遞減；停止加新模式，只修 bug |
| **閉合** | zentangle 6z 視覺驗證 | 30 秒看 demo 即可閉，別讓它無限期掛著 |
| **更新** | README badge + 「目前版本」段（README 仍寫 0.13.0 phase 表）| 對外門面與實際落差大 |
| **歸檔提醒** | 大量 5x 系列 PNG 樣本（root 下數十張）| 可移到 `samples/` 或 `docs/gallery/`，讓 repo root 乾淨（非必要、低優先）|
| **釐清** | `docs/PROJECT_PLAYBOOK.md`（複製版治理模板）| 標注「此為 personal-playbook 通用模板複本、非本專案 roadmap」，避免與本計畫檔混淆 |

> 凍結 Line B **不是放棄**，是把它當「已交付的成熟模組」，讓注意力資源回到 Line A。

---

## 5. 重新排序與建議（戰略抉擇 — 待你拍板）

**診斷**：能量配置與戰略價值倒掛（Line B 過投、Line A 停擺）。現在是把能量導回主線的好時點。

| 路徑 | 內容 | Trade-off |
|---|---|---|
| **★ Path 1：回主線 Phase B** | 先清 quick wins（zentangle 驗證 + README badge）→ 凍結 Line B → 啟動 Phase B（KanjiVG 對齊器 spike）| 推進 VISION 本體、解鎖 tinyhanzi；Phase B 較硬、需數週 |
| Path 2：續攻 Line B 廣度 | 再加 zentangle/wordart 新功能 | 短期成就感；但邊際報酬遞減、離主線更遠 |
| Path 3：先擴大蓄水（Line C）| Service Worker offline + demo/README 打磨 + gallery 推廣 | 擴大 5d 使用者＝替 Phase B/D 蓄真實手寫資料；不直接推進組合引擎 |

**我的推薦（一段話）**：走 **Path 1**，並把 **Line B 正式標為維護凍結**；同時把 Path 3 中「最低成本、能替主線蓄水」的一項（Service Worker offline 或 demo 打磨）排在 Phase B spike 之後。理由：Phase B/C/D 的品質取決於真實手寫資料量（VISION §五 Layer 2 是燃料），擴大 5d 使用者＝替主線蓄水。**順序＝清 quick wins（30–60 分）→ Phase B 對齊器 spike → 視結果全力 Phase B 或先補蓄水再回頭**。Path 2 不建議當主軸。

> 這節屬你的戰略決策。已列推薦，**未經你 sign-off 不會動 Phase B 實作**。

---

## 6. 建議下一步（今天可動、互相獨立）

1. **zentangle 6z 視覺驗證** — 開 demo 看 4 條 curve 軸（中高邊低/高中邊低/左高/右高）對 Florz 4 瓣是否如預期 → confirm 或退回，閉合最後 dangling thread。
2. **README badge + 版本段更新** — `0.13.0/0.14.0 → 0.14.133`、tests 數更新。1 行 doc commit。
3. **Phase B spike（若走 Path 1）** — 寫 KanjiVG 對齊器最小原型。**驗收：輸入「明」整字軌跡 → 自動切出「日」「月」兩組件樣本（含所屬字/位置 metadata）**。spike 成功＝可行性確認，再展開 2–3 週完整實作。

---

## 7. 風險 / 未解（引 VISION §九，挑與 Phase B 直接相關者）

- **組件邊界歧義**：「必」是 心+丿 還是原子字？對齊器切割前需先定組件邊界來源（KanjiVG `kvg:element` 主、IDS 補）。
- **對齊器準確度**：整字手寫 vs 標準軌跡比對切割，是 Phase B 核心技術風險；spike 的目的就是先壓這個不確定性。
- **冷啟動蓄水**：Phase C「七成像本人」需使用者先寫 ~600 字；5d 使用者基數不足 → 樣本不夠（呼應「先擴大蓄水」）。

---

## 8. 落地備註（git workflow）

- 依 §3.10 嚴格 default-deny：**sandbox 產檔、不在 sandbox commit**；commit 由你主機端 PowerShell 跑。
- 本檔**取代**早先的 PROJECT_PLAN 草案（同檔覆寫，無孤兒檔）。
- 對應 commit-msg：`docs/_commit_msg/2026-06-19_project_plan.txt`（已更新為統整主檔版）。
- 提交（注意先 `cd` 到 stroke_order）：
  ```
  cd C:\Users\USER\Documents\Cowork\stroke_order
  git add docs/PROJECT_PLAN_2026-06-19.md
  git commit -F docs/_commit_msg/2026-06-19_project_plan.txt
  git push origin main
  git push backup main
  ```
