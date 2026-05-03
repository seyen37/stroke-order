# 2026-05-03 — Phase 5b r4 曼陀羅模式 (Mandala mode) MVP

> 新增「曼陀羅模式」第 11 個 mode。MVP 實作 user 指定的 Case B + 半圓交織 + 九字真言預設：中心 1 字（咒）+ 字環 N 字（臨兵鬥者皆陣列在前）+ 外圍 N 個圓彼此 overlap 形成 rosette 的 mandala band。

**版號**：0.14.82 → 0.14.83
**Phase**：5b r4

---

## User intent (需求 lock-in)

User 從 3 個 case + 多種 mandala primitive 中選擇實作：

- **Case B**：中心字 + 字環 N 字 + 外圍 mandala（不是純中心字 case A，也不是中心 mandala icon case C）
- **半圓交織** primitive（直擊「彼此纏繞交會」需求）
- **九字真言預設**：中心「咒」+ 字環「臨兵鬥者皆陣列在前」(N=9)
- **獨立 toggle**：顯示中文字 / 顯示 mandala 兩個 checkbox

---

## 架構決策

### 1. 新模式 vs 擴充 wordart

選新 mode（`/api/mandala`、`mandala-view` 主面板、`mandala.py` exporter），**不**塞進 wordart concentric layout。

理由：

- wordart 已 13 種 layout / 5 種 shape variants / 多種對齊方式，內部複雜度高；mandala 的中心字 + 字環 + 裝飾的語意跟 wordart 不同方向（wordart 重「字繞圖形」，mandala 重「字＋裝飾共構同心圖騰」）。
- mandala 可以 share 工具函數（`_place_char_svg`、`_rotation_for`、`_load`），但不該共享 layout pipeline — 維護成本擴散。
- 新 mode 在用戶端命名清楚（「曼陀羅模式」直觀），跟「文字雲模式」有清楚區隔。

### 2. 後端 SVG 生成（不走前端 vector）

跟 wordart / stamp 一樣後端 server-side render：char outline 走後端 char_loader、mandala primitive 後端 SVG path。前端只 fetch + show。

理由：

- 字 outline 必須走後端（loader 跟資料源綁定）
- 整體 SVG 後端組裝可保留 G-code export pathway（後續用得上）
- 前端只負責 UI form + render 結果顯示，邏輯薄

### 3. Case A / C 用 toggle 而非顯式選擇

User 提到 3 個 case，但實作只暴露兩個 boolean：`show_chars`、`show_mandala`。Case 自動由 toggle 推導：

| show_chars | show_mandala | 視覺 case |
|------------|--------------|----------|
| ON         | ON           | Case B 全功能（默認） |
| ON         | OFF          | 純字環（非 user 列舉的 case，但有意義） |
| OFF        | ON           | 純 mandala（接近 Case A 的「字隱藏」變體） |
| OFF        | OFF          | 空 |

不需要 case dropdown — 兩個 checkbox 就 cover 完所有有意義組合。Case C（中心 mandala icon）目前未實作；後續 r5+ 再加 `center_type` (char/icon) toggle。

### 4. N 邊獨立於字環長度

`n_fold` 參數空 → 自動取 ring_text 長度（默認 9 字真言 → N=9）。User 可手動設成 12-fold mandala 配 9-fold 字環，**字環跟 mandala 對稱軸解耦**。

理由：

- 「字數 = 對稱軸數」是常見 default 但非通則（例：8 字字環配 16-fold lotus mandala 也合理）。
- 解耦讓 user 在風格實驗時有自由度，後續加 preset 主題時也能利用（preset 可固定 mandala N=12，不論字環幾字）。

### 5. 半圓交織 (interlocking arcs) 數學

```
N 個圓，圓心位於半徑 r_band 處等分排列（角度 = -90° + 360i/N）
每圓半徑 r_petal = r_band × sin(π/N) × overlap_ratio
```

`overlap_ratio = 1.0` → 相鄰圓相切（半弦長 = 半徑）；`> 1.0` → overlap rosette。預設 `1.25`（視覺上明顯交織但不過深）。

選 `circle` SVG element 而非 `path`：

- SVG `<circle>` 比 `<path>` 短 + 語義清楚 + browser/cairosvg 渲染最 fast path。
- 需要 dash / 雙線等變化時再升級到 `<path>`（後續 r5+）。

---

## 實作 footprint

| 檔案 | 動作 |
|------|------|
| `src/stroke_order/exporters/mandala.py` 新建 | `interlocking_arcs_band_svg`、`compute_mandala_placements`、`render_mandala_svg` |
| `src/stroke_order/web/server.py` | 新增 `/api/mandala` endpoint，loader 共用 `_load + _upgrade_to_*` pipeline |
| `src/stroke_order/web/static/index.html` | mode radio 加 `<input value="mandala">`；新增 `<main id="mandala-view">` 設定面板（中心字 / 字環 / N / 尺寸 / 半徑比 / overlap / 線寬 / 字朝向 / 字型 / toggles / 紙張 / 渲染按鈕）；JS `mandalaBuildParams + renderMandala`；views map 加 entry |
| `tests/test_mandala.py` 新建 | 12 個測試 — 幾何 helper（4）+ placements（3）+ full render（5）|

---

## 驗證

- pytest test_mandala + test_align + test_wordart + test_wordcloud + test_stamp → **283 passed in 4.99s**
- API smoke：`/api/mandala?center_text=咒&ring_text=臨兵鬥者皆陣列在前` 200 OK，content-type image/svg+xml，X-Mandala-Placed = 10、N-Fold = 9
- 視覺驗證 6 cases：default / chars-only / mandala-only / N=12 override / overlap=1.5 / overlap=1.0(tangent) — 都正確

---

## 後續迭代方向

每輪 1 個 small step：

- **r5**：第 2 個 mandala primitive — 蓮花瓣 (lotus petal)，搭配 dropdown 切 motif
- **r6**：層數 ≥ 2（兩個 ring band 用不同 motif）
- **r7**：preset 主題下拉（「九字真言」「蓮花」「法輪」「火焰結界」等預設套組）
- **r8**：Case C 中心 mandala icon（`center_type` = char / icon）
- **r9**：線條樣式（雙線 / 三線 / dash）
- **r10+**：火焰光環、金剛杵、編織繩紋、鋸齒邊等 primitive 補完

---

## Lessons / 適用 future round

1. **新模式做 MVP 前先確認後端能力**：mandala primitive 純幾何，後端純算就好；字渲染複用 `_place_char_svg` 不必重造。一開始就盤算清楚「啥要新寫、啥要 import」是省時間的關鍵。

2. **`_load` 回 tuple 而非 Character 是踩過的坑**：在 mandala loader 直接用 `c = _load(...)` 結果 `c` 是 `(Character, ValidationResult, applied_fix)` tuple，後續 `c.strokes` AttributeError。應該 `c, _, _ = _load(...)`。Lesson：複雜 helper signature **第一次用要先 grep 一個 caller 看 unpacking 模式**，不要假設 return Character。

3. **Toggle 兩個 boolean > 顯式 case enum**：user 提了 3 個 case，但 case 是 toggle 組合的 surface form，後端只認兩個 visibility flag 更簡潔，UI 也不需 dropdown。「枚舉用戶看到的東西」vs「枚舉內部狀態」是兩回事，後者通常較少維度。

4. **預設值要呼應主題**：「咒」+「臨兵鬥者皆陣列在前」直接讓 mandala 模式有「神秘感」first impression，比預設「日月金木水火土」中性字一打開就對味，user adoption 阻力低。

---

## r5 補丁：字保護 halo（防止 mandala 線切過字）

**版號**：0.14.83 → 0.14.84

User 反映 mandala 圓的 outline 會穿過字 glyph 的負空間（內部白色區），雖然字技術上 z-order 在最上層，但視覺上仍像「被切」。要求保護中文字、又要 halo 區域盡可能緊貼字身（不要讓 mandala 的 rosette 結構被掏空）。

**解法（Z-order blocker pattern）**：在 mandala band 跟 chars 之間插一層白色實心圓 halo，半徑 = `char_size_mm × radius_factor`（預設 0.55）。SVG 渲染順序：

1. mandala 圓圈（黑線）
2. 白色 halo（實心圓，蓋住 halo 區域內的 mandala 線）
3. 中文字（畫在 halo 之上）

效果：mandala rosette 主結構保留，僅字位置上有「咬一口」的視覺缺口，每字周圍乾淨無 stroke 干擾。

**radius_factor 定錨**：

| 數值 | 對應幾何 | 視覺 |
|------|---------|------|
| 0.50 | 內切圓（剛好涵蓋 bbox 中心十字） | 最緊；字 bbox 角落可能露邊 |
| **0.55**（預設） | 緊貼字身 | 楷書 glyph 罕填滿 bbox 角落，視覺夠用 |
| 0.65 | 涵蓋大部分 bbox | 字被完整保護，但 mandala 缺口較大 |
| 0.70 | 外接圓（√2/2 ≈ 0.707） | 完整罩住 bbox，mandala 缺口明顯 |
| > 0.70 | 過大 | mandala band 局部被掏空，rosette 結構受損 |

**實作 footprint**：`mandala.py` +20 行（`_char_protection_halos_svg` helper + render order rewire），server +2 query params (`protect_chars` / `protect_radius_factor`)，UI 多一個 row（checkbox + 半徑比 input）。後端 SVG 結構：mandala block → char-halos block → chars block，z-order 是擺位順序，不需 SVG mask/clipPath（簡單可靠）。

**驗證**：4 個新 unit test（halo on/off、show_mandala 關時 halo 也省、半徑隨 factor scale），16/16 mandala 通過；視覺驗證 halo_50 / 0.55 / 0.70 三種 factor，確認 0.55 是 sweet spot。

**Lesson**：「z-order blocker」比 SVG mask/clipPath 簡單一個量級且效果相同。SVG `<rect fill="white">` / `<circle fill="white">` 蓋在下面元素上 = poor man's mask。用前者是因為 mask 需 `<defs>` + `<mask>` + 引用 + viewport bbox 計算，而 z-order blocker 純物理擺位、語意零負擔。當「保護某區域不被別的元素覆蓋」目標明確且區域形狀規則時，z-order blocker 是首選。

---

## r6 補丁：蓮花瓣 (lotus petal) primitive + 樣式切換

**版號**：0.14.84 → 0.14.85

加入第 2 個 mandala primitive。原本 r4 只有「半圓交織 (interlocking arcs)」，視覺風格單一；r6 多一個「蓮花瓣 (lotus petal)」teardrop 形狀，藏傳/印度經典 mandala 視覺。

**幾何設計**：每瓣 2 條 quadratic bezier 構成 teardrop：

- 內側 base 點：半徑 `r_inner = r_band - half_len`
- 外側 tip 點：半徑 `r_outer = r_band + half_len`
- `half_len = r_band × sin(π/n) × length_ratio`（預設 1.25 跟 arcs 同尺度，切換 style 時整體大小一致）
- 兩條 bezier 的控制點：半徑 r_band，左右 ±`half_angle` 處
  - `half_angle = (π/n) × width_ratio`（預設 0.6 = 較瘦的尖瓣）

**為何 quadratic 不用 cubic**：

quadratic（1 個控制點）就能畫出 teardrop 兩側的弧線；cubic（2 個控制點）給更多自由度但也增加參數複雜度。teardrop 的對稱性讓 quadratic 已足夠—雙瓣 mirrored 的對稱結構由「左控制點」「右控制點」分別擔當，等效於一條 cubic。

