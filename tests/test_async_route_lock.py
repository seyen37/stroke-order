"""W1-A 回歸鎖（架構健檢 2026-07-18）：路由 async/sync 紀律。

FastAPI 的 ``async def`` 路由直接跑在 event loop 執行緒上——內部若有
同步重運算或同步 I/O，單 worker 下會凍住全站（5ck 事故、PRINCIPLES §9.1）。
sync ``def`` 路由才會自動進 threadpool。

鐵則：**路由一律 sync def**；只有「函式體內真正 await 非阻塞操作」的
路由允許 async，且必須列入下方 allowlist 並附理由。
新增 async 路由前請先想清楚：你要 await 什麼？
"""
from __future__ import annotations

import inspect

from fastapi.routing import APIRoute

from stroke_order.web.server import create_app

#: 允許 async 的路由端點（名稱 → 理由）
ASYNC_ALLOWLIST = {
    # await asyncio.to_thread(SMTP)——真非同步等待，合法
    "gallery_auth_request_login",
}


def test_no_async_route_endpoints():
    app = create_app()
    offenders = sorted(
        route.endpoint.__name__
        for route in app.routes
        if isinstance(route, APIRoute)
        and inspect.iscoroutinefunction(route.endpoint)
        and route.endpoint.__name__ not in ASYNC_ALLOWLIST
    )
    assert offenders == [], (
        f"這些路由是 async def 但不在 allowlist：{offenders}。"
        "路由請用 sync def（自動進 threadpool）；若真的需要 await，"
        "把名稱加進 tests/test_async_route_lock.py 的 ASYNC_ALLOWLIST 並附理由。"
    )


def test_allowlist_entries_still_exist_and_are_async():
    """allowlist 不留殭屍項——列名的路由必須存在且仍是 async。"""
    app = create_app()
    async_routes = {
        route.endpoint.__name__
        for route in app.routes
        if isinstance(route, APIRoute)
        and inspect.iscoroutinefunction(route.endpoint)
    }
    stale = ASYNC_ALLOWLIST - async_routes
    assert not stale, f"allowlist 中已不存在（或已改 sync）的項目：{sorted(stale)}"
