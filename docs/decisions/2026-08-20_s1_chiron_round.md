# 決策紀錄 2026-08-20（S1）：昭源環方＝第七種字模筆形風格

對應 PRINCIPLES §91（**「看著舒服」要先歸因再動旋鈕**；上游若把成品資產進版控就
直取，不必轉存自家 release；新字源沿既有路徑全數接上並鎖成 parity 測試）。
承 §16（黑體字模）、§86（降級供應／新字源接線）、§89（下結論前覆查數字）、
§90（借鏡落地五步）。版本 0.14.286。

---

## 整體脈絡

使用者分享 [昭源環方 Chiron GoRound TC](https://github.com/chiron-fonts/chiron-go-round-tc)
並說：「這個圓體看著特別舒服，我也不知為何，看起來好像沒什麼特別的，但就是很能
一直看下去。」隨後指定用途：**當字模來源，或當 R1b 圓角參數的品味參考**。

「看著舒服」是感受，不是規格。照 §90 第 2 步（不估計，實測），先**量**再決定要
動哪個旋鈕。

---

## 決策 0（前置量測）：「舒服」的歸因——不是圓角克制，是筆畫細

**量測方法**（`measure_round.py` spike，字集 永園口日十國）：

- 圓角指標 `R/(W/2)` ＝ 終端圓角半徑 ÷ 半筆寬。`0` ＝ 方頭，`1` ＝ 全圓頭。
  半徑 ＝ 弧長 / 總轉角；弧長**只算角落頂點之間**的邊（尖角只有單一頂點 →
  弧長 0 → R=0，這是首版量錯 Noto=2.652 的根因）。
- 筆寬 ＝ 光柵化後 `distance_transform_edt` 脊線值 ×2 的中位數。

| 來源 | 筆寬 (EM/2048) | `R/(W/2)` | 圓角絕對半徑 |
|---|---|---|---|
| Noto Sans TC Bold（現行預設） | 208（10.2% em） | **0.000** | 0 EM |
| 昭源環方 400R | 138（6.7% em） | **1.087** | ≈75 EM |
| 昭源環方 700B | 224（10.9% em） | **0.615** | ≈69 EM |
| skeleton_glyph `cap=round` w=138 | 138 | 1.008（理論 1.0，量法自驗） | ≈69 EM |

**推翻原假設**。動工前的直覺是「舒服＝圓角克制（半圓不到）」，因此想開一個
「圓角程度」旋鈕。實測顯示昭源環方 Regular 是**全圓頭**（1.087 ≥ 1），圓角一點
都不克制。真正的差異是**筆畫比現行預設細三分之一**（138 vs 208 EM），加上骨架
本身是設計過的黑體（昭源黑體＝思源黑體香港版的現代筆形改造）。

**含意（改變了後續兩個決策）**：

- R1b 該開的旋鈕**不是圓角、是字重**——`cap=round` 維持不動，建議區間 100–160 EM、
  預設維持 120 附近。省下一個做了也沒用的參數。
- 本專案的 `skeleton_glyph`（R1a）在 `cap=round` 下量到 1.008，**和昭源環方是同一個
  幾何家族**。所以昭源環方對本專案的價值不在「教我們怎麼圓角」（已經會了），而在
  **它有 47,174 個字符的完整字庫**，而骨架長肉受限於 g0v 骨架覆蓋。→ 定位為
  **字模來源**，不是參數參考。

---

## 決策 1：字型從上游 repo raw 直取，不轉存自家 `fonts-v1` release

**Question**：`render_fetch_fonts.sh` 的既定作法是把字型上傳到本專案的 GitHub
Release `fonts-v1` 再抓。昭源環方 Regular OTF 18.7 MB／Bold 20.5 MB，官方 zip
352 MB（10 字重＋多格式）。使用者要為此多做一次上傳嗎？

**已知／unknown**：已知 Noto 那條已經是 raw 直取的先例（`raw.githubusercontent.com`
的 noto-cjk repo）。unknown＝昭源環方是否也把**成品字型**進版控（多數字型專案只在
Release 放成品）。

**查證**：`README.md` 說「提供 `STATIC_OTF/` 目錄」，實測
`https://raw.githubusercontent.com/chiron-fonts/chiron-go-round-tc/master/STATIC_OTF/ChironGoRoundTC-700B.otf`
→ **HTTP 200、20,500,040 bytes**，md5 `88e445ce…` 與使用者本機 zip 解出的同名檔
**逐位元組相同**。（分支是 `master` 不是 `main`——先探過才寫進腳本。）

**選項**：A 上傳到 `fonts-v1`（照既定作法，但要使用者手動做一次 20 MB 上傳）／
★ B raw 直取（零人工步驟；多一個上游相依，但腳本本來就是 per-font graceful
failure，抓不到只是這個風格不可用）。

**選擇**：☑ B。理由：既有 Noto 先例證明這條路已在生產跑；且**散布的是上游未經本
專案改動的原檔**，OFL 的遵循更乾淨（見決策 3）。

**副作用（正面）**：原本規劃裡「需要使用者先上傳 OTF 到 release」這個**阻塞步驟
直接消失**，S1 從「等使用者」變成當輪可完成。

---

## 決策 2：收 Bold (700B) 而不是使用者當初看到的 Regular (400R)

**Question**：使用者覺得舒服的是 Regular 的視感。但 `sc-source` 下拉的用途是
**字模／鏤空字的筆形風格**——§16（5dm）當初選思源黑體 Bold 的整個理由就是
「筆畫粗細均勻、無收筆尖鋒，橋接/連筋落在厚壁上不易斷」。細字重與這個用途相衝。

**量測**（沿用 `test_noto_hei` 的判準：50 mm 字框、2 mm 連筋，鑿橋後殘腔須為 0）：

| 字型 | 筆寬中位 (px@50mm) | 殘腔（田圖國回圓明界） |
|---|---|---|
| Noto Sans TC Bold（基準） | 42–47 | 0 / 7 字全過 |
| 昭源環方 400R | 26–32 | 0 / 7 字全過 |
| 昭源環方 700B | 40–54 | 0 / 7 字全過 |

**兩個字重在 50 mm 都通過**——所以這不是「會不會壞」的問題，是**餘裕**的問題。
筆寬隨輸出尺寸等比縮小：400R 比基準細約 35%，做 20 mm 小字模時餘裕明顯不足。

**選項**：A 收 400R（使用者實際看到的字重）／★ B 收 700B（與現行基準同字重級距）／
C 兩個都收（下拉多一項、部署多 20 MB）。

**選擇**：☑ B。三個理由：

1. 這個 registry 的用途就是**字模底**（`docs/STENCIL_CUTTING_STYLES.md` §5 明寫
   「純提供更好的字模底：均勻黑體最佳」）。選有餘裕的那個，不留「小尺寸才炸」的
   暫時性補丁。
2. **圓角並沒有因此變少**。`R/(W/2)` 從 1.087 掉到 0.615 看似「變方」，但那是分母
   （筆寬）變大造成的——**圓角絕對半徑兩者近乎相同**（75 EM vs 69 EM），本來就是
   同一套圓角化程序跑出來的。700B 看起來一樣圓，只是筆畫粗。（這條差點誤導決策，
   是 §89「下結論前覆查自己的數字」的又一例：比值變小 ≠ 特徵變弱。）
3. C 案多 20 MB 部署成本換一個「同字型不同字重」的下拉項，不值——真要調字重是
   R1b 的旋鈕該做的事，不是塞兩個 option。

**鎖成測試**：`test_s1_round_stroke_width_in_stencil_class` 直接比對「昭源環方
筆寬 ≥ 思源黑體 × 0.75」，失敗訊息寫明「字重選錯了（400R？應為 700B）」——
把這個決策變成機器守門，日後誰改檔名會立刻紅燈。

---

## 決策 3：OFL 遵循——查證原文，不沿用姊妹字型的措辭

**觸發**：思源黑體那條寫了「Reserved Font Name: Noto」。同為 OFL，順手複製措辭
最省事。

**查證**（§89）：抓 `LICENSE.md` 與字型 name table 逐項核對，結果與直覺不同——

- 版權方**不是**「The Chiron Fonts Project Authors」（我第一版是這樣寫的，錯），
  而是 **Copyright 2024-2026 Tamcy；Copyright 2014-2025 Adobe；Copyright 2016
  The Nunito Sans Project Authors**（內嵌西文用 Nunito）。
- 上游 OFL **未宣告任何 Reserved Font Name**。若照抄思源黑體的措辭寫「保留字型名
  Chiron」，就是替上游發明了一個它沒有主張的限制。

**處置**：`LICENSE` B 段、`licenses/README.md` 對照表、模組 docstring 與
`attribution_notice()` 四處同批訂正為查證後的事實；`test_s1_license_travels_with_the_font`
鎖住「LICENSE 與 licenses/README 都要有這筆」。因為走 raw 直取（決策 1），散布的
是原檔，OFL 的「不得單獨販售整套字型／通知須同行」兩條義務單純成立。

---

## 決策 4：新字源＝七個接點全數接上，並鎖成 parity 測試

承 §86 的教訓（新字源不能只加模組）與 `docs/STENCIL_CUTTING_STYLES.md` §5 的既有
食譜。動工前先做**兄弟實作掃描**，掃出 `noto_hei` 的全部接點，逐一對應：

| 接點 | 本輪動作 |
|---|---|
| `sources/chiron_round.py` | 新增（比照 `noto_hei.py`，env `STROKE_ORDER_ROUND_FONT_FILE`/`_DIR`） |
| `zentangle.SOURCE_REGISTRY` / `_LABELS` | ＋`chiron_round`→`昭源環方`（排在 `noto_hei` 之後） |
| `index.html` `#sc-source` 下拉 | ＋`<option value="chiron_round">昭源環方（圓體，圓端點）` |
| `scripts/render_fetch_fonts.sh` | ＋`round-fonts/` mkdir ＋ raw 直取 `fetch_one` |
| `render.yaml` envVars | ＋`STROKE_ORDER_ROUND_FONT_FILE` |
| `LICENSE` B 段 ／ `licenses/README.md` | ＋OFL 條目 |
| `tests/test_chiron_round.py` | 新增 18 項 |

**不做的接點（明示）**：不加 `/api/round-status` 端點——`noto_hei` 當初也沒加，
`list_sources()` 的 `ready` 欄位已是單一事實源（§76）。不動 `popup.py` 的降級階梯
——立體字卡片的鏤空字模預設維持思源黑體，圓體是**使用者主動選**的風格，不該偷改
既有輸出（§86 誠實標注／不無聲頂替的同一精神）。

**兩道 parity 鎖**（這是本輪比食譜多出來的部分）：

- `test_s1_stencil_dropdown_matches_registry`：下拉 option 集合 **≡** `SOURCE_REGISTRY`
  鍵集合。以前「只加模組沒加下拉」或「只加下拉沒登註冊表」會靜默漂移，現在紅燈。
- `test_s1_deploy_wiring_agrees_on_one_path`：fetch 腳本落點、`render.yaml` env 值、
  模組內建檔名**三處同名**。以前這三處靠人眼對，改檔名就會部署到抓得到卻讀不到。

---

## 驗證

- 新增 `tests/test_chiron_round.py` 18 項全過（含 5 個殘腔 0 拓撲字、筆寬級距、
  兩道 parity 鎖、授權登錄）。
- 既有六項清單同批改為七項：`test_zentangle_outline`（`list_sources` 順序＋錯誤
  訊息列鍵）、`test_zentangle_server`（`/api/zentangle/sources`）。
- 全套 pytest **2030 passed / 62 skipped**，0 failed。
- raw URL 兩個字重都實抓驗過 HTTP 200＋md5 與使用者本機 zip 內檔一致。

## 待辦（未動，留給下一輪）

- **R1b**：字模字重滑桿。依決策 0 的實測，區間 100–160 EM、預設維持 120 附近，
  `cap=round` 不動。不需要新資產。
- 更早架上的：R2 GlyphWiki/KAGE 字源、R3 手寫軌跡→OTF、B 路線真輪廓 ±δ 楷書
  粗細、官方插圖翻案（數據在 `2026-08-16_t3_pic_slot.md`）。
