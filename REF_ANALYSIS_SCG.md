# 明珠中文小字庫 (SCG) — 參考資料分析

> 分析對象：`scg.zip` (1992 原版) + `scg_yang.zip` (2008 楊氏加註版)
> 關聯目標：中文字 → 向量筆跡 → 寫字機器人

---

## 一、它到底是什麼

「明珠中文小字庫」是 1992 年在 DOS 上以 MASM 撰寫的**常駐式中文字庫** (TSR)，透過 `INT 60H` 中斷對外提供字型點陣。

規格重點：

- 約 **18,000 個繁體字**，提供 15×15 / 15×16 / 22×24 / 24×24 四種點陣大小
- 整個字庫資料段 (DG) 僅 **~63 KB**、`SCG.EXE` 僅 **83 KB**
- 以**倉頡碼**為索引（輸入 5 位倉頡碼，回傳點陣）

## 二、為什麼 63 KB 能裝下 18,000 字？

這是這份資料最有價值的地方。單純儲存：
- 24×24 bitmap = 72 bytes × 18000 = **~1.3 MB**
- 即使 15×15 也要 ~540 KB

它塞進 63 KB 的關鍵是 —— **這不是字型表，是「組字指令流」資料庫**。

## 三、核心架構：組件 + 指令 + 幾何合成

每個字不是一張完整點陣，而是一串「如何用共用組件拼出來」的指令。

```
倉頡碼 (e.g. 明=AB → 1,2,0,0,0)
      │
      ▼
┌─────────────────────────┐
│  INDEX1/2/3 (TAB52)     │   ← 倉頡 5 碼 → 指令流起點 (MOMAP.ASM)
└─────────┬───────────────┘
          ▼
┌─────────────────────────┐
│  指令流 (T11..T22, T3, T4) │  ← 每字一段 bytecode
│  含三類 opcode:          │
│   ACP0D : 直接 bitmap    │
│   ACP0E : 引用另一組件   │
│   ACP0A : 組件 + 幾何變換│
└─────────┬───────────────┘
          ▼
┌─────────────────────────┐
│  NBUFH1/H2/H3 (Head)     │  ← 最多 3 層「部首」堆疊
│  NBUFDAT   (Body)        │  ← 「字身」
└─────────┬───────────────┘
          ▼
┌─────────────────────────┐
│  STR16 / STR24 渲染器     │  ← MOD1 / MO24
│  INSMAP + DTWCPT 幾何表  │  ← 置中 / 三分 / 平移 / 鏡射
└─────────┬───────────────┘
          ▼
    最終點陣
```

## 四、關鍵原始碼模組對照

| 檔案 | 用途 |
|---|---|
| `MOMAP.ASM` | 倉頡首碼索引表 (`TAB52`)、幾何變換查找表 (`PORT0E`, `PORTNO`, `DELHEAD`) |
| `MOD1.ASM` | **核心解譯器** — `START` 入口、`BODY` 匹配、`ANALYA/ACPTD` 指令迴圈 |
| `MOD2.ASM` | 15/16 點陣渲染 (`STR16`) |
| `MO24.ASM` | **24×24 合成引擎** (`STR24`) — 含 `INSMAP` 指令跳轉表、`DIV3TB`、`CENTAL` |
| `NASCD.ASM` | ASCII 字型 (純 bitmap，沒有組合) |
| `ASCC.ASM` | ASCII 切換邏輯 |
| `T*.OBJ` | 指令流資料（分區）：`T11-T14` = INDEX，`T21-T22` = 組件區 ZONE1，`T3` = ZONE2，`T4` = ZONE3 |
| `I*.OBJ` | 英數字型點陣資料 |
| `TSR.ASM` | INT 60H 中斷掛載 |

`yMOD1.ASM` 的 EXTRN 註解直接點明了資料分區：

```
TT1,TT2,TT3 = T22.OBJ     (首碼跳轉表)
ZONE1 = T21.OBJ           (主要組件區)
ZONE2 = T3.OBJ, ZONE3 = T4.OBJ  (次要組件區)
TAB52 = MOMAP.ASM         (26 倉頡首碼索引)
```

## 五、指令集解析 (`ACPTD` 主迴圈)

`MOD1.ASM` 的 `ACPTD` / `ACPLOP` 是核心指令直譯器。指令第一個 byte `AL`:

| AL 範圍 | opcode | 語意 |
|---|---|---|
| `< 0x10` (ACPINS) | 控制類 | 分支跳轉、結束 |
| `0x0A` (`ACP0A`) | **組合指令** | 讀組件+頭+底+偏移，最複雜 |
| `0x0B` (`ACP0B`) | **子例程呼叫** | 遞迴展開另一字的指令流 |
| `0x0D` (`ACP1`) | 結束標記 | 指令流終止 |
| `0x0E` (`ACP0E`) | **引用+查表** | 用 `PORT0E` (128 bytes 幾何表) 調整位置 |
| `0x0F` (`ACP0B`) | 特殊擴展 | 含 `NBUF0B` 動態參數 |
| `≥ 0x10` (`ACP0D`) | 原始位元 | 直接寫入 bitmap buffer |

`PORT0E` 128 bytes 的編碼極為緊密：高 4 bit = 水平位置類別、低 4 bit = 垂直位置類別，查表取得偏移與遮罩。

## 六、幾何合成引擎 (`STR24`)

`MO24.ASM:STR24` 是真正把組件放到畫布上的核心：

