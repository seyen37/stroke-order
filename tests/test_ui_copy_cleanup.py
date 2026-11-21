"""v0.14.305：外部評論驗證後的介面文案清理——鎖住不回流。

兩份外部評論（2026-11-21）點出的真問題：Markdown 星號外露、喚醒等待沒有
秒數、罕用字面板預設寫本機路徑、分享庫同一種檔案兩種叫法、工程術語。
只檢查使用者看得到的文字：先去掉 <script>、<style>、HTML 註解。
"""
from __future__ import annotations

import re
from pathlib import Path

STATIC = (Path(__file__).resolve().parent.parent
          / "src" / "stroke_order" / "web" / "static")


def _visible(name: str) -> str:
    s = (STATIC / name).read_text(encoding="utf-8")
    s = re.sub(r"<script\b.*?</script>", "", s, flags=re.S)
    s = re.sub(r"<style\b.*?</style>", "", s, flags=re.S)
    return re.sub(r"<!--.*?-->", "", s, flags=re.S)


def test_no_raw_markdown_bold_in_pages():
    for name in ("index.html", "gallery.html", "handwriting.html"):
        hits = re.findall(r"\*\*[^*\s<][^*<]{0,40}\*\*", _visible(name))
        assert not hits, f"{name} 有 Markdown 星號外露：{hits}"


def test_homepage_jargon_translated():
    """老師看得到的字（含 title 提示）不出現工程術語。"""
    text = _visible("index.html")
    for word in ("fit-within", "outlier", "回應標頭", "normalise",
                 "em frame", "骨架化", "RDP", "Chaikin"):
        assert word not in text, f"首頁仍有術語：{word}"


def test_wakeup_overlay_shows_elapsed_and_refresh_hint():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="wakeup-elapsed"' in html
    i = html.index('class="wakeup-sub wakeup-stage-late"')
    assert "重新整理" in html[i:i + 200]
    core = (STATIC / "modes" / "core.js").read_text(encoding="utf-8")
    assert "wakeup-elapsed" in core and "setInterval(tick" in core
    assert "clearInterval(tickTimer)" in core       # 喚醒後停止計時


def test_userdict_panel_never_claims_local_path_by_default():
    """公開站不能先寫「存放於本機 ~/.stroke-order」——由 /api/user-dict 回填。"""
    html = _visible("index.html")
    m = re.search(r'<code id="ud-path">([^<]*)</code>', html)
    assert m and "~/.stroke-order" not in m.group(1)
    js = (STATIC / "modes" / "userdict.js").read_text(encoding="utf-8")
    assert "ud-path" in js and "d.writable === false" in js


def test_gallery_psd_has_one_name():
    """/handwriting 叫「筆順練習」，它匯出的 JSON 一律叫「筆順字跡」。"""
    for name in ("gallery.html", "gallery/gallery.js", "gallery/uploader.js",
                 "gallery/hash.mjs"):
        src = (STATIC / name).read_text(encoding="utf-8")
        assert "抄經軌跡" not in src and "(PSD)" not in src, name
    assert "psd: '筆順字跡'" in (STATIC / "gallery" / "hash.mjs").read_text("utf-8")
    assert "筆順字跡" in _visible("gallery.html")
