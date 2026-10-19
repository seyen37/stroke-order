"""使用者自訂字典 CRUD（Phase 5ak）。

W3-R1（架構健檢 Wave 3）：自 server.py create_app() 機械搬遷，行為零變。
共用 helpers 暫由 ``..server`` 匯入（R2 收斂到專屬模組）。
"""
from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel

from fastapi import File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from fastapi import APIRouter
from ...sources import CharacterNotFound
from ..responses import (
    _content_disposition,
    _safe_filename_part,
    _style_label,
)

class UserDictPostRequest(BaseModel):
    """Phase 5ak: POST /api/user-dict body. Three input formats:

    - ``format=json``        : ``strokes`` is the canonical track list
    - ``format=svg``         : ``svg_content`` is parsed by svgpathtools
    - ``format=handwriting`` : ``handwriting`` carries canvas-coord points
    """
    char: str
    format: str = "json"
    strokes: Optional[list[dict]] = None
    svg_content: Optional[str] = None
    handwriting: Optional[dict] = None


router = APIRouter()

# ------ v0.14.297 P0：公開站關閉共用字庫寫入 ------------------------
# user_dict 存在伺服器「單一」資料夾、位於 AutoSource 第一順位——本機
# 單人使用時是特性（自訂字覆蓋標準字），搬到公開網站就成了「任何訪客
# 寫一個字，所有人的字帖都換成那份筆跡」。公開部署以環境變數關閉寫入；
# 沒設＝可寫（本機行為零變）。讀取照常（字庫保持空，各模式自然落到
# 教育部／g0v 字源）。

_WRITABLE_ENV = "STROKE_ORDER_USER_DICT_WRITABLE"
_FALSE_STRINGS = {"0", "false", "no", "off", "n", "f"}

USER_DICT_READONLY_DETAIL = (
    "本站是公開網站，不保存手寫字：這份字庫會被所有訪客共用，"
    "為避免你的筆跡出現在別人的字帖裡（或反過來），寫入已關閉。"
    "練習紀錄仍會存在你自己的瀏覽器裡。"
)


def user_dict_writable() -> bool:
    raw = os.environ.get(_WRITABLE_ENV, "").strip().lower()
    return raw not in _FALSE_STRINGS


def _require_writable() -> None:
    if not user_dict_writable():
        raise HTTPException(403, detail=USER_DICT_READONLY_DETAIL)


# ------ User dictionary CRUD (Phase 5ak) ----------------------------

@router.get("/api/user-dict")
def user_dict_list():
    """Return the list of user-authored characters with previews."""
    from ...sources.user_dict import UserDictSource
    src = UserDictSource()
    chars = src.list_chars()
    return {
        "dict_dir": str(src.dict_dir),
        "writable": user_dict_writable(),
        "count": len(chars),
        "chars": [
            {
                "char": ch,
                "unicode_hex": f"{ord(ch):04x}",
                "stroke_count": len(src.get_character(ch).strokes),
            }
            for ch in chars
        ],
    }

# Phase 5ar — bulk endpoints. Registered BEFORE ``/{char}`` so FastAPI
# doesn't route ``/export`` and ``/import`` into the single-char getter.
@router.get("/api/user-dict/export")
def user_dict_export(style: str = Query("")):
    """Stream every user-dict entry as one ZIP.

    5dz: ``style`` (optional) names the download after the current 字型
    風格 — ``{風格}_手寫字.zip`` (e.g. ``楷書_手寫字.zip``). The archive
    content is unchanged (all handwriting), so one export imports into
    any 經文. Without ``style`` it keeps the dated generic name.
    """
    from datetime import datetime
    from ...sources.user_dict import UserDictSource
    src = UserDictSource()
    zip_bytes = src.export_zip_bytes()
    if style:
        basename = f"{_safe_filename_part(_style_label(style))}_手寫字"
        disposition = _content_disposition(basename, "zip")
    else:
        stamp = datetime.now().strftime("%Y%m%d")
        disposition = f'attachment; filename="stroke-order-user-dict-{stamp}.zip"'
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": disposition},
    )

