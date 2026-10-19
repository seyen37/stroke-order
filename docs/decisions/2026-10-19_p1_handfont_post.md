# ADR — P1 無狀態手寫字型 `POST /api/handfont`

- 日期：2026-10-19
- 版本：0.14.297 → **0.14.298**
- 狀態：已實作
- 相關：ADR `2026-10-19_p0_user_dict_readonly.md`（P0，同案 QODA A）、
  `2026-08-20_r3_hand_font.md`（R3 引擎）、5ck（重端點 sync def）、
  5ex-B（渲染閘門）

## 脈絡

P0 關了公開站共用字庫寫入，`GET /api/user-dict/font` 在正式站因此永遠
是 400（字庫空）。個人化線「寫你的名字→得到字型」需要一條不經共用
字庫的路：筆跡留在使用者瀏覽器（練習紀錄 IndexedDB 已有），要字型時
連同筆跡一起送來，伺服器算完即丟。

## 決策

1. **介面**：`POST /api/handfont`，body
   `{"chars": {字: [[[x,y],...], ...]}, "weight": 120, "cap": "round", "owner": ""}`，
   座標 EM 2048（與練習頁 trace、user_dict 同座標系，前端不必換算）。
   回 `font/ttf`、`Content-Disposition` 附件、`X-Hand-Font-Chars`、
   `Cache-Control: no-store`。
2. **零落地**：不碰 UserDictSource 存檔、不寫任何檔案（測試以
   save_character 替身＋目錄比對鎖住）。與存檔路徑共用新抽出的
   `character_from_strokes` seam（`_load_from_file` 改走它，零行為變），
   測試鎖「同筆跡兩條路徑字形座標逐點相同」。
3. **上限依量測**：沙箱實測 100 字 6.1s／200 字 12.2s、RSS +60MB；Render
   免費層 CPU 慢數倍 → **100 字**；每字 ≤64 筆、每筆 ≤2000 點、總點數
   ≤200k、body ≤6MB（Content-Length 預檢）。名字 2～6 字約 1～2 秒。
4. **輸入驗證**：鍵須為單一非空白非控制字元；座標須為有限數且在
   [-1024, 3072]（容許手寫出格、擋荒謬值）；單點輕觸丟棄、整字無有效
   筆畫回 422 並點名哪個字。錯誤訊息皆中文說原因。
5. **掛點**：sync def（threadpool）；`/api/handfont` 加入
   `RENDER_CACHE_PREFIXES`——非 GET 只進閘門（同時 ≤2）不入快取；計數
   bucket 併入既有 `handfont`（個人化線 gate 讀的就是它）。

## 驗證

- `tests/test_handfont_post.py` 23 項：fontTools 回讀（cmap 只含送來的字、
  全形等寬、著作權具名）、FreeType 真渲染（字碗留白）、兩路徑字形相同、
  零落地、公開站唯讀下照常可用、七類非法輸入、四類上限、參數驗證、
  閘門與計數、sync def 鎖。route snapshot +1。
- 真 uvicorn：POST 十口 → 200 font/ttf 1.6KB 0.25s、`handfont: 1`、
  未建立任何字庫目錄；字型以 PIL 畫出目視正確。
