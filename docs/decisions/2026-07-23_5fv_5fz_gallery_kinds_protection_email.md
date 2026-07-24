# 決策紀錄：公眾分享庫大擴建 5fv~5fz（2026-07-23，QODA 重放）

對應 PRINCIPLES §75–§80。版本 0.14.271→0.14.275；tests 1870→1976。
工作日誌：`WORK_LOG_2026-07-23.md` 第三場。

---

## D1. 分類驗證：A 通用 SVG vs B 檔案內嵌憑據——使用者選 B，choke point 翻案成本

**Question**：分享庫要依主頁模式擴分類，匯出 SVG 當時都沒有內嵌 metadata。

**Options**：A＝通用 SVG 驗證＋分類自選（一輪上線、舊檔相容；放錯類靠檢舉
補）；B＝逐模式內嵌憑據嚴驗出處（放錯類不可能；估 3 輪＋舊檔全拒收）。

**Decision**：我推薦 A，使用者兩度追問差異與利弊後**明選 B**——優先值是
「分類絕對乾淨」，知悉舊檔不相容代價。尊重定案。

**成本翻案（重要）**：B 的「3 輪」估計基於「逐模式改匯出」；開工盤點發現
`svg_response`（W3 重構收斂的全站唯一 SVG 出口）＋
`render_pages_as_single_or_zip`（文字群共用多頁出口）兩個 choke point——
在兩點內嵌＋呼叫點標 mode，11 模式一輪接完。**估工前先盤 choke point**；
前人「散寫收斂單點」的重構投資在此兌現。→ §75。

---

## D2. 信封格式：per-mode schema vs 一套通用信封

**Decision**：一套 `stroke-order-export-v1` 蓋全模式（`mode` 欄聲明分類）——
單一 embed helper、單一驗證器；新模式加入＝呼叫點標一個字串。mandala/popup
既有 schema 不動（相容）。設計要點：冪等、決定性輸出（無時間戳→同輸入位元
相同、dedup 友善）、CDATA `]]>` 轉義防注入。

---

## D3. 檢舉身分：僅登入 vs 匿名＋登入

**Decision**（使用者 sign-off）：匿名＋登入都可——路過訪客不必註冊即可檢舉
不當內容，發現得快；匿名件以**加鹽 HMAC IP 雜湊**去重（不存明文 IP），
登入件以帳號去重；門檻 3 個獨立來源自動隱藏；每來源每日上限 10。
去重用**部分唯一索引**（登入件 (upload,user)、匿名件 (upload,ip_hash)）——
資料庫層守恆，不靠應用層檢查。

---

## D4. 防機器人：外接服務 vs 三層自製

**Options**：Cloudflare Turnstile（體驗好但要申請金鑰、多外部依賴）／僅蜜罐
＋頻率限制（零打擾但擋不住像樣的機器人）／三層自製。

**Decision**（使用者 sign-off）：**三層自製零外部依賴**——①隱形蜜罐欄位
（真人看不到，有值即拒）②伺服器簽章挑戰 token 內含發題時間（<3 秒送出拒
「太快」＝機器人特徵；>10 分鐘過期）③算術題（伺服器以「使用者送來的答案」
重算 HMAC 簽章——答錯簽章必不合，無需伺服器端存題）。無狀態、離線可測。→ §77。

---

## D5. 管理員身分：DB 欄位 vs 環境變數

**Decision**（使用者 sign-off）：`GALLERY_ADMIN_EMAILS` 環境變數（逗號分隔、
lower/strip 比對）——沿用既有魔法連結登入，email 在名單即見管理控制。
零新認證系統、零 DB 欄位；免費層不便進 DB 手動標記。

---

## D6. XSS 與黑名單：消毒/遮罩 vs 拒收

