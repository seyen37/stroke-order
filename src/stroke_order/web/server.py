"""
FastAPI backend for the local Web UI.

Endpoints
---------

- ``GET  /``                    — serve index.html
- ``GET  /api/character/{ch}`` — hanzi-writer-compatible JSON for `ch`
- ``GET  /api/meta/{ch}``      — diagnostic metadata (stroke kinds, bbox,
                                  validation warnings, signature)
- ``GET  /api/export/{ch}``    — file download; ``?format=svg|gcode|json``
- ``GET  /static/…``           — static assets (JS, CSS)

Query params shared by /api/character, /api/meta, /api/export:

    source=g0v|mmh|auto      (default auto)
    hook_policy=animation|static (default animation)
    char_size=<float mm>     (gcode only; default 20)
    feed_rate=<int>          (gcode only; default 3000)

Run with::

    stroke-order serve --port 8000
    # then open http://localhost:8000/
"""
from __future__ import annotations

import hashlib
from collections import OrderedDict

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from .. import cache_bus
from .routes import all_routers as _all_routers
from .routes import gallery as _routes_gallery
from .versioning import STATIC_DIR, _VersionedStaticFiles


# ---------------------------------------------------------------------------
# 5eu（架構健檢 W2）：重渲染回應快取常數。模組層以便測試 monkeypatch。
# 可快取＝GET 且輸出完全由 query 決定的渲染/資料端點；gallery/認證類刻意
# 不在列。資料異動入口有二：HTTP 變更端點（下方 MUTATING 前綴，middleware
# 自己看得到）與直接呼叫 reset_*_singleton()（測試換字型）——後者經
# cache_bus.bump() 通知，epoch 納入快取 key 即自然失效。
RENDER_CACHE_PREFIXES = (
    "/api/sutra", "/api/grid", "/api/notebook", "/api/letter",
    "/api/manuscript", "/api/wordart", "/api/mandala", "/api/patch",
    "/api/stamp", "/api/stencil", "/api/export",
    "/api/handwriting/reference",
)
RENDER_CACHE_MUTATING_PREFIXES = (
    "/api/user-dict", "/api/sutra/upload", "/api/sutra/user",
    "/api/sutra/builtin",
)
RENDER_CACHE_MAX_ITEM = 4 * 1024 * 1024    # 單條上限（篆書整頁 ~3.4MB）
RENDER_CACHE_MAX_TOTAL = 48 * 1024 * 1024  # 總預算（Render free 512MB 下保守）


