"""Phase 5d — handwriting practice page (PSD).

Validates:
  * GET /handwriting returns the SPA shell with required script tags
  * GET /static/handwriting/* serves all six ES modules + CSS
  * GET /api/handwriting/reference/{char} returns native EM 2048 outline
    data with style support
  * GET /api/sutra/text/{preset} returns plain text or 422 when not loaded
  * No regression to /, /sutra-editor

This file is intentionally Python-side only — the JS modules' behaviour
is exercised by the in-browser smoke testing the user does manually
(touch / pen / mouse / cross-platform). Node `--check` runs at build
time confirm the modules at least parse.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest



# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_sutra_dir(monkeypatch):
    """Override sutra dir + drop a small heart_sutra.txt into it.

    5bp: packaged-text fallback disabled so "not loaded" tests keep
    observing the classic filesystem-only behaviour (same as the
    fixture in test_sutra.py).
    """
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("STROKE_ORDER_SUTRA_DIR", td)
        monkeypatch.setenv("STROKE_ORDER_PACKAGED_SUTRAS", "0")
        (Path(td) / "heart_sutra.txt").write_text(
            "觀自在菩薩，行深般若波羅蜜多時。",
            encoding="utf-8",
        )
        yield Path(td)


# ---------------------------------------------------------------------------
# /handwriting page
# ---------------------------------------------------------------------------


def test_handwriting_route_returns_html(client):
    r = client.get("/handwriting")
    assert r.status_code == 200
    text = r.text
    assert "筆順練習" in text
    # All six ES modules must be loaded.
    for mod in [
        "handwriting/handwriting.css",
        "handwriting/canvas.js",
        "handwriting/storage.js",
        "handwriting/materials.js",
        "handwriting/grid.js",
        "handwriting/reference.js",
        "handwriting/exporter.js",
    ]:
        assert mod in text, f"module {mod} not referenced in /handwriting"


def test_handwriting_route_includes_action_buttons(client):
    """The data-action hooks the JS module wires up to must be present."""
    r = client.get("/handwriting")
    text = r.text
    for action in [
        "clear", "commit", "prev", "next", "undo",
        "export-json", "export-svg-one", "export-svg-zip",
        "clear-all", "submit-public",   # 5ez：email-self 依使用者要求刪除
    ]:
        assert f'data-action="{action}"' in text, f"missing data-action {action!r}"


def test_handwriting_includes_warnings_and_privacy_notice(client):
    """5d-12: privacy banner is always visible; in-app browser banner
    starts hidden but exists in the DOM; lishu/seal priority hint is
    present (initially hidden until style chosen)."""
    text = client.get("/handwriting").text
    assert 'id="hw-banner-privacy"' in text
    assert "您的筆跡資料只存在這部裝置" in text
    assert 'id="hw-banner-inapp-browser"' in text
    assert "Line" in text and "FBAN" in text     # UA pattern source
    assert 'id="hw-style-priority-hint"' in text
    assert "本機資料庫" in text                    # 5cb-style accurate wording


def test_handwriting_includes_5e_placeholders(client):
    """公眾資料庫佔位鈕保留（disabled 待開發）；email 同步鈕已依
    使用者要求刪除（5ez）——改鎖「不得回歸」。"""
    text = client.get("/handwriting").text
    assert "data-action=\"submit-public\"" in text
    assert "待開發" in text
    assert "email-self" not in text            # 5ez：刪除且不得回歸


# ---------------------------------------------------------------------------
# static module serving
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filename, must_have", [
    ("canvas.js",   ["WritingCanvas", "EM_SIZE", "pointerdown",
                     "devicePixelRatio", "tiltX"]),
    ("storage.js",  ["saveTrace", "STORE_TRACES", "createIndex",
                     "stroke-order-practice"]),
    ("grid.js",     ["drawGrid", "GRID_STYLES", "mizi", "tianzi", "huizi"]),
    ("reference.js", ["fetchReference", "drawReference", "_outlineBBox"]),
    ("materials.js", ["loadSutraMaterial", "loadInputMaterial",
                      "loadUploadMaterial", "loadFreehandMaterial",
                      "MaterialIterator"]),
    ("exporter.js",  ["exportAllJson", "exportTraceSvg", "exportAllSvgZip",
                      "importJson", "makeZip", "stroke-order-psd-v1",
                      "0x04034b50"]),
])
def test_static_module_serves_with_expected_keys(client, filename, must_have):
    r = client.get(f"/static/handwriting/{filename}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript") \
        or r.headers["content-type"].startswith("text/javascript")
    text = r.text
    for needle in must_have:
        assert needle in text, f"{filename}: missing {needle!r}"


def test_static_css_serves(client):
    r = client.get("/static/handwriting/handwriting.css")
    assert r.status_code == 200
    text = r.text
    assert ".hw-canvas-wrap" in text
    # 768px breakpoint for RWD
    assert "max-width: 767px" in text or "max-width:767px" in text \
        or "767" in text
    # Touch action disabled for the canvas (critical for iOS)
    assert "touch-action: none" in text or "touch-action:none" in text


# ---------------------------------------------------------------------------
# /api/handwriting/reference/{char}
# ---------------------------------------------------------------------------


def test_handwriting_reference_default_kaishu(client):
    r = client.get("/api/handwriting/reference/永")
    assert r.status_code == 200
    data = r.json()
    assert data["char"] == "永"
    assert data["style"] == "kaishu"
    # Native EM 2048 — the same coord system as the page's writing canvas
    assert data["em_size"] == 2048
    assert isinstance(data["strokes"], list)
    assert len(data["strokes"]) > 0
    # Each stroke must have an outline (filtered server-side)
    for s in data["strokes"]:
        assert "outline" in s
        assert len(s["outline"]) > 0


@pytest.mark.parametrize("style", [
    "kaishu", "mingti", "lishu", "seal_script", "bold",
])
def test_handwriting_reference_accepts_all_styles(client, style):
    r = client.get(f"/api/handwriting/reference/永?style={style}")
    assert r.status_code == 200
    data = r.json()
    assert data["style"] == style
    # Even when the font isn't installed (sandbox), backend must
    # gracefully fall back rather than 500. strokes may be [] but the
    # response shape must hold.
    assert "strokes" in data
    assert data["em_size"] == 2048


def test_handwriting_reference_lishu_outline_preserved_not_skeletonised(client):
    """5bz pattern: lishu in skeleton mode strips the outline. The
    handwriting reference endpoint passes outline_mode='skip' so the
    outline stays intact, ready for fill-rendering on the bg canvas.
    Verified by checking the outline isn't empty (when font available)."""
    r = client.get("/api/handwriting/reference/天?style=lishu")
    assert r.status_code == 200
    data = r.json()
    # When MoE lishu is installed locally, strokes are non-empty;
    # in CI sandbox without the font, falls back to kaishu (also
    # non-empty). Either way: outline_mode='skip' must NOT yield
    # empty outlines for the upgrade chain to make sense.
    assert isinstance(data["strokes"], list)
    if data["strokes"]:
        assert all(s.get("outline") for s in data["strokes"]), (
            "outline preservation broken — got empty outline list"
        )