**Decision**：兩者皆**拒收不改寫**。SVG 危險構件（script/foreignObject/
iframe/embed/object/image/use/style/on*=/javascript:/href/外部 url(）——本站
匯出器從不產生這些，拒收零誤傷、錯誤訊息直接引導重新匯出；`url(#` 內部參照
放行（布章 clip-path 合法）。文字黑名單命中回 422「內容含不當字詞」**不回顯
命中詞**（防逐字試探詞庫邊界）、不自動遮罩（避免內容被偷改）。黑名單掛
`_safe_unicode_str` 單一 sanitize 入口——一處蓋標題/評論/暱稱/簡介/檢舉說明。

---

## D7. 首次上傳審閱期：cron 排程 vs 查詢時懶釋放

**Question**：「24 小時後自動公開」誰來觸發？Render 免費層無排程器。

**Decision**：**懶釋放**——list/get 查詢入口順手一發 UPDATE（帳號首件已滿
24h → 其 first-upload-review 隱藏全部公開）；無匹配時近零成本、免 cron、
自癒。配套：本人看得到自己的隱藏件（列表 WHERE 放行 own＋卡片標章依原因給
標籤）；上傳成功訊息明示預計公開時間。

**優先序（§78）**：人工審閱（管理員勾選 review）＞ 24h 自動窗；懶釋放**只碰
first-upload-review**，pending-review／admin-takedown／community-reports／
author-blacklisted 一概不動；解除黑名單也只復原「因黑名單隱藏」的作品——
每個自動機制只回收自己造成的狀態。

---

## D8. 行為變更的測試遷移：逐測試 hack vs 視角 fixture

**Question**：「首件自動隱藏」改變「上傳即公開」的既有行為，8 個既有測試紅。

**Decision**：conftest 共用 `established_authors` fixture（monkeypatch 關閉
首件窗）＝讓既有測試以「老帳號（首件已滿 24h）」**視角**驗公開行為原契約；
新行為由專測檔（27 測）獨立覆蓋。比逐測試 backdate/改斷言乾淨，且 fixture
名字就說明了測試前提。→ §79。附註：email 測試用 `asyncio.run`（每測試全新
event loop），避免整批共跑時共用 loop 的 closed/no-current-loop 陷阱。

---

## D9. 寄信通道：SMTP 事故查證＋Brevo vs Resend 選型

**事故**：Gmail SMTP 設定正確仍 `Errno 101 Network is unreachable`。
**查證先於重試**：web search 到 Render 官方 changelog「免費 Web 服務封鎖所有
對外 SMTP 埠」——平台政策，換帳號無效；唯一通道＝走 443 的 HTTP 郵件 API。
→ §80。

**選型**（使用者 sign-off Brevo）：Brevo 免費 300 封/日、**驗證單一寄件人
email 即可寄任意收件人、不需自有網域**——本站掛 onrender.com 下沒有網域，
Resend（寄任意收件人需驗證自有網域）不合用。實作 stdlib urllib 零新依賴；
三模式優先序 dev mode＞Brevo＞SMTP fallback，SMTP 留給自架環境。

---

## D10. Brevo 401 IP 白名單：停用 vs 加網段

**第二關**：Brevo 回 401 unrecognised IP——使用者帳號開著「授權 IP 白名單」。
新版錯誤訊息把 Brevo 回應原文帶出（含指引連結），**畫面上一眼定位病因**——
「錯誤訊息寫明可辨病因」的投資當場回本（對照第一關的裸 traceback 需要查證
半天）。

**Decision**：使用者已把 Render 兩段**共用**出口網段（74.220.52.0/24、
74.220.60.0/24）加入授權清單——維持現狀即可。附註取捨：共用 /24 網段入白
名單後，白名單的實質保護已薄（同網段還有別人的服務），「整個停用、由 API
key 承擔」同樣合理；但既已設好且多一層總比零層好，不再折騰。

---

## 附：本弧兩條 live bug 的共同教訓（§76）

1. **route 層硬編白名單＝擴充死角**：列表 kind 參數
   `pattern="^(psd|mandala)$"` 讓 5ft popup 與 5fw 12 分類全 422——白名單
   該下沉 service 的 `ALLOWED_KINDS` 單一事實源，route 不重複持有清單。
   （同型：5ft popup 沒進 hash.mjs 白名單，深連結被靜默丟棄——前端同病。）
2. **E2E 要驗到「回應成功」不只「請求發出」**：5fw 的 E2E 驗了「選分類→
   發出帶 kind= 的請求」就放行，沒驗回應 200——422 就這樣穿過驗收上線，
   直到 5fx 實測才現形。斷言鏈的終點必須是使用者可感知的結果。
