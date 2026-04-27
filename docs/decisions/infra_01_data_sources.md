# 決策日誌：infra_01 — 資料源 chain（多源 fallback 設計）

**Phase 範圍**：Phase 1（g0v / mmh）→ Phase 5ai (punctuation) → 5ak (user_dict) → 5al (CNS font) → 5am (CNS Sung) → 5at (chongxi seal) → 5au (MoE Lishu) → 5av (MoE Sung) → 5aw (MoE Kaishu)
**版號階段**：0.1 → 0.11.x
**現存證據**：`src/stroke_order/sources/__init__.py`（AutoSource / RegionAutoSource）、`src/stroke_order/sources/*.py`（13 個 adapter）、`src/stroke_order/web/server.py:316` `_load()` + `_upgrade_to_*` chain

> **追溯方式**：本檔由 v0.13.0 程式碼狀態反推。每個 source adapter 的 docstring 都明寫了它對應的 phase tag，所以時序可以從 phase 字母排列推算。

---

## 整體脈絡

stroke-order 從 Phase 1 的「兩個資料源」一路擴展到目前的 **9 個 source + 3 種風格升級鏈**——這個增長過程暴露了一個核心 tension：**「字符覆蓋率」 vs 「資料品質」**。

| 軸線 | 偏好 | 代價 |
|---|---|---|
| 高品質筆順（含 raw_track + outline + 分類）| 寫字機器人友善 | 資料源稀少（g0v/mmh 約 9k 字）|
| 高覆蓋率（outline-only）| 罕見字也有字形 | 機器人輸出沒「下筆順序」 |

這條 chain 的演進就是不斷在「再多塞一個 source 補覆蓋率」的同時，**保護 raw_track 優先順序**——讓有筆順資料的字優先用筆順資料、沒有的才退到 outline。

---

## 決策 1：第一階段——g0v + MMH 雙源

**Phase**：1（最早） + 後續加 region 概念

**觸發**：Phase 1 寫 IR 時就決定要支援多源（見 `mode_01_single_char_and_ir.md` 決策 6），所以實作時 g0v 跟 mmh 同期出現

**選項**（從這兩個下選首選）：

| 編號 | 來源 | 字數 | 授權 | 含筆順？ | 含 outline？ |
|---|---|---|---|---|---|
| A | g0v/zh-stroke-data | ~6063 繁體 | open data（限制不明） | ✅ | ✅ |
| B | Make Me a Hanzi | ~9574（簡繁混）| LGPL | ✅（部分） | ✅ |
| C | KanjiVG | 日本漢字 | CC BY-SA 3.0 | ✅（centerline） | ❌ |

**選擇**：☑ **g0v 為 tw 主、MMH 為 cn 主、KanjiVG 為 jp 主**（region-aware）

**理由**：
> 立足台灣 → tw 區用 g0v。MMH 是 LGPL 商用安全 → cn 區做副選。KanjiVG 補日漢字。三個 source 各有強項，**用「region」概念當路由器**而非單一 priority list。

**程式碼證據**：
- `sources/__init__.py:126-131` `_ORDERS = {"tw": (G0V, MMH), "cn": (MMH, G0V), "jp": (KanjiVG, MMH), "auto": (G0V, MMH, KanjiVG)}`
- `sources/g0v.py` + `sources/mmh.py` + `sources/kanjivg.py`

---

## 決策 2：5ai — 加入 PunctuationSource（手刻 25 個標點）

**Phase**：5ai

**觸發**：使用者餵「你好，世界！」這種帶標點的句子進寫字機器人時，標點被當作「missing character」直接丟掉 → 機器寫到一半留白

**選項**：

| 編號 | 方案 | 評估 |
|---|---|---|
| A | 把標點當作「missing」直接略過 | 失敗——句子斷掉 |
| B | 用某個 CJK 字體的 outline 渲染標點 | outline-only，沒 raw_track，機器人 G-code 輸出空白 |
| C | **手刻 ~25 個常用標點的 raw_track** | 工程量小、品質高、機器人輸出真實有筆觸 |

