# 第三方字型授權全文 / Third-party font licenses

本資料夾集中收錄本專案於部署時抓取（`scripts/render_fetch_fonts.sh`）
的第三方字型之授權全文，方便散布時「授權與字型同行」。字型二進位檔
本身**不進版控**，於 Render 部署時抓取；本資料夾之授權檔則**進版控**、
隨 repo 一起散布。

專案自身程式碼之授權見 repo 根目錄 [`../LICENSE`](../LICENSE)（MIT）；
該檔 B 段亦列有各字型出處與授權摘要。

## 字型 → 授權對照

| 字型檔 | 用途 | 授權 | 全文 | 上游來源 |
|---|---|---|---|---|
| `NotoSansTC-Bold.otf` | 思源黑體 / Noto Sans TC（立體字鏤空字模、黑體字模） | SIL OFL 1.1 | [`SIL-OFL-1.1.txt`](SIL-OFL-1.1.txt) | <https://github.com/notofonts/noto-cjk> |
| `chongxi_seal.otf` | 崇羲篆體（篆體印章） | CC BY-ND 4.0 | [`CC-BY-ND-4.0.txt`](CC-BY-ND-4.0.txt) | <https://github.com/ButTaiwan/chongxi> |
| `TW-Kai-*.ttf` / `TW-Sung-*.ttf` | CNS 11643 全字庫（缺字補字） | 政府資料開放授權 1.0 | [`Taiwan-OGDL-1.0.md`](Taiwan-OGDL-1.0.md) | <https://www.cns11643.gov.tw/> |
| `edukai.ttf` | 教育部標準楷書 | 政府資料開放授權 1.0 | [`Taiwan-OGDL-1.0.md`](Taiwan-OGDL-1.0.md) | <https://language.moe.gov.tw/result.aspx?classify_sn=23> |
| `MoeLI.ttf` | 教育部標準隸書 | 政府資料開放授權 1.0 | [`Taiwan-OGDL-1.0.md`](Taiwan-OGDL-1.0.md) | 同上 |
| `edusong_Unicode.ttf` | 教育部標準宋體 | 政府資料開放授權 1.0 | [`Taiwan-OGDL-1.0.md`](Taiwan-OGDL-1.0.md) | 同上 |

## 重點義務

- **SIL OFL 1.1**（思源黑體）：可商用、可打包、可改作；整套字型不得**單獨販售**，
  散布時須讓上述著作權聲明與 OFL 授權隨字型同行；改作版不得沿用保留字型名
  「Source Han Sans」「Noto」。字型二進位之 name table metadata 已內嵌 OFL，
  本資料夾另備人類可讀全文（雙重保險）。
- **CC BY-ND 4.0**（崇羲篆體）：得標示出處後散布**未修改之原檔**；**不得**散布
  修改後之衍生字型。
- **政府資料開放授權 1.0**（全字庫／教育部字型）：得自由使用、散布、改作，
  須為適當之出處顯名標示；與 CC BY 4.0 相容。權威原文以官方公告為準（見
  `Taiwan-OGDL-1.0.md` 內連結）。

> 註：`Taiwan-OGDL-1.0.md` 收錄授權辨識、出處連結與重點摘要，未收錄改寫後
> 之條款正文，以官方公告為準（政府標準格式條款，逐字原文不宜由第三方轉錄）。
