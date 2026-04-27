# stroke-order

[![CI](https://github.com/seyen37/stroke-order/actions/workflows/ci.yml/badge.svg)](https://github.com/seyen37/stroke-order/actions/workflows/ci.yml)
![tests](https://img.shields.io/badge/tests-1057%20passed-brightgreen)
![python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
![license](https://img.shields.io/badge/license-MIT-yellow)
![version](https://img.shields.io/badge/version-0.13.0-orange)

中文字元 → 向量筆跡轉換器，目標是餵給寫字機器人（AxiDraw 類繪圖機／自製筆型機械臂／任何吃 G-code 或 polyline 的裝置）。

## 為什麼

市面上已經有一堆「筆順動畫」的前端工具（教育部、hanzi-writer、bishun.18dao、zeroegg…），但它們的輸出都是**給人類看的畫面**。寫字機器人需要的是**給機器吃的軌跡資料**：SVG path / G-code / JSON polyline，帶有正確的筆順與幾何資訊。

這個工具做的就是這層轉換。

## 開發歷程

本專案由 **許士彥（[seyen37@gmail.com](mailto:seyen37@gmail.com)）獨立設計與開發**，於本機環境累積了 67 個內部 phase（從 Phase 1 → Phase 5g）的功能演進，最終在 **v0.13.0** 達到「9 個 Web UI 模式 + 1057 個單元測試全綠 + 完整公眾分享庫」這個成熟度才首次公開推送到 GitHub。

詳細的設計脈絡與決策考量見 [`docs/decisions/`](docs/decisions/) — 每個模式 / 基礎建設都有對應的決策日誌，記錄當時遇到的困難、選項評估、與最終解法。專案演進的時序則記錄在 [`docs/HISTORY.md`](docs/HISTORY.md)。

> 本 repo 的 git history 從 2026-04-26 v0.13.0 首次公開時開始，但**程式碼本體在更早就已存在於本機開發環境**——所有歷史 phase 的程式碼證據（phase tag、設計註解、test docstring）都嵌入在源碼裡可以驗證。

---

## 目前版本：0.13.0 (Phase 1 → 5g 完成)

> **Web UI 9 模式**：單字 / 字帖 / 筆記 / 信紙 / 稿紙 / 塗鴉 / 文字雲 / **筆順練習** (5d) / **公眾分享庫** (5g)。
>
> **`/handwriting`** 5d MVP — 個人筆順資料庫（PSD），收集真人手寫軌跡（時間戳 + 筆壓 + 觸控筆角度），EM 2048 座標，可直接餵寫字機器人。獨立 SPA，本機 IndexedDB 儲存，可匯出 JSON / Plotter SVG / ZIP。
>
> **`/gallery`** 5g MVP — 公眾分享庫，使用者可上傳 PSD JSON 分享，email magic-link 登入，SQLite 儲存。詳見 [docs/GALLERY_DEPLOYMENT.md](docs/GALLERY_DEPLOYMENT.md)。
>
> **1057 個單元測試**全部通過。

### Phase 1 — 核心轉換 pipeline ✅

- g0v/zh-stroke-data 資料載入
- 筆畫 1-8 類自動分類（橫/豎/撇/捺/…）
- Catmull-Rom spline 平滑化
- 已知 MOE bug 自動修復（gsyan888 列表）
- SVG / G-code / JSON polyline 三種輸出

### Phase 2 — 多資料源 + Web UI ✅

- **Make Me a Hanzi (MMH)** 資料源（9,574 字，**商用合法**）
- **Source abstraction + auto-fallback**（`--source=auto`）
- **Hook policy**（`--hook-policy=animation|static`）
- **Web UI**（`stroke-order serve`，FastAPI + hanzi-writer）

### Phase 3 — 漢字文化資料 + 多區域 + 動畫 ✅

- **5000 會意字分解資料庫**（朱邦復）—— 每個字的 head/tail 拆解 + 概念定義
- **繁↔簡 variant fallback**（溫↔温、國↔国 等）
- **KanjiVG 資料源**（日本漢字，CC BY-SA 3.0）
- **`--source=tw|cn|jp`**（區域 cascade）
- **GIF 動畫 exporter**（`-f gif`）

### Phase 4 — 部首分類 + 字帖 + 教材 ✅

- **朱邦復 2018 部首分類**（本存 / 人造 / 規範 / 應用 × 3-4 子類）
- **字帖 batch mode**（`stroke-order grid`）
- **ODP 簡報 exporter**（`-f odp`）

### Phase 5a — 筆記 / 信紙 / 塗鴉 + 多頁分頁 ✅

- **文字版面引擎**（`layouts.py`）— 自動斷行、自動翻頁、支援保留區
- **筆記模式**（`/api/notebook`）— A6/A5/A4 三種尺寸，方格／橫線／點陣／無四種格線
- **信紙模式**（`/api/letter`）— A4/A5 + 標題署名區
- **塗鴉模式**（`/api/doodle`）— 上傳圖片邊緣偵測 → SVG 線稿
- **5 模式 Web UI** + 多頁 ZIP 下載

### Phase 5b → 5h — 文字雲家族（ring / fill / linear / three_band / wordcloud）✅

- **wordart 模式**（`/api/wordart`）— 7 種基礎排列：
  - `ring`：沿形狀邊緣繞圈
  - `fill`：內部逐行排字
  - `linear`：多邊形每邊獨立文字 + 邊合併（`edge_groups`）+ 邊序選擇（`edge_start`/`edge_direction`）
  - `three_band`：圓/橢圓三段式（上弧 + 中線 + 下弧）
  - `wordcloud`：7 級權重詞雲（manual/frequency/random）+ 碰撞避免
  - `concentric`：多同心環
  - `gradient_v` / `split_lr`：垂直漸變、左右分治
- **`auto_cycle`**：文字過短時自動循環填滿
- **`auto_fit`**：文字過長時自動縮字大小
- **`align`**：spread / center / left / right 字距分布

### Phase 5i → 5q — 直書、稿紙與多格式下載 ✅

- **`direction=horizontal|vertical`** — 4 個版面模式（字帖／筆記／信紙／文字雲）全支援直書
- **字帖 grid 重構**（`/api/grid`）— tier-based ghost/blank 語意 + 3 格式下載（SVG / G-code / JSON）
- **筆記/信紙 `lines_per_page`** — 強制每頁 N 行/列（覆寫 line_height）
- **`first_line_offset_mm`** — 第一行/列起始位置精確控制 + UI 尺規 hover guide
- **Letter preset** — 美規 8.5×11 紙張

### Phase 5r → 5af — 塗鴉區、稿紙模式、信紙增強 ✅

- **筆記/信紙塗鴉區 CRUD**（`/api/notebook` POST + zones）
  - X/Y/W/H 拖曳 + 4 角 resize + 字格吸附
  - 從塗鴉模式匯入向量（`svg_content`）
  - 也可上傳本機 SVG 檔 / 直接貼 SVG 文字
- **筆記/信紙下載 3 格式**（SVG / G-code / JSON）含 text_fallback 診斷
- **信紙第一行位置 + 每頁行數**（與筆記同步）
- **稿紙模式**（`/api/manuscript`）— A4 直書，300 字（25×12）/200 字（20×10），字旁注音欄
- **隱藏格線**選項（`show_grid=false`）— 信紙＋稿紙

### Phase 5ag → 5ah — 塗鴉裁切 + 文字雲新形狀 ✅

- **塗鴉自動裁切**（`auto_crop_whitespace` / `auto_crop_border`）— 去白邊 + 剝外框
- **文字雲新形狀** — `star` / `heart` / `rounded` / `trapezoid` / `arc`，含形狀專屬旋鈕（star_inner_ratio 等）
- **`show_shape_outline`** — 是否畫外框

### Phase 5ai → 5am — 字源擴展與字型風格 ✅

- **標點符號源**（`PunctuationSource`）— ~40 個 CJK + ASCII 標點，手刻 raw_track 給機器寫
- **SVG `<text>` 文字 fallback** — 字源全失敗時用瀏覽器字型顯示，G-code 跳過並回報
- **4 種字型風格**（`style=kaishu|mingti|lishu|bold`）
  - `mingti`：橫細豎粗 + 末端襯線（仿宋體濾鏡）
  - `lishu`：橫筆波磔 + 整字壓扁（仿隸書）
  - `bold`：pen_size 全縮放
- **罕用字字典 `UserDict`**（`/api/user-dict`）— `~/.stroke-order/user-dict/{hex}.json`，3 種輸入：
  - 手寫 canvas
  - SVG 上傳
  - JSON 直貼
- **CNS11643 全字庫接入**（`CNSFontSource`）— 從 TW-Kai/Sung TTF 抽 outline，~95k 字
  - 三種模式：`skip`（純 outline）/ `trace`（描輪廓）/ `skeleton`（Zhang-Suen 骨架化）
  - 部件 metadata（`/api/decompose/{char}`）
- **CNS Sung 接 mingti 風格** — 環境有宋體 TTF 時，`style=mingti` 自動換真宋體 outline；無則退回 5aj 假襯線濾鏡

### Phase 5an — 4 個新 wordcloud 子佈局 ✅

- **`gradient_h`** — 水平字大小漸變（左大右小或反之）
- **`wave`** — 字沿正弦曲線排列；多條平行波 + 切線旋轉
- **`radial_convex`** — 中央大邊緣小（凸出感）
- **`radial_concave`** — 中央小邊緣大（凹入感）

---

## 安裝

```bash
# 基本安裝（CLI + Python library）
pip install -e .

# 加 Web UI
pip install -e ".[web]"

# 加 GIF 輸出
pip install -e ".[gif]"

# 全部功能
pip install -e ".[all]"
```

---

## CLI 使用

### 基本轉換

```bash
# SVG（outline 填色 + 筆順數字）
stroke-order convert 永 -f svg -o 永.svg --show-numbers

# SVG 疊加模式（墨跡 + 軌跡同框）
stroke-order convert 永 -f svg -o 永.svg --mode both --show-numbers

# G-code（AxiDraw 相容）
stroke-order convert 永 -f gcode -o 永.gcode --char-size 30

# JSON polyline
stroke-order convert 恩 -f json -o 恩.json

# 【Phase 3 新增】GIF 動畫
stroke-order convert 永 -f gif -o 永.gif --gif-duration=400

# 【Phase 4 新增】ODP 簡報（一字一 slide）
stroke-order convert 你好世界 -f odp -o greeting.odp
```

### 字帖 batch mode (Phase 4)

```bash
# 標準田字格練習單
stroke-order grid 你好世界 -o sheet.svg \
    --guide=tian --cell-style=filled \
    --cols=4 --repeat=1 --ghost-copies=2 --blank-copies=2

# 米字格 + 更多臨摹格
stroke-order grid 永 -o 永.svg --guide=mi --cell-style=filled \
    --cols=3 --repeat=3 --ghost-copies=3

# 純機器軌跡（只有紅色中線）
stroke-order grid 漢字 -o trace.svg --cell-style=trace
```

### 資料源與區域

```bash
# 資料源直選
stroke-order --source=g0v     info 永     # 教育部繁體
stroke-order --source=mmh     info 永     # Make Me a Hanzi (商用合法)
stroke-order --source=kanjivg info 永     # 【Phase 3】日本 KanjiVG

# 區域別名（Phase 3）
stroke-order --source=tw info 永     # g0v→mmh 串聯
stroke-order --source=cn info 们     # mmh→g0v
stroke-order --source=jp info 働     # kanjivg→mmh

# 預設 auto: g0v→mmh
stroke-order info 你好世界
```

### Hook policy

```bash
stroke-order convert 日 -f svg -o 日_有鉤.svg --hook-policy=animation
stroke-order convert 日 -f svg -o 日_無鉤.svg --hook-policy=static
```

### Web UI

```bash
stroke-order serve                # http://127.0.0.1:8000/
stroke-order serve --port 9000
```

Web UI（v0.11+，7 個模式分頁）：

| 模式 | 端點 | 用途 |
|---|---|---|
| 單字 | `/api/character/{ch}` `/api/meta/{ch}` | hanzi-writer 即時筆順 + 部件 metadata + 診斷 |
| 字帖 | `/api/grid` | tier-based 練習單；3 格式下載 |
| 筆記 | `/api/notebook` (GET+POST) | A6/A5/A4，方格/橫線/點陣，塗鴉區 CRUD |
| 信紙 | `/api/letter` | 標題＋署名，多頁；隱藏格線選項 |
| 稿紙 | `/api/manuscript` | A4 直書，300/200 字 + 注音欄 |
| 塗鴉 | `/api/doodle` | 圖片邊緣偵測 + 自動裁切 → SVG 線稿 |
| 文字雲 | `/api/wordart` | 11 種子佈局 × 16 種形狀 × 4 字型風格 |

橫幅顯示 CNS 全字庫狀態（楷體 / 真宋體 / 部件 metadata 是否載入）；單字模式底部顯示 5000 會意字分解 + CNS 部件。

### 診斷模式

```bash
stroke-order info 明愛永
# 明  U+660E  8 strokes  signature=15441522  source=g0v
#   validation: VALID
#   bbox: BBox(x_min=296, y_min=224, x_max=1752, y_max=1837)
#   decomp: 明 = 首[日](體) + 尾[月](體)  [會意/甲骨] 有光之日月，可見可知，明顯
#   ...
```

---

## Python 函式庫使用

```python
from stroke_order.sources import make_source
from stroke_order.classifier import classify_character
from stroke_order.smoothing import smooth_character
from stroke_order.hook_policy import apply_hook_policy
from stroke_order.decomposition import default_db as decomp_db
from stroke_order.validation import apply_known_bug_fix
from stroke_order.exporters.svg import save_svg
from stroke_order.exporters.gcode import save_gcode, GCodeOptions
from stroke_order.exporters.gif import save_gif

# 標準 pipeline
src = make_source("auto")
c = src.get_character("明")
c, _ = apply_known_bug_fix(c)
classify_character(c)
apply_hook_policy(c, "animation")
smooth_character(c)
# Phase 3 addition — attach decomposition metadata
c.decomposition = decomp_db().get("明")

# Outputs
save_svg(c, "明.svg", mode="both", show_numbers=True)
save_gcode(c, "明.gcode", opts=GCodeOptions(char_size_mm=30))
save_gif(c, "明.gif", frame_duration_ms=400)

# Inspect decomposition (Phase 3)
d = c.decomposition
if d:
    print(f"{c.char} = {d.head_root}({d.head_role}) + {d.tail_root}({d.tail_role})")
    print(f"概念: {d.concept}")
```

---

## 資料源對照

字源呼叫順序（v0.11+，`AutoSource`）：
**`UserDict → g0v → MMH → PunctuationSource → CNSFontSource(Kai)`**

| 面向 | g0v | MMH | KanjiVG | UserDict | Punctuation | CNS Font |
|---|---|---|---|---|---|---|
| 原始來源 | 教育部 | Arphic PL | Ulrich Apel | 使用者自製 | 手刻資料 | 全字庫 TTF |
| 字量 | ~6,063 繁 | 9,574 簡+繁 | ~11,000 日 | 任意 | ~40 標點 | ~95k Han |
| 授權 | 教育合理使用 | LGPL | CC BY-SA 3.0 | 使用者所有 | MIT | CNS 公開 |
| 資料結構 | outline + track | strokes + medians | centerlines | 同 g0v | raw_track | outline only |
| 機器寫字 | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠ 需 trace/skeleton |
| 觸發優先 | 1 | 2 | 區域選 | 0（最高） | 3 | 4（最後） |

**罕用字字典** — `~/.stroke-order/user-dict/{hex}.json`，3 種建立方式：手寫 canvas / SVG 上傳 / JSON 直貼。

**CNS 全字庫安裝** — 從 [data.gov.tw/dataset/5961](https://data.gov.tw/dataset/5961) 下載 Fonts_Kai.zip / Fonts_Sung.zip / Properties.zip / MapingTables.zip：

```bash
export STROKE_ORDER_CNS_FONT_DIR=/path/to/cns-fonts        # TW-Kai-98_1.ttf 等
export STROKE_ORDER_CNS_PROPERTIES_DIR=/path/to/cns11643   # CNS_component.txt + Unicode/
```

裝好之後罕用字（如 𡃁、鱻 等）自動可用；`style=mingti` 也會升級成真宋體 outline。

---

## 專案結構

```
stroke_order/
├── README.md
├── pyproject.toml
├── src/stroke_order/
│   ├── ir.py                          # 核心資料結構
│   ├── classifier.py                  # 筆畫分類 1-8
│   ├── smoothing.py                   # Catmull-Rom
│   ├── hook_policy.py                 # Phase 2
│   ├── decomposition.py               # Phase 3 - 5000.TXT
│   ├── radicals.py                    # Phase 4 - 朱邦復 2018 部首
│   ├── validation.py                  # bug 偵測修復
│   ├── shapes.py                      # Phase 5c+5ah - 16 種幾何形狀
│   ├── layouts.py                     # Phase 5a+5i - 文字版面引擎
│   ├── cns_skeleton.py                # Phase 5al - Zhang-Suen 骨架化
│   ├── cli.py                         # 命令列
│   ├── data/
│   ├── sources/
│   │   ├── g0v.py                     # 教育部繁體
│   │   ├── mmh.py                     # Phase 2 - MMH
│   │   ├── kanjivg.py                 # Phase 3 - 日本漢字
│   │   ├── punctuation.py             # Phase 5ai - 標點符號
│   │   ├── user_dict.py               # Phase 5ak - 罕用字字典
│   │   ├── cns_font.py                # Phase 5al/5am - CNS Kai/Sung
│   │   └── cns_components.py          # Phase 5al - CNS 部件 metadata
│   ├── styles/                        # Phase 5aj - 4 種字型風格
│   │   ├── kaishu.py                  # 楷書（identity）
│   │   ├── mingti.py                  # 仿宋體（5am 接 CNS Sung）
│   │   ├── lishu.py                   # 仿隸書
│   │   └── bold.py                    # 粗楷
│   ├── exporters/
│   │   ├── svg.py / gcode.py / json_polyline.py
│   │   ├── hanzi_writer.py            # Phase 2 - Web 前端
│   │   ├── gif.py                     # Phase 3 - 動畫
│   │   ├── grid.py                    # Phase 4+5j - tier-based 字帖
│   │   ├── notebook.py                # Phase 5a - 筆記
│   │   ├── letter.py                  # Phase 5a - 信紙
│   │   ├── manuscript.py              # Phase 5ad - 稿紙
│   │   ├── doodle.py                  # Phase 5a+5ag - 塗鴉 + 自動裁切
│   │   ├── page.py                    # 頁面共用 SVG 組件
│   │   ├── annotation.py              # 註解圖層
│   │   ├── wordart.py                 # Phase 5b-5h - 文字雲
│   │   └── wordcloud.py               # Phase 5d+5an - 詞雲（10 種子佈局）
│   └── web/
│       ├── server.py                  # FastAPI
│       └── static/index.html          # 7 模式單頁前端
├── tests/                             # 666 個單元測試
├── samples/                           # 各 phase 視覺驗證輸出
└── data/                              # g0v/mmh/kanjivg cache + 5000.TXT
```

---

## 授權

- **程式碼**：MIT
- **資料**：
  - **g0v**：教育部著作權，教育/研究用（§50 合理使用）
  - **MMH**：LGPL（可商用，需標註）
  - **KanjiVG**：CC BY-SA 3.0（需標註並以相同授權散佈衍生作品）
  - **朱邦復 5000.TXT**：出自《字易》，請尊重原作者著作
  - **CNS11643 全字庫**：政府開放資料（公開使用，需以「全字庫」標註）
  - **使用者罕用字字典**：使用者所有，本套件僅提供儲存／檢索機制

---

## 後續規劃（v0.12+）

- **骨架化筆順分割**（與 `CNS_strokes_sequence.txt` 對齊，把 CNS outline → N 筆獨立 stroke）
- **罕用字字典 UX 強化**（編輯既有字、字典匯入匯出）
- **真行書／篆書**（不只是濾鏡 — 需要結構級重排）
- **PIP 上架 + Docker image**
- **真實機器人測試**（AxiDraw 端對端驗證）
- **wordart 圓錐／按鈕形狀**（cone + capsule）

## Phase 變更紀錄

每個 phase 的細節（spec、決策點、視覺樣本）保存在 `samples/{phase}/` 目錄；完整 task list 見原始開發過程。可參考最近的 5am / 5an / 5ao 樣本快速理解最新功能。