**為何 r_band 是 bezier 控制點半徑**：

控制點放在 r_band（瓣的中心半徑）讓瓣最寬處剛好在 r_band 圓周上，視覺上瓣的中央正好沿 mandala 的 nominal 半徑展開。這跟 arcs 的「圓心在 r_band」尺度一致 → 切換 style 時整個 mandala 占用半徑範圍不變，UI 不用 retune r_band_ratio。

**Dispatch 設計**：API `mandala_style: "interlocking_arcs" | "lotus_petal"`，default 維持 `interlocking_arcs` backward compat。Style-specific 參數（arcs 的 `overlap_ratio`、lotus 的 `lotus_length_ratio` / `lotus_width_ratio`）獨立並存，UI 用 dropdown change 事件 show/hide 對應 row（避免 user 看到混淆無關參數）。

**實作 footprint**：

| 檔案 | 動作 |
|------|------|
| `mandala.py` | 新增 `lotus_petal_band_svg`；`render_mandala_svg` 加 `mandala_style` dispatch + 2 個 lotus 參數 |
| `server.py` | API 加 `mandala_style` (regex pattern)、`lotus_length_ratio`、`lotus_width_ratio` 3 個 query params |
| `index.html` | 「Mandala 樣式」dropdown；2 個 row 互斥顯示（arcs / lotus 專用參數）；JS `mandalaSyncStyleRows()` change 事件 + init |
| `tests/test_mandala.py` | 5 個新測試（lotus 幾何 3 + render dispatch 2）；21 通過 |

**Lessons / 適用 future round**：

1. **同尺度切換降低 UI 摩擦**：lotus 跟 arcs 共享 `r_band`、用同樣的 `r_band × sin(π/n) × ratio` 半幅長度公式，切換 style 不需重新調整其他參數。如果 lotus 用 `r_band ± 30%` 之類另一套尺度規則，user 切換時還要手動 retune 半徑比，UX 差。Pattern：**新 primitive 的尺度公式跟既有一致是降摩擦的免費午餐**。

2. **Style-specific UI 用 row 顯隱不要塞同一 row**：arcs 用 overlap、lotus 用 length+width，如果擠在同 row 加 disabled 灰底會很亂。獨立 row + JS 切換顯隱 = 視覺乾淨 + 行為對 user 直覺（看到的就是當前 style 該調的）。

3. **後端 dispatch 用 string literal 不要 enum class**：`mandala_style: str` + Query regex pattern 比 Python Enum 簡單（FastAPI Enum 在 OpenAPI schema 會綁 import，遷移負擔大）。內部 if-elif dispatch 兩個分支可讀性高，不需 strategy pattern overkill。

---

## r7 補丁：第 3 個 primitive — 法輪 / 輻射光線 (radial rays)

**版號**：0.14.85 → 0.14.86

加入第 3 個 mandala primitive。N 條徑向直線從 r_inner 射到 r_outer，最簡單的 SVG primitive（純 `<line>`），但視覺上是經典「法輪輪輻 / 太陽光線」。

**幾何**：跟 lotus 同尺度公式

```
half_len = r_band × sin(π/n) × length_ratio
r_inner  = r_band - half_len
r_outer  = r_band + half_len
```

每條 `<line x1 y1 x2 y2>`，stroke-linecap=round 讓端點圓潤。

**為何用 `<line>` 不用 `<path>`**：

`<line>` 是 SVG 原生 primitive，比 `<path d="M ... L ...">` 短一半且語意明確。對於「直線」這種規則形狀直接用 `<line>` 是 SVG canonical 寫法；`<path>` 留給 bezier / arc 等需要 d 字串的複雜形狀。

**為何不附 hub / rim**：

附了 hub circle（中心小圓）跟 rim circle（外圈大圓）會變成「法輪 dharmachakra」傳統樣式，視覺更完整。但這樣 user 拿到的是 high-level 預成品，跟「primitive」初衷相違背 — primitive 應該是 building block，hub / rim 是 composition layer 的事（r10+ 多層 ring 時可在內外加額外圓）。**「primitive 一個就做一件事」是 unix 哲學在 SVG 設計上的應用。**

**搭 halo 後的 emergent 視覺**：

光線在字位置被 halo 白圓切斷一段 → 視覺上像「光線從字後方射出，被字遮住」。這是 r5 halo + r7 rays 兩個小 feature 疊加產生的 emergent benefit，沒額外開發成本。

**實作 footprint**：

| 檔案 | 動作 |
|------|------|
| `mandala.py` | 新增 `radial_rays_band_svg()`；`render_mandala_svg` dispatch 加 `radial_rays` 分支 + `rays_length_ratio` 參數 |
| `server.py` | API 加 `rays_length_ratio` 參數，`mandala_style` regex 加 `radial_rays` 選項 |
| `index.html` | dropdown 加「輻射光線 (radial rays / 法輪)」option；新增 `md-rays-row`（光線長度比 input）；`mandalaSyncStyleRows` 多 1 個分支 |
| `tests/test_mandala.py` | 4 個新測試（emit N lines / 0 N empty / 12 o'clock 位置 / render dispatch lines）；25 通過 |

**Lessons / 適用 future round**：

1. **同尺度公式是 primitive 系列的隱形 invariant**：arcs / lotus / rays 都用 `r_band × sin(π/n) × ratio` 算半幅 → 無論用哪個 primitive，mandala 占用半徑範圍一致。這個 invariant 不是巧合而是 r4 一開始就定的設計準則，r6 / r7 各自加新 primitive 時 follow same formula → user 切換 style 不用重 retune `r_band_ratio` / `n_fold` / 任何半徑類參數。**將「同尺度」設為設計 invariant 後，每加一個 primitive 都自動繼承這個 UX 好處。**

2. **半透明的 emergent feature**：r5 halo 設計時只想到「擋字」，沒想到 r7 rays 配上去會變成「光線穿過字」效果。Composability of small features 常常產生意外好處。Pattern：**小 feature 比大 feature 更容易組合產生 emergent visual / behavior**。

3. **複雜化 primitive (加 hub/rim) 還是組合層解決 (多 ring)**：選後者。primitive 保持 atomic，組合用 layering 達成。長期維護成本低（每個 primitive 獨立可測），UX flexibility 高（user 可自由組合 hub + spokes + rim 用 3 個獨立 layer，比 hardcoded dharma_wheel primitive 自由）。

---

## r8 補丁：字佈局原則重構 — 字在 mandala 線條內部空間

**版號**：0.14.86 → 0.14.87

User 確立 7 條曼陀羅核心原則，最關鍵 2 條：

1. **線條圓滿連續**：mandala 元素必須是 closed shape，不被切斷
2. **字在線內空間**：字位於線條圍出的「內部」（圓內 / 圓交集 vesica / 其他幾何形）

r5 的 halo z-order blocker 違反原則 #1（白圓擦掉 mandala 線一段）；r4-r7 的 layout 違反原則 #2（字環跟 mandala band 在獨立半徑，字不在 mandala 圖形內）。r8 重構 layout 數學讓字「天然」位於 mandala 線條內部。

### 三個 composition_scheme

新增參數 `composition_scheme` ∈ {freeform, vesica, inscribed}，預設 **vesica**。

| Scheme | r_band 公式 | primitive 角度 offset | 字位置語意 |
|--------|-----------|--------------------|------------|
| **vesica**（默認） | `r_ring / cos(π/N)` | `180°/N`（字之間）| 字位於相鄰兩 mandala 圓的交集 (vesica piscis) 中央 |
| **inscribed** | `r_ring`（圓心 = 字位置） | `0°` | 每字 1 圓包住，圓半徑 = `char_size × inscribed_padding_factor` |
| **freeform**（backward compat） | `r_total × r_band_ratio` | `0°` | r4-r7 行為，字環跟 mandala 各自半徑 |

### 字距 (char_spacing) 取代半徑比

vesica / inscribed 模式下，r_ring 由字距推算：

```
r_ring = char_spacing × char_size_ring + (char_size_center + char_size_ring) / 2
```

字距定義 = 中心字外緣到字環內緣的距離（單位 = 字身長度）。預設 2，user 可選 1 ~ N+1（user 規格）。

freeform 模式仍用 `r_ring_ratio` (0.1-0.9)，UI dropdown 切 scheme 時自動 show/hide 對應 input。

### vesica 數學保證

字位置 P 位於 (r_ring × cos θ_i, r_ring × sin θ_i)。相鄰兩圓圓心位於 (r_band × cos(θ_i ± π/N))。為讓 P 落在兩圓心連線的徑向中點：

```
r_band × cos(π/N) = r_ring  →  r_band = r_ring / cos(π/N)
```

P 到任一圓心距離 d = r_ring × tan(π/N)。要 P 在圓內，r_petal ≥ d。對 default `overlap_ratio = 1.25`：

```
r_petal = r_band × sin(π/N) × 1.25 = r_ring × tan(π/N) × 1.25 = 1.25 × d
```

→ 字確實在圓內（字到圓心距離 = 0.8 × r_petal，留 20% 邊距）。vesica 寬度 = `2 × r_ring × tan(π/N) × √(1.25² − 1) = 1.5 × r_ring × tan(π/N)`，約等於 1.5 × char_size_ring 對 default 配置 → 字 bbox 完整在 vesica 內。

### inscribed 為何 r_petal 直接吃 char_size

inscribed mode 圓心 = 字位置，圓半徑與其他 N-fold 幾何無關（不是 r_band × sin(π/N) 邏輯），而是「夠大包住字 bbox」。`r_petal = char_size_ring × 0.7` 是預設（外接圓 √2/2 ≈ 0.707 略小，視覺飽滿）。

新增 `r_petal` override 參數到 `interlocking_arcs_band_svg`，當顯式指定時繞過 `overlap_ratio` 公式。lotus / rays primitive 在 inscribed mode 不適用（沒有「圓內」概念），fallback 到 freeform 公式 — UI 不阻止 user 選但效果可能無 inscribed 視覺。

### Halo 預設行為改變

- freeform：halo ON（保留 r4-r7 行為，因為 mandala 線條可能切過字）
- vesica / inscribed：halo OFF（字本來就在線內空間，不需要 halo 擋；halo 反而違反原則 #1 線條圓滿）

UI 切 scheme 時 auto-toggle halo（但 user 手動勾過後不再自動切，記錄 `dataset.userTouched`）。

### 實作 footprint

| 檔案 | 動作 |
|------|------|
| `mandala.py` | 新增 `compute_r_ring_from_spacing` / `compute_layout_geometry` helpers；`interlocking_arcs_band_svg` 加 `r_petal` override；`compute_mandala_placements` 加 `r_ring` override；`render_mandala_svg` 加 3 個 scheme params + dispatch；info dict 加 `composition_scheme` / `r_ring_mm` / `r_band_mm` |
| `server.py` | API 加 `composition_scheme` (regex)、`char_spacing` (0.5-20)、`inscribed_padding_factor` (0.4-1.5)；response headers 加 X-Mandala-Scheme / R-Ring / R-Band |
| `index.html` | 「字佈局」row（dropdown + char_spacing input + inscribed-only padding row）；JS `mandalaSyncSchemeRows()` change 事件 + show/hide r_ring_ratio + auto-toggle halo |
| `tests/test_mandala.py` | 9 個新測試（helpers 5 + 3 scheme rendering + char_spacing scale）；33 個全通過 |

