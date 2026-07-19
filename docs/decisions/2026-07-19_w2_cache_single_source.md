# 決策紀錄 2026-07-19（W2）：快取層與單一事實源——5eu／5ev QODA 重放

對應 PRINCIPLES §45（部分）與 WORK_LOG_2026-07-19 第二階段。commits：
`e49594d`（5eu，0.14.228）→ `2bd06a6`（5ev，0.14.229）。線上驗收
PASS：篆書整頁 miss 40.3s → hit 10.8s → 304 0.69s；骨架快取 ≈7×。

---

## 決策 1（5eu）：回應快取用純 ASGI middleware，不用 BaseHTTPMiddleware

| 選項 | 說明 | 定案 |
|---|---|---|
| A ★ 純 ASGI class | 自己攔 scope/receive/send，不匹配路徑原封穿過 | 採 |
| B BaseHTTPMiddleware | 寫起來省事 | 實測出局 |

**出局原因（測試抓包）**：BaseHTTPMiddleware 把**所有**回應轉成無
content-length 的 streaming——外層 GZipMiddleware 的 minimum_size 因此
失效，小回應（如 /api/health）也被壓縮，test_small_response_not_gzipped
紅燈。純 ASGI 版讓不可快取路徑零觸碰。middleware 順序（Starlette 先加
＝最內層）：render-cache（存未壓縮本體）→ GZip → static-cache-headers。

## 決策 2（5eu）：跨層失效走 cache_bus 中立模組，不讓 sources import web

資料異動有兩個入口：HTTP 變更端點（middleware 自己看得到）與測試直呼
reset_*_singleton()。後者若要通知 web 層快取，sources 就得 import web
——違反分層鐵則。解法：零依賴的 `cache_bus`（單調遞增 epoch＋bump），
sources 的 reset 呼叫 bump、web 把 epoch 納入快取鍵——舊條目自然 miss、
LRU 淘汰、不需主動清。刻意無鎖（GIL 下丟失一次遞增只是多一次 miss，
無正確性問題）。

## 決策 3（5eu）：骨架幾何快取存「凍結 tuple」，消費端 deepcopy 基底

Character 是可變 dataclass，直接快取會共享突變。快取值改凍結 tuple
（軌跡），apply_*_outline_mode 每次 deepcopy 基底字再掛快取軌跡——
重算省掉、突變風險歸零。LRU 4096 條。

## 決策 4（5ev）：?v= 版本源＝pyproject 優先、importlib.metadata 後備

沙箱實測：editable install（pip install -e）的 metadata 凍結在安裝
當下——pyproject 已升 0.14.229、metadata 還回 0.14.221。checkout 內
直讀 pyproject 永遠是現值；wheel 部署（無 pyproject 同行）才退
metadata。**vendor pin 白名單**：opencv `4.11.0`／opentype `1.3.4` 是
語意版本，被 app 版本蓋掉會讓使用者每次升版重抓 10MB 級大檔——磁碟
掃描回歸鎖連同白名單一起入庫。

## 決策 5（5ev）：badge 自動化「抄實跑、紅燈拒更」

update_readme_badges.py 只認 pytest --junitxml 實跑報告（tests -
skipped - failures - errors），報告含紅燈直接拒絕更新；版本讀
pyproject。bat 端警告不擋 commit——badge 過期是 docs 債，不該擋住
程式碼收工。首跑冪等驗證：沙箱先寫入後本機回報 already current。

## 附註：健檢構想的實測修正

conftest 上收只遷「純樣板」7 檔（特殊 fixture 照舊本檔覆蓋——pytest
最近者優先），不強制全遷。此判準延續到 W3 的 capacity 修正（見
w3_w4 決策紀錄）：**健檢建議是假說，動手前先量測、不符就修正並記錄**。
