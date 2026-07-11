# Phase 5bo 科普教育分類（9 部 preset）

> **5bp 之後本步驟已為選配**：全部文本已打包進
> `src/stroke_order/data/sutras/builtin/`，新安裝與部署環境開箱即用。
> 手動放檔僅在想覆蓋打包版時需要（使用者檔優先）。

## 安裝（選配）

把本資料夾的 .txt 放到內建經文目錄即可：

```
~/.stroke-order/sutras/builtin/
├── periodic_table.txt        元素週期表（118 字）＋ table 版面頁
├── multiplication_table.txt  九九乘法表（45 句 200 字）＋ table 版面頁
├── solar_terms.txt           二十四節氣（48 字）＋ table 版面頁
├── kangxi_radicals.txt       康熙 214 部首（教育部字形）＋ table 版面頁
├── cangjie_roots.txt         倉頡字根（24＋難）＋ table 版面頁
├── zhuyin_symbols.txt        注音符號 37（聲介韻＋鍵位）＋ table 版面頁
├── chinese_numerals.txt      國字大寫數字（19 字）
├── zodiac_hours.txt          十二時辰十二生肖（24 字）
└── solar_system.txt          太陽系天體（25 字）
```

## 康熙部首與倉頡字根

- **kangxi_radicals**：214 部首採臺灣教育部標準字形（青非靑、戶非户），
  全部命中筆順資料庫、零 CNS fallback。table 頁為 18 欄流式排列、
  畫數分帶換色，每帶首格紅字標畫數。部首＝組件，與 docs/VISION.md
  組件化字型路線直接呼應。
- **cangjie_roots**：24 基本字根＋X 難，table 頁依哲理／筆畫／人身／
  字形／特殊五類分帶，格內紅字標鍵位（A-Y）。

Windows：`%USERPROFILE%\.stroke-order\sutras\builtin\`

## 九九乘法表版面頁

與週期表同機制（`page_type=table`，server 端 `_table_page_renderer`
registry 分派）：下三角 45 格階梯排列，格內阿拉伯算式提示＋中文口訣
描紅，三色循環列底。口訣拼寫依台灣國小慣例由
`exporters/multiplication_table.py::mnemonic()` 程式化生成
（得X／一十／十X／二十X），45 句經測試逐句驗證。

## 內容

全 118 元素中文名（臺灣國家教育研究院譯名），依原子序排列，
一行一週期（載入時空白自動剝除，實際抄寫 118 字連排）。

- 43 鎝、85 砈、87 鍅、71 鎦 採臺灣譯名（與中國大陸譯名不同）
- 104–118 號（鑪𨧀𨭎𨨏𨭆䥑鐽錀鎶鉨鈇鏌鉝鿬鿫）多為 CJK 擴充區罕見字，
  筆順資料庫無資料者由 CNS 全字庫字型描邊 fallback 呈現
  （需先跑 `scripts/render_fetch_fonts.sh` 或已有 `~/.stroke-order/cns-fonts/`）

## 週期表版面頁（page_type=table）

除了循序描紅 body 頁外，periodic_table preset 另有標準週期表排列的
單頁字帖（18 族 × 7 週期＋鑭錒系抽離兩列，A4 橫式）：

- Web UI：抄經模式選「元素週期表」後，頁面導覽最後一頁即為「週期表」頁
- API：`GET /api/sutra?preset=periodic_table&page_type=table`
- PDF：`/api/sutra/pdf?preset=periodic_table` 自動附於 body 頁之後（限橫式）
- 格內：原子序（左上）＋元素符號（右上）＋中文描紅（置中）＋分類淡色底
- 實作：`src/stroke_order/exporters/periodic_table.py`（版面資料 `ELEMENTS` 118 格經測試無重疊）

## 驗證紀錄（2026-07-11）

118 字逐字過 `_load(ch, "auto", "static")` 全數通過：
筆順資料 103 字（含 鎝鐽錀鏌=moe_kaishu、鑪=mmh）、
CNS 字型 fallback 15 字。