### 驗證

- pytest mandala + align + wordart + wordcloud + stamp → 305 passed in 6.07s
- 視覺驗證 5 cases：vesica（字在圓交集）/ inscribed（每字一圓）/ inscribed_pad08 / freeform（halo on）/ vesica_sp_3（字距 3 → mandala 外推）
- inscribed: 9 個小圓繞中心字，每圓包住一個字環字 ✓
- vesica: 9 個大圓 overlap，字位於 vesica piscis 中央 ✓
- 字距變化 (2 → 3) 視覺驗證 mandala 整體外推 ✓

### Lessons / 適用 future round

1. **字佈局是 mandala layout 的最重要 invariant**：r4-r7 把 r_ring 跟 r_band 當兩個獨立參數調，視覺 OK 但語意不對 — 字跟 mandala 沒幾何關係。r8 重新把 r_ring 跟 r_band 用 `r_band = f(r_ring, scheme, n)` 綁定，從此字位於 mandala 內部空間是「天然成立」的（不靠 halo 後處理）。**Pattern：當兩個半徑有確定關係時，用公式綁定比讓 user 各自調更安全**。

2. **vesica 是最有「曼陀羅感」的 scheme**：技術上 vesica piscis 是兩圓重疊區域，視覺上字位於 vesica 中央，被相鄰兩圓的弧線「擁抱」— 這正是 user 強調的「彼此纏繞交會」最直接的視覺呈現。原則 #2 的最 elegant 實作。

3. **r_petal override 是非破壞性 API 擴展**：原 `interlocking_arcs_band_svg(r_band, n, overlap_ratio)` 公式適合 vesica/freeform，但 inscribed 需獨立公式。加 `r_petal: Optional[float] = None` override，None 時走原公式（backward compat），有值時直接用。新需求不破壞老 caller。

4. **halo 這一輪沒移除是對的**：halo 在 freeform 還有用（保留 r5 機制）；vesica/inscribed 自動關但 user 仍可手動開（萬一 size 設置不當還能救援）。**「不刪舊功能、調整 default」比「刪舊功能 + 不留 escape hatch」安全**。

### 後續方向

r8 確立 scheme 框架後，後續可：

- **r9**：多層 ring band（每層獨立 scheme + style + N + 半徑）
- **r10**：補完 user 列舉的元素（圓點 dots、三角形 triangles、波浪 wave、螺旋 spiral 等 primitives）
- **r11**：preset 主題（一鍵套「九字真言 vesica」「蓮花型」「法輪」等）

---

## r9 補丁：自動縮字避免碰觸 mandala 線

**版號**：0.14.87 → 0.14.88

User 反映 r8 default config 下：

- arcs + vesica：字 (10mm) 觸碰圓邊 → 因為 vesica 寬度 = 1.5×r_ring×tan(π/N) ≈ 20mm 但徑向窄處只有 6.7mm
- lotus + inscribed：字觸碰瓣邊 → 因為瓣形 teardrop 中央寬但兩端尖，bbox 角落超出瓣

要求自動縮小字體保持 clearance。

### 設計

新增 `auto_shrink_chars: bool = True` (預設開) + `shrink_safety_margin: float = 0.85` (margin 越小越保守)。

`max_safe_char_size_ring()` helper 算出每個 (scheme, style) combo 的幾何最大字大小：

**arcs + vesica**：

```
clearance = r_petal − d
         = r_band·sin(π/N)·overlap_ratio − r_ring·tan(π/N)
         = r_ring·tan(π/N)·(overlap_ratio − 1)
max_char = 2 × margin × clearance       # 字 inscribed 圓 ≤ clearance
```

For default config (r_ring=37, N=9, overlap=1.25, margin=0.85):
```
clearance = 37 × tan(20°) × 0.25 = 3.37 mm
max_char  = 2 × 0.85 × 3.37 = 5.72 mm   # 從 10 mm 縮到 5.72
```

**lotus + inscribed**：

瓣中心半寬 W = r_band×sin(half_angle)，瓣寬隨徑向 Δr 線性收窄到 0 (linear approx of bezier)。bbox 角落 (Δr = char_size/2) 處需 ≤ margin × half_width(Δr)：

```
char_size/2 ≤ margin × W × (1 − char_size/(2·half_len))
char_size × (1 + margin·W/half_len) ≤ 2·margin·W
max_char = 2·margin·W / (1 + margin·W/half_len)
```

For default config (r_band=37, half_angle=12°, length=1.25, margin=0.85):
```
W = 37 × sin(12°) = 7.69 mm
half_len = 37 × sin(20°) × 1.25 = 15.81 mm
max_char = 2×0.85×7.69 / (1 + 0.85×7.69/15.81) = 13.07 / 1.413 = 9.25 mm
```

### 為何用「inscribed circle」而非「bounding circle」protection

使用 inscribed circle protection（char_size/2 ≤ clearance）而非 bounding circle protection (char_size·√2/2 ≤ clearance)：

- bounding circle 會多收 41% (√2 倍 stricter)
- 中文 glyph 罕填滿 bbox 角落（楷書尤其明顯）→ 用 inscribed 保護視覺已足夠
- 用 bounding 會 over-shrink，default 配置下字會縮到 4mm 太小看不清

### 為何 r_ring 不變、只縮渲染字大小

r_ring 是 char_spacing × char_size_ring 推算出。如果 shrink 後也跟著縮 r_ring，會 cascade（small char → small ring → smaller mandala → 沒空間就反而碰更嚴重）。

正解：r_ring 用 user 設的「intended char_size」算（保持 user 對 spacing 的意圖），渲染用 `effective_char_size = min(intended, max_safe)`。User 設字距 2 即字距 2 字身（用 intended size），實際畫出字小一點是因為避線。

### 為何只 cover 兩個 combo 不全部

- **arcs + inscribed**：圓半徑 = char_size × padding_factor，圓自適應字大小，不需 shrink
- **rays + vesica/inscribed**：rays 是直線、char 在線之間或之上，幾何上 char 不在 enclosed space → 沒有「碰線」問題（inscribed mode 雖然線會穿字心，但這是 rays 不適合 inscribed 的 fundamental issue，留 r10+ 處理）
- **lotus + vesica**：lotus 在字之間（vesica scheme），char 不在瓣內 → 不適用

未來新 primitive 加入時，如果有「字在線內」關係就在 `max_safe_char_size_ring` 裡新增分支即可，dispatch pattern 易擴展。

### Halo 跟 auto-shrink 的關係

兩個獨立機制：

- **halo**：z-order blocker，把 mandala 線在 halo 內擦掉（違反原則 #1 線條圓滿）。freeform 用，vesica/inscribed 預設關。
- **auto-shrink**：縮字大小，讓字 bbox 不到線。維持線條完整。vesica/inscribed 預設開。

兩者互補：freeform 用 halo（不改字大小但切線），vesica/inscribed 用 shrink（不切線但縮字）。User 可分別控。

### 實作 footprint

| 檔案 | 動作 |
|------|------|
| `mandala.py` | 新增 `max_safe_char_size_ring()` helper（公式 dispatch by scheme×style）；`render_mandala_svg` 加 2 params + 計算 effective char_size；info dict 加 original / effective / shrunk 三鍵 |
| `server.py` | API 加 `auto_shrink_chars` (bool)、`shrink_safety_margin` (0.5-1.0)；3 個新 response headers (X-Mandala-Char-Size-Original/Effective/Shrunk) |
| `index.html` | 字佈局 row 加「🔍 自動縮字避免碰線」checkbox + margin input；status bar 顯示 「字 10 → 5.72 mm（自動縮小）」提示 |
| `tests/test_mandala.py` | 6 個新測試（arcs+vesica shrink、no-shrink threshold、lotus+inscribed shrink、arcs+inscribed no-op、render info original/effective、shrink off keeps size）；40/40 通過 |

### 驗證

- pytest 全套 311 passed
- 視覺驗證：
  - arcs+vesica shrink_on：字 5.72mm 完整在 vesica 內、不碰圓邊 ✓
  - arcs+vesica shrink_off：字 10mm 凸出 vesica 邊（user 原本看到的）
  - lotus+inscribed shrink_on：字 9.25mm 在瓣內留 clearance ✓
  - arcs+inscribed shrink_on：字不變（圓自適應字）✓

### Lessons / 適用 future round

1. **constraint solver 用解析公式 > 數值搜尋**：max_safe_char 對 lotus 是隱式方程（char_size 同時在左右兩邊），但用代數技巧可解 closed form。Closed form 比 binary search 快 + 結果 deterministic + 易測。**Pattern：能 solve algebraically 就 solve，binary search 是 fallback**。

2. **「不縮 r_ring 只縮渲染字」是關鍵 insight**：cascade 的 r_ring shrink 會讓 mandala 跟字一起縮小，沒解決問題。正確做法是把 user intent (字距 N×char_size) 的字大小固定當「frame reference」，渲染字按 frame 內可放大小決定。**「frame stays, content adapts」pattern**。

3. **inscribed circle vs bounding circle 的取捨**：對中文字，inscribed circle (char_size/2 半徑) 是合理的安全 buffer；bounding circle (√2/2 半徑) 過 strict。glyph 實際 ink 分布幾乎都在 inscribed 圓內，bbox 對角線是「保留地」。設計約束時要考慮 actual content 分布而非數學最壞情況。

---

## r10 補丁：多層 ring band — 額外裝飾層

**版號**：0.14.88 → 0.14.89

加入「多層 mandala」能力。原本 1 個主 mandala band（跟字環有 scheme 關係），r10 加入 0~N 個「extra decoration layers」純裝飾層，各自獨立位置/style/N、不跟字環互動。

### 資料模型決策

**Layer 二分**：
- **主 mandala** = 跟字環有幾何關係（vesica/inscribed/freeform scheme），位置由 r_ring 推算
- **Extra layers** = 純視覺裝飾，位置自由 (`r_ratio × r_total`)，N 自由

不把所有層統一成 list-of-layers 模型，因為主 mandala 的 scheme 機制（r_ring, r_band 綁定）是 user-facing concept，跟 extra layers 的「自由位置」是不同 mental model。

### API serialization：JSON string

FastAPI Query 不直接支援 list of dict。選 JSON string param `extra_layers_json` （max 2000 chars），server 端 `json.loads` 解析，壞 JSON / 非 list / dict 內 keys 缺失都容錯（fallback 到 default）。

JSON schema：
```json
[
  {"style": "lotus_petal", "n_fold": 18, "r_ratio": 0.95,
   "lotus_length_ratio": 0.4, "lotus_width_ratio": 0.5},
  {"style": "radial_rays", "n_fold": 36, "r_ratio": 0.30,
   "rays_length_ratio": 0.8}
]
```

### UI 簡化：固定 2 個 slot

不做動態增刪 row（複雜度高、user 罕用 > 2 層）。固定提供：

- **🌸 外裝飾層**（r_ratio 預設 0.95，於主 mandala 之外）
- **⚡ 內裝飾層**（r_ratio 預設 0.30，於中心字跟字環之間）

兩 slot 各 toggle 啟用，啟用後 input 才生效（disabled 時 opacity 0.5 視覺反饋）。Style/N/半徑/長度比可獨立調。User 從這兩 slot 切到「3 層以上」直接呼叫 API 即可（不限 UI）。

### 為何外層 default N = 18 (主 N × 2)

