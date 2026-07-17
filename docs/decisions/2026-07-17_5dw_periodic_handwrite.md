# 決策紀錄 2026-07-17（5dw）：逐字手寫延伸到元素週期表頁

對應 PRINCIPLES §26。承 5dp→5dv 抄經深化弧的下弧候選，QODA 使用者選
「手寫延伸到表格頁」、範圍拍板「A：只做週期表」。commit：待收工檢查.bat
（0.14.201）。

## 背景

5dt 的逐字手寫只綁抄經內文頁。使用者要延伸到元素週期表頁。動工前先追清楚
資料契約，發現這不是「加功能」而是「補一條沒接上的線」。

## D1. 缺口＝單一未轉發旗標，靠端到端追契約定位（§26①）

點擊互動的三段契約——① render_sutra_page 產生 `#sutra-cellmap` 透明 rect
（emit_cellmap=True）② 前端 sutraRender 送 emit_cellmap:true ③ 前端
swAttachPreviewClicks 綁 rect→開彈窗——**產生端與消費端早就通用**（前端對
table 頁也送旗標、也無條件接線；render_sutra_page horizontal 方向也發
data-char）。唯一斷點：server.py `page_type=="table"` 分支呼叫 renderer
時漏傳 emit_cellmap（body 分支有傳）。判準：功能「幾乎會動」時沿契約逐段
走，斷點常是某段沒把既有參數往下傳。

## D2. registry 分派用能力偵測、不寫死 preset（§26②）

`_table_page_renderer` 是六個異質簽名的 renderer 註冊表（週期表重用
render_sutra_page、乘法表/節氣自繪且多字格、部首/倉頡/注音自繪單字格）。
要只把 emit_cellmap 餵給吃得下的 renderer：

- 方案 A（採用）：`inspect.signature(fn).parameters` 偵測，能就傳。新單字
  表 renderer 加簽名即自動 opt-in、自繪多字表零影響、分派點不維護白名單。
- 方案 B（否決）：`if preset == "periodic_table"`。每加一張表回補 if，且
  把「誰支援」的知識外洩到分派點、易過期。

## D3. 範圍只做週期表（QODA A，非過度工程）

逐字手寫是「一格＝一個可寫字形」模型。週期表每格單一元素字、天生契合。
乘法表/節氣每格多字詞（三七二十一/立春），無法指定寫哪個字＝語意不合。
部首/倉頡/注音雖單字但自繪、要各補 cellmap 疊層＝範圍×4、價值較低（參考表
非練寫場景）。故本輪只做週期表；B 留下輪乾淨延伸。

## D4. 重用複利在第 N 個消費者兌現（§26③）

只花兩行，正因 5du（§24）先把週期表改成重用 render_sutra_page、別複刻
格線——週期表天生是單字米字格頁，cellmap 機制原封套上。cellmap 收集器
第三度兌現：抄經內文頁→（本輪）週期表頁。「重用勝於自造」的省力在後續
功能免費落地時才結清。

## 驗證與交付

- render 層＋API 單元測試 4，全量 pytest 沙箱 1711 passed / 0 failed。
- Playwright 端到端（真 UI）：週期表→表格頁→真 sutraRender→118 cellmap
  rect→點「氫」→逐字彈窗開（第 1/118 字・目前：氫），截圖目視（§25 驗到
  畫面）。沙箱遠端字形源不可達，null loader 打樁＝罕用字無筆順的真實場景。
- 0.14.200→0.14.201、badge tests 1700→1704（+4 離線）、零新增依賴、node
  257 不變。
- 收官三件套：WORK_LOG_2026-07-17.md＋本檔＋PRINCIPLES §26。
