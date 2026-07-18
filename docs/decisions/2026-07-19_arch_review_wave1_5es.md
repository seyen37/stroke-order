# 決策紀錄 2026-07-19（架構線）：全景健檢 → Wave 1 止血（5er）→ 503 修復（5es）

對應 PRINCIPLES §35–§38。commits：`a62c195`（5er，0.14.222）、
`3d64cf4`（5es，0.14.223）；健檢報告 `docs/ARCHITECTURE_REVIEW_2026-07-18.md`。

---

## 整體脈絡

使用者要求「重新檢視整個程式的規劃與設計、提出效能與維護建議」。以 4 個
分面審查（後端架構／效能／前端／測試部署）＋沙箱實測產出全景報告與四波
路線圖；使用者核准後立即執行 Wave 1。5er 部署後線上抄經 503，5es 當日
搶修收官。

---

## 決策 1：健檢結論——「掃全體」優先於「重寫」（§35 的起點）

**發現結構**：最嚴重的問題不是新缺陷，而是**已寫下的鐵則未追溯掃全體**——
§9.1（async def 內同步 I/O）在 5dp 修了 sutra/stencil 四條路由後未擴散，
其餘 12+ 條重渲染路由原樣；§27 單一真相源在 SVG header（11 處手寫漂移）
與 ?v=（22 處手動）失守；「改預設值 grep 全測試」教訓的根因（186 個寫死
長度斷言）從未結構性解決。

**決策**：路線圖以「低工作量高效益的鐵則掃全體」為 W1，結構性拆分
（APIRouter/前端巨石）押後至 W3/W4。**不做**：前端 build step、換框架、
動 gallery 安全層（審查認證其為模範層）。

## 決策 2：async→sync def 批次修＋機器回歸鎖（§35）

79 條 sync-body async 路由一次刪 `async`（FastAPI sync def 自動進
threadpool）；4 處 `await file.read()` 改 `file.file.read()`（starlette
解析完 multipart 已 seek(0)）。**關鍵配套**：`test_async_route_lock.py`
用 inspect 掃 APIRoute——async 路由必須在 allowlist（僅
gallery_auth_request_login，其 await asyncio.to_thread SMTP 為真非同步）
且 allowlist 不得有殭屍項。鐵則從「人記得」升級成「機器擋」。

## 決策 3：g0v 交付鏈——三層快取＋timeout 短化＋預抓入庫（QODA：bundle 2000 字）

| 選項 | 說明 | 取捨 |
|---|---|---|
| A ★ | bundle 單檔＋常用 2000 字入 repo | 單檔乾淨、冷路徑歸零；repo +5MB |
| B | 5000 字全集 | 覆蓋最廣但 +13MB |
| C | 只改碼不預抓 | 最小改動、冷路徑風險續存 |

採 A。順修既有 bug：socket 讀取逾時丟裸 TimeoutError（⊄ URLError）
炸穿路由層——沙箱全量 19 紅的根因，改 `except (URLError, TimeoutError,
OSError)` 全映射 CharacterNotFound。附註：沙箱其實抓得到
g0v.github.io/zh-stroke-data；先前「資料中心被擋」誤判來自測錯 URL——
**可達性結論要逐 URL 實測，GitHub Pages 與 Release assets 是兩回事**。

## 決策 4（5es）：bundle 由單一大 JSON 改 gzip JSONL 懶解析（§36）

**觸發**：5er 部署後抄經 503；/api/health 正常（注意：其 version="0.3.0"
是寫死舊值，不能當部署指標——部署簽章改用 W1 的 cache-control header）。

**根因**：單一大 JSON 全量解析 1,830 字實測 **305MB RSS**（序列化 26MB
→ Python 物件 10 倍級膨脹：track/outline 是海量小 dict）。Render free
512MB → OOM → worker 被殺 → 503。**功能過了、記憶體天花板沒驗。**

| 選項 | 說明 | 取捨 |
|---|---|---|
| A | 維持大 JSON、加 swap/升級方案 | 治標、要花錢 |
| B ★ | JSONL：每行 hex<TAB>緊湊 JSON，載入只存字串、每字懶 loads | 常駐 28MB；每字解析 ~ms 由 per-request memoize 吸收 |
| C | 磁碟索引（offset 表）隨用隨讀 | 更省但複雜度不成比例 |

採 B。配套：threading.Lock 防併發首載雙倍瞬時記憶體；**回歸鎖**＝bundle
快取值必須是 str（誰改回預先解析誰紅燈）；prefetch_g0v.py 相容讀舊格式
轉換。線上驗收：503 痊癒（楷書冷 14.2s→暖 3.9s、377KB gzip）。

## 決策 5：Cowork 寫回工作流的防呆（工作流教訓，不入 PRINCIPLES 正文）

三雷：①commit msg 檔名被當日既有序號蓋過（bat 以名稱排序取最後）→
**先列目錄接續序號、用使用者本地日期**（沙箱 UTC 落後一天）②寫回工具會
靜默覆蓋既有檔→高撞名目錄先列再寫 ③給 Windows 指令要標明 shell
（`move /Y` 是 cmd 語法，PowerShell 要 `Move-Item -Force`）。

---

## 驗收與後續

- W1 線上驗收全過（gzip header、抄經復活、Actions node job 綠）。
- W2 待開工首選：`_load`＋篆隸骨架 lru_cache、GET ETag（篆書暖請求 26s
  的直接解）、?v= 版本注入（pyproject 單一事實源）。
