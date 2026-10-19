# ADR — P0 公開站關閉共用字庫（user_dict）寫入

- 日期：2026-10-19
- 版本：0.14.296 → **0.14.297**
- 狀態：已實作
- 相關：Blueprint v1.2 個人化線（Phase 2 第 7 項提前）、ADR
  `2026-08-20_r3_hand_font.md`（R3）、5ak（user_dict）、5ew-R3（練習頁同步）

## 脈絡

為「寫你的名字→得到字型」寫規格時盤點 R3 的資料來源，發現：

- user_dict 存在伺服器**單一**資料夾（正式站 `/opt/render/.stroke-order/user-dict`），
  全站共用；寫入端點 `POST /api/user-dict`、`/import`、`DELETE` **免登入**。
- `AutoSource` 第一順位就是 user_dict——自訂字覆蓋所有內建字源。
- 筆順練習頁存檔時**預設同步**進這份字庫（5ew-R3）。

本機單人使用時這是特性；公開網站上就是「任何訪客寫一個字，在主機下次
休眠前，所有老師印出的字帖都換成那份筆跡」。10-19 線上查詢 `count: 0`
——尚無實害，但路是開的。

## 決策（QODA，使用者 sign-off「A」，與 P1/P2 同案）

- 新環境變數 `STROKE_ORDER_USER_DICT_WRITABLE`；值為 false/0/no/off/n/f
  （不分大小寫、容空白）時三個寫入端點回 **403＋同一句說明**
  （`USER_DICT_READONLY_DETAIL`：講清楚「為什麼」與「練習紀錄仍在你的
  瀏覽器」）。**沒設＝可寫**：本機行為零變。
- 讀取端點照常，`GET /api/user-dict` 多 `writable` 欄位供前端判斷。字庫
  保持空，各模式自然落到教育部／g0v 字源。
- `render.yaml` 設 `"false"`。
- 前端：練習頁開頁讀 `writable`，唯讀時取消並停用「同步到渲染字庫」
  （不覆寫使用者記憶的偏好）、標「（本站不保存）」——免得每完成一字跳
  一次警告；罕用字面板說明唯讀；兩處原本吞錯的路徑（刪除、逐字手寫匯入）
  改為帶出伺服器說明。

不採：登入後才可寫（仍是共用字庫，只是縮小可破壞的人群）；每訪客一個
資料夾（休眠即消失、伺服器保存他人筆跡）。個人手寫的正解是 P1/P2：
筆跡留在瀏覽器、伺服器無狀態產字型。

## 驗證

- `tests/test_user_dict_readonly.py` 12 項：預設可寫、六種 false 寫法、
  三端點皆 403 且狀態不變、唯讀時讀取與匯出正常、說明措辭鎖、render.yaml
  鎖、前端三處行為鎖。既有 user_dict／handfont 測試 58 項同跑全綠。
- Playwright：唯讀設定下 /handwriting 勾選框 checked=false、disabled=true、
  標籤附「（本站不保存）」，無 pageerror。