放射對稱原則 #4：如果裝飾層 N 跟主 N 不對齊，會破壞「對稱軸放射」感。預設用主 N 的整數倍（×2、×4），即使 user 沒注意這點，視覺仍對齊。User 可自由調 N 但 default 就好。

### 為何 default 外層 = lotus_petal、內層 = radial_rays

「外圈花瓣 + 內圈光線」是傳統 mandala 視覺最常見組合（蓮花外、光輪內）。Default 給 user 一個「好看」的起點，可立即啟用看效果，再從那 tune。

### Z-order

```
背景 → debug 輔助圓 → 主 mandala band → 額外裝飾層 → halo → chars
```

Extra layers 跟主 mandala band 同 z-order（都在 halo / chars 之下），所以 halo 也會擋它們（如果 user 開 halo + 額外 layer 跟 char position 重疊）。實作上分兩個 `<g>` group（`class="mandala"` + `class="extra-layers"`），方便 user CSS / DevTools 分別 inspect。

### 實作 footprint

| 檔案 | 動作 |
|------|------|
| `mandala.py` | 新增 `render_extra_layer_svg(cx, cy, r_total, layer, default_n)` 公用 dispatcher；`render_mandala_svg` 加 `extra_layers: Optional[list]` param + 渲染 block；info dict 加 `extra_layers_count` |
| `server.py` | API 加 `extra_layers_json: str` (max 2000 chars)；`json.loads` 容錯解析；response header `X-Mandala-Extra-Layers` |
| `index.html` | 2 個 row：外裝飾層 / 內裝飾層，各 toggle + 5-6 個 inputs；JS `mandalaBuildExtraLayersJson()` 從 UI 構建；`mandalaSyncExtraLayerEnable()` toggle 啟用 input 視覺反饋 |
| `tests/test_mandala.py` | 7 個新測試（dispatcher 3 style + default_n fallback、render with 2 layers、skip invalid layers、no layers default）；47/47 通過 |

### 驗證

- pytest 全套 318 passed
- 視覺 5 cases:
  - main_only: 0 extra layer (預設)
  - with_outer_lotus_18: 主 vesica + 外圈 18 蓮花瓣 — 「外蓮花」傳統視覺
  - with_inner_rays_36: 主 vesica + 內圈 36 條光線 — 中心字被光輪圍住
  - with_both_layers: 內外都有 — 「外蓮花 + 中字環 vesica + 內光輪」三層豐富組合
  - rich_3_layers: 3 個 extra (18-arcs + 9-lotus + 36-rays) + 主 vesica = 4 層 mandala，極繁複裝飾

### Lessons / 適用 future round

1. **異質性比同質性更務實**：原本想做「全部 layer 統一 list-of-layer 模型」（純裝飾 list 加上 chars layer），看似乾淨。但主 mandala 跟字環的 scheme 機制是不同 mental model（user 設字距 → r_ring → r_band 推算），不該把 user 看到的「主 mandala」當 list 中的一員。**Pattern：當兩種 entities 在 user mental model 是不同 concept 時，保持 API 異質**。

2. **JSON string param 是 list-of-dict 的務實 escape hatch**：FastAPI Query 限制是不能直接傳 list of dict。JSON string + server 端 parse + 容錯（壞 JSON / wrong shape silently skip）是最常見 escape hatch。3 行 `json.loads + isinstance check` 比設計 nested Pydantic model 簡單一個量級。

3. **UI 固定 2 slot vs 動態增刪**：固定 2 slot 對 80% 用例夠用，UI 複雜度低（不需 add/remove row 邏輯、不需 dynamic input 命名）。動態增刪適合 ≥ 5 個常見 layer 的進階場景，目前不必要。**MVP 階段先固定，發現需求再擴**。

4. **Default 配置給 user「立即 OK」起點**：`default_n = 主N × 2`（保持對稱）+ default style「外蓮花內光輪」（傳統視覺）讓 user 一啟用就有合理結果。如果 default = arcs + N=2 + r=0.5 這種「最小組合」，user 開了卻看不到改善，feature discovery 失敗。**Default 是設計，不是「random 的合法值」**。

---

## r11 補丁：補 4 個 primitives — 圓點 / 三角形 / 波浪 / 鋸齒

**版號**：0.14.89 → 0.14.90

依 user spec 列舉的元素，補 4 個常見 mandala primitive。Scope decision：**只開放在 extras layers**，不擴主 mandala dispatcher（避免主 mandala 跟字環的 scheme 機制 explosion）。

### 4 個新 primitive

| Primitive | SVG 元素 | 視覺特徵 | 主要 param |
|-----------|---------|---------|----------|
| **dots** (圓點) | `<circle fill>` × N | 實心小圓繞圈，spacer / 光點 | `dot_radius_mm` |
| **triangles** (三角形) | `<polygon>` × N | 三角形 (尖端朝外/內) | `length_ratio`, `width_ratio`, `pointing` |
| **wave** (波浪) | 一條 `<polyline>` (sine 採樣) | 沿圓周正弦波，柔軟律動 | `amplitude_ratio`, samples=24/wave |
| **zigzag** (鋸齒) | 一條 `<polyline>` (alternating) | N 齒鋸狀，「結界」邊界感 | `tooth_height_ratio` |

每個 primitive 跟現有 (arcs/lotus/rays) **保持 API 一致**：(cx, cy, r_band, n) 為位置 + 各自 style-specific kwargs。

### Triangles 的 pointing 設計

- `outward`：apex 在外、base 在內 → 視覺感「太陽光線 / 火焰外射」
- `inward`：apex 在內、base 在外 → 視覺感「向心聚焦 / 三角光束」

JS 自動依 `r_ratio` 推：r_ratio ≥ 0.7（外圈）→ outward；< 0.7（內圈）→ inward。User 直覺通常是「外層三角朝外、內層三角朝內」，自動推 default 對 80% 用例。

### Wave 採樣 + 開放 vs 閉合

選 polyline (open) 而非 path Z (closed)。理由：

- wave 視覺是「沿圓周 1 圈的波形」，不是「填充區域」
- 採樣 N×24 + 1 點，最後一點回到起點 → 視覺上閉合，但 SVG 結構是 polyline (沒 fill 模糊區域)
- 用 stroke-linejoin="round" + linecap="round" 讓接合處平滑

### 為何只支援 extras 不擴主 mandala

主 mandala 的 vesica/inscribed scheme 要求字跟 primitive 有幾何關係（字在圓內 / 字在圓交集）。新 primitives 不全有「字在內部」語意：

- dots：圓點太小，字進不去
- wave：曲線無 enclosed space
- zigzag：曲線無 enclosed space
- triangles：理論上字可在三角內，但 inscribed mode 跟字 bbox 形狀（square）不對齊，視覺彆扭

所以新 primitives 只當「裝飾層」（extras）使用，純視覺，不參與字 layout 計算。User 想用三角形包字 → r12+ 再考慮（需要新 scheme 或 char_size 自動 fit）。

### UI 簡化：sliders 共用 polymorphic key

UI 上 outer/inner layer 各只有「len」(瓣長/光線長/振幅/齒高) 跟「width」(瓣寬/三角寬) 兩個共用 numeric input，依 style 對應到不同 backend param。優點：UI 不爆炸（不需 per-style row）；缺點：「len」label 不夠精確（user 不一定看得懂 dots 的 len = dot_radius_mm 是 mm 不是 ratio）。

接受這個 tradeoff，因為 r11 階段重點是「擴 primitive 數量」，每 primitive 的 fine-tune UX 留 r12+ 處理（preset 主題會包好 default，user 不直接調）。

### 實作 footprint

| 檔案 | 動作 |
|------|------|
| `mandala.py` | 4 個新 primitive 函數 (`dots_band_svg` / `triangles_band_svg` / `wave_band_svg` / `zigzag_band_svg`)；`render_extra_layer_svg` dispatcher 加 4 個分支 |
| `index.html` | outer/inner dropdown 各加 4 個 option；JS `_mandalaApplyStyleSpecificParams` 依 style 對應 polymorphic len/width input → backend param keys；triangles `pointing` 由 r_ratio 自動推 |
| `tests/test_mandala.py` | 9 個新測試（每 primitive geometry + dispatcher）；56/56 通過 |

### 視覺驗證（5 case）

- **dots** 36-fold r=0.95：外圈點陣項鍊 ✓
- **triangles_out** 12-fold outward r=0.95：外圈火焰 / 太陽光 ✓
- **triangles_in** 12-fold inward r=0.30：內圈聚焦光束 ✓
- **wave** 18-fold r=0.95：外圈波浪邊界，柔軟律動 ✓
- **zigzag** 36-fold r=0.95：外圈結界鋸齒邊框 ✓
- **rich_combo** 4 layer 疊加（wave + dots + triangles + zigzag）— 多層次裝飾 ✓

### 7 個 primitive 總覽

| Primitive | 類別 | 主用途 | 用於主 mandala? | 用於 extras? |
|-----------|-----|--------|-----------------|-------------|
| interlocking_arcs | 圓 | rosette / vesica | ✓ | ✓ |
| lotus_petal | 花瓣 | 蓮花座 | ✓ | ✓ |
| radial_rays | 線 | 法輪 / 光線 | ✓ | ✓ |
| dots | 點 | 點陣 spacer / 光點 | ✗ | ✓ |
| triangles | 三角 | 火焰 / 聚焦 | ✗ | ✓ |
| wave | 曲線 | 柔軟邊界 | ✗ | ✓ |
| zigzag | 折線 | 結界 / 邊框 | ✗ | ✓ |

### Lessons / 適用 future round

1. **Primitive class 化的進階方向**：當 primitive 數 > 5，dispatcher if-elif 鏈會變長。可重構成 `MANDALA_PRIMITIVES = {"dots": dots_band_svg, ...}` registry。**目前 7 個還在可控範圍，下次加到 ~10 個再重構**。

2. **「主 mandala 不擴」的 scope discipline**：抗住「為什麼不全部 primitive 都能當主 mandala」的誘惑。主 mandala = 跟字環有 geometric contract 的 layer，不是任何 N-fold 圖形。Primitive 沒有 enclosed space → 字無法「內部包覆」→ 違反原則 #2。**Scope discipline 是 architectural decision 不是懶**。

3. **Polymorphic UI input 是空間 vs UX trade-off**：len/width 兩個 共用 input 對 7 個 primitive map 到 ~10 種 backend keys，UI 緊湊但 label 失準。長遠看 preset 主題（r12）會把 default 包好讓 user 不必直接調這些 numeric，所以 polymorphic input 不是長期 API。**MVP 接受 ambiguity，preset 來解決**。

---

## r12 補丁：preset 主題 — 一鍵套全部設定

**版號**：0.14.90 → 0.14.91

把 r4-r11 累積的 knobs（mandala_style + scheme + char_spacing + style-specific params + extras layers）包成 5 個 high-level 風格名稱。User 從 dropdown 一選整套設定就到位，不必逐項調。

### 5 個 preset 設計

| Key | 名 | 視覺 | 主 mandala | extras |
|-----|---|-----|-----------|--------|
| **kuji_in** | 九字真言 | r4 經典 vesica + 9 字字環 | arcs/vesica | — |
| **lotus_throne** | 蓮花座 | inscribed 蓮花瓣 + 外點陣 + 內點光 | lotus/inscribed | dots(24)+dots(6) |
| **dharma_wheel** | 法輪 | 輻射光線 + 鋸齒外框 + 內三角聚光 | rays/vesica | zigzag(32)+triangles(8) |
| **flame_seal** | 火焰結界 | vesica + 外火焰三角 + 鋸齒邊 + 內波紋 | arcs/vesica | zigzag+triangles+wave |
| **minimal** | 素雅 | 純 vesica，無裝飾 | arcs/vesica | — |

