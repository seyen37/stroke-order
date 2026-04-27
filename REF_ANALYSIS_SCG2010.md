# 2010 版字庫 (fontdata2010 + testfont2010) — 參考資料分析 [重大更新]

> 分析對象：`fontdata2010-new.zip` + `testfont2010.zip`
> 發現：**這不是 1992 版的延伸，而是一個完整的向量字型引擎**

---

## 一、第一個震撼：MODVEC.ASM 是向量筆畫合成器

`MODVEC.ASM` (71 KB) 是整個字庫的核心 —— **以向量參數繪製每一筆畫**的渲染器。每種筆畫類型都有獨立的繪製例程，統一的輸入介面：

```asm
; 功能  ALL WGF DTWC          ← 黑體橫之入口
; 輸入  BX = X2,X1             ← 起訖點
;       DX = Y2,Y1
;       AL = 角度
;       AH = 參數 (頭部型態)
;       CL = 直粗 (線條粗細)
; 輸出  BUFOUT = 字形點陣
```

也就是說 —— **每一筆畫都是「起點→終點 + 角度 + 頭型 + 粗細」的向量參數**，不是預先算好的點陣資料。

## 二、筆畫原子 (Stroke Atoms)

從 MODVEC 的公開符號與註解整理出來的**筆畫類別系統**：

| Code | 筆畫類型 | 說明 |
|---|---|---|
| `DTWC` / `AWFDTC` | **橫** | 可延伸、可有頓筆，明體/黑體差異最大 |
| `JBMM` | **豎/直** | 頭型 (0平 1尖 2,3轉)、尾型可另配 |
| `JBMHEAD` | 直頭+直身 | 頭部位置/長度/類型獨立參數 |
| `ODYJ` | (某豎類變體) | 1/2 直粗可獨立設 |
| `WFR` / `WFLF` | **撇/捺** | 左撇右捺成對出現 |
| `WFRABL/R`, `WFLFAB` | 撇捺+左右帶頭 | |
| `CPI` / `CPIRRJ` | **點** (一類) | 備註「筆畫捺，2點以上專用」 |
| `UCPI` / `UCPIPI30` | **點** (另一類) | U = 反向/另一種點 |
| `IPI` / `ALL2IP` | **挑** (一類) | Input Point/Implied Point ? |
| `QAMO` | **提** | 可延長、避免右側出頭 |
| `QKMF` / `QKF` | **曲捺/鉤** | 捺尾雙線、2 點以上專用 |
| `CIR` / `INICIR` | **圓弧** | 象限參數化 (Q1/Q2/Q3/Q4) |
| `ECLIPS` / `ECLIPQ1-4` | **橢圓弧** | |
| `QKNS` | **拋物線** | X²-Y 型軌跡 (用於弧捺) |
| `NMVO` | **弧** | 由兩點推算圓心 (倉頡碼 "NMVO" 對應弧) |
| `DUBLNE` | **雙線** | 兩側同形者（門、閩類） |

這套筆畫分類比傳統「永字八法」細得多，顯然是針對實際漢字機制調校出來的。**每一種都是一個獨立 subroutine，共享同一份座標轉點陣的下游程式碼。**

## 三、第二個震撼：多字型 + 多字態的參數化

從 `MODTRACE.ASM` 節錄（已由 Big5 正確解碼）：

```asm
BBTRCWID  DB  71    ; 字寬 (點)
BBTRCLEN  DB  125   ; 字長 (點)
BBFNTKND  DB  0     ; 0=明體  4=黑體  6=圓體
BBFNTOFS  DB  0     ; 字形右移點數
BBJBMRNK  DB  6     ; 直變 (豎筆粗細級數)
BBDTCRNK  DB  3     ; 橫變 (橫筆粗細級數)
BBMADSET  DB  0     ; 橫變設定
BBFNTCHG  DB  0     ; 特殊變化種類
BBTENNUM  DB  0     ; 套花字體 (右旋次數借用之)
BBCCGTYP  DB  0     ; 漢字態：0繁 1簡 2日
```

翻譯成人話：**同一份底層資料可以透過調整全域參數一次產出**：
- **字型風格**：明體 / 黑體 / 圓體
- **粗細級數**：橫筆與豎筆可各 14 級 (BERUNTME = 14)
- **字寬字長**：完全可縮放
- **繁/簡/日** 三套字形
- **套花裝飾**：花字型變體

