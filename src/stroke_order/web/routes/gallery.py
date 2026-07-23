"""公眾分享庫（gallery）——magic-link auth／個人資料／頭像／上傳分享。

W3-R1（架構健檢 Wave 3）：自 server.py create_app() 機械搬遷，行為零變。
共用 helpers 暫由 ``..server`` 匯入（R2 收斂到專屬模組）。
"""
from __future__ import annotations

from pydantic import BaseModel

from fastapi import File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from typing import Optional
from fastapi import APIRouter
from ..char_pipeline import build_mandala_char_loader
from ..responses import SVG_MEDIA_TYPE
from ..versioning import STATIC_DIR, _versioned_page

class GalleryLoginRequest(BaseModel):
    email: str


class GalleryProfilePatch(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None


router = APIRouter()

# =================================================================
# Phase 5g — 公眾分享庫 (gallery)
# =================================================================
#
# Auth: magic-link via email, session cookie. All endpoints under
# /api/gallery/* except auth/*.  The browser identifies itself with
# the `psd_session` cookie, which we look up in the gallery's
# SQLite DB. Anonymous read of the public list is allowed; uploads
# / profile edits require a valid session.

from fastapi import Cookie, Request
from fastapi.responses import RedirectResponse
from ... import gallery as _gallery
from ...gallery.auth import (
    make_login_token, magic_link_url, consume_login_token,
    create_session, get_session_user, invalidate_session,
    purge_expired,
)
from ...gallery.smtp import send_magic_link_email
from ...gallery import service as gallery_service

SESSION_COOKIE = "psd_session"

def _resolve_user(session_token: Optional[str]):
    """Returns user dict or None. Reusable across endpoints."""
    return get_session_user(session_token)

def _require_user(session_token: Optional[str]):
    user = _resolve_user(session_token)
    if user is None:
        raise HTTPException(401, detail="請先登入")
    return user

def _gallery_error_to_http(exc: gallery_service.GalleryError):
    raise HTTPException(exc.code, detail=str(exc))

def on_boot() -> None:
    """Best-effort sweep on app boot — keeps the auth tables tidy.

    由 create_app() 每次呼叫（保留拆檔前行為：每建一個 app 掃一次）。
    """
    try:
        purge_expired()
    except Exception:
        pass  # never fatal

# ----- /gallery (SPA shell) ----------------------------------------

@router.get("/gallery", include_in_schema=False)
def gallery_page():
    page = STATIC_DIR / "gallery.html"
    if not page.is_file():
        return PlainTextResponse(
            "Gallery page missing — static/gallery.html not bundled.",
            status_code=404,
        )
    # 5fo：改走版本注入（?v=__V__ → APP_VERSION）——與 / /card /handwriting
    # 同款；本頁先前走 FileResponse＝佔位符原樣吐出、標籤手刻卡版（§57）。
    return _versioned_page(page)

# ----- magic-link auth ---------------------------------------------

@router.post("/api/gallery/auth/request-login")
async def gallery_auth_request_login(req: GalleryLoginRequest):
    email = (req.email or "").strip()
    if "@" not in email or len(email) > 200:
        raise HTTPException(422, detail="email 格式錯誤")
    try:
        token = make_login_token(email)
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    url = magic_link_url(token)
    try:
        await send_magic_link_email(email, url)
    except RuntimeError as e:
        # SMTP not configured + not in dev mode — surface clearly
        raise HTTPException(500, detail=str(e))
    return {"ok": True, "message": "登入連結已寄出，請查收信箱"}

@router.get("/api/gallery/auth/consume", include_in_schema=False)
def gallery_auth_consume(token: str = Query(...)):
    user_id = consume_login_token(token)
    if user_id is None:
        return PlainTextResponse(
            "登入連結無效或已過期。請回到登入頁重新申請。",
            status_code=400,
        )
    session_token = create_session(user_id)
    # Redirect to the gallery SPA, with the session cookie set.
    resp = RedirectResponse(url="/gallery", status_code=303)
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=session_token,
        max_age=30 * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=False,    # dev convenience; production should
                         # be set via reverse proxy header
    )
    return resp

@router.post("/api/gallery/auth/logout")
def gallery_auth_logout(
    psd_session: Optional[str] = Cookie(default=None),
):
    invalidate_session(psd_session)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE)
    return resp

# ----- profile -----------------------------------------------------

@router.get("/api/gallery/me")
def gallery_me(
    psd_session: Optional[str] = Cookie(default=None),
):
    user = _resolve_user(psd_session)
    if user is None:
        return {"logged_in": False}
    return {"logged_in": True, "user": user}

@router.put("/api/gallery/me")
def gallery_me_update(
    patch: GalleryProfilePatch,
    psd_session: Optional[str] = Cookie(default=None),
):
    user = _require_user(psd_session)
    try:
        updated = gallery_service.update_profile(
            user_id=user["id"],
            display_name=patch.display_name,
            bio=patch.bio,
        )
    except gallery_service.GalleryError as e:
        _gallery_error_to_http(e)
    return {"user": updated}

