# 2026-05-02 — Phase 12m-1 r4-r19 多輪 visual polish 迭代決策

> 連續 16 輪 patches 把橢圓章從「上弧 + body + 下弧」基本 layout 推到接近業界 production polish。每輪 5-15 分鐘 turn-around，user 提 issue → AI 分析 + 修 → render PNG 驗證 → 下 round。**這是「polish 階段 short-loop iteration」的密集驗證**。

**版號變化**：0.14.21 → 0.14.37（連 16 個 bump）
**對話 / 工作期間**：2026-05-02 下午到晚上 ~5 小時
**Round 數**：16（r4-r19）

---

## 整體脈絡

承接早上 r0-r3 完成的核心 layout（結構化欄位 + 上弧 + body + 下弧 + arc-length param + 預設雙框）。下午到晚上 user 持續看效果反映新 issue，每輪小調整逐步 polish 對齊業界 reference 視覺。

跟早上「整批 reference 圖一次 plan」不同：**晚上每個 user message 1-3 個小 issue**，AI 直接修 + 驗證，跳過大 plan 階段。Plan vs polish 是不同 phase 的不同工具。

---

## 關鍵決策（依重要性 / 一次性程度排序）

### 1. Inner ellipse semantic：concentric → body-wrapping → constant offset

橢圓章 inner ellipse 經歷 3 次 semantic shift：

| 階段 | inner ellipse 設計 | 視覺結果 |
|------|------------------|---------|
| r0   | concentric (outer × 0.97)，跟 outer 黏在一起 | 雙線外框 hairline，user 反映「沒看到雙線」|
| r9   | body-wrapping (uniform scale 0.72)，包住中央 body | T-02 風格雙圈帶，但 user 反映「曲率跟外框不同」|
| r11  | constant offset (a-d, b-d), d = 0.30 × min half | 等寬 ring band，user 滿意 |

**選 constant offset**（r11 並 r12 微調 d 從 0.20 → 0.30）：

理由：嚴格上 ellipse offset curve 不是另一個橢圓，但 (a-d, b-d) 對 typical d/a < 0.30 視覺夠 close，且符合 user 觀察「內外框距離恆定」。

### 2. Arc rotation：parameter t → radius angle → ellipse normal

弧文 char rotation 公式經歷 3 次：

| 階段 | rotation = | 視覺 |
|------|------------|------|
| r2   | `t + 90°`（圓形切線公式）| 邊緣字身歪掉跟外框曲率不同步 |
| r8   | `atan2(b sin t, a cos t) + 90°`（radius vector）| 邊緣字身朝中心傾斜過多 |
| r10  | `atan2(a sin t, b cos t) + 90°`（**outward NORMAL**）| 邊緣字身沿 ellipse 外法向，跟外框曲率對齊 |

**選 ellipse outward normal**：

數學上：normal = ellipse equation 的 gradient = `(cos t / a, sin t / b)`，角度 = `atan2(sin t / b, cos t / a) = atan2(a sin t, b cos t)`。對圓形 a=b 退化為 t（fallback OK）。對橢圓真正描述「沿 outline 朝外」方向。

### 3. Sawtooth 設計：polygon-replace → triangle attach

User r18 要求「鋸齒外框」，r19 改設計：

| 階段 | 設計 | 問題 |
|------|------|------|
| r18  | polygon centerline 替換 outer ellipse（vertices alternate outer/inner）| stroke 兩側都 zigzag，inner side 也呈鋸齒 — user 不要 |
| r19  | smooth ellipse 維持 + filled 三角形 teeth 黏外側 | inner smooth、outer zigzag — 對齊 user 要求 |

**關鍵教訓**：polygon centerline 跟 stroke 渲染後的雙邊形狀**不對等**。Unit tests 通過（polygon 形狀正確）但視覺 wrong。

→ 寫進 playbook 候選 §8.15「visual rendering 不能只依賴 unit tests，每 round 必 PNG 視覺驗證」。

### 4. Mixed-arity tuple for backward-compat（r12 bold flag）

placement tuple 從 6-tuple `(c, x, y, rot, w, h)` 加 bold flag → 7-tuple `(c, x, y, rot, w, h, bold)`。影響 5+ 個解構點：

- `_placements_for_preset` 多處 `.append((c, x, y, rot, w, h))` 維持 6-tuple
- `_oval_body_layout` 改 return 7-tuple（支援 bold）
- `render_stamp_svg` / `render_stamp_gcode` 解構 loop 需處理兩種 tuple
- 6 個 tests 用 6-tuple destructure

**選 mixed-arity**（不是強制全改 7-tuple）：

理由：強制改 7 影響 大；mixed-arity 用 `placement[:6]` 取核心 + `placement[6:]` 取 extra 解構，向後兼容。Tests 用 `*_` 處理 trailing。

```python
# Render code:
for placement in placements:
    c, x, y, rot, w, h = placement[:6]
    bold = placement[6] if len(placement) > 6 else False
```