**這正是你原始需求「不同的字型，可以快速地轉換出需要的向量筆跡」的完成形態**。2010 這個系統已經把你想做的事做出來了，只是輸出到 DOS 點陣而非向量。

## 四、資料層結構 (data files)

2010 版 T*.ASM 檔案大小（對比 1992 的 OBJ）：

| 檔案 | 1992 OBJ | 2010 ASM | 用途 |
|---|---|---|---|
| T11 | 8 KB | **204 KB** | 主索引/資料表，資料量暴增 25× |
| T12 | 8 KB | 14 KB | 次索引 |
| T21 | 11 KB | **150 KB** | SPCZONE/ANTZONE (特殊/反常字形) |
| T3 | 8 KB | 39 KB | ZONE2 資料 |
| T4 | 8 KB | 115 KB | ZONE3 資料 |
| **合計** | ~43 KB | **~523 KB** | |

資料還是 bytecode（每字幾個 bytes），但存放的是**向量指令**而非 bitmap。典型 entry 片段：

```
000H,000H,022H,00FH,000H           ; 5 bytes (short ref)
020H,004H,005H,000H,005H,030H...   ; 8 bytes (compound)
0BBH,088H,034H                     ; 3 bytes (direct)
0BBH,085H,0DEH,053H,011H,0AEH,085H ; 7 bytes (含 0xDE 指令)
```

`0xDE` 作為第三 byte 是關鍵操作碼之一；其他看到重複出現的是 `022H`, `04CH`, `0B4H`, `0A0H`, `094H` —— 推測是筆畫類型代號表。

## 五、程式檔 (testfont2010)

| 檔 | 日期 | 大小 | 推測用途 |
|---|---|---|---|
| `CGA.EXE` | 1989 | 261 KB | 初代繁體顯示器 |
| `ABV.EXE` | 1993 | 260 KB | 繁體 + 日文 (ABV = ?) |
| `DEMO.EXE` | 1994 | 160 KB | 示範程式 |
| `DEMO1.EXE` | 1996 | 219 KB | 示範 + 互動 |
| `CGB.EXE` | 2000 | 278 KB | 最新版 (繁簡雙支援) |

可以在 DOSBox 裡跑起來驗證視覺輸出，但**對我們的向量轉換價值有限**（它們也只是呼叫同一套引擎並顯示到 VGA）。

## 六、這改變了什麼 —— 策略重估

### 原本規劃 (Phase 1 用 Make Me a Hanzi 起步)

MMH 的優勢：
- 已經是 JSON + SVG medians，**零解析成本**
- 有筆順資料 (笛卡兒座標點列)

MMH 的限制：
- 約 9000 字，繁體涵蓋率低
- **沒有筆畫分類**（每個 median 就是一串點）
- **沒有多字型支援**（筆跡就是筆跡）

### 新選項：2010 版字庫 (SCG)

優勢：
- **約 18,000 繁體字**，Unicode 涵蓋更完整
- **9+ 種筆畫原子分類**，明確標註頭型/尾型/粗細
- **明/黑/圓三種字型從同一資料產出** ← 正中你核心需求
- **14 級粗細 + 寬高可調 + 裝飾變體**，參數化程度極高
- 繁/簡/日三套漢字態

代價：
- **必須逆向 bytecode 格式**（T*.ASM + MODVEC + MOD1 + MOD2 約 400 KB 原始碼要解讀）
- MOD2.ASM 有 **177 KB**，是整個系統最複雜的解譯器
- 沒有任何規格文件，只能靠反向工程

### 三條路線評估

| 路線 | 開發時間 | 字數涵蓋 | 多字型 | 風險 |
|---|---|---|---|---|
| **A. 純 MMH** | 1-2 週 | 9000 (以簡體為主) | 需自建 | 低 |
| **B. 純 SCG2010** | 4-8 週 | 18000 (繁為主) | **內建** | 高 |
| **C. 混合策略** | 2-4 週 | 9000 起，可擴 | 分階段 | 中 |

**路線 C 詳述（我目前建議）**：

1. **第 1 階段**：用 MMH 打通輸入→向量→三格式的主流程（原規劃 Phase 1-3）
2. **第 2 階段**：**只挖 MODVEC 的筆畫原子庫**（不解碼 T*.ASM 資料）
   - 從 `JBMM/DTWC/WFR/CPI/QAMO/...` 各 subroutine 反推 9 種筆畫的**參數化幾何模型**（起終點 + 頭型 + 粗細 → bezier/polyline）
   - 在 Python 裡重寫為 `Stroke.render(start, end, head_type, thickness, style)`
   - 把 MMH 的 medians 作為「範例」去訓練/對齊我們的參數化筆畫
