"""靜態資源版本注入（5ev／W2b；W3-R2 自 server.py 抽出為專屬模組）。

?v=__V__ 佔位符 → APP_VERSION（單一事實源＝pyproject 版本）。
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles


WEB_ROOT = Path(__file__).resolve().parent
STATIC_DIR = WEB_ROOT / "static"


def _resolve_app_version() -> str:
    """5ev（W2b）：?v= 快取鍵的單一事實源＝pyproject 版本。

    ⚠ 順序刻意「pyproject 優先、importlib.metadata 後備」：editable
    install（pip install -e）的 metadata 凍結在安裝當下，pyproject 升版
    不會反映——本機 .venv 會拿到舊版本號。checkout 內直讀 pyproject
    永遠是現值；wheel 部署（無 pyproject 同行）才退 metadata。
    """
    try:
        import tomllib
        root = WEB_ROOT.parents[2]  # src/stroke_order/web → repo root
        with open(root / "pyproject.toml", "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        pass
    try:
        from importlib.metadata import version
        return version("stroke-order")
    except Exception:
        return "dev"


APP_VERSION = _resolve_app_version()

#: 前端檔案裡的 ?v=__V__ 佔位符，吐出時換成 APP_VERSION。
#: vendor pin（opencv 4.11.0／opentype 1.3.4）是語意版本、刻意不用佔位符
#: ——換成 app 版本會讓每次升版重抓 10MB 級大檔。
_VERSION_PLACEHOLDER = "?v=__V__"
_INJECT_SUFFIXES = (".js", ".mjs", ".html", ".css")
#: (path str) → (mtime_ns, version, body bytes, etag)
_versioned_cache: dict = {}


def _versioned_text(full_path: Path) -> tuple[bytes, str]:
    """讀檔＋佔位符注入，帶 (mtime, version) 快取。"""
    st = full_path.stat()
    key = str(full_path)
    hit = _versioned_cache.get(key)
    if hit and hit[0] == st.st_mtime_ns and hit[1] == APP_VERSION:
        return hit[2], hit[3]
    text = full_path.read_text("utf-8")
    body = text.replace(_VERSION_PLACEHOLDER, f"?v={APP_VERSION}").encode("utf-8")
    etag = f'W/"{st.st_mtime_ns:x}-{APP_VERSION}"'
    _versioned_cache[key] = (st.st_mtime_ns, APP_VERSION, body, etag)
    return body, etag


_MEDIA_BY_SUFFIX = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


def _versioned_page(full_path: Path, if_none_match: str | None = None) -> Response:
    body, etag = _versioned_text(full_path)
    if if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(
        content=body,
        media_type=_MEDIA_BY_SUFFIX.get(full_path.suffix, "text/plain"),
        headers={"ETag": etag},
    )


class _VersionedStaticFiles(StaticFiles):
    """5ev：只攔 .js/.mjs/.html/.css 做 ?v=__V__ 注入；其餘（json/圖/字型）
    原封走 StaticFiles（保留 Range／304 條件請求等原生行為）。"""

    async def get_response(self, path: str, scope):
        if not path.endswith(_INJECT_SUFFIXES):
            return await super().get_response(path, scope)
        base = Path(self.directory).resolve()
        full = (base / path).resolve()
        if not str(full).startswith(str(base) + os.sep) or not full.is_file():
            return await super().get_response(path, scope)  # 404/traversal 交回原邏輯
        req_headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        return _versioned_page(full, req_headers.get("if-none-match"))
