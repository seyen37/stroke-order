# 描線工坊 VectorLine — 參考資料分析

> 分析對象：<https://github.com/begin0808/VectorLine>（v1.0.0，2026-07-06 發佈，MIT）
> 線上工具：<https://vector-line.vercel.app>
> 出處：Studio0808 智造實驗室發佈文（2026-07 社群貼文）
> 關聯目標：中文字 → 向量筆跡 → 寫字機器人／雷切雷雕
> 分析日期：2026-07-11

---

## 一、它到底是什麼

**圖片 → 雷切/雷雕向量線稿**的純前端網頁工具。輸入 PNG/JPG/WebP，輸出 SVG / PNG / 分層 DXF（`CUT` / `ENGRAVE` 兩層）。全程瀏覽器本地運算（OpenCV.js WASM 跑在 Web Worker），不上傳、不收集資料。

定位：台灣 maker 教育社群的自造輔助工具，作者 begin0808，репo 46 commits、無框架（Vite + vanilla JS/HTML/CSS）。

## 二、處理管線（與我們最相關的部分）

```
圖片 → 灰階 → 前處理（降噪/亮度/對比）
     → 自適應二值化（block size + C 常數，可反相）
     → 形態學清理（去斑、接斷線）
     → 三種模式之一：
         outline   — 描所有輪廓（保留內部細節）
         centerline — 骨架化成 1px 中心線（雷射每條線只切一次）
         canny     — 照片抽邊緣
     → 輪廓抽取 → RDP 節點簡化 → 可選 Bézier 平滑
     → SVG（可嵌 mm 實體尺寸）/ 分層 DXF
```

其他功能：魔術棒漫填去背（含 undo/redo）、亮部去背（white cutoff）、自動分層（外輪廓紅=切割、內部黑=雕刻，含滿版照片偵測）、原圖對比滑桿、預設參數組。

## 三、與本專案的重疊與互補

| 面向 | VectorLine | stroke-order |
|---|---|---|
| 輸入 | 任意點陣圖 | 中文字元（字串） |
| 核心資訊 | 幾何輪廓（無筆順） | **筆順 + 筆畫語意** |
| 中心線 | 骨架化（影像形態學） | CNS 字型骨架（`cns_skeleton.py`）/ 筆順資料庫 |
| 簡化/平滑 | RDP + Bézier | `smoothing.py` |
| 輸出 | SVG / PNG / 分層 DXF | SVG / G-code / JSON polyline / PNG / GIF |
| 運算位置 | 100% 瀏覽器（WASM） | 伺服器端（FastAPI + Python） |

互補關係明確：它把「**圖**變線稿」做到好，我們把「**字**變筆跡」做到好。它沒有筆順概念，做不出正確書寫軌跡；我們沒有任意圖片向量化。兩者輸出端（雷切/繪圖機）是同一批機器與軟體（Beam Studio / LightBurn / AxiDraw 類）。

## 四、可借鑑點（具體）

1. **分層 DXF 匯出（CUT/ENGRAVE）**：我們的 exporters 目前無 DXF。印章/雷雕線（Phase 11/12c convex engrave）若補 DXF 分層輸出，LightBurn 使用者可直接吃，成本低、受眾同一群。
2. **SVG 內嵌 mm 實體尺寸**：它強調「匯入 Beam Studio/LightBurn 即正確比例」。檢查我們 plotter SVG 是否一律帶 `width/height` 實體單位 + 正確 `viewBox`，這是同類工具的體驗基準線。
3. **塗鴉模式前端化的參照**：我們塗鴉模式影像處理在伺服器端（Pillow/cairosvg）。它證明 OpenCV.js WASM + Web Worker 在瀏覽器做二值化/輪廓抽取夠快，若日後想減輕 Render 免費 tier 負擔，這是現成架構樣板（MIT 可直接讀源碼）。
4. **魔術棒去背 + undo/redo、原圖對比滑桿**：塗鴉模式 UX 可對標的互動細節。
5. **centerline（骨架化）**：與 `measure_cns_skeleton_alignment.py` 的問題同源。它用純影像形態學骨架化，可當作我們字型輪廓→中心線的 baseline 對照組。

## 五、邊界（它不能替我們做什麼）

- 骨架化**無筆順、無筆畫分段**，輸出是幾何線不是書寫軌跡——寫字機器人拿它的 centerline 會亂序亂向。
- 無 G-code 輸出、無下筆/提筆語意。
- 對「字」的處理只是把字當圖，楷書筆意、鉤挑起收全部丟失。

## 六、行動項候選（不承諾，待排優先序）

- [x] exporters 增加分層 DXF（2026-07-11 Phase 5bq：`exporters/dxf.py`
      自寫 R12 writer 零依賴＋布章 CUT/ENGRAVE/WRITE 三層匯出；
      印章 hatch 填充線待下一輪）
- [x] 印章模式接分層 DXF（2026-07-11 Phase 5bs：scanline_segments
      收集器＋_stamp_polylines 幾何抽取；陰刻輪廓／陽刻 hatch 雙模式）
- [x] audit：plotter SVG 的 mm 實體尺寸與 viewBox 是否全模式一致
      （2026-07-11 Phase 5bt：抓到印章全 preset 縮 2.4-3.5% 實體尺寸
      bug 並修復；export 加選配 size_mm；14 項契約測試鎖定全站）
- [x] 塗鴉模式前端化（2026-07-11 Phase 5ca：doodle_engine.js 瀏覽器
      復刻 Python 管線＋可插拔引擎表＋調參即時預覽；node×Python
      parity 驗證等價。OpenCV.js WASM 引擎——即本文件借鑑點 3 的
      完整架構樣板——預留 5cb 掛入同一張引擎表）
- [x] 社群層面互連（2026-07-11 Phase 5ca：塗鴉模式 UI 導流連結
      「進階向量化 → 描線工坊 VectorLine」；對方回鏈待社群接洽）
- [ ] 塗鴉模式雷雕情境：試把我們的 SVG 丟進它的 workflow 反向驗證相容性
