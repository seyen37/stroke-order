# 4 天、22 個 commit、5 個產品階段：與 AI 協作開發 stroke-order 印章模組的 retrospective

> 從 2026-05-01 到 2026-05-04，stroke-order（一個中文字 → 雷射雕刻機 G-code 的轉換器）的印章模組從「能用」推到「業界對齊」。**Phase 11 + 12** 涵蓋 5 個產品階段、20+ 子任務、22 個 commit、版本從 0.13.0 → 0.14.7。本文整理出 7 條從這四天歸納出來的 AI 協作 + 工程實踐原則。

## 為什麼是 stroke-order？

[stroke-order](https://github.com/seyen37/stroke-order)（[線上 demo](https://stroke-order.onrender.com/)）是個個人專案：把任意中文字轉成雷射雕刻機可吃的 G-code，加上五種模式（單字筆順 / 字帖 / 信紙 / 抄經 / 印章）。技術棧：FastAPI + 純 inline SVG + cairosvg PDF 輸出，部署在 Render free tier。

印章模式 (Phase 5ay)是其中最「有業務語意」的一塊——不像字帖只是 grid，印章涉及「3 字傳統 1+2 layout」「篆書 OTF 字型品質」「陽刻 vs 陰刻」「業界 8 級尺寸（公分 / 4 分 / 5 分 / ... / 1 寸）」這些業界 know-how。本次 Phase 11 + 12 就是把這些 know-how 從「靠 user 試錯回饋」階段推到「對齊業界範例圖」階段。

---

## 四天的 timeline

| 日期 | Phase | 子任務 | Commits |
|---|---|---|---|
| 5/1 | Phase 11 收尾（11h shape-rendering）+ 文件 (§8.8) + .gitattributes | 3 | 3 |
| 5/2 | Phase 12a Cold-start wakeup overlay | 1 + docs | 2 |
| 5/3 | Phase 12b 業界規範對齊（8 級尺寸 + 警示 + PDF + 2 輪 bug fix）+ Phase 12c 陽刻支援 | 13 | 8 |
| 5/4 早 | Phase 12d 1 字章撐滿 + sync 4 條原則到 personal-playbook | 1 + 4 原則 | 4 |

**總計**：22 commits in 4 days，從 0.14.0 → 0.14.7（7 個 patch bump）。

---

## 5 個產品階段

### Phase 11h（5/1）—— 篆書邊緣鋸齒：OTF 字型品質的天花板

User 問：「篆書字邊緣不平滑，能再平滑些嗎？」

直覺反應是「渲染端鋸齒問題」。但**先 inspect 實際輸出**——curl 取 stamp SVG 看「王」字 outline path：

```
142 段 L (直線) + 181 段 Q (二次 Bezier) + 0 段 C (三次 Bezier)
```

崇羲篆體 OTF 字型作者用大量短直線近似平滑曲線（OTF 設計選擇），bbox-based scale 放大後直線之間的鋸齒就明顯。**這不是 stroke-order 渲染 bug，是字型本身的設計**。

緩解：SVG 加 `shape-rendering="geometricPrecision"` 強制瀏覽器最高品質 anti-aliasing。

→ 教訓沉澱進 PROJECT_PLAYBOOK §8.8「先 inspect 實際輸出，再下 root cause 結論」。

### Phase 12a（5/2）—— Cold-start wakeup overlay

User 問了一連串網站架構問題：「網站架在哪？字型放哪？使用者下載什麼？」

我用「角色分層 → 流量 trace → 三種等待」三段答完。User 接著追問：「所以等的是 server 重啟？」**這個問題暴露了 cold start 對使用者的隱形成本**——Render free tier 閒置 15 分鐘 server 就睡，第一個請求 ~30 秒喚醒，使用者完全沒回饋。

工程：包 `window.fetch` wrapper，第一個 in-flight 請求超過 3 秒未回應就顯示 overlay，3 階段訊息切換（3s 標準 / 10s 補解釋 / 30s 升級警告），sessionStorage 標記已喚醒避免重複跳。

inline 寫進 index.html 的 SPA 風格，全站 fetch 自動受惠（不用改 50 處呼叫端）。

→ 候選原則：「免費 PaaS tier 的固有限制，要在 UX 層告知使用者，不是隱藏」。

### Phase 12b（5/3）—— 業界規範對齊（user 上傳 8 張範例圖驅動）

User 上傳 8 張印章業界規範範例圖（豬豬小姐、吉祥刻印、無上印鋪、傳家手工、好福印、隆興印章），要求對齊業界。

從 8 張圖整理出共識：

- **8 級尺寸**：公分 1.0 / 4 分 1.2 / 5 分 1.5 / 6 分 1.8 / 7 分 2.1 / 8 分 2.4 / 9 分 2.7 / 1 寸 3.0 cm
- **字數對應排列**：1 字粗體置中 / 2 字上下或左右 / 3 字 1+2（右姓拉長+左 2 字堆疊） / 4 字 2×2 / 5+ 字直書多列
- **字體 6 種**：正楷 / 隸書 / 仿宋 / 毛楷 / 毛行 / 篆字
- **陽刻 vs 陰刻**：兩種都常見

實作 7 個子任務 + 2 輪 bug fix：

1. UI quick-pick select（業界 8 級制 dropdown）
2. 小尺寸警示（1.2cm + 3 字 → 提示筆劃可能相連）
3. 字數推薦尺寸提示
4. PDF 下載（cairosvg svg2pdf 直出向量）
5. **bug fix 1**：`inner_w/h` 計算受 `char_size_mm` 污染（5 週前的舊 bug 被 11g bbox-scale 暴露）
6. `border_padding_mm` 預設 2.0 → 0.8（對齊業界小章）
7. cell 內留 8% padding 防 4 字邊互碰

**最大教訓**：5 處 `border_padding_mm = 2.0` 散布在 server.py × 3 + stamp.py × 4 + index.html × 1 = 7 處，更新時要 grep + sed 同步。→ §8.10「Default 值 single source of truth」。

### Phase 12c（5/3）—— 陽刻支援：演算法 module 的 prototype-first SOP

陽刻（朱文）= 字凸出 + 紅底白字。涉及兩個新 rendering pipeline：
- **SVG**：fill-based 渲染（不是 stroke-based）
- **G-code**：光柵掃描鋪滿背景（不是沿字 outline 走）

G-code 那塊是新類型演算法，沒驗證可行性前不敢動主線。**走 prototype-first SOP**：

1. 寫 `scripts/prototype_engrave_convex.py`（不進主分支）
2. 跑壓力測試：4 分 / 8 分 / 1 寸 各尺寸 + 不同 line_pitch
3. 渲染 PNG 視覺驗證 even-odd rule（綠色 = 雷射 ON、字內無綠線）
4. 確認效能 < 100ms、G-code 規模 < 5K、雷射時間 0.5-5 分鐘合理
5. **prototype 通過**才動主線

主分支結果：**1 個 commit (74b996d) 完成 5 子任務 + 5 新測試 + 200 passed 回歸**，沒有 churning。

演算法 module `exporters/engrave.py` 獨立，只依賴 polygon 抽象，不 import stamp / sutra / patch 業務概念。**保留跨用途複用彈性**（patch 鏤空、sutra watermark 都能用）。

→ §8.11「演算法工作 SOP：先 prototype 後主線」+ §8.12「演算法 module 獨立」。

### Phase 12d（5/4 早）—— 1 字章撐滿章面

驗證 1 字章對齊業界。發現現況「字身 = char_size_mm cap」邏輯讓 1 字章字過小（12mm 章 char_size=5 → 字身 5mm 佔 inner 48%），不像業界範例圖的 90%+ 撐滿。

**Fix**：1 字情境 ignore char_size_mm cap，固定 ratio 0.96 撐滿 cell。理由：多字章 cap 是為了避免字撐爆 cell；1 字章只有單一 cell，cap 變成多餘的縮小。

12mm 章 1 字字身 5mm (48%) → **9.98mm (96%)**，將近 2 倍放大。

---

## 7 條 AI 協作原則（從這四天歸納）

### 1. 「先 inspect 實際輸出，再下 root cause 結論」

UI 看到「不對」不要直接改 UI；先 dump 真實輸出。Phase 11h 篆書鋸齒、12b 印章預覽空白、12d 1 字字大小，三次都是先 curl / dump 看實際資料層才找到 root cause。**盲改前端的修法都只解一半**。

### 2. 「使用者問架構 ≠ 要架構圖」

User 問「網站架在哪、字型放哪」表面是學習問題，實際是「我在診斷我遇到的問題」。回答時要想：「他下一步可能想做什麼？」用這個指南針回答比純粹的「正確架構解釋」更有用。Phase 12a wakeup overlay 直接從這個問題鏈鎖反應。

### 3. 「user 提供高品質參考圖」是 ROI 最高的開場

8 張業界範例圖讓我能在 30 分鐘內整理出印章業界共識，並做出 5+ 個對齊決策。如果只靠口頭描述「想做傳統印章」，光釐清標準就要 1 小時+。**任何「對齊外部標準」工作，先請 user 提供 3-10 個範例圖**。

### 4. 「底層改動會暴露上層舊 bug」

Phase 11g 改 bbox-based scale，目標解「字沒撐滿 cell」視覺問題；但因為 bbox-scale 比 EM-scale 「貼合」，5 週後在 Phase 12b 才暴露 `inner_w = max(_, char_size_mm)` 計算的副作用。**重要 base infra 改動後，要主動 audit 周邊**——不只看直接相關功能。→ §8.9。

### 5. 「Default 值散布在多處是反模式」

`border_padding_mm = 2.0` 散布在 7 處（3 server + 4 stamp.py + 1 index.html）。手動 sed + grep 同步能 work，但累積 debt（任何一處遺漏會造成 default 不一致）。**grep 看到 magic number 散布 ≥ 3 處應重構成 named constant**。→ §8.10。

### 6. 「未驗證可行性的演算法工作要 prototype-first」

Phase 12c 陽刻 G-code 光柵掃描——直接動主線會變成「邊改邊試」式 churning。**寫 prototype 在 `scripts/`，驗證演算法正確性 + 效能規模 + 視覺/業務正確性，通過後才 port 進主線**。Phase 12c 證明：prototype-first 讓主分支 1 commit 完成 5 子任務 + 5 測試 + 200 passed 回歸。→ §8.11。

### 7. 「演算法 module 獨立，不依賴業務 module」

演算法 module（如 `exporters/engrave.py`）只依賴抽象資料結構（polygon / vector），不 import stamp / sutra / patch 業務概念；業務 module 反過來 import 演算法 module。好處：跨 use case 重用、god file 控制、測試獨立。→ §8.12。

---

## 數字總結

| 維度 | 數字 |
|---|---|
| 工作天 | 4 |
| Commits | 22 |
| 子任務 | 20+ |
| 版本 bump | 0.14.0 → 0.14.7（7 patch） |
| 新測試 | +6 個（Phase 12c 5 個 + 12d 1 個） |
| 全套 pytest | 1140 → 1146 passed |
| 沉澱進 PROJECT_PLAYBOOK 的原則 | 5 條（§8.8 / §8.9 / §8.10 / §8.11 / §8.12） |
| 反同步 personal-playbook 第十次修訂 | ✅ |

---

## 給未來自己的話

這四天最大的啟示不是某個技術 lesson，而是 AI 協作的工作節奏：

1. **每天 morning audit**：跑一次「上一個工作日的 gap」清單（commit / docs / tag / sync），通常 30 分鐘清掉，主工作不在歪掉的基礎上累積。
2. **每個 Phase 結束寫 work log + decision log**：不是事後補，是當下寫。事後補質量會降。
3. **AI 對話本身就是工作的一部分**：架構問題 → 工程觸發點，這個鏈條讓「問」變成「做」之間沒有斷層。
4. **Prototype 是人機協作的 sweet spot**：演算法 prototype 在 sandbox 跑得快，AI 寫 + 跑 + render PNG 看效果整個流程在分鐘內。要等 deploy 看效果就慢。

---

**stroke-order**：[github.com/seyen37/stroke-order](https://github.com/seyen37/stroke-order) · [線上 demo](https://stroke-order.onrender.com/)

**personal-playbook**（含本文歸納的 5 條原則 + 9 條 case index）：private repo，未公開。

— 2026-05-04 morning，許士彥（seyen37）+ Claude（Anthropic）協作 retrospective
