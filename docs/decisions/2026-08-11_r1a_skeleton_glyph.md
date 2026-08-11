# 決策紀錄 2026-08-11（R1a）：骨架長肉字模引擎＋popup 降級階梯

對應 PRINCIPLES §86（降級要「供應」不只「報錯」／替身 getattr 防禦／實證錨點
鎖常數／長壽會話每輪對表）。承 §8（降級誠實）、§66（守門鎖不變式）、§68（紙藝
機構＋字型部署相依）、§69（跨會話寫回三步對表）。commit：`a943ac4`（0.14.282）。
前置文件：`docs/analysis/2026-08-11_fangcun_evaluation.md`（FANGCUN 評估建議書，
R1~R4 選項）。

---

## 整體脈絡

FANGCUN 評估定調「借鏡它的骨架長肉層、不正面做字型工作室」，使用者 sign-off
R1。流程嚴格走「spike 實證→規格→sign-off→動工」：spike 用永/春/歡驗證 A（骨架
buffer）/B（真輪廓 ±δ）兩路線與密度補償，通過後才簽 R1a 規格動工。

---

## 決策 1：長肉走 A 路線（骨架 buffer），B 路線另案

**觸發**：骨架「長肉」有兩條路——A 純參數化（track buffer）；B 真輪廓形態學
縮放（保留書法風味）。

**選項**：A spike 顯示圓體/黑體感、參數自由度全開；B 保留起收筆、但參數範圍
受限（±30 內、密字碗易閉合）。

**選擇**：☑ R1a 用 A；B 驗證可行、明確另案（楷書字模粗細微調）。

**理由**：R1a 的任務是「缺字型時的字模降級供應＋未來參數化玩法」，A 完全
不依賴字型檔（B 仍要真輪廓來源）；spike 已把 A 最大的坑（密筆畫糊黑塊）用
密度補償 `w_eff=w·√(10/(10+n))` 實證解掉（歡 180→101 字碗全開）。

**後續驗證**：✅ 密度補償單調性＋實證錨點（101±2）進守門測試。

## 決策 2：輸出契約＝對齊 `_outline_to_polylines`（下游 drop-in）

**觸發**：新引擎輸出要給 popup（未來 stencil 類）消費。

**選擇**：☑ `glyph_polylines` 回傳 list[list[(x,y)]]、EM2048、Y-down、外環＋
洞環攤平、even-odd 相容——與既有 `_outline_to_polylines` 同形。

**理由**：消費端零改演算法（scanline 填充照舊），降級接線只是「換供應器」；
承 §27 單一事實源精神——契約沿用既有形狀，不發明第二種輪廓格式。

**後續驗證**：✅ popup 降級路徑實渲染（永春/快樂雙層）方向正確、鏤空正確、
連筋後單一件。

## 決策 3：降級要「供應」不是只「報錯」；誠實標注、不無聲頂替

**觸發**：既有行為是缺字型→503。R1a 有了後備字模，要怎麼接？

**選項**：A 維持 503、只在訊息裡提示可裝 shapely／B 自動降級供應＋回應標注
／C 自動降級但不標注（無聲頂替）。

**選擇**：☑ B。階梯：noto_hei → skeleton（回應 `glyph_source`＋`degraded`、
UI 顯示「骨架字模（降級）」）→ 兩者皆缺才 503（原安裝指引語意不變）。

**理由**：§8 降級誠實的升級版——**能供應就供應，標注即誠實**。C 是無聲頂替
（品質不同的字模冒充 Noto）；A 把已能解決的問題留給使用者。附帶：hei 有字型
但缺某字時也走 skeleton 後備（bonus 覆蓋）。

**後續驗證**：✅ 字型缺→200+degraded+components==1；兩者皆缺→503 訊息含
「思源黑體」。

## 決策 4：新回應欄位取值走 getattr 防禦（替身相容）

**觸發**：重做時發現 5ft 測試以 monkeypatch 替身（無 glyph_source 屬性的
假 PopupResult）餵端點——直接 `r.glyph_source` 會 AttributeError。

**選擇**：☑ 端點取值 `getattr(r, "glyph_source", "noto_hei")`。

**理由**：回應層加新欄位時，「消費端測試用替身餵假結果」是既存慣例——新欄位
要向替身相容，否則等於逼所有歷史替身同批擴欄（改動半徑失控）。預設值取
最保守語意（noto_hei＝不標降級）。

## 事故重放：§69 再犯（長壽會話變體）——收工檢查 6 紅攔下

首版 R1a 基於過期雲端基底（c3dc41a，落後 origin 17 commit）動工並寫回，
倒退 5ft~5ge 四檔。**收工檢查全量測試 6 紅全數攔截**、無任何損失（新功能都
在 git HEAD）。復原＝fetch 對齊後重做。教訓：**會話跨多日存活＝等同跨會話，
「每輪動工前」都要 fetch 對表**——上輪結束時對齊過不等於這輪還新鮮。

---

## 沒做的決策（明確擱置）

- **R1b 參數滑桿**（字重/圓角直通 API）——等使用者 sign-off。
- **stencil/zentangle 接線**：stencil 不直接消費 noto_hei；zentangle 是
  使用者自選字源 registry，硬塞後備會改變語意——留待需要再議。
- **R2 GlyphWiki 來源／R3 手寫轉 OTF／B 路線楷書粗細**——建議書選項，另案。

---

## 學到的規則（→ PRINCIPLES §86）

缺資源的端點有了同格式後備供應器，就從「報錯」升級成「降級供應＋誠實標注」；
新回應欄位用 getattr 防替身；演算法常數用實證錨點測試鎖住；長壽會話每輪
動工前重新對表。

---

## 相關檔案

- 引擎：`src/stroke_order/sources/skeleton_glyph.py`
- 接線：`src/stroke_order/exporters/popup.py`（_char_contours／glyph_source）、
  `src/stroke_order/web/routes/pages.py`（+glyph_source/degraded、getattr）、
  `src/stroke_order/web/static/popup.html`（降級註記）
- 相依：`pyproject.toml`（web +shapely>=2.0；v0.14.282）
- 測試：`tests/test_skeleton_glyph.py`（6 測）
- 評估：`docs/analysis/2026-08-11_fangcun_evaluation.md`
- 工作紀錄：`docs/WORK_LOG_2026-08-11.md`；原則：`docs/PRINCIPLES.md` §86