@router.get("/api/user-dict/font")
def user_dict_font(
    weight: float = Query(120.0, gt=0, le=400,
                          description="R3：筆畫全寬（EM2048；經 R1a 密度補償）"),
    cap: str = Query("round", pattern="^(round|square)$",
                     description="筆畫端頭：round=手寫感圓頭、square=方頭"),
    owner: str = Query("", max_length=40,
                       description="書寫者名字（進字型著作權標注；可留空）"),
):
    """R3：把使用者的手寫字打包成可安裝的 TrueType 字型檔。

    字集**只含寫過的字**（sign-off）——字型裡每個字形都是本人手寫，沒寫
    過的字顯示 .notdef（字型的正常行為，也是「純手寫」的誠實保證）。
    字形著作權歸書寫者本人，name table 寫明。
    """
    from ...exporters.handfont import HandFontUnavailable, build_hand_font
    from ...sources.user_dict import UserDictSource

    src = UserDictSource()
    written = src.list_chars()
    if not written:
        raise HTTPException(
            400, detail="還沒有任何手寫字——先在手寫練習或罕用字管理寫幾個字")
    chars = [src.get_character(ch) for ch in written]
    try:
        ttf = build_hand_font(chars, weight=weight, cap=cap,
                              owner=owner or None)
    except HandFontUnavailable as e:   # pragma: no cover — fonttools 必要相依
        raise HTTPException(503, detail=str(e)) from e
    basename = f"{_safe_filename_part(owner) + '_' if owner else ''}手寫字型"
    return Response(
        content=ttf,
        media_type="font/ttf",
        headers={
            "Content-Disposition": _content_disposition(basename, "ttf"),
            "X-Hand-Font-Chars": str(len(chars)),
        },
    )

# ------ v0.14.297 P1：無狀態手寫字型 POST /api/handfont --------------
# 筆跡在請求裡、字型在回應裡——伺服器**不落地任何東西**（P0 關了共用
# 字庫；個人手寫的正解是資料留在使用者瀏覽器）。上限依實測：沙箱 100 字
# 6.1s／200 字 12.2s、RSS +60MB；Render 免費層 CPU 慢數倍，故 100 字。
# 端點 sync def（重 CPU 走 threadpool，不凍 event loop——5ck 教訓），並在
# server.py 掛進渲染閘門（同時 ≤2）。

HANDFONT_MAX_CHARS = 100
HANDFONT_MAX_STROKES_PER_CHAR = 64
HANDFONT_MAX_POINTS_PER_STROKE = 2000
HANDFONT_MAX_TOTAL_POINTS = 200_000
HANDFONT_MAX_BODY_BYTES = 6 * 1024 * 1024
# 座標以 EM 2048 為框；容許寫出框一些（手寫常超格），但擋荒謬值
HANDFONT_COORD_MIN, HANDFONT_COORD_MAX = -1024.0, 3072.0


class HandFontRequest(BaseModel):
    """``chars``：{字: [筆畫, ...]}，筆畫＝``[[x, y], ...]``（EM 2048）。"""
    chars: dict[str, list[list[list[float]]]]
    weight: float = 120.0
    cap: str = "round"
    owner: str = ""


def _validate_handfont_char(ch: str) -> None:
    import unicodedata
    if len(ch) != 1:
        raise HTTPException(422, detail=f"每個鍵必須是單一個字，收到 {ch!r}")
    if unicodedata.category(ch)[0] in ("C", "Z"):
        raise HTTPException(
            422, detail=f"U+{ord(ch):04X} 是空白或控制字元，不能做成字形")


