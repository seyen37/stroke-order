# Work Log — 2026-05-02 — Phase 12m-1 多輪 polish 迭代（r4 ~ r19）
> （當天上午 r0-r3 → see `WORK_LOG_2026-05-02_phase12l_12m.md`；下午到晚上又做 r4-r19 共 16 個 patches，是橢圓章 visual polish 的密集迭代日）

**版本**：0.14.21 → 0.14.37（連 16 個 patch round）
**Commits**（截至 r19）：~10 個（部分合併推送）
**修改檔**：`exporters/stamp.py`、`web/server.py`、`web/static/index.html`、`tests/test_stamp.py`、`pyproject.toml`
**Tests**：145 → 150（+5 oval slot tests）；多次更新預期值對應 layout 演算法演進

---

## 一、本日 narrative

承接上午 12m-1 r0-r3 的核心 layout 完成後，user 一路給 visual feedback 16 輪修正。每輪規模 5-15 分鐘 turn-around，累積把橢圓章從「上弧 + body + 下弧」基本 layout 推到貼近業界 reference visual。

| Patch | 主題 |
|-------|------|
| r4 | oval capacity hint 結構化（弧文 / body 各自 cap）|
| r5 | capacity API async race fix（reorder listeners + sequence guard）|
| r6 | 姓名章專用排列（2字/5字 layout）UI grouping，preset-conditional |
| r7 | preset dropdown 名稱簡化（去除括號註解）|
| r8 | 弧文 rotation phi 公式 + char-size aware padding |
| r9 | UI 條件顯示：3字補字 / 每字位移 per-preset；inner ellipse semantic 從 concentric → body-wrapping |
| r10 | rotation 公式從 radius angle 改 ellipse NORMAL 方向（atan2(a sin, b cos)）|
| r11 | inner ellipse constant offset (a-d, b-d) + slot-based body positioning + 預設文字重排 + ❀ 梅花裝飾 |
| r12 | inner d 0.20→0.30 + 動態 max_h cap（受 inner ellipse 限制）+ 梅花細 stroke + bold flag (placement 6→7 tuple) + 中央 1/2 加粗 checkbox |
| r13 | outer×1.5 雙線、span 160→140、裝飾切換 (plum/star/circle/none)、slot_max_h bump |
| r14 | viewBox padding match outer stroke、outer×1.5→1.3、ring_band cap on arc char_size、body usable_w 改用 INNER ellipse |
| r15 | arc placement 從 outer 邊緣 → ring band midpoint（inner gap 0.1mm → 0.5mm 對稱）|
| r16 | 梅花縮小 (×0.40→×0.30)、雙線 5:1 ratio (outer×1.5/inner×0.3) |
| r17 | oval 專用 「顯示內框」checkbox（取代既有「雙線外框」）+ 5 placeholder 業界化 |
| r18 | 鋸齒外框 feature（v1：polygon 替換 outer ellipse）+ 5 placeholders |
| r19 | 鋸齒重設計（v2）：smooth ellipse 維持，teeth 改 filled triangle 黏外側 |

每 round 流程：user 截圖 → 我列分析 + 提修法 → 動工 + 視覺驗證（render PNG）→ bump version → user 看部署效果 → 下 round。

---

## 二、本日學到的規則

### Layout / 視覺工作 unit test 抓不到 stroke render 細節

r18 的 sawtooth 用 polygon-replace outer ellipse，演算法數學上是「鋸齒 polygon」沒問題。但 SVG stroke 渲染時，polygon centerline 兩側都各加 stroke 半寬 → **內外邊都 zigzag**，不是 user 要的「外鋸齒、內 smooth」。

Unit tests 通過（polygon 形狀符合預期）但視覺 wrong。靠 PNG render 才抓到。

→ 寫進 candidate playbook §8.15「visual rendering tests 不能省 — unit tests + PNG/截圖驗證每個 round」。

### API tuple lock-in：增加 element 牽動 N 個解構點

r12 加 `bold` flag → placement tuple 從 6 → 7。影響：

