"""W3-R1：路由分組套件——七群 APIRouter（機械搬遷自 server.py）。

include 順序＝拆檔前路由註冊順序（Starlette 依註冊序匹配）。
"""
from __future__ import annotations


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
    """延遲 import：routes 模組需要 ``..server`` 的模組頭 helpers，
    server.create_app() 又要 include 這裡的 router——模組層互相 import
    會循環。create_app 呼叫時 server 模組已初始化完畢，屆時再載入即可。
    （R2 把共用 helpers 移出 server 後可改回模組層 import。）
    """
    from . import pages, meta, modes_text, modes_art, user_dict, sutra, gallery
    return [
        pages.router,
        meta.router,
        modes_text.router,
        modes_art.router,
        user_dict.router,
        sutra.router,
        gallery.router,
    ]
