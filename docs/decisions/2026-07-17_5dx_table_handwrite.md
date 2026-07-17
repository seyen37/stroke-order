# 決策紀錄 2026-07-17（5dx）：逐字手寫延伸到部首/倉頡/注音單字表

對應 PRINCIPLES §27。承 5dw（週期表逐字手寫）的下弧候選 B，QODA 使用者選
「A：抽共用 helper、三表一輪」。commit：待收工檢查.bat（0.14.202）。

## 背景：5dw 的複利當場兌現

部首（214）、倉頡（25）、注音（37）三張表都是**自繪** renderer（各自
`_wrap_svg(inner)`，不重用 render_sutra_page），但每格單一字/符號＝貼合
逐字手寫「一格一字」模型。落地只需各自吐 `#sutra-cellmap` 疊層，而兩端
都不用動：

- **後端 server 零改動**：5dw table 分支已用 `inspect.signature` 能力偵測
  轉發 emit_cellmap（§26②）。三 renderer 簽名一長出 emit_cellmap，server
  自動餵旗標——「新單字表 opt-in 免費」當場應驗。
- **前端零改動**：sutraRender 對任何頁送 emit_cellmap:true＋無條件
  swAttachPreviewClicks，契約 `#sutra-cellmap rect[data-char]`。

## D1. 跨層契約要單一真相源：抽共用 emitter（§27）

三個自繪 renderer 要吐的 rect，格式必須與抄經頁**逐字節一致**——因為前端
parser（swAttachPreviewClicks）只認 `#sutra-cellmap rect[data-char]` 這個
確切結構（含 data-pos 讀序、data-missing 缺字標記）。若各 renderer 各自
內嵌一份 rect 字串產生，就是同一個跨層契約複製 4 份，任一處漂移都會讓前端
悄悄接不到。

故在 sutra.py 抽出 `cellmap_rect()`＋`cellmap_group()` 單一真相源，並把
render_sutra_page 原本內嵌那段也改用（零行為變化，既有 sutra cellmap 三
測試綠證）。判準：**當 N 個產生端要吐同一個由別層 parser 消費的字串契約，
把「產生那段」抽成一個共用函式，別讓每個產生端各持一份會漂移的複本。**
契約要改時一處改、全體生效、parser 端不會突然對不上。

## D2. 只對可寫格發 rect：語意邊界（倉頡/注音的標籤帶）

倉頡/注音的左側是分類**標籤帶**（哲理類/聲母…），不是可寫字格。cellmap
只在內圈的字/符號格發 rect，跳過標籤帶——否則「哲」「聲」等標籤字會變成
可點手寫格，語意錯誤。測試明確斷言 `data-char="哲"`／`data-char="聲"`
不出現在 cellmap。pos 用跨分組全域計數（內圈 k 每組重置，全域 cell_pos
才是正確讀序）。

## D3. 範圍：三表一輪、多字格不做

逐字手寫是「一格一字」模型。週期表（5dw）＋部首/倉頡/注音（本輪）＝所有
單字表已覆蓋。乘法表/節氣每格多字詞（三七二十一/立春），無法指定寫哪個
字＝語意不合，維持不做（server 能力偵測自動跳過它們＝零回歸）。

## 驗證與交付

- helper 重構零回歸（sutra cellmap 3 測試）；三表測試 +6（rect 數
  214/25/37＋標籤字不成 rect＋API 流通＋loader 記憶化不破）。
- 全量 pytest 沙箱 1717 passed / 0 failed（1711→+6）。
- Playwright 端到端三表（真 UI）：選表→表格頁→cellmap 214/25/37→點格子
  （一/日/ㄅ）→逐字彈窗開 current_char 相符，3/3 PASS 零 error。
- 0.14.201→0.14.202、badge tests 1704→1710（+6 離線）、零新增依賴、node
  257 不變。
- 收官三件套：WORK_LOG_2026-07-17.md（5dx 節）＋本檔＋PRINCIPLES §27。