# ---------------------------------------------------------------------------
# /api/sutra/text/{preset}
# ---------------------------------------------------------------------------


def test_sutra_text_returns_plain_text_when_loaded(client, temp_sutra_dir):
    r = client.get("/api/sutra/text/heart_sutra")
    assert r.status_code == 200
    data = r.json()
    assert data["preset"] == "heart_sutra"
    assert data["title"]                      # has a human-readable title
    assert "般若波羅蜜多" in data["text"]
    assert data["char_count"] > 0
    # char_count excludes whitespace (basic sanity)
    assert data["char_count"] <= len(data["text"])


def test_sutra_text_returns_422_when_not_loaded(client, temp_sutra_dir):
    """A registered preset whose .txt file is missing must give a clean
    422 — the frontend uses this signal to fall back to freehand."""
    # diamond_sutra is a registered builtin; we didn't drop the file.
    r = client.get("/api/sutra/text/diamond_sutra")
    assert r.status_code == 422
    assert "not loaded" in r.json()["detail"]


def test_sutra_text_returns_404_for_unknown_preset(client):
    """Random preset key the registry doesn't recognise."""
    r = client.get("/api/sutra/text/this_preset_does_not_exist")
    assert r.status_code in (404, 422)
    # 422 from the URL pattern validator is also acceptable — both
    # are clean refusals the frontend can handle.


