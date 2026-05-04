# Phase 5b r28c：Mandala MD Upload Thumbnail（含 char loader DI）

**日期**：2026-05-04
**版本**：0.14.108 → 0.14.109
**範圍**：r28b 補充 — gallery mandala MD upload 也生成 thumbnail
**測試**：`tests/test_gallery_mandala.py` +4 → 30（原 26 + r28c 4）

---

## 1. 動機

r28b ship 後 mandala SVG upload 有 thumbnail，但 mandala MD upload 還是沒（user 從外部編輯器寫的 `.mandala.md`，或 mandala 模式上傳 SVG fallback 到 MD path 的場景）。Gallery card 會用 `<img onerror>` 隱藏，但 user 看不到視覺預覽 → 找作品難。

r28c 補上 MD path：parse state → server-side render → cairosvg 生成 PNG。需要 char loader（CharLoader）DI。

## 2. 設計核心：DI 而非 import

### 2.1 為什麼 char_loader 不能在 gallery service 內 build

Gallery service（`gallery/service.py`）是「不知道 stroke-order 怎麼 load 字」的純 upload 業務層。char loading 涉及：

- `_load(ch, source, hook_policy)` — 從不同 char database 拉取
- `_upgrade_to_sung / _seal / _lishu(c, style)` — outline 升級
- `_apply_style(c, style)` — 字型 filter（楷書 / 隸書 / 篆書 / etc）
- `_apply_cns_mode(c, cns_mode)` — CNS 11643 outline 模式

這些 helpers 在 `web/server.py` module-level，gallery 直接 import 會造成跨層耦合。

**解法**：DI。Gallery service 接受 optional `char_loader` callable。API 層構造 loader 傳入。Gallery service 不知道 loader 內部邏輯。

### 2.2 為什麼從 server.py 抽 `build_mandala_char_loader()` helper

既有 `/api/mandala` endpoint 內 inline 寫 loader 邏輯 — 跟 gallery upload 完全相同的需求。重複等於漂移風險（將來 loader 邏輯改一邊忘改另一邊 → render 行為不一致）。

**解法**：抽出 module-level `build_mandala_char_loader(*, style, source, hook_policy, cns_outline_mode)` factory。`/api/mandala` 跟 gallery upload 都用這個 helper。Single source of truth。

### 2.3 為什麼 state → render kwargs 映射放在 mandala.py

state schema 有 30+ 欄要 map 到 `render_mandala_svg` 的 kwargs。這是 mandala domain 邏輯：

- 屬於 mandala module 知識（state schema → render API 怎麼對齊）
- 多個 caller 會用（gallery upload thumbnail / 未來 server-side preview / 未來 r28d batch render）

**解法**：`exporters/mandala.py` 加 `render_mandala_from_state(state, char_loader) → (svg, info)`。Gallery service 只 call 這個 helper，不用自己拼 kwargs。

## 3. 實作

### 3.1 `exporters/mandala.py` 加 `render_mandala_from_state`

```python
def render_mandala_from_state(
    state: dict, char_loader: CharLoader,
) -> tuple[str, dict]:
    """Render `.mandala.md` schema state → SVG。"""
    canvas = state.get("canvas") or {}
    center = state.get("center") or {}
    ring = state.get("ring") or {}
    mandala = state.get("mandala") or {}
    extras = state.get("extra_layers") or []

    n_fold = mandala.get("n_fold")
    if n_fold is not None:
        try: n_fold = int(n_fold)
        except (ValueError, TypeError): n_fold = None

    return render_mandala_svg(
        center_text=str(center.get("text", "")),
        ring_text=str(ring.get("text", "")),
        char_loader=char_loader,
        size_mm=float(canvas.get("size_mm", 140)),
        # ... 30+ 個 kwargs map ...
        mandala_line_color=str(mandala.get("line_color", "#000000")),
        char_line_color=str(
            ring.get("line_color", center.get("line_color", "#000000"))),
    )
```

Defensive：每個 section 缺漏用 default、type cast 錯（如 `n_fold` 不能轉 int）回 None 不爆。

### 3.2 `web/server.py` 抽 `build_mandala_char_loader`

```python
def build_mandala_char_loader(
    *, style: str = "kaishu", source: str = "auto",
    hook_policy: str = "animation", cns_outline_mode: str = "skip",
):
    """Return a CharLoader for mandala rendering."""
    def _loader(ch: str):
        try:
            c, _r, _ = _load(ch, source, hook_policy)
            c = _upgrade_to_sung(c, style)
            c = _upgrade_to_seal(c, style)
            c = _upgrade_to_lishu(c, style)
            if style != "kaishu":
                c = _apply_style(c, style)
            if cns_outline_mode != "skip":
                c = _apply_cns_mode(c, cns_outline_mode)
            return c
        except (HTTPException, Exception):
            return None
    return _loader
```

`/api/mandala` endpoint 改用此 helper，丟掉 inline loader（DRY）。

### 3.3 `gallery/service.py` `create_upload(..., char_loader=None)` + MD path