**遭遇的困難**：
- B 看起來最快但會破壞「寫字機器人輸出」這個核心 use case——outline-only 字形寫 G-code 時是空 polyline，機器人筆抬下抬下沒實際移動
- 標點種類不多（句號 / 逗號 / 引號 / 全形 / 半形）→ 手刻不會爆

**選擇**：☑ C（手刻）

**程式碼證據**：`sources/punctuation.py` 包含 ~25 個標點的 hand-authored stroke data

**後續驗證**：✅ 5bi 抄經模式的「斷句點」功能直接利用了標點 raw_track（變成 polyline 描在格底）；如果當初選 B，5bi 整個功能無法成立

---

## 決策 3：5ak — UserDictSource 放在最高優先

**Phase**：5ak

**觸發**：使用者反饋「g0v / mmh 沒有的罕用字（地名、姓名、PUA 字）我想自己畫加進去」

**選項**：

| 編號 | 方案 |
|---|---|
| A | 把使用者的字加到內建 source 裡 → 程式碼污染 |
| B | 寫一個 UserDictSource，**最高優先級** |
| C | 寫一個 UserDictSource，最低優先級（fallback）|

**選擇**：☑ B（最高優先級）

**理由**：
> **使用者自畫的字應該 override 內建版本**——譬如「我覺得 g0v 的『的』字寫法不對，我想用我的版本」。如果放最後 fallback，使用者改不了已經有的字，違反「自訂優先」直覺。

**程式碼證據**：`sources/__init__.py:78` user_dict 第一個被嘗試
```python
def get_character(self, char):
    try: return self.user_dict.get_character(char)
    except CharacterNotFound: pass
    # 才接著嘗試 g0v / mmh / ...
```

**後續驗證**：✅ 後續 5d/5g 的 PSD（使用者筆順資料庫）的設計也繼承這個哲學——使用者的字最大

---

## 決策 4：5al / 5am — CNS 全字庫 outline 補覆蓋率

**Phase**：5al + 5am

**觸發**：使用者反饋「我想寫古文 / 罕見字 / 異體字，但 g0v + mmh + 自畫都還不夠」

**遭遇的困難**：
- 全字庫有 ~95k 字（覆蓋率比 g0v/mmh 高 10 倍）→ 強烈誘惑加進來
- 但全字庫**只有 outline 沒有筆順 / 沒有 raw_track**
- 強制 skeletonize（用 Zhang-Suen 取中線）能擠出 polyline，但品質低

**選項**：

| 編號 | 方案 | 取捨 |
|---|---|---|
| A | 不用全字庫 | 罕用字無法寫 |
| B | 全字庫直接放在 g0v / mmh **後面** fallback | 罕用字可寫但只有 outline 渲染（描紅可、筆順動畫不可） |
| C | 全字庫放第一，用 skeletonize 出 polyline | 機器人輸出可，但品質差 |

**選擇**：☑ B（fallback 模式）

**理由**：
> 不破壞高品質字符的優先級——g0v 有的字繼續用 g0v 的 raw_track，**只有 g0v 沒有的字**才退到 CNS 的 outline。代價：罕用字寫字機器人輸出**只能描 outline**（沒有真正的筆順），但這是「有得寫」vs「完全沒得寫」的取捨。

**程式碼證據**：
- `sources/__init__.py:108-113` CNS font 在 chain 最後
- `sources/cns_font.py` docstring 強調「outline geometry only — not stroke-by-stroke」

**後續驗證**：⚠ 部分問題——5d 筆順練習頁規劃時就明確指出，這些 outline-only 字「沒有真正筆順資料」是缺口。5d 的整個動機就是讓使用者**手寫補進真正筆順**。