每個 preset 自帶配套的 center_text / ring_text（神主題對應的字）：

- 九字真言 → 「咒」+「臨兵鬥者皆陣列在前」
- 蓮花座 → 「佛」+「南無阿彌陀佛」（6 字 → N=6）
- 法輪 → 「法」+「苦集滅道」（4 字 → N=4）
- 火焰結界 → 「封」+「臨兵鬥者皆陣列在前」（9 字）
- 素雅 → 「心」+「色不異空空不異色」（8 字 → N=8）

### Architecture: Backend single source of truth

選 backend 定義 `MANDALA_PRESETS` const + 提供 `/api/mandala/presets` GET endpoint。前端 fetch 後 populate dropdown，change 時把整個 config 套到 UI inputs。

**不選**前端 hardcoded JS const 因為：

- 配置散兩端（Python const + JS const）= 二份 source of truth，易發散
- Backend 可寫 unit test 驗證每個 preset config 跑得起來（render_mandala_svg 不報錯）
- 未來 preset 增加 / 改 default 在 Python 一處改即可

**不選** preset 解析放 backend (i.e. user 傳 `preset=kuji_in` 後端套設定)：

- preset 套用後 user 通常還要 fine-tune（改 char_spacing 等），fine-tune 邏輯 in URL 跟 preset 邏輯 in URL 會搞混 priority
- 改用前端套用 → preset 只是 「UI helper」，按「產生」時 URL 還是跟 inputs 一致；fine-tune 直接改 input 即可

### UI 互動：dropdown 即時套用

dropdown change → JS `mandalaApplyPreset(key)`：

1. 找到 preset config (`MANDALA_PRESETS` cached from API call)
2. 把每個 input 用 `_setIfExists(id, value)` set 值
3. extras layers：按 r_ratio 排序，最大的 → outer slot，第二大 → inner slot（>2 layers 從 UI 填不下）
4. dispatch `change` event 到所有 sync handler（觸發 row visibility / disabled / halo auto-toggle）

UI 顯示 preset 的 description 在 hint span，user 知道每個 preset 是什麼風格。

### 為何 preset 包 center_text + ring_text

每個 preset 對應一個 mood/theme（蓮花座 vs 法輪 vs 火焰結界），對應的字也應該換（佛/法/封）。如果 preset 只換配置不換字，user 套了「蓮花座」但中心字還是「咒」會違和。

User 可以套 preset 後再改 center_text / ring_text — preset 只是 starting point。

### 實作 footprint

| 檔案 | 動作 |
|------|------|
| `mandala.py` | `MANDALA_PRESETS` dict (5 個 preset)；`get_mandala_preset(key)` / `list_mandala_presets()` helpers |
| `server.py` | `/api/mandala/presets` GET endpoint，回傳 list of {key, name, description, config} |
| `index.html` | preset dropdown row（最上方 highlight）；JS `mandalaLoadPresets()` (init fetch)、`mandalaApplyPreset(key)` (套設定 + 觸發 sync events) |
| `tests/test_mandala.py` | 5 個新測試（registry contains kuji_in、unknown returns None、list_keys complete、each preset renders、API endpoint）；61/61 通過 |

### 驗證

- pytest 全套 332 passed
- API smoke：`/api/mandala/presets` 回 5 個 preset metadata
- 視覺：每個 preset 跑 render endpoint（傳 preset 的 config 當 query params）都成功 render，視覺各具特色
  - 蓮花座：6 瓣花 + 外圈 24 點 + 中央 6 點
  - 法輪：4 條光線 + 鋸齒邊框 + 內三角
  - 火焰結界：9 圓 vesica + 18 三角火焰 + 36 鋸齒 + 18 波紋
  - 素雅：純 8 圓 vesica
  - 九字真言：r4 經典默認（沒 extras）

### Lessons / 適用 future round

1. **Preset = 「設計師決策」不是「random combo」**：每個 preset 的 config 是經過視覺設計過的（合理 N、合理 r_ratio、合理 length）。user 一鍵套就應該得到「好看」的結果，這是 preset 的價值。如果 preset 只是「default 組合 dump」，user 套了還要大幅 tune 才看得，preset 失去意義。**Pattern：preset 開發階段花時間 tune visually，user 階段直接享受**。

2. **Preset 包字（不只配置）的取捨**：包字 → 切換 preset 像「換主題」連字一起換，sense of「整套換」。不包字 → user 文字保留，只換視覺風格，更靈活但失去主題感。選包字因為大部分 user 用 preset 是探索風格，不是「我固定這 9 字想換看看不同視覺」。**Default behavior 取「最有引導性」的選項**。

3. **Single source of truth at backend > duplicated at frontend**：邏輯上 preset 純前端 helper（不影響 server-side render），可以全 hardcode in JS。但 backend 為 source of truth 換來：可測 + 集中改 + future 可給 CLI 也用。多 1 個 API endpoint 的成本遠小於兩端配置 drift 的長期成本。**Pattern：configuration-as-data 一律 backend single source**。

### r12 後 mandala 模式的 maturity

8 輪迭代（r4 → r12）後，mandala 模式現有：

- 7 個 primitives（圓 / 蓮花 / 光線 / 點 / 三角 / 波 / 鋸齒）
- 3 個 composition schemes（vesica / inscribed / freeform）
- 多層 ring band（主 + 外 + 內，獨立 N/r/style）
- 字保護機制（halo + auto-shrink）
- 5 個 preset 主題（一鍵套）
- 完整 toggle（show_chars / show_mandala / 個別 layer enable）
- 61 個 unit tests 覆蓋幾何 / dispatch / scheme / shrink / extras / preset

---

## r13 補丁：螺旋 (spiral) primitive

**版號**：0.14.91 → 0.14.92

補完 user spec 列舉的元素裡剩下的「螺旋」。視覺上「成長 / 演化 / 能量流動」象徵，常見於漩渦曼陀羅 / 銀河 / DNA 螺旋。

### 幾何

N 個 spiral arm 從 `r_inner` 旋向 `r_outer`，N-fold 對稱。每 arm = 1 條 `<polyline>`（採樣 N×24 點）。

每 arm 參數 t (0→1)：

```
r(t)   = r_inner + (r_outer − r_inner) × t        # Archimedean
phi(t) = θ_i + sign × spin_turns × 2π × t          # 旋轉
```

跟其他 primitive 同尺度（`half_len = r_band × sin(π/N) × length_ratio`）。

**參數**：

- `length_ratio`: 跟其他 primitive 同尺度（半幅）
- `spin_turns`: 每 arm 旋幾圈
    - 0.0 = 直線（degenerate 到 rays，但語義上應該用 rays primitive）
    - 0.5 = 半圈（柔和螺旋，default）
    - 1.0 = 整圈（明顯螺旋感）
    - > 1.0 = 多重纏繞
- `direction`: cw / ccw

### Archimedean vs Logarithmic

選 Archimedean (linear r(t))，不選 logarithmic：

- Archimedean = 等距螺旋圈，視覺均勻
- Logarithmic = 黃金螺旋（指數增長），視覺強烈但跟 mandala 「均勻對稱」氣質不合
- mandala 系統其他 primitive 都是 linear / 對稱，spiral 跟它們配套用 Archimedean 較和諧

未來若要加 logarithmic spiral，可加新 primitive `spiral_log` 或 spin_turns 參數加 type literal。目前不需要。

### UI polymorphic input 對應

利用現有 outer/inner slot 的 len + width 兩個 input：

- `len` → `length_ratio`（跟 lotus/rays 一致）
- `width` → `spin_turns`（spiral-specific）
- `direction` 不暴露，default `cw`（user 用 API 可改）

5b r11 設計的 polymorphic input 在 spiral 仍可用，繼續 reuse。

### 加碼：螺旋星雲 preset

順手加第 6 個 preset「螺旋星雲」：

- 中心字「氣」+ 字環「金木水火土風雷山澤」（9 字 → N=9）
- 主 vesica（9 圓 overlap=1.30）
- 外圈順時針 spiral（9-fold, 0.6 turn）
- 內圈逆時針 spiral（9-fold, 0.7 turn）
- **雙旋方向相反 → 視覺「能量流動 / 對流」感**

讓 user 立即感受 spiral 的視覺衝擊。

### 實作 footprint

| 檔案 | 動作 |
|------|------|
| `mandala.py` | 新增 `spiral_band_svg()`；dispatcher 加 `spiral` 分支；`MANDALA_PRESETS` 加 `spiral_galaxy` preset |
| `index.html` | outer/inner dropdown 加「螺旋」option；JS `_mandalaApplyStyleSpecificParams` 加 spiral case (len → length_ratio, width → spin_turns, direction default cw) |
| `tests/test_mandala.py` | 5 個新測試（emit N polylines、0/null N empty、cw vs ccw 中段點 y 符號相反、spin_turns=0 degenerate 到直線、dispatcher routing）；66/66 通過 |

### 驗證

- pytest 全套 337 passed
- 視覺 5 cases：
  - **spiral_default** (9, 0.5 turn)：漩渦感，溫和
  - **spiral_full_turn** (9, 1.0 turn)：纏繞明顯
  - **spiral_ccw**：逆時針
  - **spiral_galaxy** (6, 1.2 turn)：銀河感（橢圓形 spiral）
  - **spiral_combo** (兩層 cw + ccw)：對流

### Mandala 模式現況（r4 → r13 9 輪累積）

- **8 個 primitives**（圓 / 蓮花 / 光線 / 點 / 三角 / 波 / 鋸齒 / 螺旋）
- 3 schemes / 多層 ring / 字保護 / 6 preset / 完整 toggle
- **66 unit tests + 整套 337 passed**

### Lessons / 適用 future round

1. **Spiral 是「線形 primitive 自然延伸」**：rays（直線輻射）→ wave（沿圓周波動）→ spiral（徑向 + 角度同時變化）。每個 primitive 都是 r(t) 跟 phi(t) 的函數，spiral 是把 phi 也吃進 t 函數而已。**Pattern：當 primitive 系統有「徑向變化」+「沿圓周變化」兩條軸，spiral 是自然的對角線**。

2. **加 preset 同時帶新 primitive 提升 discoverability**：r13 不只加 primitive，還加 `spiral_galaxy` preset 展示 spiral 視覺。User 從 dropdown 選到「螺旋星雲」立即看到雙旋對流，比看到 spiral 是一個 dropdown option 更有 wow factor。**Pattern：新 feature 應 ship 時帶展示用的 default config**。

3. **Polymorphic UI input 的 spin_turns 例外**：原本 width 對應 lotus_width_ratio / triangles_width_ratio。spiral 重用 width = spin_turns 語義不直觀（width 跟「圈數」物理意義不同）。但 reuse 比加 row 簡單一個量級，且 preset 會 cover 90% 用例，user 直接拉 dropdown 就好。**MVP 接受 minor UI ambiguity，preset 解決 discovery**。

### 後續方向 (user 自選)