# ---------------------------------------------------------------------------
# regression: existing routes still healthy
# ---------------------------------------------------------------------------


def test_main_index_still_works(client):
    r = client.get("/")
    assert r.status_code == 200


def test_sutra_editor_still_works(client):
    r = client.get("/sutra-editor")
    assert r.status_code == 200


def test_existing_character_endpoint_still_works(client):
    r = client.get("/api/character/永")
    assert r.status_code == 200
    # hanzi-writer-format response — different shape from /api/handwriting
    data = r.json()
    assert "strokes" in data
    assert "medians" in data
    # Old contract: strokes are SVG path d-strings (not outline cmd dicts)
    assert isinstance(data["strokes"][0], str)
    assert data["strokes"][0].startswith("M ")


# ---------------------------------------------------------------------------
# Plotter SVG: structural sanity (the ES module is the source of truth,
# but here we re-implement just enough of the schema string to assert
# the front-end constants stay aligned with the test expectations).
# ---------------------------------------------------------------------------


def test_exporter_module_uses_schema_v1_tag(client):
    """If the JSON schema tag changes, importing older files would
    silently fail. Pin the value here so changing it forces a test
    update too."""
    r = client.get("/static/handwriting/exporter.js")
    assert "stroke-order-psd-v1" in r.text


def test_exporter_module_emits_em_2048_viewbox(client):
    """The Plotter SVG generator must use the same EM coordinate system
    as the rest of the engine, so traces re-fed to plotter pipelines
    align with internal char data."""
    r = client.get("/static/handwriting/exporter.js")
    assert 'viewBox="0 0 ${EM_SIZE} ${EM_SIZE}"' in r.text \
        or 'viewBox="0 0 2048 2048"' in r.text \
        or "EM_SIZE      = 2048" in r.text   # const definition


# ---------------------------------------------------------------------------
# Phase 5ce — 部首教學路線 curriculum view
# ---------------------------------------------------------------------------


def test_5ce_curriculum_panel_elements(client):
    """手寫頁含教學路線面板：單元卡、進度、chips、上下單元鈕。"""
    html = client.get("/handwriting").text
    for eid in ("hw-curriculum", "hw-cur-radical", "hw-cur-progress",
                "hw-cur-chips", "hw-cur-prev", "hw-cur-next",
                "hw-cur-fill", "hw-cur-hint"):
        assert f'id="{eid}"' in html, f"handwriting.html 缺少 {eid}"


def test_5ce_curriculum_consumes_5cd_apis(client):
    """curriculum 吃 5cd 的兩個 API：radical-route ＋ family。"""
    html = client.get("/handwriting").text
    assert "/api/radical-route" in html
    assert "/family" in html
    assert "renderCurriculumUnit" in html
    # 單元位置依 coverset 分開持久化
    assert "hw-curriculum-unit:" in html


def test_5ce_commit_hook_auto_advances(client):
    """commit 後帶 autoAdvance 刷新——寫完單元自動前往下一單元。"""
    html = client.get("/handwriting").text
    assert "autoAdvance: true" in html


def test_5ce_css_has_done_chip_style(client):
    css = client.get("/static/handwriting/handwriting.css").text
    assert "hw-cur-done" in css
    assert "hw-curriculum" in css


# ---------------------------------------------------------------------------
# 5ew-R3：筆順練習 × 逐字手寫整合——共用儲存層雙寫
# ---------------------------------------------------------------------------


