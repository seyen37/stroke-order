# stroke-order 文件中心

> 中文字元 → 向量筆跡轉換器，目標是餵給寫字機器人。

---

## 🚀 快速開始

| 想做什麼 | 看哪份文件 |
|---|---|
| 安裝 + 啟動本機伺服器 | [QUICK_START.md](QUICK_START.md) |
| 把專案推到自己的 GitHub | [PUSH_TO_GITHUB.md](PUSH_TO_GITHUB.md) |
| 設定 Git SSH / HTTPS 認證 | [GIT_AUTH_SETUP.md](GIT_AUTH_SETUP.md) |
| 多 GitHub 帳號異地備份 | [MULTI_GITHUB_BACKUP.md](MULTI_GITHUB_BACKUP.md) |
| 公開部署到網路上 | [PUBLIC_DEPLOYMENT.md](PUBLIC_DEPLOYMENT.md) |
| 公眾分享庫部署細節 | [GALLERY_DEPLOYMENT.md](GALLERY_DEPLOYMENT.md) |

---

## 📚 設計脈絡 / 開發歷程

| 項目 | 說明 |
|---|---|
| [WORK_LOG_2026-04-26.md](WORK_LOG_2026-04-26.md) | 2026-04-26 工作紀錄（5d/5g 完成總結）|
| [decisions/](decisions/) | 完整決策日誌 — 每個模組的設計取捨、遭遇困難、解法 |
| [decisions/_TEMPLATE.md](decisions/_TEMPLATE.md) | 決策日誌模板 |

### 決策日誌索引（依模組）

#### 模式（Web UI）
- [mode_01: 單字模式 + 核心 IR 設計](decisions/mode_01_single_char_and_ir.md)
- mode_02: 字帖模式（追溯中）
- mode_03: 筆記模式（追溯中）
- mode_04: 信紙模式（追溯中）
- mode_05: 稿紙模式（追溯中）
- mode_06: 塗鴉模式（追溯中）
- mode_07: 文字雲家族（追溯中）
- mode_08: 抄經模式（追溯中）
- mode_09: 筆順練習頁 PSD（追溯中）
- mode_10: 公眾分享庫（追溯中）

#### 基礎建設
- [infra_01: 資料源 chain（多源 fallback）](decisions/infra_01_data_sources.md)
- infra_02: 字型風格（filter vs swap）（追溯中）
- infra_03–07：（追溯中）

#### 已完成的階段日誌
- [2026-04-26: 5d 筆順練習頁 + 5g 公眾分享庫](decisions/2026-04-26_5d_5g.md)

---

## 🛠 技術概覽

- **後端**：Python 3.10+ FastAPI、stdlib SQLite + smtplib（無 ORM、無 PyJWT、零 auth 依賴）
- **前端**：原生 ES modules（無 React / Vue / build step）
- **資料源**：g0v / Make Me a Hanzi / KanjiVG / CNS 全字庫 / 教育部 楷/隸/宋 / 崇羲篆體 / 使用者字典
- **核心 IR**：EM 2048 Y-down 座標系、Character / Stroke / Point 三層 dataclass
- **測試**：1057 條 pytest（涵蓋 Phase 1 → 5g 全模組）

詳細：[README.md](https://github.com/seyen37/stroke-order#readme)

---

## 🌐 線上資源

- 📦 GitHub repo：<https://github.com/seyen37/stroke-order>
- 🚀 線上 demo：（部署中，預計 `https://stroke-order.onrender.com/`）

---

## 📜 授權

- 程式碼：MIT License（詳見 [LICENSE](https://github.com/seyen37/stroke-order/blob/main/LICENSE)）
- 第三方資料源：各保留原始授權，整理見 LICENSE 末段