- **r14 動態增刪 layer row**（從固定 2 slot 變成 list UI）
- **r15 Case A/C 完善**（中心 mandala icon 取代字）
- **r16 補剩餘 primitives**（葉片 leaves / 淚滴 teardrops / 心形 hearts / 雲朵紋 clouds / 方形 squares）
- 或 enjoy 8 primitives + 6 preset 段落

---

## r14 補丁：動態增刪 layer row — list-based UI

**版號**：0.14.92 → 0.14.93

把 r10 的「固定 2 slot (外/內)」UI 重構成 list-based 動態 UI。User 可加任意層數（cap 8 上限避免 UI 爆炸 + 視覺過載），每層可獨立刪除。

### Before (r10) vs After (r14)

**r10 固定 2 slot**：外/內各 1 row，toggle 啟用 + 各自 controls；preset 套用時按 r_ratio 排序填 outer/inner，> 2 layers 從 UI 填不下。

**r14 動態 list**：容器 div + 「+ 增加裝飾層」按鈕；每按 + 加一個 row（class `.md-layer-row`），每 row 有「× 刪除」按鈕；count badge `(N/8)` 即時更新；達上限 add button disabled；preset 套用 → clear list + 依 cfg.extra_layers 順序 add 每層（不限 2 個）。

### Backend 零改動

`extras_layers_json` 早就支援任意 list length（r10 設計時已 list-based）。r14 純前端重構，build JSON logic 從「兩個 prefix 各拼一個 layer」變成「迭代 `.md-layer-row` 各拼一個 layer」。

### Row 模板

每 row 6 個控制 + 編號 + 刪除：

```
[第 N 層] [style ▾] [N: 18] [半徑: 0.50] [主: 0.6] [次: 0.5] [×]
```

「主」「次」取代 r11 的「len/width」label（更抽象，配合 tooltip 描述 7 styles 各自語義）。

### 新加 row default

style=lotus_petal, N=18, r=0.50, len=0.6, width=0.5。中等 r_ratio (0.50) 視覺中性，user 看到立刻調 適合自己。

### 編號重排：刪除中間 row 後

`_mandalaRenumberRows()` 用 `forEach((row, idx) => ...)` 重寫 idx span；row 用 class-based selector 而非 fixed ID（刪除中間 row 不影響其他 row 的 selector）。

### 5-layer regression test

新測試 `test_render_with_many_extra_layers` 驗證 5 層極端：arcs 24 + spiral 9 + lotus 18 + triangles 12 + dots 8 → 5 個 `data-style="..."` 都在 SVG 中各 ≥ 1 個。

### 實作 footprint

| 檔案 | 動作 |
|------|------|
| `index.html` HTML | 移除 r10 兩個固定 row，改 1 row（標題+count badge+add button）+ 1 個空 div container |
| `index.html` JS | 新增 `MD_LAYER_MAX=8` / `mandalaAddLayerRow` / `_mandalaRenumberRows` / `mandalaUpdateExtrasCount` / `mandalaClearAllLayers`；`mandalaBuildExtraLayersJson` 改成迭代 `.md-layer-row`；`mandalaApplyPreset` 改成 clear + add；移除舊 `_applyExtraLayer(prefix)` / `mandalaSyncExtraLayerEnable(prefix)` |
| `tests/test_mandala.py` | 1 新測試 (5-layer regression)；67/67 通過 |

### 驗證

- pytest 全套 338 passed
- JS parse OK (206433 char)
- 5-layer stress test：arcs 24 + spiral 9 + lotus 18 + triangles 12 + dots 8 全部疊加成功（神聖幾何感）
- 所有 6 preset 套用 → 自動 clear + add row（preset 配置仍正確還原）

### Lessons

1. **Fixed slot → dynamic list 重構是 frontend-only**：backend 早 list-based（json 接 array），r10 為了 MVP UI 簡化用 fixed slot。Backend API 一開始就用 list 是 future-proof key —「先 list-design backend，後限 UI」比「fixed UI 後 backend 重構」便宜 100x。

2. **Class-based selectors > ID-based 對 dynamic list**：固定 ID 刪中間 row 要 cascade rename；class + row scope 自動處理。**Pattern：dynamic 元素用 class + scope，不用 sequential ID**。

3. **Hard cap 防 UI 爆炸**：MD_LAYER_MAX=8 不是技術限制而是 UX 自我約束。8 層已視覺超載（每層 ~30 SVG element × 8 = 240 elements 跟 char paths 同 z-order，雜訊 > 信號）。**UX cap ≠ 技術 cap，UI 端 cap 給 design control**。

4. **Polymorphic label「主/次」抽象 win**：r11 用「len/width」對 spiral 不準（spin_turns ≠「寬度」）。改抽象 label + tooltip 描述 7 styles 各自語義 → label 不再 misleading。**抽象 label > 具體但不準的 label**。

### r14 後 mandala 模式現況（r4 → r14 10 輪）

- 8 primitives / 3 schemes / 字保護 / 6 preset / **動態多層 (1-8 層)**
- 67 unit tests + 338 整套 passed

接下來：
- **r15 Case A/C 完善**（中心 mandala icon 取代字）
- **r16 補剩餘 primitives**（葉片 / 淚滴 / 心形 / 雲朵紋 / 方形）
- 或 enjoy 段落

---

## r15 補丁：Case A/C 完善 — 中心類型 (字 / icon / 空)

**版號**：0.14.93 → 0.14.94

完成 user 原 spec 提的 3 個 case 全支援：

| Case | 中心 | 字環 | 對應 center_type |
|------|------|------|------------------|
| **A**: 中心字 + 周圍 mandala（無字環） | 字 | 空 | `char` + ring_text="" |
| **B**: 中心字 + 字環 + 周圍 mandala（默認） | 字 | N 字 | `char` + ring_text |
| **C**: 中心 mandala icon + 字環 + 周圍 mandala | icon | N 字 | `icon` + ring_text |

加 `center_type ∈ {char, icon, empty}` 三選一 enum。

### 實作策略：重用 extras dispatcher

中心 icon 本質上是「半徑很小的 mandala band」，跟 r10-r11 加的 `render_extra_layer_svg()` dispatcher 完全相同的概念。直接 reuse：

```python
icon_layer = {
    "style": center_icon_style,
    "n_fold": center_icon_n,
    "r_ratio": (center_icon_size_mm / 2.0) / r_total,  # mm → ratio
}
icon_svg = render_extra_layer_svg(cx, cy, r_total, icon_layer, ...)
```

8 個 primitive 全部可以當中心 icon 用（lotus / arcs / rays / dots / triangles / wave / zigzag / spiral）。default 用 `lotus_petal`（最經典 mandala 中央 icon）。

### Case A 隱藏 bug：vesica n=2 退化

實作 Case A 時發現預設 N=2 在 vesica scheme 會 cos(π/2)→0 造成 r_band 發散到無窮，mandala 畫到 viewBox 外。

修復：empty ring + 沒指定 n_fold 時用 default N=8（合理 mandala 對稱數，避開 vesica n=2 退化）：

```python
elif ring_chars:
    n = max(2, len(ring_chars))
else:
    n = 8  # Case A fallback：vesica 對 N=2 數學退化
```

### Z-order

```
背景 → debug 輔助圓 → 主 mandala band → 額外 layers → center icon → halo → chars (ring only)
```

center icon 放在 extras 之後、halo + chars 之前。語意：icon 是「中央焦點裝飾」位於最外但不被 chars 蓋（因為 ring chars 不在中心）。如果 user 同時設 center_type="icon" 跟有 center_text，center_text 會被忽略（不載入 char），icon 完全取代字位置。

### UI radio + sub-controls

3 個 radio button (字 / icon / 空) + 一個 conditional row「icon 子控制」：

- center_type="char"：中心字 input enabled、icon row 隱藏（默認）
- center_type="icon"：中心字 input disabled (opacity 0.5)、icon row 顯示 (style + N + size_mm)
- center_type="empty"：兩者都隱藏 / disabled

`mandalaSyncCenterType()` 在 radio change 時 toggle 顯隱。

### 實作 footprint

| 檔案 | 動作 |
|------|------|
| `mandala.py` | 4 新 params (center_type / center_icon_style / center_icon_n / center_icon_size_mm)；render block 加 center icon (重用 render_extra_layer_svg)；Case A fallback N=8；info dict 加 center_type / has_center_icon |
| `server.py` | API 加 4 query params (regex pattern check style)；response header `X-Mandala-Center-Type` |
| `index.html` | 中心類型 radio row + icon 子控制 row；JS pass through + `mandalaSyncCenterType()` 顯隱切換 |
| `tests/test_mandala.py` | 5 個新測試 (char default / icon emit / empty no center / Case A 仍 render mandala / icon style dispatch 4 styles)；72/72 通過 |

### 驗證

- pytest 整套 343 passed
- 視覺：
  - **Case A** (字「咒」+ 無字環 + N=8 vesica)：中心字 + 8 圓 rosette
  - **Case C lotus icon** (8 瓣 + 9 字字環)：中央小 8 瓣花 + 環 + 主 mandala
  - **Case C arcs/dots/rays icon**：各 primitive 都正確 dispatch
  - **empty 中心 + 9 字環**：純字環無中心

### Lessons

1. **「中心 icon = 小半徑的 extras layer」是 elegant 抽象**：r10 設計 extras dispatcher 時沒想到後續會這樣 reuse。但 dispatcher 抽象設計得當（單純依 style key 路由 primitive），新需求自動 fit。**Pattern：通用 dispatcher 的 reuse 機會比 specific path 高很多**。

2. **Edge case 在實作 user-facing feature 時才暴露**：vesica n=2 退化是 r8 當時沒測到的（r8 default N=9，沒人 trigger n=2 vesica）。Case A 的 empty ring → default N=2 把這個 silent bug 拉出來。**Pattern：新 feature 是 edge case detector**。

3. **3-state radio button 比 2 個 checkbox 清楚**：原本想「中心字 toggle + icon toggle」雙 checkbox，但「字 + icon 都選」是無意義狀態。改用 mutex radio (char/icon/empty) → state 永遠 valid。**Pattern：mutually exclusive 用 radio 不要兩個 checkbox**。

### r15 後 mandala 模式現況（r4 → r15 11 輪）

- 8 primitives / 3 schemes / 字保護 / 6 preset / 動態多層 / **3 case (A/B/C) 完整支援**
- 72 unit tests + 343 整套 passed
- User 原 spec 的 3 case 全部 ship

---

## r16 補丁：補 4 個 primitives（squares / hearts / teardrops / leaves）

**版號**：0.14.94 → 0.14.95

依 user spec 列舉的元素，補 4 個。Clouds（雲朵紋）較複雜（多 lobe 構成）留 r17。

### 4 個新 primitive

| Primitive | SVG | 視覺 | 主要 param |
|-----------|-----|------|----------|
| **squares** | `<polygon>` × N (4 點) | 方形繞圈，穩定/物質世界平衡 | length_ratio, rotation_alignment ("radial"/"diamond") |
| **hearts** | `<path>` × N (cubic bezier) | 雙 lobe 心形，愛/慈悲/連結 | length_ratio, pointing |
| **teardrops** | `<path>` × N (cubic bezier) | 圓端 + 尖端，柔性能量 | length_ratio, pointing |
| **leaves** | `<path>` × N (quad bezier + L vein) | 葉形 + 中央葉脈，有機律動 | length_ratio, width_ratio, with_vein |

### 設計決策：SVG transform 簡化複雜形狀