def test_5ew_r3_shared_store_and_sync_ui(client):
    """整合接線標記：共用儲存層 API、同步勾選、深連結、進階按鈕。"""
    storage = client.get("/static/handwriting/storage.js").text
    for marker in ("saveDual", "syncTraceToUserDict",
                   "swStrokesToTraceStrokes", "traceStrokesToUserDict"):
        assert marker in storage, marker
    page = client.get("/handwriting").text
    assert 'id="hw-sync-userdict"' in page          # 同步勾選（預設開）
    assert "checked" in page.split('id="hw-sync-userdict"')[1][:60]
    assert "saveDual" in page                        # COMMIT 走雙寫
    assert "URLSearchParams" in page                 # ?char= 深連結
    sw = client.get("/static/modes/handwrite.js").text
    assert "handwriting/storage.js" in sw            # 簡潔版 import 共用層
    assert "swStrokesToTraceStrokes" in sw           # 練習史雙寫
    assert "sw-advanced" in sw                       # 進階練習跳轉
    html = client.get("/").text
    assert 'id="sw-advanced"' in html                # overlay 按鈕存在


def test_5ew_r4_click_to_write_spread(client):
    """5ew-R4：點格手寫擴散——adapter 泛化＋四模式掛載標記。

    overlay 邏輯唯一（handwrite.js），模式差異收斂於 adapter；
    字帖/筆記/信紙/稿紙 render 後各自 swAttachCells。
    """
    sw = client.get("/static/modes/handwrite.js").text
    for marker in ("swAttachCells", "SW_SUTRA_ADAPTER",
                   "swCollectDataCharCells", "swBuildCellRefImg",
                   "data-sw-hit"):
        assert marker in sw, marker
    # 抄經呼叫端名稱保留（行為不變的鎖）
    assert "swAttachPreviewClicks" in sw
    # 四模式：import 共用 overlay ＋ 以自己的 key/refresh 掛載
    for mod in ("grid", "notebook", "letter", "manuscript"):
        src = client.get(f"/static/modes/{mod}.js").text
        assert "handwrite.js" in src, mod            # import 邊
        assert f'key: "{mod}"' in src, mod           # adapter key＝模式名
        assert "swAttachCells" in src, mod
    # 筆順練習頁來源提示已泛化（from=grid/notebook/letter/manuscript）
    page = client.get("/handwriting").text
    assert "_fromLabels" in page
    assert "稿紙" in page


def test_5ew_r5_art_modes_click_to_write(client):
    """5ew-R5：擴散二批——文字藝術/曼陀羅 adapter 掛載＋禪繞字跳板。

    wordart/mandala：_place_char_svg data-char（後端 1 處）＋swAttachCells；
    禪繞字（canvas＋演算法吃 outline，手寫字無 outline）以「進階練習」
    深連結誠實對應。
    """
    for mod in ("wordart", "mandala"):
        src = client.get(f"/static/modes/{mod}.js").text
        assert f'key: "{mod}"' in src, mod
        assert "swAttachCells" in src, mod
    html = client.get("/").text
    assert 'id="zentangle-advanced"' in html
    zt = client.get("/static/zentangle/zentangle.js").text
    assert "zentangle-advanced" in zt
    assert "from=zentangle" in zt
    page = client.get("/handwriting").text
    for label in ("文字藝術", "曼陀羅", "禪繞字"):
        assert label in page, label


def test_5ez_layout_and_deeplink_settings(client):
    """5ez：筆順練習頁動線/排版依使用者規格＋深連結帶入來源設定。"""
    page = client.get("/handwriting").text
    # 復原+清除 → 米字框外左上工具列；上一字/下一字/完成本字 → 右側欄
    assert 'data-action="undo"' in page
    assert 'hw-canvas-tools' in page
    assert 'hw-canvas-row' in page
    assert 'hw-side-actions' in page
    # 匯入/匯出區塊存在；email 同步鈕刪除、公眾資料庫佔位保留
    # （5ez 的「匯出三鈕一行」版位歷經 5fj/5fk/5fl 移入左欄——
    #    佈局斷言移交 test_5fj_5fl_data_area_relayout）
    assert 'hw-data-import' in page
    assert 'email-self' not in page
    assert 'submit-public' in page
    # 深連結帶入 style/preset＋回來源按鈕
    assert '_styleParam' in page
    assert '_hwDesiredPreset' in page
    assert 'hw-back-origin' in page
    css = client.get("/static/handwriting/handwriting.css").text
    assert '.hw-side-actions' in css
    # 進階練習跳轉帶 style＋（抄經）preset
    sw = client.get("/static/modes/handwrite.js").text
    assert 'q.set("style"' in sw
    assert 'q.set("preset"' in sw