- `INSMAP` 陣列是指令→subroutine 的跳轉表（見 l.122: `CALL CS:WORD PTR [BX+INSMAP]`）
- `DIV3TB` / `DIV3BX` / `DIV3BL` — 三等分點計算（左右結構、上中下結構）
- `CENTAL` / `CENTAC` — 置中對齊
- `DTWCPT` / `DTWC0` — 位移寬度表 (8-byte 位元遮罩: `0FFH,07FH,03FH,01FH,00FH,007H,003H,001H`)
- `JBMM33`, `RIGTWZ` — 水平右移、垂直壓縮

程式在解析組件時，會判斷：
- `AL == AH`？ → 對齊
- `CL < CH`？ → 左右關係
- `AL < AH`？ → 包含關係

依此選擇 `INSMAP` 的不同 entry 進行渲染。

## 七、這份資料對你專案的價值

### 直接可用的部分 — **架構思想**

| SCG 做的事 (bitmap) | 你要做的事 (vector) |
|---|---|
| 倉頡碼 → 組件 bytecode | 中文字 → 筆劃/部首組件 |
| 組件 = 點陣 stripe | 組件 = polyline / SVG path |
| 指令流 (ACPTD opcode) | IR (AST 或組件引用樹) |
| 幾何表 `PORT0E` | 組件變換 (translate/scale/mirror) |
| `STR24` 佈局引擎 (`INSMAP`/`DIV3TB`/`CENTAL`) | Canvas layout — 左右結構、上下結構、三分、置中 |
| 3 層 head buffer (NBUFH1/H2/H3) | 遞迴組件樹 |

**最重要的啟發**：它證明了「組件重用 + 指令流」的設計**真的能讓字庫超小又完整**，在 1992 年的 64KB 限制下做到 18,000 字。這驗證了你「拆解出共用筆跡」的直覺方向完全正確。

### 不能直接用的部分 — **資料本身**

- T*.OBJ 是 **bitmap 資料**，不是向量。抽出來也只有低解析度點陣，不適合給寫字機器人。
- 就算反編譯，指令格式是為 8-bit bitmap 設計的（高 4 bit / 低 4 bit 壓縮），轉換到向量需要完全重寫 codec。
- 倉頡碼作為 key 太依賴輸入法，我們主流程應該用 Unicode，但可以**沿用「倉頡碼暗示組件結構」的啟發**（例如「明」= AB = 日 + 月，這本身就是拆解提示）。

### 已經比它好的部分 — **Make Me a Hanzi**

- 現代來源：MMH 的 `graphics.txt` 本身就是 9000 字的**向量骨架 (medians)**，直接可做筆跡。
- 沒有 ACP0E/PORT0E 那種位元壓縮的痛苦，JSON 格式直接吃。
- 不過 MMH **沒有做「組件重用」**，每個字 medians 是獨立的；SCG 在這點上反而領先 30 年。

## 八、結論與後續建議

1. **主流程繼續用 MMH** 起頭（最快、最完整的向量骨架資料），不碰 SCG 的 bitmap 資料。
2. **把 SCG 的組件重用架構移植到 Phase 4 筆劃範本庫**：
   - 參考 `PORT0E` 表設計我們的「組件變換參數」—— 但用浮點 (scale, dx, dy) 取代 4-bit 整數。
   - 參考 `INSMAP` + `STR24` 的「結構類型判斷」(左右/上下/包圍/三分)。
   - 參考 `ACPTD` 的遞迴展開，做 Character → Component tree 的遞迴渲染器。
3. **Cangjie code 可以當 secondary index**：
   - 若未來要做字元組件分解的 hint，倉頡碼本身就是人類整理好的「組合提示」。
   - 可做輔助查詢：輸入「明」→ 找到 AB → 分別渲染「日」「月」→ 左右合併。
4. **「組件樹」IR 格式**可以直接參考 SCG 的分層概念：
   ```python
   Character
     └─ Component (type=left_right, children=[...])
          ├─ Component (type=atom, strokes=[...])
          └─ Component (type=atom, strokes=[...])
   ```
   這比原本規劃的「Character → flat Stroke list」更能支援「共用筆跡」的終極目標。

## 九、動工時要同步修正的架構

原規劃的 IR 是「Character → flat list of Stroke」。看過 SCG 後，我會改成：

```python
@dataclass
class Stroke:
    points: list[Point]
    category: str    # 橫/豎/撇/捺/折...
    bbox: BBox

@dataclass
class Component:
    """可以是一個筆劃、一個部首、一個組合結構"""
    id: str                        # 例: "stroke:橫", "radical:日", "char:明"
    type: Literal['stroke', 'radical', 'character']
    structure: Literal['atom', 'left_right', 'top_bottom', 'enclose', 'three_part'] | None
    strokes: list[Stroke] | None   # atom 型才有
    children: list[ComponentRef] | None  # 非 atom 型才有
    bbox: BBox

@dataclass
class ComponentRef:
    component_id: str
    transform: tuple[float, float, float, float]  # scale_x, scale_y, dx, dy
```

這樣才能做「一次定義『日』→ 所有含日的字重用」。MMH 資料載入後可以用 cluster/對齊演算法去**自動發現**共用組件，這是 SCG 當年手工做的事，現在可以演算法化。

---

**簡言之**：這份資料是 1992 年的字庫考古，**bitmap 不能直接用**，但它的**組件化思想正好驗證你的方向**，且明確指出我原本規劃裡沒想透的一件事 —— IR 應該是「組件樹」而非「筆劃列表」。等你說可以動工，我會把這點納進 Phase 1 的 IR 設計。