- `_placements_for_preset` 多處 `placements.append((c, x, y, rot, w, h))` 
- `render_stamp_svg` `for c, x, y, rot, w, h in placements:` 解構 loop
- `render_stamp_gcode` 同樣
- `_oval_body_layout` return 簽名
- 6 個 tests destructure 6-tuple
- Char_offsets clamp loop

策略選 **mixed-arity tuple**：6-tuple 跟 7-tuple 共存，render 端用 `placement[:6]` 取核心 6 元素 + `placement[6:]` 取 extra。Tests 用 `*_` 處理 trailing element。**Backward compat ON**，沒破現有 6-tuple users。

→ candidate memory：「placement tuple 加 element 用 `[:N]` 解構 + 預設 extra 為空 `*_` pattern 兼容」。

### Multi-round visual iteration ≈ 5-15 mins/round 是 polish 階段最有效

跟 phase 12b（8-stamp reference 4 rounds）+ 12m-1 早上 r0-r3 4 rounds 對比：

| 階段 | rounds | 平均 round 時間 | 結果 |
|------|--------|----------------|------|
| 12b | 4 | ~30 mins（含 plan）| 業界規範對齊 |
| 12m-1 早上 r0-r3 | 4 | ~30-45 mins | T-02 復刻 |
| 12m-1 晚上 r4-r19 | 16 | ~5-15 mins | 接近 production polish |

晚上 16 rounds 的 turn-around 短，因為：

1. 核心架構（r0）已穩定，每 round 改細節不動 architecture
2. 每 round 1-3 個小 issue（單 user message），不像早上整批 reference 圖
3. local server hot-reload + sandbox 直接 render PNG → 跳過部署等待

**結論**：polish 階段適合 short-loop iteration；plan 階段適合 long-loop（先 plan + design Q）。**Plan vs polish 不是同一個工具**。

### Cowork sandbox git index 不可信

晚上工作中發生 2 次 git index 異常：r3 commit 卡 lock；r19 後 git status 顯示 533 file 大量 deletion（實際檔案在 disk）。

User 端 Windows terminal 的 git 不受影響。Cowork sandbox 的 .git/index 因隔離問題容易 stale / lock。

→ 修法：sandbox 不要 main commit，所有 commits 由 user 端 PowerShell 跑。Sandbox 只負責檔案編輯。已部分內化（feedback_cross_session_race），但本日再次踩。

---

## 三、版本 / commit 對應

| Patch | Commit | Version |
|-------|--------|---------|
| r4    | (合併 r3 retrofit) | 0.14.21 |
| r5    | 後續合併推 | 0.14.22→0.14.23 |
| r6    | (合併 r5+r6) | 0.14.24 |
| r7    | (合併到 r4-r7 commit) | 0.14.25 |
| r8    | (合併推) | 0.14.26 |
| r9    | (合併推) | 0.14.27 |
| r10   | (合併推) | 0.14.28 |
| r11   | (合併推) | 0.14.29 |
| r12   | 部分合併 | 0.14.30 |
| r13   | 4eb65d8 (合併 r12-r14) | 0.14.31→0.14.32 |
| r14   | 同上 | 同上 |
| r15   | 64a8766 | 0.14.33 |
| r16   | 2164c8d | 0.14.34 |
| r17   | (合併到 r17+r18) | 0.14.35 |
| r18   | 71341b6 | 0.14.36 |
| r19   | 4b9e8f3 | **0.14.37** |

**注意**：歷次 commits 部分合併，commit 訊息不總是跟 patch round 1:1 對應。

---

## 四、決策紀錄

- [Phase 12m-1 r4-r19：多輪 visual polish 迭代決策](decisions/2026-05-02_phase12m_iterative_polish.md)

---

## 五、明日 / 後續 backlog

- [ ] Cowork sandbox git index reset 後 push（user 端執行 `git reset` 然後重做 commit）
- [ ] HTTP 503 cold start observability（Render free tier）
- [ ] Phase 12m-2 / 12m-3 / 12m-4 待 user 啟動
- [ ] 觀察 r17-r19 deploy 後 user reaction
- [ ] §8.15 visual render verification SOP 寫進 playbook（候選）
- [ ] mixed-arity tuple 解構 pattern 加 memory（候選）
