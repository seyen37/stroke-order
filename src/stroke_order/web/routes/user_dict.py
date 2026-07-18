"""使用者自訂字典 CRUD（Phase 5ak）。

W3-R1（架構健檢 Wave 3）：自 server.py create_app() 機械搬遷，行為零變。
共用 helpers 暫由 ``..server`` 匯入（R2 收斂到專屬模組）。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from fastapi import File, Form, HTTPException, Query, UploadFile
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

# ------ User dictionary CRUD (Phase 5ak) ----------------------------

@router.get("/api/user-dict")
def user_dict_list():
    """Return the list of user-authored characters with previews."""
    from ...sources.user_dict import UserDictSource
    src = UserDictSource()
    chars = src.list_chars()
    return {
        "dict_dir": str(src.dict_dir),
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

@router.post("/api/user-dict/import")
def user_dict_import(
    file: UploadFile = File(...),
    policy: str = Form("skip"),
):
    """Restore characters from a ZIP. ``policy`` is ``skip`` or ``replace``."""
    from ...sources.user_dict import UserDictSource
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
