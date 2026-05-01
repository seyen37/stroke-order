# 2026-05-03 — Phase 12c 陽刻支援（concave / convex engrave mode）

> 印章新增「陽刻」（朱文，字凸出 + 紅底白字）模式，補齊業界規範對齊缺口。從 prototype 驗證演算法可行性 → 5 子任務主線實作 → 5 個新測試 + 200 passed 回歸。**演算法工程量等同於另開一個 mode 系統**，但決策路線、prototype-first SOP、向後相容設計都很單純。

## 背景

Phase 12b（業界規範對齊）已完成 8 級尺寸 + 警示 + PDF + 多輪 bug fix，但留下兩個業界基本維度沒解：
- **陽刻 vs 陰刻**：業界印章兩種主流刻法都有，stroke-order 只有陰刻
- 1 字粗體置中 preset、5 字非均勻佈局（這次不解，留 12d/e）

陽刻非平凡——SVG 渲染要紅底白字（fill-based vs stroke-based），G-code 要光柵掃描鋪滿背景而不是沿字 outline 走。這是新的 rendering pipeline，不是參數調整。

## 路線決策（先 prototype 後動主線）

按 §8.8「先 inspect 實際輸出再下 root cause 結論」延伸——對「未驗證可行性的演算法」要先 prototype，不直接動主線：

1. 先寫 `scripts/prototype_engrave_convex.py` 驗證 scanline + even-odd 演算法
2. 跑壓力測試（4 分 / 8 分 / 1 寸 各尺寸），確認效能與 G-code 規模
3. 渲染 PNG 視覺驗證 ON/OFF 區段正確
4. **prototype 通過後** 才把演算法 port 進 `exporters/engrave.py` 主線 module

→ 這個 SOP 值得寫進 PROJECT_PLAYBOOK，候選 §8.11。

## Prototype 驗證結果

| Case | G-code lines | 雷射時間 | 演算法時間 |
|---|---|---|---|
| 4 分章 (12mm) 1 字 | 810 | 38 秒 | 6 ms |
| 8 分章 (24mm) 4 字 | 4126 | 3.1 分 | 69 ms |
| 1 寸章 (30mm) 4 字 | 4986 | 4.5 分 | 84 ms |
| 4 分 + 0.05 mm 高密度 | 1598 | 75 秒 | 11 ms |
| 4 分 + 0.20 mm 低密度 | 414 | 19 秒 | 3 ms |

結論：所有 case 演算法 < 100ms（遠快於網路 RTT）、G-code 5K 行（雷射機都吃得下）、雷射時間 0.5-5 分鐘合理。

PNG 視覺驗證：印章邊框內部分「字外」全綠線（雷射 ON），「字內」完全沒綠線 — even-odd rule 正確套用。

## 演算法選擇：scanline + boustrophedon

選項評估：

| 選項 | 描述 | 評估 |
|---|---|---|
| A | Scanline filling（水平掃描 + even-odd） | ✅ 簡單、效能好、業界標準 |
| B | Concentric infill（邊框往內等距內縮） | 字 outline 形狀不規則時複雜 |
| C | Spiral / Hilbert curve 路徑 | 過度工程，雷射機不需要 |
| D | Adaptive density（字邊密、中央疏） | 過度工程，0.1mm pitch 已夠 |

**選 A**：演算法明確、邊角情況可控（半開區間 `y0 <= y < y1` 處理頂點 degenerate）、雷射機 firmware 全部支援 G0/G1/M3/M5（不需要 G02/G03 圓弧）。

加上 **boustrophedon**（之字形掃描，奇偶行反向）：減少空跑時間 ~30%，演算法成本 0（只是 segments order 反向）。

## 7 個關鍵設計決策

### 決策 1：演算法 module 獨立（不污染 stamp.py）

新檔 `exporters/engrave.py` 含三個 helper：
- `scanline_intersections(polygons, y)` — 演算法核心
- `scanline_engrave_gcode(polygons, **opts)` — G-code 生成
- `char_outlines_to_polygons` + `transform_polygons_em_to_mm` — 跟現有 patch.py 演算法銜接

stamp.py 直接 import 用。**避免 stamp.py 1100+ 行再變大、保留未來給 patch / sutra 重用**。

### 決策 2：陰刻維持現況、向後相容

`engrave_mode: Literal["concave", "convex"]` 預設 `"concave"`，**所有既有 caller 不傳此參數時行為不變**。Phase 11/12b 的測試（包含 `tintPreviewFill` UI 邏輯）100% 維持。

### 決策 3：陽刻 SVG 用 fill 而非 mask/clipPath

陽刻 SVG 結構：

```html
<svg ...>
  <!-- 1. 邊框紅底 (z-index 1) -->
  <path d="border" fill="#c33" stroke="none"/>
  <!-- 2. 字白色 fill (z-index 2，凸出效果) -->
  <g fill="#fff" stroke="none">
    <path d="字 outline"/>
    ...
  </g>
  <!-- 3. 邊框黑線描邊 (z-index 3，視覺邊界清楚) -->
  <path d="border" fill="none" stroke="#000"/>
</svg>
```

**為什麼不用 `<mask>` 或 `<clipPath>`**：
- 雷射雕刻軟體對 mask/clip 支援度不一（Lightburn 早期版本會吃不掉）
- 三層獨立 path 在所有 SVG viewer / cairosvg / Inkscape 都正確渲染

### 決策 4：陽刻顏色硬編碼

