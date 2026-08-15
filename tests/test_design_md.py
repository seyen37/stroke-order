"""5ga: DESIGN.md 同步鎖——設計真理源與實際 CSS 不得漂移。

DESIGN.md §2 的 token 表是機器可讀 markdown 表格（| 角色 | `--token` |
`#hex` | `路徑` |）；本測試逐列驗證「該檔案裡確實有 `--token: #hex`」。
文件過期（改了 CSS 沒改文件、或反之）→ 紅燈。承 §76 單一事實源。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "DESIGN.md"

# | 角色 | `--token` | `#hex` | `path` |（僅取單一色值列；多值列另驗）
_ROW_RE = re.compile(
    r"^\|[^|]*\|\s*`(--[\w-]+)`\s*\|\s*`(#[0-9a-fA-F]{3,8})`\s*\|"
    r"\s*`([^`]+)`\s*\|", re.M)


def _rows():
    text = DESIGN.read_text(encoding="utf-8")
    rows = _ROW_RE.findall(text)
    assert len(rows) >= 10, "DESIGN.md §2 token 表列數異常（格式被改壞？）"
    return rows


def test_design_md_exists_and_has_core_sections():
    text = DESIGN.read_text(encoding="utf-8")
    for marker in ("視覺氣質", "色彩語意", "設計護欄",
                   "AI 代理提示指引", "tests/test_design_md.py"):
        assert marker in text, f"DESIGN.md 缺核心節：{marker}"


def test_tokens_match_actual_css():
    """表列的 token: hex 必須真實存在於宣稱的檔案中。"""
    misses = []
    for token, hexval, relpath in _rows():
        src = (ROOT / relpath).read_text(encoding="utf-8")
        pat = re.compile(re.escape(token) + r"\s*:\s*" + re.escape(hexval),
                         re.I)
        if not pat.search(src):
            misses.append(f"{relpath}: {token}: {hexval}")
    assert not misses, (
        "DESIGN.md 與 CSS 漂移（改 token 要文件與程式碼同批改）：\n"
        + "\n".join(misses))


def test_primary_blue_locked_across_three_scopes():
    """鐵則：主要動作藍全站同值——5gd 起由三處擴為六處
    （--primary ×4／--hw-accent／--gl-accent）。"""
    blue = "#2c5cb8"
    checks = {
        "src/stroke_order/web/static/index.html": "--primary",
        "src/stroke_order/web/static/handwriting/handwriting.css":
            "--hw-accent",
        "src/stroke_order/web/static/gallery/gallery.css": "--gl-accent",
        "src/stroke_order/web/static/card.html": "--primary",
        "src/stroke_order/web/static/sutra-editor.html": "--primary",
        "src/stroke_order/web/static/popup.html": "--primary",
        "src/stroke_order/web/static/teach.html": "--primary",
    }
    for relpath, token in checks.items():
        src = (ROOT / relpath).read_text(encoding="utf-8")
        assert re.search(re.escape(token) + r"\s*:\s*" + blue, src, re.I), \
            f"{relpath} 的 {token} 不再是 {blue}——若刻意改色，" \
            f"三處＋DESIGN.md 要同批改"


def test_danger_red_never_primary():
    """紅=破壞性專用：btn-danger 必須是白底紅字（非紅實底）。"""
    src = (ROOT / "src/stroke_order/web/static/index.html").read_text(
        encoding="utf-8")
    # ^ 錨定：避免誤中「.btn-primary, .btn-secondary, ... .btn-danger {」
    # 的共用宣告行，只取獨立的 .btn-danger 規則
    m = re.search(r"^\s*\.btn-danger\s*\{([^}]*)\}", src, re.M)
    assert m, "index.html 缺 .btn-danger 定義"
    body = m.group(1)
    assert "background: var(--surface)" in body, \
        "btn-danger 應為白底紅字（降低誤觸吸引力），不得改紅實底"


def test_pagination_active_uses_primary_blue():
    """5gb：分頁「目前頁」button.primary 是高亮非破壞——必須用主要動作藍。

    歷史病：button.primary 曾以 var(--accent)（破壞性紅）做底色，
    letter/manuscript/notebook 的頁碼高亮因此整排紅。
    """
    src = (ROOT / "src/stroke_order/web/static/index.html").read_text(
        encoding="utf-8")
    m = re.search(r"^\s*button\.primary\s*\{([^}]*)\}", src, re.M)
    assert m, "index.html 缺 button.primary 定義（分頁高亮仍在用）"
    body = m.group(1)
    assert "var(--primary)" in body and "var(--accent)" not in body, \
        "button.primary 應為主要動作藍，不得回退破壞性紅"


def test_accent_never_redefined_off_red():
    """5gd：--accent 全站固定＝破壞性/錯誤紅。

    歷史病：card.html 曾定 --accent:#1976d2（藍、當主色用）、popup.html
    曾定 --accent:#149046（綠主鈕）——同名反義會誤導照 DESIGN.md 動手的
    後人。凡定義 --accent 的檔案，值只准是 #c33。
    """
    pages = [
        "src/stroke_order/web/static/index.html",
        "src/stroke_order/web/static/card.html",
        "src/stroke_order/web/static/popup.html",
        "src/stroke_order/web/static/teach.html",
        "src/stroke_order/web/static/sutra-editor.html",
        "src/stroke_order/web/static/gallery.html",
        "src/stroke_order/web/static/handwriting.html",
    ]
    bad = []
    for relpath in pages:
        src = (ROOT / relpath).read_text(encoding="utf-8")
        for m in re.finditer(r"--accent\s*:\s*(#[0-9a-fA-F]{3,8})", src):
            if m.group(1).lower() != "#c33":
                bad.append(f"{relpath}: --accent: {m.group(1)}")
    assert not bad, (
        "--accent 被定義成非破壞性紅（同名反義回流）：\n" + "\n".join(bad))


def test_sutra_editor_primary_is_blue():
    """5gd：sutra-editor .btn-primary 不得回退 var(--accent) 紅實底。"""
    src = (ROOT / "src/stroke_order/web/static/sutra-editor.html").read_text(
        encoding="utf-8")
    m = re.search(r"^\s*\.btn-primary\s*\{([^}]*)\}", src, re.M)
    assert m, "sutra-editor.html 缺 .btn-primary 定義"
    body = m.group(1)
    assert "var(--primary)" in body and "var(--accent)" not in body, \
        "sutra-editor .btn-primary 應為主要動作藍，不得回退破壞性紅"


def test_handwriting_single_breakpoint():
    """5ge：handwriting.css 曾同檔並存 760/767 兩個近同斷點——鎖回單一值。"""
    src = (ROOT /
           "src/stroke_order/web/static/handwriting/handwriting.css"
           ).read_text(encoding="utf-8")
    bps = set(re.findall(r"@media\s*\(max-width:\s*(\d+)px\)", src))
    assert bps == {"767"}, f"handwriting.css 斷點應單一 767，實得 {sorted(bps)}"


def test_home_nav_arrow_unified():
    """5ge：各獨立頁「← 回主頁」統一箭頭（曾 ←/↩ 混用）。"""
    pages = ["card.html", "popup.html", "teach.html", "gallery.html",
             "handwriting.html", "sutra-editor.html"]
    bad = []
    for name in pages:
        src = (ROOT / "src/stroke_order/web/static" / name).read_text(
            encoding="utf-8")
        if "↩ 回主頁" in src:
            bad.append(name)
        if "← 回主頁" not in src:
            bad.append(f"{name}（缺「← 回主頁」導覽）")
    assert not bad, f"回主頁導覽不統一：{bad}"


def test_info_box_stray_blues_never_return():
    """5gb：資訊提示框雜色（四種藍＋兩種底＋三種字色）已歸一 token，
    不得回流散寫。允許例外：token 定義註解行（含「歸一」字樣）。"""
    src = (ROOT / "src/stroke_order/web/static/index.html").read_text(
        encoding="utf-8")
    strays = ("#46a", "#4a90c2", "#69a", "#6998d9",
              "#f0f6ff", "#2a5a8a", "color:#235", "color:#234",
              # 5gf：模式識別色已 token 化，散寫不得回流
              "#fafaf8", "#f4f4f4", "#fff8e0", "#fafaf5", "#cc8",
              "#b09a66", "#f5fafa", "#6aa", "#8cc", "#fff8f0", "#c96",
              "#d97", "#f0fff4", "#494", "#fafaff", "#88c", "#fff8e8",
              "#c93", "#742")
    tokendef = re.compile(r"^\s*--[\w-]+\s*:\s*#")   # :root token 定義行豁免
    offenders = []
    for i, line in enumerate(src.splitlines(), 1):
        if "歸一" in line or tokendef.match(line):
            continue
        for s in strays:
            # 3 碼 hex 需防「較長 hex 的前綴」誤中（如 #494 vs #494a5b）
            if re.search(re.escape(s) + r"(?![0-9a-fA-F])", line):
                offenders.append(f"L{i}: {s}")
    assert not offenders, (
        "已 token 化的識別色散寫回流（一律引用 --info-*/--chip-*/"
        "--callout-*/--warn-bg/--decor-ink）：\n" + "\n".join(offenders))