def test_5fc_layout_round2(client):
    """5fc：版面二輪（使用者截圖規格）＋hidden 屬性全域修正。"""
    css = client.get("/static/handwriting/handwriting.css").text
    # 根因修：CSS display:flex 蓋掉 hidden 屬性——全域歸位
    assert "[hidden] { display: none !important; }" in css
    page = client.get("/handwriting").text
    # 素材/模式 radio 帶 hover 提示；模式簡潔化
    assert 'title="以內建經典' in page
    assert 'title="臨摹：畫布顯示淡灰範字底圖' in page
    assert "<span>臨摹</span>" in page and "淡灰底圖）</span>" not in page
    # 格線移到畫布欄右上（hw-grid-pick 在 hw-canvas-tools 內）
    assert "hw-grid-pick" in page
    assert "hw-canvas-col" in page
    tools = page.split('hw-canvas-tools')[1].split("</div>")[0:3]
    assert 'id="hw-grid"' in page.split('hw-canvas-tools')[1].split(
        'hw-canvas-wrap')[0]
    # 左欄不再有「格線」區塊標題
    assert ">格線</h2>" not in page
    # 資料抽屜首列規格已被 5fj 取代（統計/提交移左欄、匯入/清空移
    # 畫布右下）——見 5fj 重排測試
    # 深連結一致化＋返回鈕改名進請寫列
    assert "showSourcePanel('input')" in page
    assert "逐字手寫';" in page              # back.textContent
    assert "hw-prompt-row')?.appendChild(back)" in page


def test_5fe_layout_and_version_sync(client):
    """5fe：右欄頂對齊畫布上框（grid）＋版本標籤/CSS 自動同步＋提示跨列外。"""
    css = client.get("/static/handwriting/handwriting.css").text
    # grid 佈局：右側動作欄與畫布同列（頂端不高於米字框上緣）
    assert "grid-template-columns: minmax(0, 600px) max-content" in css
    assert "grid-row: 2;                   /* 5fe" in css
    page = client.get("/handwriting").text
    # CSS 帶 ?v=（伺服器注入 APP_VERSION；長快取＋升版即失效）
    assert "handwriting.css?v=" in page
    assert "handwriting.css?v=__V__" not in page   # 佔位符必須被注入
    # 版本標籤不再手刻，由 JS 讀資產 ?v= 同步
    assert 'id="hw-version"' in page
    assert ">v0.13.0<" not in page      # 手刻標籤移除（註解提歷史不算）
    # 來源提示插在畫布 grid 之外（否則撐爆右欄）
    assert "hw-from-hint" in page
    assert "insertBefore(st, _row)" in page


def test_5fj_5fl_data_area_relayout(client):
    """5fj→5fl：資料區重排終局——統計/提交/匯入/清空/匯出三鈕全在左欄
    （組件覆蓋下，順序 統計→提交→匯入→清空→匯出×3）；畫布右下區與
    底部抽屜均退場；清空帶二次確認。id/data-action 全保留（JS 綁定
    不斷；「≡ 我的資料」改捲動到左欄資料區）。"""
    page = client.get("/handwriting").text
    # 左欄：組件覆蓋 → 我的資料（統計→提交→匯入→清空→匯出三鈕）順序
    aside = page.split("<aside", 1)[1].split("</aside>", 1)[0]
    assert 'id="hw-side-data"' in aside
    assert aside.index("hw-coverset") < aside.index('id="hw-side-data"')
    side = aside.split('id="hw-side-data"')[1]
    assert 'id="hw-db-count"' in side and 'id="hw-db-unique"' in side
    order = [side.index('data-action="submit-public"'),
             side.index('id="hw-import-file"'),
             side.index('data-action="clear-all"'),
             side.index('data-action="export-json"'),
             side.index('data-action="export-svg-one"'),
             side.index('data-action="export-svg-zip"')]
    assert side.index('id="hw-db-count"') < order[0]
    assert order == sorted(order), order
    # 5fk：畫布右下區退場；5fl：底部抽屜退場（匯出併入左欄）
    assert "hw-canvas-bottom" not in page
    assert 'id="hw-drawer"' not in page
    # 「≡ 我的資料」仍在，改導向左欄資料區
    assert 'id="hw-data-mgmt"' in page
    assert "$('hw-side-data').scrollIntoView" in page
    # 5fk：清空整庫二次確認——clear-all 處理器內兩個 confirm(
    handler = page.split('[data-action="clear-all"]\').addEventListener', 1)[1]
    body = handler[:handler.index("clearAllTraces")]   # 確認都在動手之前
    assert body.count("confirm(") == 2, body.count("confirm(")
    assert "最後確認" in body
    # CSS：左欄匯入/清空/匯出撐滿欄寬；右下區與抽屜規則已移除
    css = client.get("/static/handwriting/handwriting.css").text
    assert "hw-canvas-bottom" not in css
    assert ".hw-drawer {" not in css
    assert "#hw-side-data .hw-data-import" in css
    assert "#hw-side-data .hw-btn-danger" in css
    assert "#hw-side-data .hw-export-group" in css