```python
def create_upload(*, ..., char_loader=None) -> dict:
    """char_loader 為 mandala MD upload 生成 thumbnail 用的 DI；可選"""
    ...
    _maybe_generate_thumbnail(
        content_bytes, kind=kind, source_format=ext, abs_path=abs_path,
        char_loader=char_loader,
    )
```

新增 `_generate_md_thumbnail(state, *, char_loader)` 走 mandala render path：
```python
def _generate_md_thumbnail(state: dict, *, char_loader, size_px=256) -> bytes:
    from ..exporters.mandala import render_mandala_from_state
    import cairosvg
    svg_str, _info = render_mandala_from_state(state, char_loader)
    return cairosvg.svg2png(
        bytestring=svg_str.encode("utf-8"),
        output_width=size_px, output_height=size_px,
    )
```

`_maybe_generate_thumbnail` 改成 dispatch：
- `source_format == "svg"` → `_generate_svg_thumbnail`
- `source_format == "md"` AND `char_loader is not None` → `_generate_md_thumbnail`
- 其他（含 MD 但無 loader）→ skip
- 任何例外 → log warning + skip（不擋上傳）

### 3.4 API `gallery_uploads_create` 構造 loader

```python
upload_loader = None
if kind == "mandala":
    upload_loader = build_mandala_char_loader()  # server default
record = gallery_service.create_upload(
    user_id=user["id"], content_bytes=content,
    filename=file.filename, title=title, comment=comment, kind=kind,
    char_loader=upload_loader,
)
```

**Known limitation**：upload time 用 server default style/source/cns_mode（kaishu / auto / skip）。MD state 內 `style.font` 若是 lishu / seal_script，thumbnail 字會是 kaishu，跟 user mandala 模式內看到的不同。完美修法是從 state 解 style 兩次（一次拿 style.font 給 loader，再 parse 完整 state 給 render）— 留給 r28d 優化（如果 user 反映是問題）。

## 4. 測試 +4

| Test | 驗證 |
|---|---|
| `test_thumbnail_generated_for_mandala_md_with_loader` | MD + stub loader → 生成 PNG（缺字也能 render） |
| `test_thumbnail_md_without_loader_skipped` | MD + 無 loader → 跳過（保 r28b 行為） |
| `test_thumbnail_md_loader_exception_graceful` | loader 拋例外 → upload 不爆，thumbnail graceful 跳過 |
| `test_render_mandala_from_state_helper` | helper 直接測：state schema → SVG 含 layer color |

30 累計 pass。

## 5. E2E 視覺驗證

[r28c MD thumbnail E2E](computer:///sessions/friendly-dreamy-noether/r28c_md_thumbnail.png) — fixture `sample.mandala.md`（紅 vesica + 紅 dots + 綠 lotus_petal）+ stub loader（無字）→ 256×256 PNG 8.6KB，layer 配色完整呈現。

## 6. 涉及檔案

```
src/stroke_order/exporters/mandala.py        (render_mandala_from_state helper + __all__)
src/stroke_order/web/server.py                (build_mandala_char_loader + /api/mandala 改用 + upload endpoint 傳 loader)
src/stroke_order/gallery/service.py           (create_upload char_loader DI + _generate_md_thumbnail + dispatch)
tests/test_gallery_mandala.py                 (+4 r28c tests，總 30)
pyproject.toml                                 (0.14.108 → 0.14.109)
```

## 7. 教訓 / 共通性

- **DI > import**：跨層共用功能（loader）用 callable injection 比 service 直接 import web layer helpers 乾淨。Gallery service 維持「不知道 stroke-order」，可獨立測試 / 可遷移到別 web framework。
- **Single source of truth for char loader**：`/api/mandala` 跟 gallery upload 都呼叫 `build_mandala_char_loader()`，loader 邏輯改一處全 propagate。原本兩處 inline 是 latent bug（漂移無 alarm）。
- **Domain helper 放 domain module**：`render_mandala_from_state` 是 mandala 知識（state schema → render API mapping），放 `exporters/mandala.py` 而不是 gallery service。多個 caller 重用，不該被綁在某個 endpoint 內。
- **Graceful degrade 三層遞進**：
  1. PSD upload → 不需 thumbnail（service 直接 skip）
  2. Mandala SVG → cairosvg 直接轉，render 不會 fail（因 SVG 已預先 render）
  3. Mandala MD → 需 loader；loader fail（缺字 / 例外）依 render_mandala_svg 的 missing chars 容錯機制吞掉 → 仍生 thumbnail（部分字缺）。整個 render 爆才跳過。

## 8. Defer 留給後續

| 待做 | Phase |
|---|---|
| Loader 用 state.style.font 而非 server default（精準 thumbnail 字體） | r28d 視 user 反饋 |
| Lazy thumbnail（首次請求才 render） | 觀察 upload latency 必要性 |
| 多尺寸 thumbnail（list / detail / preview） | r28d+ |
| Thumbnail 重生成 endpoint（user 可手動觸發） | r28d+ |
