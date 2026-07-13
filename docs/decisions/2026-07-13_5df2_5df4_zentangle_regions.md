# 決策紀錄 2026-07-13（第三弧）：5df-2→5df-4 禪繞區段模型與互動編輯

對應 PRINCIPLES §13。0.14.174 → 0.14.177，pytest 1676 不動、
node 30 → 125。QODA A 案延伸實作；方向鍵撞鍵位一項回頭請使用者
定案（情境切換）。

## D1. 區段模型＝band 矩形起家、poly 選配升級（5df-2/5df-4）

region = {id, kind: glyph|bg, band, poly?, tangle, orientation}。
起家用純矩形 band（圖樣生成器天然吃矩形 area）；5df-4 自訂切分
需要不規則形狀時，poly 以**選配欄位**疊加——「生成吃 bbox、
裁剪吃真形」：band 同步為 poly 的 bbox、圖樣生成照舊、渲染 clip
換 poly。八個 tangle builder 與 buildTangleOriented 全程零改動。
不規則形狀的成本被封在渲染與命中兩個消費點，生成層不知情。

## D2. 雙重 clip＝組合既有語意，不寫新幾何（5df-2）

glyph 區段＝clip(字形 path, evenodd) ∩ clip(區段形狀)；bg 區段
＝clip(區段形狀) ∩ clip(大矩形＋字形, evenodd)。孔洞語意自動
正確：「日」的內孔在 glyph 模式被 evenodd 排除、在 bg 模式算
背景——不用寫任何「孔洞特判」。canvas 的巢狀 clip 就是交集，
兩個既有語意疊起來就是新功能。

## D3. 鐵則要追溯掃全體，消費情境變窄＝舊蟲現形（5df-2）

5df-1 的「迴圈邊界含最大外伸」鐵則只約束了六個新圖樣；5df-2
區段窄帶（120px 級 vs 全磚 600px）一來，6z-3 時代與 5df-1 漏掃
的**五個舊 builder 全數越界**（crescent_moon dot、florz 花瓣、
tipple jitter、bales 格角、flux 葉端）。全磚時代格步殘量大、蟲
藏得住；帶一窄就露餡。教訓：新守則入庫時要回掃既有全體，「只
管新增碼」的鐵則是半條鐵則。界內測試慣例同步明文化：錨點級
（端點與中心），半徑外伸不在斷言內。

## D4. 命中判斷＝與渲染同語意的純幾何重刻（5df-3）

選取需要「點在字形內嗎」。捷徑是 ctx.isPointInPath（DOM、canvas
綁定、node 測不到）；正解是 pointInGlyph（evenodd 跨 contour 計
數）＋ resolveRegionAt（glyph 要求字形內、bg 要求字形外）——
與渲染端 clip 的 evenodd **同一套語意、兩個消費者**，行為天然
一致，且 30 項 node 測試全蓋得到。依賴執行環境 API 換來的省事，
會在可測性上加倍還回去。

## D5. 同一輸入多語意＝明確模式狀態，入口互清（5df-3/5df-4）

方向鍵（區段朝向 vs 6z-5a 透視）與 canvas 點擊（選區段 vs 兩點
切分 vs 手放 unit）都是一鍵多義。定案＝情境切換：以明確狀態
（_selectedRegionId、_splitMode、config.mode）分流，且**每個
模式入口清掉另一模式的中間狀態**（開切分清選取、重抽清切分
定錨）——兩套語意永不同時活著，使用者不用猜現在按鍵歸誰。
撞鍵位這類決策在前一輪收工時就預先標出，下輪開工使用者一句話
定案，零返工。

## D6. 分裂物件 id＝父後綴，不設全域計數器（5df-4）

切分後兩半 id＝父 id＋a/b（r2 → r2a/r2b）。父 id 移出清單＋
後綴可巢狀（r2aa…）＝天然唯一、可多代、免計數器狀態、id 本身
就是族譜（除錯時一眼看出切分史）。

## D7. UI 清單從 registry 動態生成（5df-3）

5df-1 靜態 HTML 的 tangle radio 只列 3 個、新六圖樣缺席——
§8.3 型漂移的 UI 版。5df-3 圖樣鈕列改為 buildRegionToolbar()
從 listTangles() 動態生成，HTML 只留空容器：新圖樣入 registry
即現身，杜絕「registry 改了、UI 忘了」這一整類蟲。