def create_app() -> FastAPI:
    app = FastAPI(
        title="stroke-order",
        version="0.3.0",
        description="中文字 → 向量筆跡轉換器（寫字機器人專用）",
    )

    # 5eu（W2）：重渲染回應快取＋ETag。**純 ASGI middleware**、不用
    # BaseHTTPMiddleware——後者會把所有回應轉成無 content-length 的
    # streaming，讓外層 GZip 的 minimum_size 失效（小回應也被壓）。
    # 純 ASGI 讓不匹配路徑原封穿過；只有可快取渲染路徑才緩衝本體。
    # 註冊在 GZip 之前＝最內層：存未壓縮本體，壓縮仍由外層 GZip 處理。
    render_cache: "OrderedDict[str, tuple[bytes, list]]" = OrderedDict()
    render_cache_stat = {"bytes": 0, "hits": 0, "misses": 0}

    def _render_cache_evict():
        while (
            render_cache_stat["bytes"] > RENDER_CACHE_MAX_TOTAL and render_cache
        ):
            _, (old_body, _h) = render_cache.popitem(last=False)
            render_cache_stat["bytes"] -= len(old_body)

    class _RenderCacheMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                return await self.app(scope, receive, send)
            path = scope["path"]
            method = scope["method"]

            if method != "GET":
                if not path.startswith(RENDER_CACHE_MUTATING_PREFIXES):
                    return await self.app(scope, receive, send)
                # 資料異動端點：成功（<400）才 bump 全域失效
                seen = {}

                async def send_watch(message):
                    if message["type"] == "http.response.start":
                        seen["status"] = message["status"]
                    await send(message)

                await self.app(scope, receive, send_watch)
                if seen.get("status", 500) < 400:
                    cache_bus.bump()
                return

            if not path.startswith(RENDER_CACHE_PREFIXES):
                return await self.app(scope, receive, send)

            query = scope.get("query_string", b"").decode("latin-1")
            key = f"{cache_bus.epoch()}|{path}?{query}"
            req_headers = {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in scope.get("headers", [])
            }

            hit = render_cache.get(key)
            if hit is not None:
                body, headers = hit
                render_cache.move_to_end(key)
                render_cache_stat["hits"] += 1
                etag = dict(headers)["etag"]
                if req_headers.get("if-none-match") == etag:
                    await _send_simple(send, 304, [(b"etag", etag.encode())], b"")
                    return
                out = [
                    (k.encode(), v.encode()) for k, v in headers
                    if k != "etag"
                ]
                out += [
                    (b"content-length", str(len(body)).encode()),
                    (b"etag", etag.encode()),
                    (b"x-render-cache", b"hit"),
                ]
                await _send_simple(send, 200, out, body)
                return

            # miss：緩衝完整回應 → 計 ETag → 入庫 → 補 header 後送出
            cap = {"status": None, "headers": [], "body": bytearray()}

            async def send_capture(message):
                if message["type"] == "http.response.start":
                    cap["status"] = message["status"]
                    cap["headers"] = list(message.get("headers", []))
                elif message["type"] == "http.response.body":
                    cap["body"] += message.get("body", b"")
                    if message.get("more_body"):
                        return
                # 全部收齊才動作（在結尾統一送出）

            await self.app(scope, receive, send_capture)
            body = bytes(cap["body"])
            status = cap["status"] if cap["status"] is not None else 500
            hdr_pairs = [
                (k.decode("latin-1").lower(), v.decode("latin-1"))
                for k, v in cap["headers"]
            ]
            hdr_map = dict(hdr_pairs)
            if status != 200 or "set-cookie" in hdr_map:
                out = [
                    (k.encode(), v.encode()) for k, v in hdr_pairs
                ]
                await _send_simple(send, status, out, body)
                return

            render_cache_stat["misses"] += 1
            etag = f'W/"{hashlib.md5(body).hexdigest()[:20]}"'
            keep = [
                (k, v) for k, v in hdr_pairs
                if k in ("content-type", "content-disposition")
                or k.startswith("x-")
            ]
            if len(body) <= RENDER_CACHE_MAX_ITEM:
                render_cache[key] = (body, keep + [("etag", etag)])
                render_cache_stat["bytes"] += len(body)
                _render_cache_evict()
            out = [(k.encode(), v.encode()) for k, v in keep]
            out += [
                (b"content-length", str(len(body)).encode()),
                (b"etag", etag.encode()),
                (b"x-render-cache", b"miss"),
            ]
            await _send_simple(send, 200, out, body)

    async def _send_simple(send, status, headers, body):
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": headers,
        })
        await send({"type": "http.response.body", "body": body})

    app.add_middleware(_RenderCacheMiddleware)
    app.state.render_cache_stat = render_cache_stat

    # W1-B（架構健檢 2026-07-18）：大型 SVG/JSON 回應壓縮。心經整頁 SVG
    # 1.25MB → 約 150KB；zhuyin_tw.json 454KB → 約 60KB。
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # W1-B：/static 快取策略——帶 ?v= 版本參數的資源可長快取（URL 即快取
    # 鍵，改版即失效，見 PRINCIPLES §11.4）；未帶版本的短快取靠 ETag 再驗證。
    @app.middleware("http")
    async def _static_cache_headers(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/") and response.status_code == 200:
            if "v" in request.query_params:
                response.headers.setdefault(
                    "Cache-Control", "public, max-age=604800"
                )
            else:
                response.headers.setdefault("Cache-Control", "public, max-age=3600")
        return response

    if STATIC_DIR.is_dir():
        # 5ev：版本注入型靜態服務（?v=__V__ → APP_VERSION）
        app.mount(
            "/static", _VersionedStaticFiles(directory=STATIC_DIR), name="static"
        )

    # ------ W3-R1/R2：路由分組 ------------------------------------------
    # 87 條路由住 web/routes/ 七群 APIRouter；include 順序＝拆檔前註冊
    # 順序。R2 起共用 helpers 移居 char_pipeline／responses／versioning，
    # routes 不再 import server——循環已解，此處為正常模組層 import。
    for _router in _all_routers():
        app.include_router(_router)

    # gallery 開機清掃：保留「每次 create_app 都掃」的原行為
    _routes_gallery.on_boot()

    return app


def __getattr__(name: str):
    """W3-R1 起：``app`` 惰性建立（PEP 562）。

    R2 解掉 routes↔server 循環後這不再是必要解法，但保留它——單純
    import 本模組（測試、工具鏈）不必付「建整個 app」的成本；uvicorn
    的 "stroke_order.web.server:app" 走屬性存取，第一次取用才建。
    """
    if name == "app":
        application = create_app()
        globals()["app"] = application
        return application
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def run(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Start the uvicorn dev server."""
    import uvicorn
    uvicorn.run(
        "stroke_order.web.server:app",
        host=host, port=port, reload=reload,
    )


__all__ = ["app", "create_app", "run"]


if __name__ == "__main__":
    # Allows `python -m stroke_order.web.server`
    import argparse
    ap = argparse.ArgumentParser(description="stroke-order Web UI")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--reload", action="store_true")
    args = ap.parse_args()
    print(f"[ok] starting stroke-order web UI on "
          f"http://{args.host}:{args.port}/")
    run(host=args.host, port=args.port, reload=args.reload)