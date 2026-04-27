# Phase 5bb 抄經自訂功能

## 目錄結構

```
~/.stroke-order/sutras/
├── builtin/                 ← 程式內建（佛教 4 部）
│   ├── heart_sutra.txt
│   ├── diamond_sutra.txt
│   ├── great_compassion.txt
│   └── manjushri_mantra.txt
└── user/                    ← 使用者自訂
    ├── <key>.txt            純文字
    └── <key>.json           metadata
```

## 範例 metadata json

```json
{
  "title": "千字文",
  "subtitle": "手抄本",
  "category": "classical",
  "source": "周興嗣",
  "description": "南朝梁周興嗣編，用一千個不重複漢字寫成的韻文",
  "language": "zh-TW",
  "is_mantra_repeat": false,
  "repeat_count": 1,
  "tags": ["經典", "蒙學"]
}
```

## 6 個分類 category key

| key | 中文標籤 |
|---|---|
| `buddhist`     | 佛教 |
| `taoist`       | 道家 |
| `confucian`    | 儒家 |
| `classical`    | 文學經典 |
| `christian`    | 基督宗教 |
| `user_custom`  | 自訂 |

## 兩種上傳方式

1. **手動放檔**：把 `.txt` (+ 同名 `.json`) 放進 `user/`，重整網頁
2. **網頁 UI**：抄經模式按「✎ 經文管理」浮層上傳

## 重複型咒語

設 `is_mantra_repeat: true` 跟 `repeat_count: 108`，程式會自動把單一循環重複 N 次（同文殊心咒邏輯）。