- 紅底 `#c33`（傳統朱印色）
- 字白 `#fff`
- 邊框黑 `#000`

**不暴露給 user 配色**：印章傳統色彩慣例固定，不是 user 該調的。需要時未來再加參數。對比陰刻的 `color="#000"` UI 可改 tint 預覽，這是不同抽象層。

### 決策 5：G-code 陽刻 line_pitch 暴露給 user

預設 0.1 mm，但 UI 加 input field 讓 user 微調：
- 0.05 mm：細緻（時間 2x，邊緣更平滑）
- 0.10 mm：標準（推薦預設）
- 0.20 mm：粗略（時間 0.5x，看得到雕痕但快）

**為什麼這個參數要暴露**：line_pitch 直接決定雷射時間 + 雕刻品質，user 對自己雷射機的吃功率最了解。

### 決策 6：陽刻 G-code 字 outline 不單獨雕

陰刻 G-code：邊框 polygon + **每條字 stroke outline**（雷射沿字邊界走）
陽刻 G-code：邊框 polygon + **scanline 鋪滿背景**（字 outline 不單獨雕）

陽刻字 outline 邊界由 scanline 自動處理（雷射在字內 OFF、字外 ON），重複雕字 outline 會浪費時間 + 可能燒焦字邊。

### 決策 7：UI 預覽 tint 邏輯陽刻跳過

陰刻 SVG 是 stroke-only（黑線），UI 用 `tintPreviewFill` 把 stroke 改成紅色 + 加灰色 fill 模擬實體印章視覺。

陽刻 SVG 已自帶紅底白字，**直接顯示就跟實體印章一樣**，跳過 `tintPreviewFill`（套了反而會破壞顏色）。

```js
const isConvex = engraveR && engraveR.value === "convex";
if (!isConvex) tintPreviewFill(inner);
```

## 副產物：演算法 module 跨用途複用

`exporters/engrave.py` 的 `scanline_engrave_gcode` 不依賴 stamp 業務邏輯，只需要 polygons + border_box + 雷射參數。**未來可重用於**：
- patch (5ax) 抄經補丁的「鏤空」效果
- sutra 經文頁的 watermark
- 任何「邊框內鋪滿、字 outline 鏤空」的 use case

設計時刻意保持 module pure（不 import stamp.py），保留這個彈性。

## 測試覆蓋

5 個新測試 + 既有測試完整 regression：

| 測試 | 驗證 |
|---|---|
| `test_api_stamp_convex_svg_has_red_fill_white_chars` | 陽刻 SVG 含 `#c33` 紅底 + `#fff` 字白 |
| `test_api_stamp_concave_svg_unchanged` | 陰刻不該有紅底（向後相容） |
| `test_api_stamp_convex_gcode_has_scanline` | 陽刻 G-code 含 raster scan header + M3 命令 > 50 |
| `test_api_stamp_invalid_engrave_mode_rejected` | invalid mode 422 |
| `test_api_stamp_convex_pdf_has_red_fill` | 陽刻 PDF 跟陰刻 PDF 內容不同 |

周邊回歸：`stamp + web + patch + chongxi + align + handwriting + exporters + cns` 共 **200 passed / 24 skipped / 0 failed**。

## 教訓沉澱建議

### 候選 §8.11：先 prototype 後主線（演算法工作的 SOP）

**規則**：對「未驗證可行性的演算法」工作，動主線之前先寫 prototype（在 `scripts/` 或 `notebooks/`，不進主分支），驗證：
1. 演算法正確性（單元 case 對）
2. 效能規模（最大 case 不爆）
3. 視覺 / 業務正確性（render → 看圖 / 跑端對端 case）

prototype 通過後才 port 進主線 module。

**反例**：直接動主線寫演算法 + 直接接 API → 邊改邊試 → 主分支被 churn 多輪 commit / 測試持續紅 / 多次 force push 修細節。

**正例**：12c-3 prototype 跑出 PNG 確認 even-odd 正確 → 才開始改 stamp.py。整個過程主分支只有 1 commit（74b996d 含完整 5 子任務 + 5 測試），沒有 churning。

### 候選 §x.x：演算法 module 獨立（避免 god file）

**規則**：演算法工作（特別是新類型）獨立 module，不污染既有 file。如：
- `exporters/engrave.py` 不丟進 `exporters/stamp.py`
- `engrave.py` 只依賴 polygon 抽象，不知道 stamp/sutra/patch 業務概念

**好處**：
- 跨 use case 重用（不被 stamp 綁住）
- 測試獨立（單元測試只給 module 自己）
- god file 控制（stamp.py 已 1100+ 行，再塞進去沒人能看完）

→ 跟 §8.10「default 值 single source of truth」是同一個 cluster：「物件職責邊界要清楚」。

## 後續

**短期**：
- [ ] 補 v0.14.6 git tag + push 雙 remote
- [ ] commit + push 本日 docs

**中期**：
- Phase 12d：1 字 preset 驗證（粗體置中？），需要 user 確認 use case
- Phase 12e backlog：毛楷 / 毛行字體、5 字非均勻佈局

**長期 / 未來**：
- 演算法 module（engrave）跨用途複用：patch 鏤空、sutra watermark
- prototype-first SOP 寫進 PROJECT_PLAYBOOK §8.11

## 相關 commits

- prototype: `scripts/prototype_engrave_convex.py`（保留參考）
- 主線: `74b996d feat(stamp): Phase 12c 陽刻支援`

## 版本

pyproject.toml: 0.14.5 → 0.14.6