hearts 跟 teardrops 形狀複雜（cubic bezier × 2），手算每點 在世界座標複雜。改用：

```python
heart_d = "M ... C ... C ... Z"  # 在 local frame (中心原點)
parts.append(
    f'<g transform="translate({cx_i:.3f},{cy_i:.3f}) rotate({rot_deg:.2f})">'
    f'<path d="{heart_d}" .../></g>'
)
```

local path 一次定義 + SVG transform 旋轉/平移。比手算每個 control point 在 world 座標的位置簡單一個量級。

### squares 兩種 alignment

- **radial**: 方形邊軸對齊徑向（方形邊面向中心）— 像「土」字框、規矩
- **diamond**: 對角線對齊徑向（方形角面向中心）— 像鑽石、菱形列陣

UI polymorphic 對應：r_ratio ≥ 0.7 (外圈) → "diamond"（對角更合適外圈裝飾）；< 0.7 (內圈) → "radial"。

### leaves 跟 lotus 的差別

leaves 重用 lotus 的 quadratic bezier (兩端尖)，但加 `M base L tip` 中央葉脈線。視覺差別：

- lotus = 純 almond/vesica 形（光滑）
- leaves = almond + 葉脈（更有機，看起來像植物葉）

### Z-order pattern 統一

4 新 primitive 全部走 `render_extra_layer_svg` dispatcher（已建好的 8 個 primitive dispatcher 模式），加 4 個 if-elif 分支即可。新 primitive 自動 inherit z-order / extras layer 機制 / preset 系統能力。

### UI polymorphic param mapping

JS `_mandalaApplyStyleSpecificParams` 加 4 個 case：

```js
} else if (style === "squares") {
  layer.length_ratio = len || 1.0;
  layer.rotation_alignment = (layer.r_ratio >= 0.7) ? "diamond" : "radial";
} else if (style === "hearts") {
  layer.length_ratio = len || 1.0;
  layer.pointing = (layer.r_ratio >= 0.7) ? "outward" : "inward";
} else if (style === "teardrops") {
  layer.length_ratio = len || 1.25;
  layer.pointing = (layer.r_ratio >= 0.7) ? "outward" : "inward";
} else if (style === "leaves") {
  layer.length_ratio = len || 1.4;
  layer.width_ratio = width || 0.5;
  layer.with_vein = true;
}
```

外/內圈自動推 alignment / pointing 維持 user 直覺（外朝外 / 內朝內）。

### 實作 footprint

| 檔案 | 動作 |
|------|------|
| `mandala.py` | 4 新 primitive 函數；render_extra_layer_svg dispatcher 加 4 分支 |
| `index.html` | MD_STYLE_OPTIONS 加 4 entry；_mandalaApplyStyleSpecificParams 加 4 case |
| `tests/test_mandala.py` | 8 個新測試（squares emit/radial-vs-diamond、hearts emit/pointing differs、teardrops emit、leaves with-vein/without-vein、4-primitive dispatcher）；80/80 通過 |

### 驗證

- pytest 全套 351 passed
- 視覺 7 cases:
  - squares_radial（12 方形邊朝心）
  - squares_diamond（12 鑽石格列陣）
  - hearts_out（12 心朝外，盛開）
  - hearts_in（9 心朝內，內聚焦）
  - teardrops_out（16 淚滴朝外，水簾感）
  - leaves_with_vein（12 葉片 + 中央葉脈）
  - all_4_combo（4 層各 1 種，疊加）

### Lessons

1. **SVG transform 簡化複雜形狀的 placement**：複雜 path (heart/teardrop) 在 local frame 定義一次，translate + rotate 套到 N 個位置 → 比每位置重算 path 點簡單一個量級。SVG `<g transform>` 是 free-of-cost performance（瀏覽器 GPU 加速 transform）。**Pattern：複雜 shape 用 local + transform，簡單 shape 用 absolute coords**。

2. **Polymorphic param 的 r_ratio-based 推斷**：squares alignment / hearts pointing / triangles pointing 都用 r_ratio ≥ 0.7 推斷外/內。這個 heuristic 對 80% user 直覺對。**Pattern：UI 不暴露的 param 用相關 param 推斷，比加更多 input 簡單**。

3. **新 primitive 加入只需 dispatcher 1 分支 + UI 1 option + JS 1 case**：r16 加 4 primitive 共改 12 處（4 × 3 layer）。如果 primitive 是 class hierarchy 設計，加新 primitive 要 ≥ 5 處 (class def + register + factory + tests + UI)。**Pattern：functional dispatcher 比 OOP class registry 加新類別更簡單**。

### r16 後 mandala 模式現況（r4 → r16 12 輪）

- **12 primitives**（圓 / 蓮花 / 光線 / 點 / 三角 / 波 / 鋸齒 / 螺旋 / **方形** / **心形** / **淚滴** / **葉片**）
- 3 schemes / 字保護 / 6 preset / 動態多層 / 3 case (A/B/C)
- 80 unit tests + 351 整套 passed

User spec 元素清單剩 1 個：**雲朵紋 (clouds)**（r17 候選，多 lobe 設計需思考）。其他幾何/自然/裝飾元素全 ship。

---

## r17 補丁：雲朵紋 (clouds) primitive — User spec 全 ship

**版號**：0.14.95 → 0.14.96

補完 user spec 列舉的最後一個元素「雲朵紋」。同時加第 7 個 preset「祥雲」。

### Cloud 設計：3 lobe overlapping circles

每 cloud unit = 3 個 overlapping `<circle>` 構成漫畫式雲輪廓：

```
local frame (+y = 徑向方向):
- 左 lobe: (-0.7s, 0),      radius 0.45s
- 中 lobe: (0, ±0.3s),      radius 0.55s   (中央較大)
- 右 lobe: (+0.7s, 0),      radius 0.45s
```

其中 s = `r_band × sin(π/N) × length_ratio`（半寬，跟其他 primitive 同尺度）。

中 lobe 的 y 偏移由 `pointing` 決定：

- `outward`: +0.3s（中 lobe 朝外，雲朵蓬鬆向外）
- `inward`: -0.3s（中 lobe 朝內，雲朵蓬鬆向內）

### 為何用 3 個 circle 而非 path

雲朵輪廓需要多段弧線，用 SVG `<path>` 配 `A` arc 命令算 sweep flag / 端點 連續性麻煩；用 3 個 overlapping `<circle>` (各自獨立 SVG element) 視覺上自動形成「3 bumps」，瀏覽器渲染負擔低，且每 lobe 大小可獨立調整。

代價：總 SVG element 數 3× 多 (N cloud → 3N circle)，但對 typical N≤12 仍很少 (≤36 circle)，無 performance 顧慮。

### 為何選 3 lobe (不是 5 / 7)

3 lobe 是 cloud 視覺最 minimum 識別度（少於 3 = 不像雲）。多 lobe 會更繁複但跟其他 primitive 形態雷同（多 lobe ≈ wave/zigzag）。3 lobe 最有「漫畫雲」的 distinctive 感。

User 要更繁複可疊兩層 cloud（外大 + 內小，r17 default preset 「祥雲」就是這個設計）。

### 第 7 個 preset：祥雲

```python
"auspicious_clouds": {
    "name": "祥雲",
    "extra_layers": [
        {"style": "clouds", "n_fold": 8, "r_ratio": 0.95, "pointing": "outward"},
        {"style": "clouds", "n_fold": 8, "r_ratio": 0.28, "pointing": "inward"},
    ],
}
```

中心字「雲」+ 字環「乾兌離震巽坎艮坤」(8 卦 → N=8) + 內外雲朵層形成「中式祥雲」感。

### 實作 footprint

| 檔案 | 動作 |
|------|------|
| `mandala.py` | `clouds_band_svg()` (3 lobe per cloud)；dispatcher 加 `clouds` 分支；MANDALA_PRESETS 加「祥雲」第 7 preset |
| `index.html` | MD_STYLE_OPTIONS 加 `["clouds", "雲朵紋"]`；`_mandalaApplyStyleSpecificParams` 加 clouds case (width → lobe_radius_ratio, pointing 自動推) |
| `tests/test_mandala.py` | 5 個新測試 (emit 3n circles / zero N empty / outward vs inward / dispatcher / preset exists)；85/85 通過 |

### 驗證

- pytest 全套 356 passed
- 視覺 4 cases：
  - clouds_outward (9 cloud N=9, lush 朝外)
  - clouds_inward (9 cloud N=9, 朝內聚焦)
  - clouds_n12_lush (12 cloud, lobe 加大 0.55, 蓬鬆)
  - clouds_combo (內外雙層 cloud) ✓

### Lessons

1. **3 lobe 是「雲」的 minimum 識別**：少於 3 不像雲，多於 3 跟 wave 視覺雷同。User spec 提到雲紋時，3-bump 漫畫雲是 cultural shared image。**Pattern：抽象元素的設計選 minimum identifiable count**。

2. **疊層替代複雜單體**：「祥雲」preset 用兩層 cloud (內外) 而非設計「複雜多層 cloud unit」。Layer composition > complex monolith：每層 atomic primitive，組合層次出複雜度，跟 Unix「small tools, composed」哲學一致。

3. **「3 circles per cloud」打破 N-circle pattern 但仍 fit dispatcher**：之前 primitives 都是「N elements」(N circle / N polygon / N path)；clouds 是「3N」。但 dispatcher 不在意內部 element count，只關心 r_band/n 接口統一。**Pattern：dispatcher abstraction layer 隱藏 primitive 內部複雜度**。

### r17 後 mandala 模式現況（r4 → r17 13 輪）— **User spec 全 ship**

- **13 primitives**（圓 / 蓮花 / 光線 / 點 / 三角 / 波 / 鋸齒 / 螺旋 / 方形 / 心形 / 淚滴 / 葉片 / **雲朵紋**）
- 3 schemes / 字保護 / **7 preset** / 動態多層 / 3 case (A/B/C)
- 85 unit tests + 356 整套 passed
- **User 原 spec 列舉的所有元素全部 ship 完畢**

User spec 元素覆蓋：
- ✅ 圓圈 / 圓點 / 三角形 / 方形 (幾何)
- ✅ 花瓣 / 葉片 / 螺旋 / 波浪線 (自然/植物)
- ✅ 淚滴 / 心形 / 鋸齒線 / 雲朵紋 (裝飾)
- ✅ 法輪 / 輻射光線 (額外)

13 個 primitives + 多層組合 + 7 preset + 3 case 完整支援，mandala 模式 feature-complete。後續 polish 視 user 反映調 default 即可。

---

## r18 補丁：多格式下載 (SVG / PNG / PNG 透明 / PDF)

**版號**：0.14.96 → 0.14.97

原本只能下載 SVG。User 要求加更多格式。

### 4 個下載格式

| 格式 | 用途 | 實作 | content-type |
|------|------|------|------|
| **SVG** (向量) | 跨用、編輯、無限放大 | 直接 render | image/svg+xml |
| **PNG** (白底) | 社群分享 / 簡報 / 列印 | cairosvg.svg2png | image/png |
| **PNG 透明** | 疊圖 / 貼紙 / 設計稿 | cairosvg.svg2png + skip bg rect | image/png (RGBA) |
| **PDF** | 列印品質 / 印刷店 | cairosvg.svg2pdf | application/pdf |

PNG 解析度 user 三選一：1024（中、~80KB）/ 2400（大、~200KB，預設）/ 4096（超大、~800KB）。

