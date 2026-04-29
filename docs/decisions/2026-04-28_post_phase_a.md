# 2026-04-28（後 Phase A 段）：5 個 cover-sets + Spinoff 戰略 + 多源字頻 schema

> 範圍：Phase A 主體完成（已記錄於 `2026-04-28_phase_a_backend.md` + `2026-04-28_phase_a_complete.md`）之後的後續工作決策。
>
> 本文不重複 Phase A 主體決策，聚焦 6 個關鍵後續決策：
> 1. IP 保護身份鏈標準化
> 2. PROJECT_PLAYBOOK §六「資料源稽核」從個案升級為系統性 SOP
> 3. CoverSet 從 3 個 → 5 個的擴充策略
> 4. CoverSet dataclass 加 `entries` 欄位的架構升級
> 5. 「不立即實作」決策（NAER + BIAU 進 backlog）
> 6. 多源字頻交叉驗證 schema（strict/majority/any consensus）

---

## 決策 1：IP 保護身份鏈三處同步

**情境**：早段使用者展示 quadruped-koding 專案的 LICENSE 用「許士彥 (Hsu Shih-Yen) (https://github.com/seyen37)」三件式格式，比 stroke-order 原本的 `(seyen37) <seyen37@gmail.com>` 更強。希望 stroke-order 也採用。

**選項**：
- A. 只改 LICENSE（最小改動）
- B. LICENSE + README + footer 三處同步（建立身份鏈）
- C. 全 codebase 任何提到作者的地方都改

**決定**：B。

**考量**：
1. **多點互相印證**：法律文件（LICENSE）+ 第一印象（README）+ 文件站每頁 footer 三處都導向同一個可驗證身份，建立完整身份鏈
2. **A 太弱**：只 LICENSE 不夠對外
3. **C 過頭**：commit message、code comments 等地方不需強制統一
4. **這是個重複模式**：寫進 PROJECT_PLAYBOOK §二「智慧財產權三件套」當未來新專案的標準

**教訓**：身份鏈是「**多點冗餘 vs 單點權威**」的妥協——三處同步達到「任何一處被質疑都能用其他兩處反證」的安全度。

---

## 決策 2：PROJECT_PLAYBOOK §六「資料源稽核」從個案升級為 SOP

**情境**：6b-11 教育部 4808 cover-set 製作時發現 Gist 來源夾帶 1 個 GB18030 變體字（彝 vs 彞）。當時把這個發現寫進該 phase 的決策日誌。但這個議題的「普遍性」遠超單一案例。

**選項**：
- A. 只在 phase 決策日誌記錄，不外推
- B. 寫進 PROJECT_PLAYBOOK 當常設章節，未來所有專案套用
- C. 寫進 stroke-order 的 README 警語

**決定**：B。

**考量**：
1. **這個 lesson 是跨專案的**：以後做 quadruped-koding 或新專案如果引用「政府公告字表 / 標準規範」，都會遇到同樣風險
2. **A 不夠廣**：埋在某個 phase 決策日誌裡未來找不回來
3. **C 太狹**：是工作 SOP 不是說明，不該對外宣傳
4. **PROJECT_PLAYBOOK 本來就是「跨專案個人標準」的定位**，這 fits perfectly

**實作**：寫成 §六「資料源稽核 Source-of-Truth Audit」六小節：
- 6.1 何時必跑（不只 public release，是任何引入新資料源時）
- 6.2 三段檢查（A 一手公文 / B 內容比對 / C 區域變體完整性）
- 6.3 範例：教育部 4808 案例
- 6.4 自動化建議（build script SOP）
- 6.5 給未來自己的話

順便重編號 §六~§十一 → §七~§十二，§十 AI prompt 補第 8 條 audit 規則。

**教訓**：把「個案發現」升級為「系統性 SOP」是高槓桿動作。一次 5 分鐘的個案要花 30 分鐘升級成 SOP，但下次遇到同類問題會省 30 分鐘。

---

## 決策 3：cover-set 從 3 個 → 5 個的擴充策略

**情境**：Phase A 完整收尾時有 3 個 cover-sets（808、4808、5000）。同日陸續加 4808 雙源驗證、bentu_6792、moe_elementary_5021 兩個新 cover-set。

**選項**：
- A. 收尾就停，新 cover-set 留下次
- B. 一次到位 3 → 5
- C. 先加一個（4808 或 5021）試水溫

**決定**：B（無計畫，但累積完成）。

**考量**：
1. **每個新 cover-set 都有獨立差異化**：
   - bentu_6792：含台/客/原住民語特有字 + CNS 11643 metadata
   - moe_elementary_5021：實證使用頻率資料
2. **Coverage 框架本身已成熟**：6b-3 的 cover-set 載入器設計支援「多 cover-set 同存」，加一個 = 改 _BUILTIN_NAMES + 一個 JSON
3. **資料來源都是乾淨官方**：4808 PDF、bentu xlsx、moe_elementary .txt 都是一手或近一手
4. **使用者需求 pull**：使用者主動提供 + 確認動工

**結果**：5 個 cover-sets 各有清楚 niche——
- 808：國際共用最高頻
- 4808：台灣標準字（雙源驗證）
- 5021：學童實證頻率
- 6792：本土語言含罕字
- 5000：朱邦復會意字

**教訓**：當基礎建設（cover-set 框架）成熟時，「新增資料」變成低成本動作。但要防止「容易做就一直做」變成範圍蔓延——所以後段 NAER + BIAU 收進 backlog 而非當天動工（決策 5）。

---

## 決策 4：CoverSet dataclass 加 `entries` 欄位

**情境**：6b-13 製作 bentu_6792 時，每個字帶 cns11643 / os_support / moe_index 等 per-entry metadata。但 `CoverSet.metadata` 設計是只存「top-level 額外欄位」，entries 在 load 時被 strip 掉了。

**選項**：
- A. 改測試，繞過 metadata 不要的 entries 部分
- B. 把 entries 從 metadata 提升為 CoverSet 的一等公民欄位
- C. 完全省略 per-entry metadata，只存字單

**決定**：B。

**考量**：
1. **per-entry metadata 是真正資產**：cns11643 是 Taiwan-variant integrity 的證據；os_support 是渲染警告 UI 的依據；moe_id 是 traceability。這些不該丟掉
2. **A 是 hack**：透過 metadata.entries 取資料是繞路，不直觀
3. **C 喪失資料價值**：違反 PROJECT_PLAYBOOK §六的「保留 traceability」原則
4. **實作成本低**：dataclass 加一個 `entries: tuple = ()` + load 時填入 + 測試改用 `cs.entries`

**架構意義**：`CoverSet` 從「字 + 簡單 metadata」升級為「字 + 完整 per-entry rich data」。未來所有 cover-set 都可以帶任意 metadata 而不需 schema 升級。

**前瞻價值**：明天 Group A 整合（NAER + BIAU 三源字頻 metadata）能直接套用——entries 已經是一等公民，只是新增 `freq_*` 欄位。

**教訓**：當你發現「測試在跟 dataclass 設計打架」，通常 dataclass 該改而非測試該繞路。

---

## 決策 5：「不立即實作」決策（NAER + BIAU 收進 backlog 而非當天動工）

**情境**：凌晨 1 點，使用者繼續送 NAER 99-108 字頻 xlsx 跟 BIAU 簡編本字頻資料。每份都有「重大實證發現」可寫，加起來 ~6 hr 工作量。

**選項**：
- A. 繼續做，硬撐到天亮
- B. 寫進 SPINOFFS backlog，明天動工
- C. 半做：簡單版整合，跳過深度分析

**決定**：B。

**考量**：
1. **疲勞 cost**：17 hr 工作後 schema 設計、決策日誌、跨源整合會出 bug。3 hr 累的活 ≠ 3 hr 精神好的活
2. **這份資料有重大策略 finding**（4808 中 41% 已不在現代高頻使用）——值得**新精神認真寫**而非草率帶過
3. **C 是中庸但弱**：跳過深度分析就喪失資料的核心價值（多源交叉）
4. **SPINOFFS.md 是「想法的活倉庫」設計**，正好用上

**對等價值動作**：把資料的戰略價值寫進 SPINOFFS Group A，升級為**三源字頻交叉驗證 schema**——明天動工時有清楚 plan。

**教訓**：**「停下動作收進 backlog」本身是一個有意識的決策**，不是輸給時間。在工程專案中，knowing when to stop 跟 knowing when to push 同樣重要。今天上午能 push 6 hr 寫 4 個 cover-set，凌晨 1 點 push 6 hr 寫多源字頻——後者品質一定比前者差。

---

## 決策 6：多源字頻交叉驗證 schema（strict/majority/any）

**情境**：截至凌晨，stroke-order 接觸到 3 份獨立的台灣字頻資料：
- moe_elementary_5021（已實作，2002 學童作文）
- NAER 99-108（待實作，2010-2019 媒體）
- BIAU 簡編本（待實作，1990s 辭典編纂語料）

每份都對應到不同 sampling 邏輯 + 不同時間維度，跟 4808 標準字的對比結果都不一樣。

**選項**：
- A. 各源獨立 cover-set，使用者自己挑
- B. 三源整合到 educational_4808 的 metadata，加 `modern_consensus` flag（strict/majority/any/none）
- C. 只挑最權威的一源，其他棄用

**決定**：B（寫進 SPINOFFS Group A，明天動工）。

**考量**：
1. **每源獨立有偏誤**：學童作文偏簡單；辭典語料偏文白；媒體偏新聞用詞——任一源都不代表「真實 Taiwan 字頻」
2. **A 推卸責任**：使用者不會比我們更知道該怎麼挑
3. **C 失去交叉驗證機會**：三源的差異 / 一致 本身就是 finding（哪些字三源都標 high-freq？哪些只一源？）
4. **B 的 elegance**：用 `consensus` flag 表達「跨源一致度」，使用者選 strict 就是「三源都標的最穩高頻字」，選 any 就是「至少一源高頻就要練」

**前瞻 UI 設計**：

```
Cover-set: 教育部 4808 ▼
   └─ Modern filter: ⦿ Off  ○ Any (≥1 source)  ○ Majority (≥2)  ○ Strict (=3)
```

選 strict 時 4808 動態縮成 ~2,500 真正穩定高頻的字。

**教訓**：當有多份獨立資料源時，**「整合 schema」比「挑一個 winner」更有研究價值**。差異本身是資訊，不是雜訊。

---

## 後 Phase A 段反思

**做得好的**：

1. **拒絕了夜間 over-engineering**（決策 5）：凌晨遇到豐富新資料時沒硬上，收 backlog 是成熟工程習慣
2. **單一決策觸發 SOP 升級**（決策 2）：Gist 變體污染這個個案，被升級成跨專案的 audit checklist——這種「把意外變成系統」的能力是長期專案的關鍵
3. **CoverSet 架構演進有節奏**（決策 4）：發現需要 entries → dataclass 加欄位 → 後續所有 cover-set 受益。沒過早設計也沒太晚補強

**可以更好的**：

1. **Cover-set 4 → 5 是無預期蔓延**（決策 3）：早段沒預料到會收這麼多資料，每加一個就要回頭改 SPINOFFS / decision logs。下次有新資料源接連進來時，應該先盤點全部再決定優先序
2. **時間管理可以更紀律**：凌晨還在 catalog 新資料，雖然每件都很值得做但累積疲勞 cost 高。下次當天的「軟收工」應該更早

**值得保留的方法論**：

1. **PROJECT_PLAYBOOK §六「資料源稽核」三段檢查**——以後處理任何「官方 / 標準」資料時 ritualize 跑這個 checklist
2. **SPINOFFS.md 「想法活倉庫」設計**——觸發決策框架（4 題全 yes 才動工）讓「不做」也是合理選擇
3. **多源交叉驗證 schema（決策 6）**——以後遇到類似情境（多份語料 / 多份字典 / 多份 IDS 來源）都套用 consensus 邏輯

---

## 對 stroke-order 主線的長期影響

1. **「Taiwan-first」哲學**從口號升級為**多層可驗證實踐**：身份鏈（IP）+ 一手公文（資料源）+ 雙源驗證（4808）+ 即將推進的三源字頻交叉
2. **CoverSet 框架成熟**：5 個 cover-sets 加 entries 欄位讓 per-entry 任意 metadata 可掛入；未來新 cover-set 加入成本接近零
3. **PROJECT_PLAYBOOK §六**成為個人專案開發 SOP 的核心章節，未來所有新專案都套用
4. **NAER 41% 4808 字過時**這個實證 finding 會驅動下一個策略討論：標準字表的時序維度該怎麼納入？

---

## 明天的動工順序（依 SPINOFFS Group A 優先序）

1. 🔥 **多源字頻 metadata 整合**（3-4 hr）
   - NAER 99-108 + BIAU 簡編本 + moe_elementary 三源整合到 educational_4808 entries
   - 加 `modern_consensus` flag
   - 衍生 `educational_4808_modern_strict` cover-set
2. **寫對應決策日誌**：「2026-04-29_modern_freq_triangulation.md」
3. **5d UI 加 modern filter**（1-2 hr）
4. **commit + push** 完成

預估明天的工作量約 5-6 hr，做完是個有意義的 milestone：**stroke-order 從「字單管理」升級為「時序穩健字單管理」**。

---

## 修訂歷史

- 2026-04-28：初版。基於後 Phase A 段的工作累積。