# ----- public profile (Phase 5b r29d) ------------------------------

@router.get("/api/gallery/users/{user_id}")
def gallery_user_profile(user_id: int):
    """Public user profile + stats（任何人都可看，不需登入）。"""
    try:
        return gallery_service.get_user_profile(user_id)
    except gallery_service.GalleryError as e:
        _gallery_error_to_http(e)

# ----- avatar (Phase 5b r29j) --------------------------------------

@router.post("/api/gallery/me/avatar")
def gallery_me_avatar_upload(
    file: UploadFile = File(...),
    psd_session: Optional[str] = Cookie(default=None),
):
    """Upload / replace own avatar (PNG / JPEG，max 2MB raw)。"""
    user = _require_user(psd_session)
    # FastAPI UploadFile.read() async；type 從 content_type
    file_bytes = file.file.read()
    try:
        updated = gallery_service.update_avatar(
            user_id=user["id"],
            file_bytes=file_bytes,
            content_type=file.content_type or "",
        )
    except gallery_service.GalleryError as e:
        _gallery_error_to_http(e)
    return {"user": updated}

@router.delete("/api/gallery/me/avatar")
def gallery_me_avatar_delete(
    psd_session: Optional[str] = Cookie(default=None),
):
    """Remove own avatar — fall back to initials display。"""
    user = _require_user(psd_session)
    try:
        updated = gallery_service.clear_avatar(user_id=user["id"])
    except gallery_service.GalleryError as e:
        _gallery_error_to_http(e)
    return {"user": updated}

@router.get("/api/gallery/users/{user_id}/avatar")
def gallery_user_avatar_get(user_id: int):
    """Serve avatar PNG file. 404 if user has no avatar uploaded.

    Cache header `max-age=86400` 但 client 用 ?v=<nonce> URL 強制
    revalidate（nonce 換了就 URL 換 → 新 fetch）。
    """
    target = gallery_service._avatar_path_on_disk(user_id)
    if not target.exists():
        raise HTTPException(404, detail="無 avatar")
    return FileResponse(
        target, media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400, immutable"},
    )

# ----- uploads -----------------------------------------------------

@router.get("/api/gallery/uploads")
def gallery_uploads_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    # Phase 5b r28: 可選 kind filter (psd / mandala)；未傳 = 全部
    kind: Optional[str] = Query(
        None, pattern="^(psd|mandala)$",
        description="upload 種類 filter；未傳列出全部",
    ),
    # Phase 5b r29b/r29c: sort 選項
    sort: str = Query(
        "newest", pattern="^(newest|likes|hot)$",
        description="排序：newest (default) / likes / hot (r29c 加 hot)",
    ),
    # Phase 5b r29b: 「我的收藏」filter — 只列當前 user 已 bookmark 的 upload
    bookmarked: bool = Query(
        False,
        description="True 時只列當前 user 已 bookmark 的 upload（需登入）",
    ),
    # Phase 5b r29c: text search
    q: Optional[str] = Query(
        None, max_length=100,
        description="search query：比對 title / comment / uploader email / display_name",
    ),
    # Phase 5b r29d: user_id filter (profile page — 只列指定 user 的 uploads)
    user_id: Optional[int] = Query(
        None, ge=1, description="只列指定 user 的 uploads（profile filter）",
    ),
    # Phase 5b r29: 從 cookie 拿 user，list 內每 item 加 liked_by_me
    psd_session: Optional[str] = Cookie(default=None),
):
    viewer = _resolve_user(psd_session)
    # r29b: bookmarked=true 需登入（否則沒 user 也沒 filter 對象）
    bookmarked_by = None
    if bookmarked:
        if viewer is None:
            raise HTTPException(401, detail="?bookmarked=true 需先登入")
        bookmarked_by = viewer["id"]
    try:
        return gallery_service.list_uploads(
            page=page, size=size, kind=kind,
            viewer_user_id=(viewer["id"] if viewer else None),
            sort=sort,
            bookmarked_by=bookmarked_by,
            q=q,
            user_id=user_id,
        )
    except gallery_service.GalleryError as e:
        _gallery_error_to_http(e)

@router.post("/api/gallery/uploads")
def gallery_uploads_create(
    file: UploadFile = File(...),
    title: str = Form(...),
    comment: str = Form(""),
    # Phase 5b r28: kind 表單欄位；default 'psd' 給既有 PSD 上傳保留向後相容
    kind: str = Form("psd"),
    psd_session: Optional[str] = Cookie(default=None),
):
    user = _require_user(psd_session)
    content = file.file.read()
    # Phase 5b r28d: 用 state-aware loader factory，loader 跟 user 在
    # mandala 模式看到的字體一致（讀 state.style.font / source /
    # cns_outline_mode）。State 缺欄位 fall back 到 server default。
    upload_loader_factory = None
    if kind == "mandala":
        def upload_loader_factory(state):
            s = (state.get("style") or {}) if isinstance(state, dict) else {}
            return build_mandala_char_loader(
                style=str(s.get("font", "kaishu")),
                source=str(s.get("source", "auto")),
                cns_outline_mode=str(s.get("cns_outline_mode", "skip")),
            )
    try:
        record = gallery_service.create_upload(
            user_id=user["id"],
            content_bytes=content,
            filename=file.filename,
            title=title,
            comment=comment,
            kind=kind,
            char_loader_factory=upload_loader_factory,
        )
    except gallery_service.GalleryError as e:
        _gallery_error_to_http(e)
    return {"upload": record}

