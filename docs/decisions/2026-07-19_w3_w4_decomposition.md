# 決策紀錄 2026-07-19（W3＋W4）：前後端巨石拆分——四輪 QODA 重放

對應 PRINCIPLES §41–§44。commits：`3bd5ce5`（W3-R1，0.14.230）→
`a771538`（W3-R2，0.14.231）→ `1283625`（W4-R1，0.14.232）→
`3e5a047`＋`8eb7887`（W4-R2 兩批，0.14.233→234）。
成果：server.py 5,010→269 行；index.html 10,859→3,255 行、16 個
ES modules＋顯式 import/export 網。

---

## 總決策：兩輪制（機械搬遷輪 ↔ 去重複輪分離）

W3、W4 皆 QODA 定案「兩輪」：R1 純機械搬遷、**行為零變**、先立機器
快照鎖（W3＝92 條路由 (method,path) 集合；W4＝拆檔串接與拆前 inline
**逐位元組一致**＋載入序快照）；R2 才改邏輯（工廠收斂／module 化）。
理由：搬家與改邏輯混在同個 diff 出問題難定位；零變更輪可以被全量
測試＋快照鎖完全鎖死，改邏輯輪站在綠色地基上動刀。

## W3-R1 三坑（當場規則化，見 §42）

1. **模組層 `app = create_app()` 循環**：server import routes、routes
   import server，模組層建 app 會在 server 未初始化完就重入 routes。
   → PEP 562 `__getattr__` 惰性建立（uvicorn "server:app" 屬性存取
   不受影響；R2 解掉循環後仍保留——import 不付建 app 成本）。
2. **FastAPI 0.139 include_router 巢狀掛載**：app.routes 只見
   `_IncludedRouter` 容器、非攤平——三個 introspect 路由的既有測試
   沉默失效或誤判。→ 立 `routes.iter_routes()` 攤平走訪器
   （走 `original_router`），所有路由 introspection 一律過它。
3. **monkeypatch by-value**：測試 `setattr(srv, "_load", ...)` 對
   `from ..server import _load` 的綁定無效（import 時已取值）。
   → 跨界被 patch 的符號一律執行期屬性存取（`_server._load(...)`）；
   R2 起 patch 目標唯一住址（char_pipeline），server 不留別名——
   「patch 別名不影響實際呼叫」是沉默失效地雷。

## W3-R2：主題拆模組＋工廠收斂

QODA 定案主題拆（char_pipeline／responses／versioning／capacity）非
單一 shared.py（拒絕再養雜燴桶）。`make_char_loader(source, hook_policy,
style, *, cns_outline_mode, seal/lishu_outline_mode, catch_all, memoize)`
收斂 9 個 inline 閉包——差異全部變具名參數；sutra outline／mandala
loader 改工廠委派。**健檢修正**：「capacity Depends」實測只有
notebook/letter 同構（其餘五端點各有專屬計算）——收斂共用尾段
capacity_summary() 即止、不硬抽（OpenAPI 合約零變）。分層三鎖：
routes 禁 import server／載字鏈符號唯一住址／svg media_type 只寫一次。

## W4-R1：傳統 script 拆檔（不是直上 ES modules）

QODA 三選一定案「兩輪＋依模式 16 檔」：先傳統 script＋原文件序＝
全域語意（頂層 const/let 全域詞法可見、onclick 綁全域）與定義順序
**完全不變**，唯一語意差「跨檔無 function hoisting」以 Playwright
13 模式零 pageerror 實測排除。直上 ES modules 被否決：7,600 行全域
耦合網＋零 JS 單測護網，一輪動完是在賭。測試面：14 個「對 / 回應斷
JS 內容」的測試遷到 conftest `index_bundle` fixture（html＋modes
串接照載入序＝拆檔前語意）。

## W4-R2：AST 量測驅動的 module 化（見 §43／§44）

首批只轉「零被依賴」四檔——**用 AST def/use 矩陣挑、不是猜**；轉前
三道掃描（嚴格模式未宣告賦值／頂層 this／隱性全域外洩）全過才動。
次批 12 檔一次收尾：跨檔相依 ~25 條邊由矩陣生成顯式 import/export
（UNRESOLVED=0）。三個關鍵語意處理：

1. **import binding 唯讀**：`lastDoodleSvg` 由 doodle 寫入、notebook
   宣告——宣告權移居寫入方，消費端 import live binding 讀取。
2. **循環 import TDZ**：sutra↔handwrite、core↔fonts——函式宣告在
   instantiation 期已初始化＋雙方都事件時才呼叫＝安全；唯一跨邊
   const（API_BASE）逐一確認無頂層取用。
3. **import 路徑帶 `?v=__V__`**：5ev 注入對 .js 內文生效——跨檔
   import 的瀏覽器快取隨版本自動失效。

意外發現：**開機引導段住 mandala.js 尾端**（原 inline script 的
boot 區呼叫九檔 init）——次批將其 import 顯式化，這是「量測揭露
隱性結構」的直接例證。

## 驗收方法論（全四輪一致）

沙箱全量 pytest＋node → 真 uvicorn 起服抽測 → Playwright 真瀏覽器
（模式切換＋渲染流）→ 寫回 md5 hash-of-hashes 驗證 → 收工檢查.bat
（badge 自動化）→ 雙 remote → 部署後排程線上驗收（含合併驗收）。
環境噪音（沙箱擋 jsdelivr、缺 noto_hei／教育部字型）逐項判定
「拆檔前既有＝非回歸」後放行——不誤判也不放水。