**事後備註**：5ap (CNS_strokes_sequence.txt) 後續又加了「全字庫的官方筆畫順序」資料，但只有「stroke type 序列」沒有「座標」——可以用來分類但不能直接渲染。是個未完整的補救。

---

## 決策 5：5at / 5au / 5av / 5aw — 字型風格 source（篆/隸/宋/楷）

**Phase**：5at（崇羲篆體）→ 5au（教育部隸書）→ 5av（教育部宋體）→ 5aw（教育部標準楷書）

**觸發**：「我想寫篆書 / 隸書」——但 g0v / mmh 都只有楷書

**遭遇的困難**：
- 這些字型源**結構性**就跟楷書不同：篆書「日」是橢圓形不是方形、隸書有獨特波磔——用「楷書 outline + filter（讓字看起來像隸書）」是假隸書，書法家看一眼就破功
- 但又**不能**整個系統把楷書專屬的 hook policy / 筆畫分類丟掉，否則其他模式壞掉

**選項**：

| 編號 | 方案 |
|---|---|
| A | 寫「filter」style——用楷書資料 + 視覺處理（拉伸、加波磔）模擬其他字體 |
| B | 寫「swap」source——直接從真字型抓 outline 整個換 |
| C | 兩個並用：filter 給沒安裝字型的 fallback，swap 給有字型的 |

**選擇**：☑ **C（filter + swap 雙模式）**

**架構決策的關鍵**：

```
舊模式（5aj 之前）：style = filter
  楷書 IR → filter（5aj LishuStyle 加波磔/squash）→ 假隸書

新模式（5au/5av/5aw 之後）：style = swap
  使用者要求 lishu → 試 MoE 隸書字型 → 拿到真隸書 outline
                                  → 失敗 fallback 5aj 假隸書 filter
```

**理由**：
> 真字型的視覺品質碾壓 filter，但部署門檻高（要安裝 MoE 字型）。雙模式讓「有字型 → 真字體」「沒字型 → 至少有 filter 假樣子」兩種使用者都顧到。

**程式碼證據**：
- `web/server.py` 有 `_upgrade_to_sung` / `_upgrade_to_seal` / `_upgrade_to_lishu` 三個函式
- 每個都先試 swap（真字型）→ 失敗 fallthrough（保留 5aj 的 filter style）

**事後遭遇的 bug**：
- 5bw：lishu/seal **預設用 skeleton 模式**（從 outline thinning 取中線當 raw_track）→ outline 變空 → 抄經模式 outline-only 渲染變空白。後來修成「skeleton 模式仍保留 outline」+「skip 模式整個跳過 thinning」的雙模式。
- 5d-7-bugfix：lishu outline 的 EM bbox 不在中央 → reference 字形偏下方。後來加 bbox-center 對齊。

**這條決策的代價**：每加一個字型風格，後面要踩的 outline 座標 / hook / classifier 兼容性 bug 都會浮出來。最終 `_load()` 跟 server.py 的 upgrade chain 邏輯變得相當複雜——但這是覆蓋率 vs 品質的客觀代價。

---

## 決策 6：source chain 順序的最終定案

**Phase**：5aw 完成後穩定下來

**最終 AutoSource chain**（`sources/__init__.py:46-113`）：

```
1. UserDictSource          ← 最高優先（5ak）
2. G0VSource (primary)     ← 高品質筆順（Phase 1）
3. MMHSource (secondary)   ← LGPL 副選（Phase 1）
4. PunctuationSource       ← BEFORE outline-only fallbacks（5ai 故意）
5. MoeKaishuSource         ← outline-only 但較好品質（5aw）
6. CNSFontSource           ← 最後保險的 ~95k 字覆蓋（5al）
```

**關鍵設計**：punctuation 故意排在 outline-only fallbacks 之前

**為什麼這順序**：