@router.get("/api/gallery/uploads/{upload_id}")
def gallery_uploads_get(
    upload_id: int,
    psd_session: Optional[str] = Cookie(default=None),
):
    try:
        upload = gallery_service.get_upload(upload_id)
    except gallery_service.GalleryError as e:
        _gallery_error_to_http(e)
    # r29 / r29b: 若 user 登入，加 liked_by_me + bookmarked_by_me
    user = _resolve_user(psd_session)
    if user is not None:
        info = gallery_service.get_like_info(
            upload_id=upload_id, user_id=user["id"])
        upload["liked_by_me"] = info["liked_by_me"]
        upload["bookmarked_by_me"] = gallery_service.is_bookmarked_by(
            upload_id=upload_id, user_id=user["id"])
    else:
        upload["liked_by_me"] = False
        upload["bookmarked_by_me"] = False
    return {"upload": upload}

@router.get("/api/gallery/uploads/{upload_id}/download")
def gallery_uploads_download(upload_id: int):
    try:
        upload = gallery_service.get_upload(upload_id)
    except gallery_service.GalleryError as e:
        _gallery_error_to_http(e)
    if upload.get("hidden"):
        raise HTTPException(403, detail="這份檔案目前隱藏中")
    path = gallery_service.absolute_path_of(upload)
    if not path.is_file():
        raise HTTPException(
            500,
            detail="檔案在伺服器上遺失（DB 紀錄存在但實體檔不見）",
        )
    # Phase 5b r28: kind-aware filename + media_type
    kind = upload.get("kind") or "psd"
    ext_map = {"psd": ".json", "mandala": ".md"}  # mandala 多數是 md
    # 真實副檔名從 file_path 抓（mandala 可能是 .svg）
    real_ext = ""
    try:
        real_ext = "." + str(upload.get("file_path", "")).rsplit(".", 1)[-1]
    except Exception:
        real_ext = ext_map.get(kind, ".bin")
    if real_ext not in (".json", ".md", ".svg"):
        real_ext = ext_map.get(kind, ".bin")
    media_map = {
        ".json": "application/json",
        ".md":   "text/markdown",
        ".svg":  SVG_MEDIA_TYPE,
    }
    media_type = media_map.get(real_ext, "application/octet-stream")
    nice_name = (upload.get("filename") or
                 f"{kind}_{upload_id}{real_ext}")
    return FileResponse(
        path,
        media_type=media_type,
        filename=nice_name,
    )

# Phase 5b r29: like toggle endpoint（需登入）
@router.post("/api/gallery/uploads/{upload_id}/like")
def gallery_uploads_like(
    upload_id: int,
    psd_session: Optional[str] = Cookie(default=None),
):
    user = _require_user(psd_session)
    try:
        result = gallery_service.toggle_like(
            user_id=user["id"], upload_id=upload_id,
        )
    except gallery_service.GalleryError as e:
        _gallery_error_to_http(e)
    return result

# Phase 5b r29b: bookmark toggle endpoint（需登入）
@router.post("/api/gallery/uploads/{upload_id}/bookmark")
def gallery_uploads_bookmark(
    upload_id: int,
    psd_session: Optional[str] = Cookie(default=None),
):
    user = _require_user(psd_session)
    try:
        result = gallery_service.toggle_bookmark(
            user_id=user["id"], upload_id=upload_id,
        )
    except gallery_service.GalleryError as e:
        _gallery_error_to_http(e)
    return result

# Phase 5b r28b: thumbnail endpoint（mandala+svg upload 才有；其他回 404）
@router.get("/api/gallery/uploads/{upload_id}/thumbnail")
def gallery_uploads_thumbnail(upload_id: int):
    try:
        upload = gallery_service.get_upload(upload_id)
    except gallery_service.GalleryError as e:
        _gallery_error_to_http(e)
    if upload.get("hidden"):
        raise HTTPException(403, detail="這份檔案目前隱藏中")
    thumb_path = gallery_service.thumbnail_path_of(upload)
    if not thumb_path.is_file():
        # PSD 永遠沒 thumbnail；mandala+md 也沒 — 都 404 給 frontend
        # 用 onerror 隱藏 img tag
        raise HTTPException(404, detail="thumbnail 不存在")
    return FileResponse(
        thumb_path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )

@router.delete("/api/gallery/uploads/{upload_id}")
def gallery_uploads_delete(
    upload_id: int,
    psd_session: Optional[str] = Cookie(default=None),
):
    user = _require_user(psd_session)
    try:
        gallery_service.delete_upload(
            upload_id=upload_id, user_id=user["id"],
        )
    except gallery_service.GalleryError as e:
        _gallery_error_to_http(e)
    return {"ok": True}