### Architecture: 透明背景靠 render-time skip 而非 cairosvg flag

cairosvg 沒有「忽略 SVG 內 fill rect」的 flag — `background_color=None` 只控制 cairosvg 自己的 padding fill，不會移除 SVG 內既有的 `<rect fill="white">`。

選方案：**SVG render 階段加 `include_background: bool = True` param**。當 user 要透明 PNG → 改 render SVG 時不畫 white rect → 結果 SVG 已是透明 → cairosvg 轉 PNG 自然是 RGBA 透明。

優點：

- 透明邏輯在 render 階段一次決定，不需 cairosvg 二次處理
- 透明 SVG 也能直接給 user 下載（雖然 UI 沒暴露，API 支援）

### Format dispatch

API endpoint 加：

```python
format: str = Query("svg", pattern="^(svg|png|png_transparent|pdf)$")
png_size_px: int = Query(2400, ge=256, le=8192)
```

依 format dispatch：

```python
include_bg = (format != "png_transparent")
svg, info = render_mandala_svg(..., include_background=include_bg)

if format == "png" or format == "png_transparent":
    content = cairosvg.svg2png(bytestring=svg.encode(),
                               output_width=png_size_px,
                               output_height=png_size_px)
    mime = "image/png"
elif format == "pdf":
    content = cairosvg.svg2pdf(bytestring=svg.encode())
    mime = "application/pdf"
else:
    content = svg
    mime = "image/svg+xml"
```

### UI: 4 download buttons + size selector

原單一「下載 SVG」按鈕替換成 download row：

```
⤓ 下載：
[SVG 向量]  PNG 解析度 [大 2400 ▾]  [PNG]  [PNG 透明背景]  [PDF 列印]
```

JS `mandalaDownload(format)`：fetch → blob → `<a download>` click → revoke URL。

### 實作 footprint

| 檔案 | 動作 |
|------|------|
| `mandala.py` | `render_mandala_svg` 加 `include_background: bool = True`；條件略過 white bg rect |
| `server.py` | `/api/mandala` 加 `format` (regex pattern) + `png_size_px` query params；format dispatch（cairosvg 轉 PNG/PDF）；download 時 Content-Disposition 含格式對應副檔名 |
| `index.html` | 移除單一 download `<a>`；新增 download row（5 buttons + size selector + status）；JS `mandalaDownload(format)` 通用函數 + 4 個 click handler |
| `tests/test_mandala.py` | 6 個新測試（include_bg true/false、format=png/png_transparent/pdf 各回正確 magic bytes、format=invalid 422）；91/91 通過 |

### 驗證

- pytest 全套 362 passed
- API smoke 4 cases:
  - SVG 42KB（向量）
  - PNG 1024 74KB / 2400 195KB（white background, RGB）
  - PNG transparent 2400 221KB（RGBA, 略大因 alpha channel）
  - PDF 32KB（v1.5, 1 page）
- 檔頭 magic bytes 全部正確（PNG `\x89PNG\r\n\x1a\n` / PDF `%PDF`）

### Lessons

1. **「透明邏輯在 source format 一次決定」是最 robust pattern**：
   - 替代方案 A：cairosvg flag（不存在 — 它只控制 padding）
   - 替代方案 B：render 後 strip `<rect>` element via 字串 replace（fragile）
   - 選擇方案 C：render 階段 toggle bg → 一次決策、無下游 hack

2. **多 format 用 dispatch + 共享 SVG render**：所有 format 都從 SVG 出發（SVG 是 source of truth），PNG/PDF 是衍生格式。dispatcher 在 endpoint 末尾統一處理 → SVG render 邏輯不知道也不在意有沒有要轉成 PNG。**Pattern：core 不污染 / dispatcher 結尾統一收尾**。

3. **PNG 解析度給 size 而非 DPI**：DPI 對「mandala 印多大」需要綁紙張尺寸（DPI × 紙張英吋 = 像素）。給直接像素數 (1024/2400/4096) user 直覺好懂，無需理解 DPI 概念。**Pattern：給 user 看到的單位，內部換算**。

### r18 後 mandala 模式現況（r4 → r18 14 輪）

- 13 primitives / 3 schemes / 7 preset / 動態多層 / 3 case (A/B/C) / **4 下載格式**
- 91 unit tests + 362 整套 passed

User spec 全 ship + 多格式輸出 production-ready。

---

## r19 補丁：G-code 輸出（寫字機 / 雷射 / CNC toolpath）

**版號**：0.14.97 → 0.14.98

呼應「中文字 → 寫字機軌跡」專案核心，加 mandala G-code 輸出，user 可直接用機器執行 mandala 圖案。

### Architecture: SVG 解析提取 polylines

**選擇**：reuse SVG render（source-of-truth），用 ElementTree 解析 + 自訂 path d parser 提取 polylines → 轉 G-code。

**不選**：平行寫 13 個 `compute_*_polylines()` primitive 函數（duplicates 13 functions worth of geometry code）。

優點：

- 零代碼 duplication（SVG render 已計算所有幾何）
- 加新 primitive 時 G-code 自動 work（只要 emit 標準 SVG element）
- transform handling 統一（hearts/teardrops 用 `<g transform>`）

代價：

- 多一層 SVG 解析（~30ms for typical mandala）
- Bezier 採樣精度有限（24 點/curve），但對 G-code 機器解析度足夠

### 自訂 path d parser

不引入 svgpathtools 依賴擴張用法（雖已有 dependency），用 minimal 自訂 parser 限定 mandala 用得到的 commands：M / L / Q / C / Z（lowercase 也支援）。

```python
def _parse_path_d(d):
    tokens = re.findall(r'[MLQCZmlqcz]|[\-+]?\d*\.?\d+(?:[eE][\-+]?\d+)?', d)
    # ... walk tokens, emit (cmd, [coords])
```

Quadratic / cubic bezier 用標準公式採樣 24 點：

```
Q: P(t) = (1-t)² · P0 + 2(1-t)t · CP + t² · P1
C: P(t) = (1-t)³ · P0 + 3(1-t)² t · CP1 + 3(1-t)t² · CP2 + t³ · P1
```

### Transform handling (hearts / teardrops 用)

hearts / teardrops 用 `<g transform="translate(X,Y) rotate(R)"><path .../></g>`。需要 parse transform → 套到 path 點：

```
x_world = x_local × cos(R) - y_local × sin(R) + X
y_world = x_local × sin(R) + y_local × cos(R) + Y
```

不支援 `scale`, `skew`, matrix transform — mandala 不用這些。

### Y 軸翻轉

SVG y-axis 朝下（top=0），多數機器（pen plotter / laser）y 朝上（bottom=0）。Default `flip_y=True` → `y_gcode = page_height - y_svg`，user 看到的 mandala 在機器上「正立」。

User 用古早翻 y-down 的雷射可關掉。

### 不含字 outline（first cut）

字 outline 走 `_char_cut_paths_stretched`（stamp 模式 helper），跟 mandala primitive 用的 SVG element 結構不同（字是 nested `<g transform>` 套精細 path）。要支援需 reuse stamp 的 G-code 邏輯（已有），第一輪先省，user 可：

- 先用 G-code 雕 mandala 線條
- 用 SVG / PDF 輸出含字的整體版本當參考圖
- 字位置另外手寫 / 雷射對位

跟其他模式對齊：stamp 模式的 G-code 是專門設計給字雕刻；mandala 模式 G-code 是「圖騰雕刻」。職能分離。

### Skip 邏輯

ElementTree walk 時跳過：

- `<rect>` 背景（白底，不該雕）
- `<g class="chars">` 字 outline（暫不支援）
- `<g class="char-halos">` halos（z-order blocker，不是 mandala 線）
- 其他非 target group（debug 輔助圓等）

只取 `<g class="mandala|extra-layers|extra-layer|center-icon">` 內容。

### G-code 結構

```
; Mandala G-code (Phase 5b r19)
; polylines: 51
; total points: 3027
G21 ; mm
G90 ; absolute
F1000 ; feed rate
G0 Z2.00 ; pen up
G0 X<x0> Y<y0> ; travel to start
G1 Z-1.00 F3000  ; pen down (with travel rate for Z)
F1000            ; restore drawing feed rate
G1 X<x> Y<y>     ; ... drawing
G0 Z2.00 ; pen up
... (next polyline)
```

User-tunable params: `feed_rate` (drawing speed), `pen_up_z` / `pen_down_z` (Z-axis levels), `flip_y`, `curve_samples`。

### 實作 footprint

| 檔案 | 動作 |
|------|------|
| `mandala.py` | `render_mandala_gcode()` ~100 行 + helpers (`_parse_path_d` / `_path_d_to_polylines` / `_circle_to_polyline` / `_parse_points_str` / `_parse_transform` / `_apply_transform`) |
| `server.py` | `/api/mandala` `format` regex 加 `gcode`；4 個 G-code 參數（feed_rate / pen_up_z / pen_down_z / flip_y）；dispatch 走 render_mandala_gcode |
| `index.html` | 「⤓ G-code 機器軌跡」綠虛框按鈕；JS extMap 加 `gcode: "gcode"` |
| `tests/test_mandala.py` | 7 個新測試（basic structure / polyline count / skip chars+halos / Y flip / quadratic bezier / cubic bezier / API gcode endpoint）；98/98 通過 |

### 驗證

- pytest 全套 369 passed
- API smoke：default config → 9 polylines / 585 points / 12KB G-code
- With 2 extras (lotus 18 + dots 24)：51 polylines / 3027 points / 60KB G-code
- Y flip：flip on Y + flip off Y = page_height（210mm）✓
- skip chars+halos：純 mandala 9 polylines（無 halo 10 額外）✓

### Lessons

1. **Source-of-truth 統一是 G-code 從不同 primitive 自動 work 的關鍵**：13 primitives 各自 emit SVG element type (circle/polygon/polyline/line/path)，G-code 從 SVG 端統一 parse → 加新 primitive 時 G-code 不用改。**Pattern：dispatcher 收尾統一、上游 source 不變**。

2. **自訂小 parser > 大 lib API**：path d parser 用 30 行 regex 解決 80% case。svgpathtools 雖然已是 dependency 但其 API 更通用（支援 A 弧線等 mandala 不用的命令），引入更多複雜度。**Pattern：複雜 lib 只用其 entry point，內部用最小自訂 parser**。

3. **Transform handling 限制範圍 = MVP 簡化**：不支援 scale/skew/matrix，因為 mandala 用不到。如果後續加新 primitive 需要 scale，再加 parser 分支。**Pattern：YAGNI — 只實作現有 primitive 用得到的能力**。

4. **字 outline 暫不支援是合理 scope cut**：mandala 圖騰雕刻 vs 字雕刻是兩個 use case，字模式 G-code 已有（stamp）；mandala G-code 專注圖騰。職能分離 = 模組可組合（user 可分別 G-code mandala + stamp 字 → 兩次雕刻分層）。

### r19 後 mandala 模式現況（r4 → r19 15 輪）— FEATURE COMPLETE

- 13 primitives / 3 schemes / 7 preset / 動態多層 (1-8) / 3 case (A/B/C)
- **5 下載格式**: SVG / PNG / PNG 透明 / PDF / **G-code**
- 98 unit tests + 369 整套 passed

**從 r4 MVP 到 r19 production-ready，15 輪累積 mandala 模式達 feature complete**。後續 polish 視 user 反映調 default 即可。
