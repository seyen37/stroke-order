# 決策紀錄 2026-07-18（5eq）：逐字手寫篆書範字太粗——styled 範字只複製填實字形層

對應 PRINCIPLES §34（承 §32 styled 範字 reuse 伺服器 SVG）。承 5en/5ep（styled
範字 styled 修復 v1/v2）。commit：`b8b3cd9`（0.14.221）；收工 msg 18。

---

## 整體脈絡

5ep 實機驗收通過（抄經選篆書→逐字手寫視窗範字已是篆書、不再楷書）。但同一
視窗暴露新問題：篆書範字**筆劃太粗、筆畫互相重疊糊成一團、與格子描紅的大小
比例略偏大**。這是 styled 範字這條線（5en→5ep→5eq）的第三發、也是最後一發。

---

## 決策 1：篆書範字的「代表層」是填實外框，不是那條粗中線骨架（§34）

**觸發**：實機三症狀（太粗／重疊／偏大）。

**根因**：`swBuildRefImg`（5en）一次 clone 抄經預覽的三個範字層並把 opacity
**全設 1**：

| 圖層 | 內容 | 預覽 opacity | 備註 |
|---|---|---|---|
| `sutra-glyph-reference` | 填實外框（fill、stroke=none） | 0.55 | 篆書真正的範字（格子看到的細灰篆形） |
| `sutra-trace` | 楷/宋填實外框 | — | 篆書為空 |
| `sutra-trace-skeleton` | 中線骨架（stroke、fill=none） | **0.03** | stroke-width＝char_size×0.12＝**粗**；隸/篆的幾乎透明 hint |

篆書＝skeleton 模式（sutra.py §47-76）：格子主要靠 0.55 填實層呈現、0.03 粗
骨架幾乎看不見。popup 把 0.55→1（變重）、**0.03 的 12% 粗骨架也拉到 1 全顯**、
疊在填實層上 → 又粗又重疊的黑團；骨架 round-cap 端點超出字形 bbox → 比例偏大。
**三症狀同一根因＝平權堆疊 + 全 opacity=1。**

**選項**：

| 編號 | 方案 | 優點 | 缺點 |
|---|---|---|---|
| A | 只 clone 填實層（reference/trace），無填實才 fallback 骨架 | 篆書拿到細填實篆形＝格子描紅；一處改、通用 | 罕見「只有骨架無填實」字走 fallback 仍可能粗（極罕見） |
| B | 保留三層但各層乘不同 opacity 因子 | 保留骨架 hint | 硬編因子脆弱、仍可能糊 |
| C | 把骨架 stroke-width 改細 | 直接 | 動到 server 渲染、影響格子/PDF（scope 爆） |

**選擇**：☑ A

**理由**：格子裡篆書的視覺主體就是 0.55 填實層（使用者確認那是想要的樣子），
骨架只是被刻意壓到 0.03 的 hint。popup 要複製的是「填實外框」這個代表層，不是
那條為疊合而存在的粗中線。A 一處改（純 index.html 的 swBuildRefImg 圖層選擇）、
不動 server、不影響格子/PDF，最小 scope。

**後續驗證**：✅ 見下。

---

## 決策 2：驗證對真實渲染跑，不只靜態鎖字串（承 §33）

**觸發**：§33 剛立——「修 JS 讀哪個資源/圖層的 bug，e2e 要對真實渲染跑」。本弧
正是「讀哪幾個圖層」的改動。

**做法**：`e2e_5eq`（真瀏覽器、真 swBuildRefImg）。沙箱無真篆體字型，故注入
「填實 reference ＋ 12% 粗 skeleton **並存**」的篆書情境 mock 預覽，呼叫真的
swBuildRefImg，**解碼它回傳的 Image 的 data-URL SVG**，斷言：含填實 path、
**排除粗骨架**、recolor #c8c8c8、img 載入；另「僅骨架」情境確認 fallback 用骨架。
皆 PASS。（踩點：頁面既有 `#su-preview` 在隱藏抄經區塊、rect getBBox=0；e2e 先
移除它、在 body 建可見同 id host 才量得到——正是 §33「對真實渲染的元素跑」。）

pytest：5en/5ep 斷言仍綠（`_filledIds` 含那兩層字串、fallback 含 skeleton）；新增
`test_5eq_handwrite_ref_prefers_filled_layer_over_thick_skeleton` 鎖「填實優先、
骨架 fallback、三層並列舊寫法已移除」。全量沙箱 1764 passed / 0 failed / 55 skipped
（+1）；user 機 1757 passed / 62 skipped。

---

## 學到的規則（→ PRINCIPLES §34）

**reuse 一份「各層 opacity/stroke 是為原用途（印刷描紅疊合）調好」的多圖層 SVG
到另一用途（螢幕 styled 範字）時，別平權全 clone 再統一拉 opacity=1**——那會把
原本的 hint 層（0.03 的粗骨架）放大成主體。先辨識「哪一層代表你要的那個東西」
（篆書＝填實外框、非粗中線），只取那層。各層權重帶著原用途的假設，換用途要重挑。

---

## 相關檔案

- 程式碼異動：`src/stroke_order/web/static/index.html`（`swBuildRefImg` 圖層選擇）
- 測試：`tests/test_sutra.py`（`test_5eq_*`）；`e2e_5eq.py`（沙箱 scratch、未寫回）
- 工作紀錄：`docs/WORK_LOG_2026-07-18.md`（5eq 節）
- 原則：`docs/PRINCIPLES.md` §34（承 §32/§33/§8.15）
- 前弧：`docs/decisions/2026-07-18_5ef_5ep_stencil_registry_centerline_styled.md`
  （§32 styled 範字機制、§33 真實渲染 e2e）
