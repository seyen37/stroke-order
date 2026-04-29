# 2026-04-29：§七 公開前審查 retrospective audit

> 範圍：morning audit 發現 repo 自 2026-04-27 公開後從沒正式跑過 §七「公開前審查清單」。本文補做。
>
> 起點：repo public 第 3 天，已累積 7+ commits 但沒有系統性 secret / 個資 / 授權 audit
> 終點：§七.1 ~ §七.4 全部通過 ✅

---

## §七.1 Secret 稽核 — ✅

**檢查**：grep `password|api_key|API_KEY|secret_key|SECRET_KEY|private_key|access_token|credentials|bearer`

**Findings**：

| 位置 | 內容 | 狀態 |
|---|---|---|
| `src/stroke_order/gallery/smtp.py:37` | `"password": os.environ.get("STROKE_ORDER_SMTP_PASS", "")` | ✅ 從 env var 讀，非 hardcoded |
| `gallery/{auth,gallery,uploader}.js` 多處 | `credentials: 'same-origin'` | ✅ fetch API option，非 secret |
| `.gitignore:44` | `# NEVER commit these — they contain SMTP credentials` | ✅ ignore 規則，鼓勵性質 |
| 全 codebase | base64 long strings | ✅ 唯一 false positive 是 GitHub raw URL |

**結論**：沒任何 hardcoded secrets。所有敏感配置都透過環境變數。

**雙保險**：[`render.yaml`](../../render.yaml) 用 `generateValue: true` 讓 Render 動態產生 `STROKE_ORDER_AUTH_SECRET`（32-byte random），永不 commit 進 repo。

---

## §七.2 個資稽核 — ✅

**檢查**：grep 台灣手機號 / email / 信用卡 / 第三人姓名 patterns

**Findings**：

| 類型 | 結果 |
|---|---|
| 台灣手機號（09xx-xxx-xxx）| 0 個 ✅ |
| Email（除 noreply / example）| 1 個 `Alice@Example.COM`（測試用例）✅ |
| 信用卡 / 銀行帳號 16 位 | 0 個 ✅ |
| 個人地址（路 / 號 / 區 / 巷 / 郵遞區號）| 0 個 ✅ |

**作者本人 email**：刻意不在 codebase 內留 `seyen37@gmail.com` 字串，README + LICENSE 用 GitHub URL 替代。**這是 PROJECT_PLAYBOOK §二「IP 三件套」的副作用——三處身份鏈不留 email**。

**結論**：個資稽核乾淨。Test fixture 用的 fake email（`Alice@Example.COM`、`noreply@example.com`）符合慣例。

---

## §七.3 授權稽核 — ✅

**檢查**：LICENSE 存在 + 第三方資料 attribution + 商業條款明確

**Findings**：

主授權：**MIT License** ✅

第三方資料 attribution（在 LICENSE 末段）：
- ✅ Make Me a Hanzi — LGPL 3.0
- ✅ KanjiVG — CC BY-SA 3.0
- ✅ 全字庫 (CNS 11643) — Taiwan Government Open Data License 1.0
- ✅ 崇羲篆體 — CC BY-ND by 季旭昇 + Institute of Information Science
- ✅ cjkvi-ids（透過 KanjiVG attribution 涵蓋，因為衍生自 KanjiVG schema）

**還沒寫進 LICENSE attribution 的新資料源**：
- ⚠️ TCS 808（公共領域，無需 attribution，但建議補）
- ⚠️ 教育部 4808（民國 71 年公告，公共領域，建議補）
- ⚠️ 教育部本土語言 6792（民國 113 年公告，建議補）
- ⚠️ MOE 國小學童 5021（民國 91 年公告，公共領域，建議補）
- ⚠️ 朱邦復漢字基因 5000（2012 公開，建議補 attribution）

**結論**：核心通過（MIT + 4 個第三方 attribution）。**5 個 cover-set 來源建議下次補進 LICENSE 末段**——加進 TODO。

---

## §七.4 文件稽核 — ✅

**檢查**：README 是否能讓陌生人 30 秒理解 + 安裝指令可重現 + decisions 至少一份

**Findings**：

- ✅ README 第一段「不只是筆順工具——世界上第一個整合『**真實手寫軌跡 × 組件化字型 × 個人風格生成**』的開源系統」——清楚的 elevator pitch
- ✅ README 「🔗 線上資源」block 給陌生人 1 個 click 看 demo + 1 個 click 看完整 VISION
- ✅ 安裝指令可重現（`pip install -e .` / `pip install -e ".[web]"` 等三層）
- ✅ docs/decisions/ 有 9 份 decision logs（含 _TEMPLATE.md）

**結論**：文件層級完整，新讀者 friendly。

---

## 結論：§七 全四項通過 ✅

stroke-order 在 public 第 3 天通過完整 §七 audit。**沒發現需要立即修復的 leak / risk**。

唯一輕量 follow-up：把 5 個 cover-set 的資料來源 attribution 補進 LICENSE 末段——納入下次 release（v0.15.0 或 v0.14.1）的 patch。

---

## 教訓

**做得好的**：
- repo 公開前的隱性 secret scan（2026-04-27）+ 後續系統性 retrospective（本文）形成雙保險
- IP 三件套副作用（不留 email）讓 §七.2 個資稽核自動通過
- LICENSE 末段第三方 attribution block 是好習慣，未來新資料源加入時延伸即可

**Process 建立**：

> SOP 寫好後對既有 public repo 做一次 retrospective audit，是「**對自己的 SOP 執行誠實度測試**」。
> 即使結論是 ✅，這個測試本身的「跑過」就是對 SOP 的尊重。

---

## TODO（不阻塞，下次有空時補）

- [ ] LICENSE 末段補 5 個 cover-set 的資料來源 attribution（TCS 808 / MOE 4808 / MOE 5021 / MOE 6792 / 朱邦復 5000）
- [ ] 評估是否要在 PROJECT_PLAYBOOK §七 加「7.5 第三方資料源 attribution 完整性」當第五個必跑項
