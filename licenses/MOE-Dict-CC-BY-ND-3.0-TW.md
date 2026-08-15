# 教育部《國語辭典簡編本》開放資料（CC BY-ND 3.0 臺灣）

適用於本專案隨版控散布的字義資料：

- **`data/moe_dict_bundle.jsonl.gz`** — 由 `scripts/build_moe_dict.py` 從教育部
  公眾授權網下載的 `dict_concised_2014_*.xlsx` 轉出（單字 6,028、常用詞
  22,195；含注音一式、部首字、總筆畫數、釋義原文與其中的 `[例]` 例句）。

## 授權

**創用CC-姓名標示-禁止改作 3.0 臺灣**
（Creative Commons Attribution-NoDerivatives 3.0 Taiwan）。

- 授權說明（權威原文以官方公告為準）：
  <https://language.moe.gov.tw/001/Upload/Files/site_content/M0001/respub/index.html>
- 資料下載頁：
  <https://language.moe.gov.tw/001/Upload/Files/site_content/M0001/respub/dict_concised_download.html>
- 授權條款全文：<https://creativecommons.org/licenses/by-nd/3.0/tw/legalcode>

得重製、散布、公開傳輸（**包括商業性利用**），惟須姓名標示且**不得修改**該著作。

## 本專案的遵循方式

1. **內容逐字保留、不改作**：`build_moe_dict.py` 僅做技術上必要的載體轉換
   （xlsx → JSONL、還原 xlsx 的 `_x000D_` 換行編碼假影）與**節錄**
   （取單字條目與每字前 12 個常用詞）；**任何一條釋義的文字都未經改寫、
   摘要或截斷**。`sources/moe_dict.py` 原文取出、原文回傳。
2. **姓名標示**：`/api/dict/{char}` 回應帶 `attribution`／`license`／
   `source_url`；識字教學頁（`/teach`）於頁面與下載的教學單檔頁尾標示出處。
3. **使用者若編輯內容**：教學頁的字義／造詞欄位可由教師修改（教學需要）；
   下載檔頁尾註明「若經教師修改則非原文」，避免把修改後的文字冒稱教育部原文。

## 未納入的資料

同一授權頁另提供插圖檔與讀音聲音檔（單字讀音 zip 約 1.5 GB、詞目全文聲音檔
分五part）。因體積不適合隨 repo 散布，本專案**未納入**；教學頁的發音改用
瀏覽器內建語音合成（`speechSynthesis`，非教育部錄音）。
