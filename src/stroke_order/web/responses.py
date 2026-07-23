"""下載回應與檔名 helpers（W3-R2／架構健檢 Wave 3）。

原散落 server.py 的檔名/標籤 helpers 與 12 處
``Response(content=svg, media_type="image/svg+xml", ...)`` 散寫收斂於此
——媒體型別字串只寫一次。
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi.responses import Response

SVG_MEDIA_TYPE = "image/svg+xml"


def _content_disposition(basename: str, ext: str) -> str:
    """RFC 5987-compliant attachment header supporting Unicode filenames."""
    ascii_fallback = f"char.{ext}"  # plain ASCII for old clients
    utf8_encoded = quote(f"{basename}.{ext}", safe="")
    return (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{utf8_encoded}"
    )


# 5dz: 下載檔名友善化——字型風格代碼 → 顯示標籤（與前端 su-style 一致）。
_STYLE_LABELS = {
    "kaishu": "楷書",
    "mingti": "宋體",
    "lishu": "隸書",
    "bold": "粗楷",
    "seal_script": "篆書",
}


def _style_label(style: str) -> str:
    """字型風格代碼 → 中文標籤（未知代碼原樣返回）。"""
    return _STYLE_LABELS.get(style, style or "楷書")


def _safe_filename_part(s: str) -> str:
    """去掉檔名不合法字元（Windows/macOS/Linux 通用），保留中英數。"""
    out = []
    for ch in (s or "").strip():
        out.append("_" if ch in '\\/:*?"<>|' else ch)
    return "".join(out).strip() or "sutra"


def svg_response(svg: str, headers: dict | None = None, *,
                 mode: str | None = None,
                 envelope_params: dict | None = None) -> Response:
    """SVG 回應——全站唯一的 ``image/svg+xml`` 出口。

    5fv：``mode`` 給定時內嵌統一出口信封（stroke-order-export-v1，
    含 app_version）——分享庫收件側（5fw）驗此憑據。守門測試要求
    routes 層每個呼叫點都明示 ``mode=``（刻意不嵌的例外進白名單）。
    """
    if mode is not None:
        from ..exporters.envelope import embed_export_envelope
        from .versioning import APP_VERSION
        svg = embed_export_envelope(svg, mode=mode,
                                    app_version=APP_VERSION,
                                    params=envelope_params)
    return Response(content=svg, media_type=SVG_MEDIA_TYPE, headers=headers)