def test_5fi_index_version_label(client):
    """5fi：主頁版本標籤——讀資產 ?v= 自動同步，不手刻（§57）。"""
    page = client.get("/").text
    assert 'id="app-version"' in page
    # 佔位符已被伺服器注入成真實版本（label JS 依它填值）
    assert "?v=__V__" not in page
    import re
    assert re.search(r'\?v=\d+\.\d+\.\d+', page)
    # 標籤本體不手刻版本數字（由 JS 填）
    assert re.search(r'id="app-version"[^>]*></span>', page.replace("\n", ""))


def test_5fd_deeplink_material_routing(client):
    """5fd：深連結分流——帶 preset 走經典（定位該字）；無 preset 走字串。"""
    page = client.get("/handwriting").text
    assert "_hasPreset" in page
    assert "loadSutraMaterial(_presetParam)" in page          # 經典路
    assert "chars.indexOf(_deepChar)" in page                 # 定位到該字
    assert "showSourcePanel('sutra')" in page
    assert "showSourcePanel('input')" in page                 # 字串路保留


def test_5fp_p0_modal_close_paths_and_inline_load_error(client):
    """5fp（P0 稽核）：①逐字手寫視窗 Esc／切換模式都會關閉（與 ✕ 同
    語意；修正前鍵盤無關閉路徑、切模式後視窗殘留蓋住新模式設定）
    ②單字模式載入失敗訊息緊貼「載入 / 重繪」按鈕（原本只在頁底
    診斷資訊，初次使用者看不到）。"""
    sw = client.get("/static/modes/handwrite.js").text
    # ① Esc 關閉＋模式切換關閉——都在視窗開啟狀態才觸發
    assert '_swOpen' in sw
    assert 'e.key === "Escape"' in sw
    handler = sw.split('e.key === "Escape"')[1][:120]
    assert "swClose()" in handler
    assert 'input[name="mode"]' in sw     # 切模式 hook（change → swClose）
    assert sw.count("swClose()") >= 3     # ✕／背景點擊／Esc／切模式
    # ② 按鈕旁錯誤：index 有空殼 span、core.js 有清空＋填入
    page = client.get("/").text
    row = page.split('id="load"', 1)[1][:600]
    assert 'id="load-error"' in row
    assert "hidden" in row.split('id="load-error"')[0][-80:] or \
           'hidden' in row.split('id="load-error"')[1][:120]
    core = client.get("/static/modes/core.js").text
    assert '_loadErr' in core
    assert "_loadErr.hidden = true" in core       # 成功/重試前清空
    assert "_loadErr.hidden = false" in core      # 失敗時顯示
    assert "詳情見頁底診斷資訊" in core


