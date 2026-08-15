"""W3-R1（架構健檢 Wave 3）：路由清單快照回歸鎖。

拆 APIRouter 是「機械搬遷、行為零變」——最直接的鎖就是：拆前後
(method, path) 全集必須一字不差。任何路由的增刪改都得先來改這份
快照（並在 commit 訊息說明），防止搬遷過程默默掉路由或改路徑。

快照產生方式（拆檔前於 2bd06a6 實跑）：
    for r in create_app().routes: 收集 (method, path)；HEAD/OPTIONS
    為 FastAPI 自動附帶、不入快照；mount 記為 ("MOUNT", path)。
"""
from __future__ import annotations

from stroke_order.web.server import create_app

# 拆檔前基準（2bd06a6，0.14.229）：92 條
ROUTE_SNAPSHOT = {
    ("GET", "/"),
    ("POST", "/api/card/pdf"),
    ("GET", "/popup"),
    ("POST", "/api/popup/svg"),
    ("GET", "/teach"),
    ("GET", "/api/radical-info/{char}"),
    ("GET", "/api/dict/{char}"),
    ("GET", "/api/character/{char}"),
    ("GET", "/api/cns-status"),
    ("GET", "/api/cns-stroke-diagnostics/{char}"),
    ("GET", "/api/components/{char}"),
    ("GET", "/api/components/{char}/family"),
    ("POST", "/api/coverage/recommend"),
    ("GET", "/api/coverset/list"),
    ("GET", "/api/coverset/{name}"),
    ("GET", "/api/decompose/{char}"),
    ("POST", "/api/doodle"),
    ("GET", "/api/export/{char}"),
    # 5fx: 檢舉＋管理端
    ("GET", "/api/gallery/admin/reports"),
    ("POST", "/api/gallery/admin/uploads/{upload_id}/hide"),
    ("POST", "/api/gallery/admin/users/{user_id}/moderation"),
    ("GET", "/api/gallery/auth/consume"),
    ("POST", "/api/gallery/auth/logout"),
    ("POST", "/api/gallery/auth/request-login"),
    ("GET", "/api/gallery/me"),
    ("GET", "/api/gallery/report-challenge"),
    ("PUT", "/api/gallery/me"),
    ("DELETE", "/api/gallery/me/avatar"),
    ("POST", "/api/gallery/me/avatar"),
    ("GET", "/api/gallery/uploads"),
    ("POST", "/api/gallery/uploads"),
    ("DELETE", "/api/gallery/uploads/{upload_id}"),
    ("GET", "/api/gallery/uploads/{upload_id}"),
    ("POST", "/api/gallery/uploads/{upload_id}/bookmark"),
    ("GET", "/api/gallery/uploads/{upload_id}/download"),
    ("POST", "/api/gallery/uploads/{upload_id}/like"),
    ("POST", "/api/gallery/uploads/{upload_id}/report"),
    ("GET", "/api/gallery/uploads/{upload_id}/thumbnail"),
    ("GET", "/api/gallery/users/{user_id}"),
    ("GET", "/api/gallery/users/{user_id}/avatar"),
    ("GET", "/api/grid"),
    ("GET", "/api/handwriting/reference/{char}"),
    ("GET", "/api/health"),
    ("GET", "/api/kaishu-status"),
    ("GET", "/api/letter"),
    ("GET", "/api/letter/capacity"),
    ("GET", "/api/lishu-status"),
    ("GET", "/api/mandala"),
    ("GET", "/api/mandala/presets"),
    ("GET", "/api/manuscript"),
    ("GET", "/api/manuscript/capacity"),
    ("GET", "/api/meta/{char}"),
    ("GET", "/api/notebook"),
    ("POST", "/api/notebook"),
    ("GET", "/api/notebook/capacity"),
    ("GET", "/api/patch"),
    ("POST", "/api/patch"),
    ("GET", "/api/patch/capacity"),
    ("GET", "/api/radical-route"),
    ("GET", "/api/seal-status"),
    ("GET", "/api/song-status"),
    ("GET", "/api/stamp"),
    ("POST", "/api/stamp"),
    ("GET", "/api/stamp/capacity"),
    ("GET", "/api/stencil"),
    ("GET", "/api/sutra"),
    ("POST", "/api/sutra"),
    ("DELETE", "/api/sutra/builtin/{key}"),
    ("GET", "/api/sutra/builtin/{key}"),
    ("PUT", "/api/sutra/builtin/{key}"),
    ("GET", "/api/sutra/capacity"),
    ("GET", "/api/sutra/categories"),
    ("GET", "/api/sutra/closing-templates"),
    ("GET", "/api/sutra/pdf"),
    ("GET", "/api/sutra/presets"),
    ("GET", "/api/sutra/text/{preset}"),
    ("POST", "/api/sutra/upload"),
    ("DELETE", "/api/sutra/user/{key}"),
    ("GET", "/api/sutra/user/{key}"),
    ("PUT", "/api/sutra/user/{key}"),
    ("GET", "/api/user-dict"),
    ("POST", "/api/user-dict"),
    ("GET", "/api/user-dict/export"),
    ("POST", "/api/user-dict/import"),
    ("DELETE", "/api/user-dict/{char}"),
    ("GET", "/api/user-dict/{char}"),
    ("GET", "/api/wordart"),
    ("GET", "/api/wordart/capacity"),
    ("GET", "/api/zentangle/outline"),
    ("GET", "/api/zentangle/sources"),
    ("GET", "/card"),
    ("GET", "/docs"),
    ("GET", "/docs/oauth2-redirect"),
    ("GET", "/gallery"),
    ("GET", "/handwriting"),
    ("GET", "/openapi.json"),
    ("GET", "/redoc"),
    ("MOUNT", "/static"),
    ("GET", "/sutra-editor"),
    ("GET", "/vendor/opencv.js"),
    ("GET", "/vendor/opentype.min.js"),
    ("GET", "/vendor/status"),
}


def _current_routes() -> set[tuple[str, str]]:
    from stroke_order.web.routes import iter_routes

    app = create_app()
    routes: set[tuple[str, str]] = set()
    for r in iter_routes(app):
        path = getattr(r, "path", None)
        if path is None:
            continue
        methods = getattr(r, "methods", None)
        if methods:
            for m in methods - {"HEAD", "OPTIONS"}:
                routes.add((m, path))
        else:
            routes.add(("MOUNT", path))
    return routes


def test_route_set_matches_snapshot():
    current = _current_routes()
    missing = ROUTE_SNAPSHOT - current
    extra = current - ROUTE_SNAPSHOT
    assert not missing and not extra, (
        f"路由集合偏離快照——遺失：{sorted(missing)}；多出：{sorted(extra)}。"
        "若為刻意增刪路由，請同步更新本快照並於 commit 訊息說明。"
    )
