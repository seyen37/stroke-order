# 決策日誌：mode_01 — 單字模式 + 核心 IR 設計

**Phase 範圍**：Phase 1（核心 pipeline）
**版號階段**：0.1 → 0.2
**現存證據**：`src/stroke_order/ir.py`、`src/stroke_order/cli.py`（cmd_convert / cmd_info）、`src/stroke_order/sources/g0v.py`、`src/stroke_order/sources/mmh.py`、`README.md` Phase 1 段、`REF_ANALYSIS_G0V.md`

> **追溯方式**：本檔由 v0.13.0 程式碼狀態 + README 段落 + 程式碼 phase tag 反推。沒有原始 git history，故聚焦於「為什麼最終長這樣」而非「當時 commit 順序」。

---

## 整體脈絡

stroke-order 專案最初的目標是把中文字元轉成可餵寫字機器人（AxiDraw 類繪圖機 / 自製筆型機械臂）的向量資料。市面已有 hanzi-writer / 教育部筆順網等工具但都是「給人類看」的動畫——機器需要的是 polyline / G-code / SVG path 等可執行格式。

Phase 1 的任務：**把網路上現成的中文筆順資料源（g0v、Make Me a Hanzi）轉換成統一的 IR**，再從 IR 輸出機器讀得懂的格式。整個專案後續所有功能都以這個 IR 為地基。

---

## 決策 1：座標系選用 EM 2048（Y-down）

**觸發**：規劃 IR 時必須先鎖定座標系——後面所有資料源、所有渲染、所有測試都依賴這個

**選項**：

| 編號 | 方案 | 來源 / 慣例 |
|---|---|---|
| A | EM 2048（Y-down）| g0v / 教育部標準楷書 |
| B | EM 1024（Y-up） | hanzi-writer / Make Me a Hanzi（Arphic 1024 + ascender=900）|
| C | 自定義 0–1 normalized float | 抽象、無偏好 |

**考慮的因素**：
- g0v 是台灣本地最完整的開源筆順資料集 → 跟它對齊降低轉換誤差累積
- 教育部標準楷書字體（後來 5aw 加入）內部就是 2048 EM → 不用做雙重縮放
- HTML Canvas / SVG 預設 Y-down → 跟瀏覽器渲染天然一致
- 1024 EM 過小，未來高 DPI 渲染或 EM 內細節會失精度
- 0–1 normalized 看似乾淨，但所有資料都要先除/再乘，bug 風險增加

**選擇**：☑ A（EM 2048, Y-down）

**理由**：
> g0v 是「立足台灣」的核心資料源，跟它的內部表示一致 = 少一層轉換 = 少一個 bug 來源。Y-down 順著 SVG/Canvas 自然慣例。EM 2048 給未來的 outline 精細度足夠空間。

**程式碼證據**：`ir.py:20` `EM_SIZE: int = 2048`，docstring 明寫「g0v uses 2048, MMH uses 1024 (adapters scale)」

**後續驗證**：✅ 整個專案 67 個 phase 從未動過這個座標系。MMH 在 `mmh.py` adapter 自動 scale ×2 進入 IR，從未產生衝突。後來加入的全字庫 / 篆書 / 隸書 outlines 全都跟著 normalize 進 EM 2048，沒踩坑。

---

## 決策 2：IR 結構——Character → Stroke → Point 三層

**觸發**：IR 設計時要決定原子粒度

**選項**：

| 編號 | 方案 | 描述 |
|---|---|---|
| A | 單一大 dict + JSON | 全部塞進 dict，需要時 .get() |
| B | 三層 dataclass：Character / Stroke / Point | 結構清晰，type-checked |
| C | 物件 + 方法（OOP）：Character.draw() 直接渲染 | 物件導向，但混合 IR + 渲染 |

**考慮的因素**：
- Python 標準庫 `dataclass` 在 3.7+ 內建，零依賴
- 後續測試會大量寫 fixture 字符 → dataclass 構造方便
- 不想把渲染邏輯混在 IR 裡（單一職責）
- frozen + slots 可降低記憶體 + 防意外修改

**選擇**：☑ B（三層 dataclass，IR 與渲染分離）

**理由**：
> 純資料結構 + 渲染另放 `exporters/`。IR 在很多測試 fixture 裡需要被建立 / 比對 → dataclass 自動產生 `__eq__` / `__repr__` 省事。`Point` 設成 frozen+slots 因為座標不該變動且很多——記憶體成本累積快。

**程式碼證據**：
- `ir.py:29` `@dataclass(frozen=True, slots=True) class Point`
- `ir.py:148` `@dataclass class Character`
- 渲染邏輯全部在 `exporters/` 不在 IR

**後續驗證**：✅ 5d 階段（筆順練習頁）的 trace JSON 格式直接用了這個結構（traces[].strokes[].points[]）；5g 上傳的 PSD JSON 也對齊；機器人 plotter SVG 同樣使用——IR 設計從未需要破壞性更新。

---

## 決策 3：Stroke 同時保留 outline + raw_track 兩套表示