def _handfont_tracks(ch: str, strokes: list) -> list[dict]:
    import math
    if len(strokes) > HANDFONT_MAX_STROKES_PER_CHAR:
        raise HTTPException(
            413, detail=f"「{ch}」筆畫數 {len(strokes)} 超過上限 "
                        f"{HANDFONT_MAX_STROKES_PER_CHAR}")
    out = []
    for s in strokes:
        if len(s) > HANDFONT_MAX_POINTS_PER_STROKE:
            raise HTTPException(
                413, detail=f"「{ch}」單一筆畫點數超過上限 "
                            f"{HANDFONT_MAX_POINTS_PER_STROKE}")
        track = []
        for p in s:
            if len(p) != 2:
                raise HTTPException(422, detail=f"「{ch}」座標必須是 [x, y]")
            x, y = float(p[0]), float(p[1])
            if not (math.isfinite(x) and math.isfinite(y)):
                raise HTTPException(422, detail=f"「{ch}」含非數值座標")
            if not (HANDFONT_COORD_MIN <= x <= HANDFONT_COORD_MAX
                    and HANDFONT_COORD_MIN <= y <= HANDFONT_COORD_MAX):
                raise HTTPException(
                    422, detail=f"「{ch}」座標超出範圍（EM 2048 座標系）")
            track.append([x, y])
        if len(track) >= 2:          # 單點輕觸不算筆畫（同 handwriting_to_strokes）
            out.append({"track": track})
    if not out:
        raise HTTPException(422, detail=f"「{ch}」沒有有效筆畫（每筆至少 2 點）")
    return out


@router.post("/api/handfont")
def handfont_post(req: HandFontRequest, request: Request):
    """P1：把請求裡的手寫筆跡做成可安裝的 TrueType 字型，**不保存任何資料**。

    與 ``GET /api/user-dict/font`` 同一顆引擎（R3：純手寫字集、著作權歸
    書寫者），差別只在資料來源：這裡的筆跡來自請求本體（使用者瀏覽器裡
    的練習紀錄），處理完即丟，不經任何字庫。
    """
    from ...exporters.handfont import HandFontUnavailable, build_hand_font
    from ...sources.user_dict import character_from_strokes

    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > HANDFONT_MAX_BODY_BYTES:
        raise HTTPException(413, detail="請求太大（上限 6 MB）")
    if not (0 < req.weight <= 400):
        raise HTTPException(422, detail="weight 必須在 0～400 之間")
    if req.cap not in ("round", "square"):
        raise HTTPException(422, detail="cap 必須是 round 或 square")
    if len(req.owner) > 40:
        raise HTTPException(422, detail="owner 最多 40 字")
    if not req.chars:
        raise HTTPException(400, detail="還沒有任何手寫字——先寫幾個字")
    if len(req.chars) > HANDFONT_MAX_CHARS:
        raise HTTPException(
            413, detail=f"一次最多 {HANDFONT_MAX_CHARS} 個字（收到 {len(req.chars)}）")
    total = sum(len(s) for strokes in req.chars.values() for s in strokes)
    if total > HANDFONT_MAX_TOTAL_POINTS:
        raise HTTPException(413, detail="筆跡總點數超過上限，請分批產生")

    chars = []
    for ch, strokes in req.chars.items():
        _validate_handfont_char(ch)
        chars.append(character_from_strokes(ch, _handfont_tracks(ch, strokes)))
    try:
        ttf = build_hand_font(chars, weight=req.weight, cap=req.cap,
                              owner=req.owner or None)
    except HandFontUnavailable as e:   # pragma: no cover — fonttools 必要相依
        raise HTTPException(503, detail=str(e)) from e
    basename = (f"{_safe_filename_part(req.owner) + '_' if req.owner else ''}"
                "手寫字型")
    return Response(
        content=ttf,
        media_type="font/ttf",
        headers={
            "Content-Disposition": _content_disposition(basename, "ttf"),
            "X-Hand-Font-Chars": str(len(chars)),
            "Cache-Control": "no-store",
        },
    )