→ Memory 候選：「placement tuple 加 element 用 `[:N]` 解構 + 預設 extra 為空 `*_` pattern 兼容」。

### 5. Decoration 切換 (r13)：plum / star / circle / none

User r13 要梅花切換或關閉。實作 dispatcher pattern：

```python
def _oval_decoration_svg(kind, cx, cy, radius, stroke):
    if kind == "plum":   return _oval_flower_svg(...)
    if kind == "star":   return _oval_star_svg(...)
    if kind == "circle": return _oval_circle_svg(...)
    return ""  # 'none' or unknown → 空字串 → caller skip
```

**選 dispatcher 而非 inline if-else**：易擴充、testable。

### 6. UI conditional grouping per preset（r6 / r9）

不同 preset 適用不同 UI 元素：
- 2 字/5 字排列：square_name / round_name
- 3 字補字：square_name only
- 公司章短列：square_official only
- 每字位移：grid-based 3 個 preset
- 橢圓 5 欄位：oval only

**選**：每組 UI 一個 toggle 函式 (`stampUpdateXxxUI`)，hook 到 preset.change + init time。Pattern 跟 §8.14 對齊。

### 7. Body slot-based positioning（r11）

中央 body chars 從 count-based（依填的 count 算 y_offsets）→ slot-based（slot 1 永遠 top, slot 2 永遠 middle, slot 3 永遠 bottom）。

**選 slot-based**：

User 要 「中央 2 永遠中央位置」、「中央 3 永遠下方」即使 slot 1 或 2 為空也不擠位。Slot semantics 比 count-based 對齊 user mental model。

代價：API 需保留 empty slot（不能 filter empty list）→ 5+ 個 tests 改 destructure。

---

## 沒做的決策（明確擱置）

- **Sawtooth depth 可調**：目前固定 1mm，非 API 可調。等 user 反映需要再開
- **裝飾大小可調**：目前 d_offset × 0.30 固定。同上
- **裝飾方向（朝內 / 朝外）切換**：目前只朝外。Inner-pointing 變體少見，不開
- **多種 Bold 強度**：bold = stroke ×2 固定，不分 medium/heavy。簡化
- **Body slot 個別 y_offset 可調**：固定 ±0.15 / 0 / +0.15。User 沒提

---

## 學到的規則 / pattern（適用未來）

### Layout/visual 工作 unit test 不夠 — PNG render 必驗

r18 → r19 的 sawtooth 設計教訓。Unit tests 驗 polygon 形狀正確，但 SVG stroke 渲染後雙邊都 zigzag。**只有 PNG 視覺驗證能抓**。

→ playbook 候選 §8.15。

### Plan-stage 跟 polish-stage 用不同工具

- **Plan stage**: 整批 user reference 圖 / 多面向需求 → 寫 detailed spec + design Q + user 確認 + 一次實作（30-45 mins/round）
- **Polish stage**: 1-3 小 issue / round → 直接修 + 視覺驗證 → 下 round（5-15 mins/round）

混用會出問題：plan stage 跳過 design Q 容易做錯方向；polish stage 寫 detailed spec 浪費時間。**識別當前 phase + 切換工具**。

→ 已內化在 `feedback_iterative_visual_loop`，今天再次驗證。

### Mixed-arity tuple backward compat pattern

placement tuple 加 element 用 `[:N]` + `placement[N:]` 解構。Tests 用 `*_`. 比強制全改更省工。

→ memory 候選。

### Cowork sandbox git index 仍不可信

晚上又踩到 `.git/index` 顯示 533 file deletion 的 ghost stale state。User 端 terminal 沒事。

→ 已有 memory `feedback_cross_session_race`，今天再次驗證 — 重要 commit 都 user 端跑。

---

## 相關檔案

- 工作紀錄：[`docs/WORK_LOG_2026-05-02_phase12m_iterative.md`](../WORK_LOG_2026-05-02_phase12m_iterative.md)
- 早上 12m-1 r0-r3 決策：[`docs/decisions/2026-05-02_phase12m_oval_structured.md`](2026-05-02_phase12m_oval_structured.md)
- 程式碼異動（16 round 累計）：
  - `src/stroke_order/exporters/stamp.py`：~600 行新增/修改（4 個新 helpers + 多 layout 公式調整 + sawtooth path）
  - `src/stroke_order/web/server.py`：StampPostRequest +5 fields (oval_body_bold/oval_decoration/oval_sawtooth/oval_show_inner（透過 double_border 傳遞）)
  - `src/stroke_order/web/static/index.html`：~150 行新增（5 個欄位 + checkboxes + dropdown + JS sync logic）
  - `tests/test_stamp.py`：6 個 destructure pattern 改 + 多預期值更新
- Commits：4eb65d8 / 64a8766 / 2164c8d / 71341b6 / 4b9e8f3 + 數個 in-between