**觸發**：g0v 的資料本身就有「輪廓」(outline) 跟「中線軌跡」(track) 兩套——要選一個還是都留？

**選項**：

| 編號 | 方案 | 描述 |
|---|---|---|
| A | 只留 outline | 渲染填色字、不能畫成 polyline |
| B | 只留 raw_track | 渲染 polyline、不能填色 |
| C | 兩套都留 | 雙倍體積，但任何渲染需求都能滿足 |

**考慮的因素**：
- 寫字機器人需要 **polyline**（一筆一線）→ 必要 raw_track
- 要做「描紅版」(faded fill) → 必要 outline
- g0v JSON 兩種都有 → 不留是浪費資料
- 字源後來擴展：CNS 全字庫只有 outline、教育部隸書/篆書也只有 outline → 必須有 fallback 邏輯

**選擇**：☑ C（兩套都留）

**理由**：
> 不知道未來會做什麼模式，但已經有資料的兩種表示都先吃下來。後續確實全用上：
> - 寫字機器人輸出（plotter SVG）：raw_track polyline
> - 字帖 / 描紅 / 抄經 reference：outline fill
> - 5d 筆順練習頁的 reference layer：outline fill
> - 5bw skeleton fallback：outline 為空時退回 raw_track

**程式碼證據**：`ir.py:117-118` `raw_track: list[Point]; outline: list[OutlineCommand]`

**後續驗證**：✅ 多次救命——尤其 5bw 修隸書/篆書空白 bug 時，正是「skeleton 模式 outline=[] 但 raw_track 有值」這個並存設計救了沒爆掉，只需加 fallback render path。

---

## 決策 4：筆畫分類（kind_code 1-8）

**觸發**：Phase 1 需要對每個 stroke 標分類（豎/橫/撇/捺…），給後續分析跟 signature 用

**選項**：

| 編號 | 方案 | 來源 |
|---|---|---|
| A | 直接用 g0v 自帶的 stroke type 欄位 | 但 g0v 不一定有 |
| B | 用 hanzi-writer 風格的 32 類細分 | 太細、寫起來繁瑣 |
| C | 自訂 1-8 簡化分類（豎/橫/豎點/橫點/順彎/逆彎/撇/捺）| 涵蓋常見筆型 |

**考慮的因素**：
- 8 類已涵蓋 95% 漢字筆畫
- 0 = 未分類、9 = 其他 → 不確定的不勉強
- 1-8 數字便於做「字符 signature」（如「恩」= "1527823644" 十位數字）
- 教育部官方分類也是個位數量級

**選擇**：☑ C（自訂 1-8 + 0/9 兜底，總共 10 種）

**理由**：
> 「signature 字串」這個設計（每位數字代表一個 stroke kind）很重要——讓字符可以做機械式比對與分類。32 類太細、實際寫程式時 if-else 爆炸；3-4 類太粗，無法區分「橫」跟「橫折」。8 類是甜蜜點。

**程式碼證據**：
- `ir.py:78` `STROKE_KIND_NAMES` dict
- `ir.py:174` `Character.signature` property（`恩 → '1527823644'`）
- 「恩」這個字的 signature 還寫進 `REF_ANALYSIS_G0V.md §四`，算原始參考

**後續驗證**：✅ Phase 4 的部首分類、Phase 3 的字符比對、Phase 5 多個模式都依賴 signature；測試裡也用 signature 做 fixture 比對

---

## 決策 5：BBox.overflows_em 的設計

**觸發**：g0v 部分字符的 outline 會超出 [0, 2048] 範圍（譬如手寫風的捺鋒拖出 EM 框外）→ 後續排版需知道哪些字會「溢出」

**選項**：

| 編號 | 方案 |
|---|---|
| A | 渲染時自動裁切 / 縮放至 EM 框內 |
| B | 把資訊保留下來、由消費端決定怎麼處理 |

**考慮的因素**：
- 強制裁切會破壞字形美感
- 強制縮放會讓不同字大小不一致
- 消費端（字帖、信紙、筆記）需求不同——有的允許溢出、有的不允許

**選擇**：☑ B（在 IR 提供 `BBox.overflows_em` 訊號，由消費端自決）

**理由**：
> IR 不該預設一個視覺政策。後續 `validation.py` 跟 `docs/overflow_scan_report.csv` 都用這個訊號做篩選。

**程式碼證據**：`ir.py:55` `BBox.overflows_em` property

---

## 決策 6：source-agnostic IR — 第一日就決定要支援多源

**觸發**：Phase 1 寫第一個 source（g0v）時就要決定：IR 是綁 g0v 還是中性？

**選項**：

| 編號 | 方案 |
|---|---|
| A | IR 直接照搬 g0v 結構（最快） |
| B | IR 中性，每個 source 寫一個 adapter 轉成 IR |

**考慮的因素**：
- 已知未來會加 Make Me a Hanzi（不同 EM 1024、欄位名也不同）
- 也想保留加 KanjiVG / 教育部字體 / 全字庫的可能性
- B 多寫一個轉換層、A 之後要支援第二個 source 必然得重構

**選擇**：☑ B（IR 中性 + adapter pattern）