| 順序 | 為什麼 |
|---|---|
| user_dict 第一 | 使用者自訂優先（決策 3） |
| g0v / mmh 緊接 | 高品質筆順優先（決策 1） |
| **punctuation 早於 outline-only** | CNS 字型雖含標點 outline，但**會壞掉寫字機器人輸出**——拿手刻的標點才有 raw_track。**這個順序是 5ai 設計的核心**，搞錯位置整個機器人輸出鏈會崩 |
| moe_kaishu / cns_font 最後 | outline-only 字源做覆蓋率兜底，盡量別用 |

**這條順序的測試保護**：
- `tests/test_sources.py` 多條測試 pin 死順序（避免後人改動誤踩）
- `tests/test_punctuation_source.py` 驗證機器人輸出含標點 raw_track 而非 outline

---

## 決策 7：region-aware 路由（tw / cn / jp / auto）

**Phase**：1（早期）+ 5ak/al/aw 補強

**觸發**：簡繁中文 + 日漢字使用者群有不同預設偏好

**選項**：

| 編號 | 方案 |
|---|---|
| A | 統一 chain（一視同仁） |
| B | 給使用者 `--region tw/cn/jp/auto` 參數路由不同 chain |

**選擇**：☑ B

**理由**：
> 台灣使用者寫「峰」想要繁體寫法，大陸使用者寫「峰」想要簡體寫法。同一個 codepoint 但兩個資料源的字形可能差異——region 路由讓使用者明示偏好。

**程式碼證據**：`RegionAutoSource._ORDERS` (`__init__.py:126`)

```python
"tw":   (G0VSource, MMHSource),       # 台灣繁體優先
"cn":   (MMHSource, G0VSource),       # 大陸簡體優先  
"jp":   (KanjiVGSource, MMHSource),   # 日本漢字優先
"auto": (G0VSource, MMHSource, KanjiVGSource),
```

**測試保護**：`tests/test_region.py` 確保 `_sources[0]` 對應 region 主資料源

---

## 沒做的決策（明確擱置）

- **OpenCC 簡繁轉換融進 source chain**：考慮過但決定**只在 fallback 時做變體查找**（`opencc-python-reimplemented` 在 punctuation 跟 KanjiVG adapter 內），不污染主 chain
- **加韓文 / 越南字喃 source**：覆蓋率有限的小眾需求，先擱置
- **網路即時拉 g0v JSON**：g0v.py 雖然有這個能力但預設不用——避免使用者沒網路就壞掉

---

## 學到的規則 / pattern（適用未來）

1. **Source chain 順序就是優先級政策**：每加一個 source 不是「塞個位置就好」——必須想清楚跟前後 source 的互動。punctuation 早於 outline-only 就是血淚教訓
2. **Outline-only vs raw_track 是兩個世界**：outline 給「人看的字形」，raw_track 給「機器人寫的軌跡」——選錯會讓某個 use case 整個失能
3. **Filter style vs Swap style 雙模式**：依賴外部字型的功能必須 fallback——「有最好、沒有也能堪用」
4. **Region awareness 從第一日就該設計**：後加會打亂既有測試
5. **每加一個 source 都要寫測試 pin 順序**：不然下次重構會誤改順序、bug 難察覺

---

## 相關檔案

- 主路由：`src/stroke_order/sources/__init__.py`
- 9 個 adapter：`src/stroke_order/sources/{g0v,mmh,kanjivg,punctuation,user_dict,cns_font,cns_strokes,cns_components,chongxi_seal,moe_kaishu,moe_lishu,moe_song}.py`
- _load() 統合：`src/stroke_order/web/server.py:316`
- 字型風格升級鏈：`src/stroke_order/web/server.py:345-434` (`_upgrade_to_sung/seal/lishu`)
- 測試：`tests/test_sources.py`、`tests/test_region.py`、`tests/test_punctuation_source.py`、`tests/test_user_dict.py`
- 部分後續決策：`infra_02_styles_filters_vs_swaps.md`（filter/swap 細節）、`mode_08_sutra.md`（5bz outline-preserving 補救）
