# 第三方資產授權全文 / Third-party asset licenses

本資料夾集中收錄本專案散布之第三方資產授權全文，方便「授權與資產同行」：

- **字型**：於部署時抓取（`scripts/render_fetch_fonts.sh`），二進位檔本身
  **不進版控**；本資料夾之授權檔進版控、隨 repo 散布。
- **資料**：教育部辭典資料（`data/moe_dict_bundle.jsonl.gz`）**隨 repo 進版控**，
  其授權與遵循方式見下方資料對照表。

專案自身程式碼之授權見 repo 根目錄 [`../LICENSE`](../LICENSE)（MIT）；
該檔 A 段列資料來源、B 段列各字型出處與授權摘要。

## 字型 → 授權對照

| 字型檔 | 用途 | 授權 | 全文 | 上游來源 |
|---|---|---|---|---|
| `NotoSansTC-Bold.otf` | 思源黑體 / Noto Sans TC（立體字鏤空字模、黑體字模） | SIL OFL 1.1 | [`SIL-OFL-1.1.txt`](SIL-OFL-1.1.txt) | <https://github.com/notofonts/noto-cjk> |
| `ChironGoRoundTC-700B.otf` | 昭源環方 / Chiron GoRound TC（圓體字模風格） | SIL OFL 1.1 | [`SIL-OFL-1.1.txt`](SIL-OFL-1.1.txt) | <https://github.com/chiron-fonts/chiron-go-round-tc> |
| `ChironGoRoundTCVF.otf` | 昭源環方可變字體（R1b 字重滑桿，wght 200–900） | SIL OFL 1.1 | [`SIL-OFL-1.1.txt`](SIL-OFL-1.1.txt) | 同上 |
| `chongxi_seal.otf` | 崇羲篆體（篆體印章） | CC BY-ND 4.0 | [`CC-BY-ND-4.0.txt`](CC-BY-ND-4.0.txt) | <https://github.com/ButTaiwan/chongxi> |
| `TW-Kai-*.ttf` / `TW-Sung-*.ttf` | CNS 11643 全字庫（缺字補字） | 政府資料開放授權 1.0 | [`Taiwan-OGDL-1.0.md`](Taiwan-OGDL-1.0.md) | <https://www.cns11643.gov.tw/> |
| `edukai.ttf` | 教育部標準楷書 | 政府資料開放授權 1.0 | [`Taiwan-OGDL-1.0.md`](Taiwan-OGDL-1.0.md) | <https://language.moe.gov.tw/result.aspx?classify_sn=23> |
| `MoeLI.ttf` | 教育部標準隸書 | 政府資料開放授權 1.0 | [`Taiwan-OGDL-1.0.md`](Taiwan-OGDL-1.0.md) | 同上 |
| `edusong_Unicode.ttf` | 教育部標準宋體 | 政府資料開放授權 1.0 | [`Taiwan-OGDL-1.0.md`](Taiwan-OGDL-1.0.md) | 同上 |

## 資料 → 授權對照（隨 repo 散布）

| 資料檔 | 用途 | 授權 | 說明 | 上游來源 |
|---|---|---|---|---|
| `data/moe_dict_bundle.jsonl.gz` | 教育部《國語辭典簡編本》——識字教學頁（/teach）的注音／部首／字義／常用詞例句 | CC BY-ND 3.0 臺灣 | [`MOE-Dict-CC-BY-ND-3.0-TW.md`](MOE-Dict-CC-BY-ND-3.0-TW.md) | <https://language.moe.gov.tw/001/Upload/Files/site_content/M0001/respub/index.html> |

## 重點義務

- **SIL OFL 1.1**（思源黑體、昭源環方）：可商用、可打包、可改作；整套字型不得
  **單獨販售**，散布時須讓上述著作權聲明與 OFL 授權隨字型同行；改作版不得沿用
  保留字型名「Source Han Sans」「Noto」（昭源環方之 OFL 未宣告保留字型名）。字型二進位之 name table
  metadata 已內嵌 OFL，本資料夾另備人類可讀全文（雙重保險）。
  兩者皆由 `render_fetch_fonts.sh` 從**上游 repo** 直取（非本專案 release），
  故散布的是未經本專案改動的原檔。
- **CC BY-ND 4.0**（崇羲篆體）：得標示出處後散布**未修改之原檔**；**不得**散布
  修改後之衍生字型。
- **政府資料開放授權 1.0**（全字庫／教育部字型）：得自由使用、散布、改作，
  須為適當之出處顯名標示；與 CC BY 4.0 相容。權威原文以官方公告為準（見
  `Taiwan-OGDL-1.0.md` 內連結）。

> 註：`Taiwan-OGDL-1.0.md` 收錄授權辨識、出處連結與重點摘要，未收錄改寫後
> 之條款正文，以官方公告為準（政府標準格式條款，逐字原文不宜由第三方轉錄）。