**理由**：
> ir.py 第一段 docstring 明寫「The IR is **source-agnostic**」——刻意。短期工程量略高但避開了重構。

**程式碼證據**：
- `ir.py:1-8` 模組 docstring 強調 source-agnostic
- `Character.data_source: str = "unknown"` 欄位記錄字符來源（g0v / mmh / cns_font / chongxi_seal / moe_lishu / moe_song / moe_kaishu / kanjivg / user_dict）
- `sources/` 子目錄下 13 個 adapter 各司其職

**後續驗證**：✅ 後續加入 mmh / kanjivg / cns_font / chongxi_seal / moe_lishu / moe_song / moe_kaishu / user_dict / punctuation 共 9 個額外資料源，**全部不用動 IR**——本決策是最有 leverage 的一個。

---

## 決策 7：g0v 當作首選資料源

**觸發**：要選一個 Phase 1 的「主資料源」當開發起點

**選項**：

| 編號 | 來源 | 優 | 缺 |
|---|---|---|---|
| A | **g0v/zh-stroke-data** | 中文社群、open data、~9000 字、含 outline + track + 筆順 | 授權限商業使用（需確認）|
| B | Make Me a Hanzi | LGPL 授權安全、~9000 字 | 簡體為主、Arphic 1024 EM、欄位較少 |
| C | KanjiVG | SVG 直接可用 | 日本漢字為主，繁中覆蓋不全 |
| D | 自己手動畫 | 完全自主 | 工作量爆表，不切實際 |

**考慮的因素**：
- 立足台灣，要繁體中文友善
- g0v 資料品質高、有筆順資訊、座標系跟教育部對齊
- 商用授權可後續用 mmh 補

**選擇**：☑ A（g0v 為首選）+ B (mmh) 為副選

**理由**：
> g0v 的繁中支援跟 outline+track 雙重表示最契合 IR。授權問題用 mmh fallback 解決——LGPL 商用安全，覆蓋同樣 ~9000 字。

**程式碼證據**：`sources/g0v.py` + `sources/mmh.py` 同期出現，`_load()` 函式裡 g0v 優先、mmh fallback

**後續驗證**：⚠ 部分驗證——後來發現 g0v 仍有覆蓋限制（罕見字 / 異體字 / 古文無），導致 5al 引入 CNS 全字庫（~95k 字）做最後 fallback。但 g0v 至今仍是主資料源。

---

## 決策 8：CLI 命令分四個子命令（convert / info / grid / serve）

**觸發**：Phase 1–2 設計命令列界面

**選項**：

| 編號 | 方案 |
|---|---|
| A | 單一 `stroke-order CHAR` 命令，行為猜測 |
| B | 子命令明確分工：convert / info / grid / serve |
| C | 多個獨立 binary：`stroke-convert` / `stroke-info` / … |

**考慮的因素**：
- CLI UX 慣例：git / kubectl / poetry 等都用子命令
- 每個子命令有自己的參數集，混在一起會 flag 爆炸
- 多個 binary 安裝部署複雜

**選擇**：☑ B（子命令模式）

**理由**：
> argparse `add_subparsers` 容易維護，每個 sub 自己定參數。`serve` 子命令把 Web UI 啟動跟 CLI 用法分開——使用者一看 `--help` 就知道有 web 界面。

**程式碼證據**：`cli.py:177-251`

---

## 沒做的決策（明確擱置）

- **單元換成 mm（毫米）**：考慮過讓 IR 直接帶物理單位，但決定維持 EM 抽象單位 + 在 exporter 層做最終 mm 換算（保持 source agnostic）
- **multi-language 漢字（韓國 / 日本 / 越南字喃）**：Phase 1 只做中文，KanjiVG（日文）後來加但是次要
- **stroke 順序的型別保證**：用 `index` 欄位 + list 順序兩重，但沒嚴格驗證是否連續，因為部分資料源會有跳號

---

## 學到的規則 / pattern（適用未來）

1. **「先選座標系」是地基決策**：所有後續模組依賴，一旦選定就再也不該改（5d 寫字練習、5g 公眾分享庫的座標系都是繼承這個 EM 2048）
2. **adapter pattern 對未知未來最有效**：IR 中性 + 每個 source 一個 adapter，13 年後加新字源只需要寫 adapter，IR 一行不動
3. **不要讓 IR 預設視覺政策**：overflow / 縮放 / 裁切交給消費端決定，IR 只提供訊號
4. **dataclass 比 dict 值得**：類型保護 + 自動 `__eq__` / `__repr__` 省去大量測試 fixture 工程

---

## 相關檔案

- 程式碼：`src/stroke_order/ir.py`（211 行）
- CLI：`src/stroke_order/cli.py:177-251`
- 第一資料源：`src/stroke_order/sources/g0v.py`
- 副資料源：`src/stroke_order/sources/mmh.py`
- 字符匯出：`src/stroke_order/exporters/`（多個 SVG/JSON exporter）
- 參考分析：`REF_ANALYSIS_G0V.md`（g0v 資料格式逆向工程）
- 後續資料源（不在 Phase 1）：`infra_01_data_sources.md`
