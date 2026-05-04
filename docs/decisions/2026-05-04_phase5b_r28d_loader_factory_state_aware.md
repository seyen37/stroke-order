# Phase 5b r28d：Mandala MD Thumbnail Loader 從 State 動態構造

**日期**：2026-05-04
**版本**：0.14.109 → 0.14.110
**範圍**：r28c 補完 — char_loader 用 state.style 字段動態構造
**測試**：`tests/test_gallery_mandala.py` +3 → 33（30 → 33）

---

## 1. 動機

r28c 解決 mandala MD upload 的 thumbnail 生成，但 known limitation：
- API endpoint 用 server default 構造 loader（`build_mandala_char_loader()` 無參數 → kaishu / auto / skip）
- State 中 `style.font = lishu` / `seal_script` 時，thumbnail 字體仍 render 為 kaishu，跟 user 在 mandala 模式看到的不同

r28d 修這個限制：API 從 state 讀 `style.font` / `style.source` / `style.cns_outline_mode`，build state-aware loader。

## 2. 設計核心：Factory 模式取代靜態 loader

### 2.1 為什麼不能用 r28c 的 `char_loader` 直接傳 state-aware loader

API endpoint 在 `create_upload` **開始之前**沒有 state（state 由 `VALIDATORS[kind](content_bytes)` 在 `create_upload` 內部 parse 出來）。要 state-aware loader，要嘛：

- (A) API 層先 parse state 一次，再 call create_upload（會 parse 兩次）
- (B) 用 factory 模式：API 給 `char_loader_factory(state) → loader`，create_upload 內部 parse state 後 call factory

(B) 乾淨：state 只 parse 一次，API 不需要知道 parse 細節。

### 2.2 保留 char_loader 為靜態 fallback

API 主要 path 用 factory；但 r28c 的 `char_loader=` 參數保留供：

- Tests（直接傳 stub loader 不關心 state）
- 任何 caller 想用「不依 state」固定 loader

優先：`char_loader_factory(state)` > `char_loader`。Factory 拋例外時 fall back 到 static `char_loader`（graceful）。

## 3. 實作

### 3.1 `gallery/service.py`

```python
def create_upload(
    *, user_id, content_bytes, filename, title, comment, kind=KIND_PSD,
    char_loader=None,
    char_loader_factory=None,
) -> dict:
    ...
    state, ext = VALIDATORS[kind](content_bytes)
    summary = SUMMARIZERS[kind](state)
    ...
    
    # Resolve loader: factory(state) > static char_loader > None
    loader_for_thumbnail = char_loader
    if char_loader_factory is not None:
        try:
            loader_for_thumbnail = char_loader_factory(state)
        except Exception as e:
            logging.warning("factory failed: %s, fall back to static", e)
    
    _maybe_generate_thumbnail(
        ..., char_loader=loader_for_thumbnail,
    )
```

### 3.2 `web/server.py` API endpoint

```python
upload_loader_factory = None
if kind == "mandala":
    def upload_loader_factory(state):
        s = (state.get("style") or {}) if isinstance(state, dict) else {}
        return build_mandala_char_loader(
            style=str(s.get("font", "kaishu")),
            source=str(s.get("source", "auto")),
            cns_outline_mode=str(s.get("cns_outline_mode", "skip")),
        )

create_upload(..., char_loader_factory=upload_loader_factory)
```

State 缺 `style` section / 缺欄位 → fall back 到 server default（kaishu / auto / skip）。

## 4. 測試 +3

| Test | 驗證 |
|---|---|
| `test_thumbnail_md_uses_loader_factory_with_state` | factory 被 call、收到正確 state（fixture style.font=kaishu）、生成 thumbnail |
| `test_loader_factory_takes_priority_over_static` | 同時傳 factory + char_loader 時 factory 優先 |
| `test_loader_factory_exception_falls_back_to_static` | factory 拋例外時 fall back 到 static loader（graceful，仍生成 thumbnail） |

250 累計 pass（mandala + gallery + web + wordart 全套）。

## 5. 涉及檔案

```
src/stroke_order/gallery/service.py     (create_upload 加 char_loader_factory + factory(state) resolve)
src/stroke_order/web/server.py           (gallery_uploads_create 改傳 factory)
tests/test_gallery_mandala.py            (+3 r28d tests，總 33)
pyproject.toml                            (0.14.109 → 0.14.110)
```

## 6. 教訓 / 共通性

- **Factory 模式比靜態 DI 更彈性**：當 dependency 需要 callee 內部資料動態構造時（如 state），factory pattern 比預先構造好的 instance 乾淨。靜態 DI 適合 stateless 場景。
- **Two-level fallback**：factory > static > None。三層保證 graceful — factory 失敗（例外 / 不存在）退到 static、static 也無則 skip thumbnail（不擋 upload）。
- **state.style schema 預留 reserved fields 早就用上了**：r27 schema 定 `style: { font, cns_outline_mode, source }` 三欄當時看似多餘，r28d 立刻派上用場 — 用來重建 user 的 mandala 視覺。預留 schema 欄位 = 未來性。

## 7. r28 系列收尾

| Phase | 內容 | 版本 | Test 累計 |
|---|---|---|---|
| r28 | Gallery 接 mandala upload (multi-kind) | 0.14.107 | 237 |
| r28b | SVG thumbnail (cairosvg direct) | 0.14.108 | 243 |
| r28c | MD thumbnail (char loader DI) | 0.14.109 | 247 |
| r28d | Loader factory state-aware | 0.14.110 | 250 |

r28c known limitation 完整修復。Mandala upload thumbnail 現在跟 user 看到的視覺**完全一致**（含字型 / 字源 / outline mode）。

剩下 future work（r28e+ / r29）：

- Lazy thumbnail（首次 view 才 render，需要 cache 管理）
- 多尺寸 thumbnail（list / detail / preview）
- Thumbnail 重生成 endpoint（user 手動觸發）
- Rating / like / score 機制（r29）