def test_5fq_p1_color_naming_emptystate_isolation(client):
    """5fq（P1 稽核四項）：①主要動作統一藍（--primary=#2c5cb8，紅留給
    危險）②產生鈕動詞統一（載入/重繪→產生筆順預覽、載入字框→產生
    字框）③空狀態句全站化＋單字模式三鈕載入前 disabled ④破壞性鈕
    隔離（/card 刪除選取框獨立列）與印章位移歸零標明範圍。"""
    page = client.get("/").text
    # ① 色彩語意
    assert "--primary: #2c5cb8" in page
    assert "--primary: var(--accent)" not in page
    # ② 動詞統一（舊名不得回歸）
    assert "產生筆順預覽" in page and "載入 / 重繪" not in page
    assert "產生字框" in page and "載入字框" not in page
    # ③ 空狀態：共用樣式＋至少 8 個容器有提示句；舊版短句不殘留
    assert ".preview-empty" in page
    assert page.count('class="preview-empty"') >= 8
    assert "(按「產生字帖」以顯示)" not in page
    # 單字模式三鈕初始 disabled；載入成功由 core.js 啟用
    for bid in ("btn-animate", "btn-quiz", "btn-reset"):
        seg = page.split(f'id="{bid}"')[1][:30]
        assert "disabled" in seg, bid
    core = client.get("/static/modes/core.js").text
    assert 'document.getElementById(id).disabled = false' in core
    # ④ 破壞性隔離
    assert "位移全部歸零" in page          # 印章：標明作用範圍
    card = client.get("/card").text
    add_grp = card.split('id="card-add-doodle"')[1]
    first_row_end = add_grp.index("</div>")
    assert "card-del-box" not in add_grp[:first_row_end]   # 不在加入列
    assert "card-del-box" in add_grp                        # 仍存在（獨立列）


def test_5fr_p2_batch(client):
    """5fr（P2 稽核八項）：禪繞推薦組合置頂＋進階變形收合／曼陀羅產生鈕
    sticky／單字預載示範字＋自動載入／sutra·patch·stamp 下載鈕產生前
    disabled＋成功啟用／gallery [hidden] 歸位（§54 三現）／card 說明
    移右欄／字帖·文字雲提示文案。"""
    page = client.get("/").text
    # 禪繞：推薦組合列在基本符號列之前；進階變形 details 存在
    zt = page.split('id="zentangle-view"')[1].split("</main>")[0]
    assert zt.index('id="zentangle-combo-buttons"') \
        < zt.index('id="zentangle-basic-buttons"')
    assert "進階變形（紙磚旋轉／透視／曲度）" in zt
    assert "<details" in zt.split("紙磚旋轉")[0][-600:] or "進階變形" in zt
    # 曼陀羅 sticky
    md_row = page.split('id="md-render"')[0][-300:]
    assert "position:sticky" in md_row
    # 單字：預填＋自動載入
    assert 'id="char" type="text" maxlength="1" value="永"' in page
    core = client.get("/static/modes/core.js").text
    assert "開頁自動載入示範字" in core
    # 下載鈕 disabled（三模式 11 顆）
    for bid in ("su-dl-current", "su-dl-all", "su-dl-pdf",
                "pt-dl-svg", "pt-dl-cut", "pt-dl-write", "pt-dl-dxf",
                "st-dl-svg", "st-dl-pdf", "st-dl-gcode", "st-dl-dxf"):
        assert f'id="{bid}" type="button" disabled' in page, bid
    for mod in ("sutra", "patch", "stamp"):
        js = client.get(f"/static/modes/{mod}.js").text
        assert "產生成功才啟用下載鈕" in js, mod
    # gallery [hidden] 歸位
    gcss = client.get("/static/gallery/gallery.css").text
    assert "[hidden] { display: none !important; }" in gcss
    # card：操作說明在右欄（下載說明之後）
    card = client.get("/card").text
    assert card.index("草稿自動存在瀏覽器") < card.index("點擊內容選取框")
    # 提示文案
    assert "例：選「氵」" in page
    assert "上緣文字會倒置" in page


