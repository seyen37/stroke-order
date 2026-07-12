# 2026-07-12：自訂字型全能力線＋注音欄（5cr→5cu）

**版本**：0.14.157 → 0.14.161（commits 3c9ff94 → aa99a55）
**Tests**：1642 → 1647
**關聯**：前情見 `2026-07-11_5ck_5cq_opencv_delivery_userfont.md`；
原則沉澱見 `../PRINCIPLES.md` §10；生態參考見
`../../REF_ANALYSIS_WORKSHEET_ECOSYSTEM.md`（含五之一 IVS 增補）

---

## 一、5cr：凍頁陷阱（延伸修復，自主推進）

使用者本機伺服器（127.0.0.1）重測 opencv 整頁凍死，帶來兩個
定論：①執行病灶與檔案來源徹底無關（昨日環境層定性的獨立
複驗）②降級階梯設計缺陷——「worker 失敗退主執行緒」在
「主執行緒自身會懸掛」的機器上是死路，且主執行緒一凍 timer
全停、看門狗完全失效。

**決策**：opencv 引擎 worker 失敗後直接 throw（UI 層退伺服器
＋sessionStorage 失敗記憶），不再嘗試主執行緒；browser 引擎
（純 JS、無大型腳本載入）維持原 fallback。原則化為 §10.3：
**fallback 目的地不可與失敗層共享病灶**。

## 二、5cs／5ct：自訂字型第二、三步（5cn QODA 既定路線）

- 5cs 機器軌跡：glyph 光柵化 → 5cg 純函式三件組（Zhang-Suen／
  圖論追蹤／RDP）→ EM 軌跡 → 前端組 G-code（與
  render_grid_gcode 慣例逐項對齊）。誠實標注「幾何近似、
  非教育部筆順」。驗證方法論：node 假 DOM 座標級斷言
  （flip_y／格位移／ghost 跳過）——前端幾何在出貨前用數學驗。
- 5ct 擴模式：notebook/letter 共用 page.py `_char_svg`，字元
  群組 transform 自帶 translate(mm)+scale(mm/EM)——一處加
  data-* 錨點、多模式生效，注入器零修改。**分層的價值在第二個
  消費者出現時兌現**（§10.1）。

## 三、5cu：注音欄（QODA 完整流程）

- Q：REF 行動項之首「注音欄」；字→注音查詢從何而來？
- O：①前端 pinyin-pro＋規則轉換表（零伺服器依賴）
     ②伺服器 pypinyin 新依賴 ③手動輸入
- D：①——pinyin-pro 已載（詞境判定）、拼音→注音是確定性
     規則（數學題不是資料題）、「語言知識在前端、排版渲染在
     伺服器」與 5cn 同構
- A：使用者 OK（2:1 欄寬、破音字預設讀音、SVG 先行）
- 實作：zhuyin_map 參數存在即開欄；pair 版面 3072 EM；
  _zhuyin_strip 復用 _cell_content（描紅樣式全繼承——
  「注音也能練筆順」的機制核心）；聲調手作 polyline（機器
  可寫）；data-pair-em 讓 5cs G-code 格距同步。
- 驗證：轉換表 33 樣本 node 全對；exporter 版面契約測試
  （開欄 3072／關欄完全回舊版）。

## 四、REF 增補：IVS 注音字型生態

字嗨注音體（But Ko 注音 IVS 規格）＋讀音選擇工具＋McBopomofo
＋ToneOZ。三個收穫：

1. **⚠ 讀音標準兩套**：pinyin-pro＝大陸體系，台灣以教育部
   「一字多音審定表」為準（ToneOZ 遵循）——5cu 已知落差，
   行動項「台灣讀音校正表」（前端覆寫常見衝突字）。
2. **IVS（變體選擇器）是破音字社群共識解**——未來破音字修正
   UI 對齊「讀音選擇工具」互動模型；注入器可評估保留 IVS。
3. **組合技零開發**：字嗨注音體 TTF（開源免商用）餵 5cn
   自訂字型＋5cu 注音欄＝「看印刷注音、練筆順注音」同一張紙。

## 五、遺留與下一步

- 注音 v2 四項（修正 UI／台灣校正表／符號進 G-code／擴模式）
- 筆記/信紙 userfont G-code
- 家用機 OpenCV 驗證；部署後 5cs/5ct/5cu 實機驗收
