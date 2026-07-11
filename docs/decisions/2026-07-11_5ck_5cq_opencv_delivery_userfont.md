# 2026-07-11（第二弧）：OpenCV 交付鏈五層根因 ＋ 自訂字型（5ck→5cq）

**版本**：0.14.151 → 0.14.157（commits 884f368 → 022c675，含 docs）
**Tests**：1631 → 1642
**關聯**：第一弧見 `2026-07-11_5bt_5ch_doodle_engines_teaching_route.md`；
原則沉澱見 `../PRINCIPLES.md` §9；生態參考見
`../../REF_ANALYSIS_WORKSHEET_ECOSYSTEM.md`

---

## 一、背景：一個「產生中…」挖出五層根因

第一弧收官時（5cj，同源代抓），以為 OpenCV 引擎的校網問題已解。
第二弧由使用者持續複驗逼出更深的四層，加上第一弧的死 CDN 共五層，
每一層都被上一層掩蓋：

| 層 | 根因 | 揭露方式 | 修法（輪） |
|---|---|---|---|
| 1 | CDN pin 4.10.0 是死連結 | 使用者蓮花照雙盲實測 | 清單重試 pin 4.9.0（5ch） |
| 2 | 校網防火牆靜默丟包 docs.opencv.org | 使用者判斷＋提案 | 同源代抓 /vendor（5cj） |
| 3 | docs.opencv.org 對資料中心出站 403 | 線上錯誤訊息（4.x 轉跳 4.13.0） | jsDelivr 鏡像為主源（5cl） |
| 4 | 代抓端點 async def＋同步 requests 凍整個 event loop | 讀碼＋線上實測端點無回應 | 同步 def＋啟動預熱＋原子換檔（5ck） |
| 5 | 受管理電腦環境層卡「大型腳本的正式管道執行」 | Chrome MCP 對照實驗＋無儀器人工測試 | 換預設路徑＋失敗記憶（5cp） |

## 二、QODA 重放

### 5ck／5cl（延伸實作，無新 QODA）：把「使用者提案」做完

使用者提案「改由本伺服器下載」＝5cj 方向；5ck 補上它欠的三件
（預熱、解凍 event loop、可觀察性 /vendor/status），5cl 在 403
實錘後把抓取源換到 hotlink 友善的 jsDelivr（@techstark/opencv-js
dist＝官方 4.9.0 原檔，README 明載＋API 查證後採用）。

### 5cm→5co：worker 載入機制三段演化

- 5cm：importScripts（同步、不可逾時、silent-drop 下永久懸掛）
  → fetch＋間接 eval（可逾時、MB 進度）
- 部署驗收：下載鏈痊癒，但 10MB eval 在引擎情境 CPU 懸掛
  （inline 同字串 216ms ✓、引擎內同行無限卡、攔截包層即恢復）
- 5co 定型：**fetch 當看門狗＋暖身、importScripts 讀暖快取執行**
  ——「壞掉的那層不修，改讓它永遠不會走到」

### 5cp（QODA，使用者 sign-off「動工」）：接受環境層現實

八組 Chrome MCP 對照實驗＋使用者無偵錯器人工原生測試定案：
同 bytes 在 blob worker 4/4 成功、正式管道（URL worker
importScripts／主執行緒 script tag／worker eval）一律懸掛＝
環境層病灶（疑端點防護／code cache），網頁端不可修。
決策：預設引擎改伺服器（5ch 輪廓向量化）、OpenCV 降實驗性、
sessionStorage 失敗記憶、看門狗 90→30s。

### 5cn（QODA 完整流程）：自訂字型

- Q：「用自己電腦已安裝的字型」——字型只有外框、無筆順；
  版權要求本機處理
- O：①瀏覽器端匯入（opentype.js）②伺服器字型目錄③user-dict 橋接
- D：推薦①（資料不出本機、伺服器零版權風險、與塗鴉前端化同哲學）
- A：使用者選①＋「描紅列印先行、機器軌跡後續」
- 實作架構「伺服器管版面、前端管字形」：grid.py 每格 data-char/
  data-cell-style 錨點（視覺零變化）＋前端逐格替換字型外框 path；
  API 零侵入（送 style=kaishu 出版面）。驗收：MoeLI.ttf 隸書
  「永日」字帖 PASS（主字墨色＋ghost 描紅＋blank 留空＋blob 下載）

### 5cq（使用者提案）：vendor 燒入部署

build 時下載 opencv/opentype 進 git checkout 路徑（照
render_fetch_fonts.sh 慣例），runtime 同環境變數指路——執行期
零外網依賴；抓檔復用 _ensure_vendor_cached（單一事實來源）。

### REF（參考資料輪）：字帖／生字簿／注音工具生態六站

`REF_ANALYSIS_WORKSHEET_ECOSYSTEM.md`：twpen／澎湖硬筆網／雄
生字簿／新北生字簿／BopoDoc／家長評測。定位結論：紙本列印生態
成熟，本專案護城河＝軌跡層＋機器輸出＋組件覆蓋；缺口＝注音欄、
筆順序號、老師語彙參數。獨家機會：zhuyin.py 37 符筆順 →
「注音也能練筆順描紅」全生態沒有。

## 三、方法論亮點

1. **Chrome MCP 實機解剖**：十餘組對照實驗全在使用者的瀏覽器／
   校網環境執行，把「我的環境重現不了」這類問題的猜測空間逐步
   收斂到單一變因（blob worker vs 正式管道）。
2. **儀器效應自覺**：CDP 偵錯器本身是變因——最終定案前補了
   無儀器人工原生測試（§9.8）。
3. **QODA 的節奏**：大方向（5cn/5cp）走完整 QODA 等 sign-off；
   使用者已提案的延伸（5cj→5ck、5cq）與 bug 修復自主推進。

## 四、遺留與下一步

- Render 新 buildCommand 首次重建後驗 /vendor/status 雙 cached:true
- 家用電腦驗 OpenCV 引擎（環境病灶應不存在，屆時「實驗性」
  標籤可視結果調整）
- 自訂字型第二階段：骨架化（5cg 三件組復用）出機器軌跡；
  筆記／信紙模式複製注入架構
- REF 行動項候選七項（注音欄位為首）待排優先序