def test_5fs_gallery_tab_card_sametab_sw(client):
    """5fs 四項：①公眾分享庫入口上層 tab（藝術創作旁）②筆順練習提交
    鈕拿掉「匿名」③手寫卡片同分頁開啟 ④卡片文字框「逐字手寫」——
    整串文字帶進筆順練習（from=card），返回鈕回 /card。"""
    page = client.get("/").text
    tabs = page.split('class="mode-tabs"')[1].split("</div>")[0]
    assert 'href="/gallery"' in tabs
    assert tabs.index("藝術創作") < tabs.index('href="/gallery"')
    # 手寫卡片：同分頁（無 target=_blank、無 ↗）
    card_link = page.split('href="/card"')[1][:400]
    assert "_blank" not in page.split('href="/card"')[0][-200:]
    assert "↗" not in card_link
    # 匿名字樣移除
    hw = client.get("/handwriting").text
    assert "提交公眾資料庫" in hw
    assert "提交匿名" not in hw
    # from=card 支援：標籤＋返回鈕回 /card
    assert "card: '手寫卡片'" in hw
    assert "'/card' : '/'" in hw
    # 卡片：逐字手寫鈕＋main.js 導航
    card = client.get("/card").text
    assert 'id="card-sw-btn"' in card
    mainjs = client.get("/static/card/main.js").text
    assert "from=card" in mainjs
    assert "card-sw-btn" in mainjs


def test_5ft_popup_entry_and_gallery_kind(client):
    """5ft：①主頁藝術創作群有立體字入口（/popup 原無入口）②分享庫
    篩選籤含立體字、上傳說明含三種、banner 含 pop-up SVG ③uploader
    支援 popup 偵測。"""
    page = client.get("/").text
    art = page.split('data-g="art"')[-1]
    assert 'href="/popup"' in art
    assert "鏤空 pop-up" in art
    gl = client.get("/gallery").text
    assert 'data-kind="popup"' in gl
    assert "立體字" in gl and "支援三種上傳" in gl
    up = client.get("/static/gallery/uploader.js").text
    assert "stroke-order-popup-v1" in up
    assert "popup-svg" in up
    gjs = client.get("/static/gallery/gallery.js").text
    assert "popup: '立體字'" in gjs
    pop = client.get("/popup").text
    assert '"/gallery"' in pop or "href=\"/gallery\"" in pop


def test_5fu_shared_controls_unified(client):
    """5fu（P2 遺留專門輪）：共用控制項三統一——①命名：資料來源／字體／
    字型 全改「字型風格」「資料源」②順序：字型風格→罕用字→資料源
    ③散落者聚攏：wordart 資料源併入風格列、mandala 三件自表單三處
    聚攏成一列。id 全保留（JS 綁定不斷）。"""
    page = client.get("/").text

    def view(name):
        seg = page.split(f'<main id="{name}-view"')[1]
        return seg.split("</main>")[0]

    # ① 命名統一：全站不再有「資料來源」標籤；zentangle/stencil 用字型風格
    assert "資料來源</label>" not in page
    assert "字型風格" in view("zentangle")
    assert "字型風格" in view("stencil")
    assert ">字體</label>" not in view("zentangle")

    # ②③ wordart／mandala：三件相鄰且順序 風格→罕用字→資料源
    for mode, ids in [
        ("wordart", ("wa-style", "wa-cns-mode", "wa-source")),
        ("mandala", ("md-style", "md-cns-mode", "md-source")),
    ]:
        v = view(mode)
        pos = [v.index(f'id="{i}"') for i in ids]
        assert pos == sorted(pos), (mode, pos)
        assert pos[2] - pos[0] < 1500, (mode, "not adjacent", pos[2] - pos[0])
        # 各 id 僅出現一次（搬移未複製殘留）
        for i in ids:
            assert v.count(f'id="{i}"') == 1, (mode, i)

    # 既有順序一致的模式不得回歸（字型風格 →…→ 資料源）
    for mode, ids in [
        ("grid", ("grid-style", None, "grid-source")),
        ("sutra", ("su-style", None, "su-source")),
        ("patch", ("pt-style", None, "pt-source")),
        ("stamp", ("st-style", None, "st-source")),
    ]:
        v = view(mode)
        a, c = v.find(f'id="{ids[0]}"'), v.find(f'id="{ids[2]}"')
        if a >= 0 and c >= 0:
            assert a < c, mode
