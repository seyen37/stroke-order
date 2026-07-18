"""路由分組套件——七群 APIRouter（W3-R1 機械搬遷、W3-R2 去重複）。

include 順序＝拆檔前路由註冊順序（Starlette 依註冊序匹配）。
R2 起共用 helpers 住 ``..char_pipeline``／``..responses``／
``..versioning``——routes 不再 import ``..server``，循環已解，
一律正常模組層 import。
"""
from __future__ import annotations

from . import gallery, meta, modes_art, modes_text, pages, sutra, user_dict


def iter_routes(router_or_app):
    """遞迴走訪路由樹，攤平吐出每條「葉端」路由。

    FastAPI 0.139 的 ``include_router`` 是巢狀掛載（``_IncludedRouter``）
    而非攤平合併——直接迭代 ``app.routes`` 只會看到七個容器。所有要
    introspect 路由的程式（async 回歸鎖、路由快照）一律走這裡。
    Mount（如 /static）本身也會吐出（呼叫端自行判別型別）。
    """
    for r in router_or_app.routes:
        inner = getattr(r, "original_router", None)   # _IncludedRouter
        if inner is None and getattr(r, "routes", None):
            inner = r                                  # 一般巢狀 router
        if inner is not None:
            yield from iter_routes(inner)
        else:
            yield r


def all_routers():
    """七群 router，依拆檔前註冊順序。"""
    return [
        pages.router,
        meta.router,
        modes_text.router,
        modes_art.router,
        user_dict.router,
        sutra.router,
        gallery.router,
    ]