3. **第 3 階段**：得到一套「9 種筆畫 × 3 種字型風格 × 連續粗細」的生成器，任何字 = 組件樹 + 每筆參數，和 SCG 2010 同架構但以向量直出
4. **第 4 階段（選）**：若有動機，再回頭解 T*.ASM 的 18000 字編碼

## 七、具體收穫清單（可直接搬進程式碼的設計）

以下是這批資料給出的**明確設計決定**：

1. **筆畫不是 polyline，是參數化物件**
   ```python
   @dataclass
   class Stroke:
       kind: Literal['heng', 'shu', 'pie', 'na', 'dian', 'ti',
                     'zhe', 'gou', 'arc', 'parabola']
       start: Point
       end: Point
       head_type: int      # 0平 1尖 2,3轉
       tail_type: int
       thickness: float    # 連續值 (原系統 14 級)
       angle: float | None # 某些筆畫需要
   ```

2. **字型風格是全域參數，不是多套資料**
   ```python
   @dataclass
   class FontStyle:
       kind: Literal['ming', 'hei', 'yuan']  # 明/黑/圓
       hstroke_weight: int   # 1-14
       vstroke_weight: int   # 1-14
       width: int            # 字寬
       length: int           # 字長
       x_offset: int         # 右移
       decoration: int       # 套花 0 = 無
       char_form: Literal['trad', 'simp', 'jp']
   ```

3. **渲染管線 = 單一 Stroke 物件 × FontStyle → polyline**
   - 直接對應 MODVEC 的 subroutine 結構
   - 三格式 exporter (SVG/G-code/JSON) 放在 polyline 之後

4. **「共用筆跡」= 儲存 Stroke 類別 + 參數，不儲存點列**
   - 每個字存為 `[Stroke, Stroke, ...]` 列表，每 Stroke 僅 8 個 float
   - 對比 MMH 每字動輒 100+ 個點，資料量可再縮 10×
   - 切換字型只改 FontStyle，不動字元資料

5. **分區 ZONE 的啟示**：資料庫分三層
   - ZONE1 (T21) = 常用字組件庫
   - ZONE2 (T3) = 次常用
   - ZONE3 (T4) = 特殊/罕用
   - 依頻率分區可以做出**漸進式載入**的本地 Web 應用

## 八、對原規劃的修正

在前一份 `REF_ANALYSIS_SCG.md` 我建議的 IR 改為「組件樹」。結合這份資料，再進一步：

```
Character
  └─ ComponentTree
       ├─ structure: left_right / top_bottom / ...
       ├─ Component (radical)
       │    └─ StrokeList
       │         ├─ Stroke(kind=heng, start=..., end=..., head=...)
       │         ├─ Stroke(kind=shu, ...)
       │         └─ ...
       └─ Component (radical)
            └─ StrokeList

＋ FontStyle (全域套用)
```

渲染時：
```
Character × FontStyle
  → ComponentTree 展開（遞迴）
    → Stroke list
      → 每 Stroke.render(style) → polyline
        → Exporter (SVG / G-code / JSON)
```

這和 SCG 2010 的管線架構完全等價，但：
- 輸出端改為向量（polyline）而非 bitmap
- Stroke 參數用 float 而非 8086 的 byte packing
- IR 用 Python dataclass 而非 bytecode

## 九、結論

1. **這份 2010 資料證實你的目標是可實現的** —— 30 年前就有人做到了（雖然輸出是 bitmap）。
2. **「不同字型快速轉換」的技術方案是「參數化筆畫 + 全域風格參數」**，不是為每種字型存一套資料。
3. **建議走路線 C（混合）**：MMH 起步 + 挖 MODVEC 的筆畫原子定義，兩者結合做出比 MMH 更豐富（多字型）、比 SCG 更現代（向量直出）的系統。
4. **動工時 Phase 1 的 IR 應直接用本文件第七節的 `Stroke` + `FontStyle` 設計**。

---

**等你說「可以動工」。** 若你對上面的路線 C 或筆畫分類有意見，先提出，我再調整。若還有更多資料要給我，我繼續分析。