@router.post("/api/user-dict/import")
def user_dict_import(
    file: UploadFile = File(...),
    policy: str = Form("skip"),
):
    """Restore characters from a ZIP. ``policy`` is ``skip`` or ``replace``."""
    from ...sources.user_dict import UserDictSource
    _require_writable()
    if policy not in ("skip", "replace"):
        raise HTTPException(
            422, detail=f"policy must be 'skip' or 'replace', got {policy!r}",
        )
    try:
        zip_bytes = file.file.read()
    except Exception as e:   # pragma: no cover
        raise HTTPException(400, detail=f"failed to read upload: {e}") from e
    src = UserDictSource()
    try:
        summary = src.import_zip_bytes(zip_bytes, policy=policy)
    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from e
    # 5dq：使用者字庫變動後，清 make_source 快取——否則已建的
    # AutoSource 內 UserDictSource 讀不到新匯入的字（見 __init__.py）。
    from ...sources import reset_source_cache
    reset_source_cache()
    return summary

@router.get("/api/user-dict/{char}")
def user_dict_get(char: str):
    from ...sources.user_dict import UserDictSource
    if len(char) != 1:
        raise HTTPException(400, detail="char must be a single character")
    src = UserDictSource()
    try:
        c = src.get_character(char)
    except CharacterNotFound as e:
        raise HTTPException(404, detail=str(e)) from e
    return {
        "char": c.char,
        "unicode_hex": c.unicode_hex,
        "data_source": c.data_source,
        "strokes": [
            {
                "track": [[p.x, p.y] for p in s.raw_track],
                "kind_code": s.kind_code,
                "kind_name": s.kind_name,
                "has_hook": s.has_hook,
            }
            for s in c.strokes
        ],
    }

@router.post("/api/user-dict")
def user_dict_post(req: UserDictPostRequest):
    """Add or replace a user-dict entry. Three input formats:

    - ``json``        : ``strokes`` is the canonical track list
    - ``svg``         : ``svg_content`` is parsed via svgpathtools
    - ``handwriting`` : ``handwriting`` carries canvas-coord points
    """
    from ...sources.user_dict import (
        UserDictSource, handwriting_to_strokes, svg_to_strokes,
    )
    _require_writable()
    if len(req.char) != 1:
        raise HTTPException(400, detail="char must be a single character")

    if req.format == "json":
        if not req.strokes:
            raise HTTPException(
                400, detail="format=json needs strokes=[{track:...}, ...]")
        strokes = req.strokes
    elif req.format == "svg":
        if not req.svg_content:
            raise HTTPException(400, detail="format=svg needs svg_content")
        try:
            strokes = svg_to_strokes(req.svg_content)
        except ValueError as e:
            raise HTTPException(400, detail=f"SVG parse: {e}") from e
    elif req.format == "handwriting":
        hw = req.handwriting or {}
        try:
            strokes = handwriting_to_strokes(
                hw.get("strokes") or [],
                canvas_width=float(hw.get("canvas_width", 0)),
                canvas_height=float(hw.get("canvas_height", 0)),
            )
        except (ValueError, TypeError) as e:
            raise HTTPException(400, detail=f"handwriting: {e}") from e
    else:
        raise HTTPException(
            400,
            detail=f"unknown format {req.format!r}; "
                   "expected json/svg/handwriting",
        )

    src = UserDictSource()
    try:
        path = src.save_character(req.char, strokes=strokes)
    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from e
    # 5dq：使用者字庫變動後，清 make_source 快取——否則已建的
    # AutoSource 內 UserDictSource 讀不到新寫入的字（見 __init__.py）。
    from ...sources import reset_source_cache
    reset_source_cache()
    return {
        "char": req.char,
        "unicode_hex": f"{ord(req.char):04x}",
        "stroke_count": len(strokes),
        "path": str(path),
    }

@router.delete("/api/user-dict/{char}")
def user_dict_delete(char: str):
    from ...sources.user_dict import UserDictSource
    _require_writable()
    if len(char) != 1:
        raise HTTPException(400, detail="char must be a single character")
    src = UserDictSource()
    if not src.delete_character(char):
        raise HTTPException(
            404, detail=f"no user-dict entry for U+{ord(char):04X}")
    # 5dq：使用者字庫變動後，清 make_source 快取——否則已建的
    # AutoSource 內 UserDictSource 仍回傳已刪的字（見 __init__.py）。
    from ...sources import reset_source_cache
    reset_source_cache()
    return {"deleted": char, "unicode_hex": f"{ord(char):04x}"}
