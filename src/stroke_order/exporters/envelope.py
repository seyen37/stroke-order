"""
5fv — 統一出口信封（export envelope）。

所有模式匯出的 SVG 內嵌同一格式的出處憑據：

    <metadata><stroke-order-export><![CDATA[
      {"schema": "stroke-order-export-v1", "mode": "grid",
       "app_version": "0.14.271", "params": {...}}
    ]]></stroke-order-export></metadata>

用途（5fw 分享庫收件側）：上傳時伺服器開檔驗證這段憑據——分類不是
使用者選的，是檔案自己聲明的（``mode`` 欄）。沒有信封／schema 錯／
mode 不在冊 → 拒收。

設計要點：

- **一套信封蓋全模式**：不做 per-mode schema。單一 embed helper、
  單一驗證器；新模式加入＝呼叫點標一個 mode 字串。
- **既有 kind 不動**：mandala（``<mandala-config>``）、popup
  （``<popup-config>``）維持各自 schema，本信封不套用。
- **決定性輸出**：信封內容不含時間戳——同參數同版本重複匯出
  位元相同，利於測試與 dedup。
- CDATA 安全：JSON 序列化後把 ``]]>`` 轉義為 ``]]\\u003e``
  （字串值內合法的 JSON escape），杜絕提早關閉 CDATA 的注入。

前端對應：``web/static/zentangle/exporters.mjs`` 的 pathsToSvg
（禪繞是唯一前端產 SVG 的模式）以同一格式內嵌。
"""
from __future__ import annotations

import json
import re

EXPORT_SCHEMA_TAG = "stroke-order-export-v1"

#: 信封在 SVG 內的元素名（前後端一致；勿改字面——5fw 驗證器依此比對）
ENVELOPE_ELEMENT = "stroke-order-export"

_SVG_OPEN_RE = re.compile(r"(<svg\b[^>]*>)")
_ENVELOPE_RE = re.compile(
    r"<stroke-order-export[^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?"
    r"</stroke-order-export>",
)


def build_envelope_json(mode: str, *, app_version: str | None = None,
                        params: dict | None = None) -> str:
    """組信封 JSON 字串（含 CDATA 轉義）。"""
    payload: dict = {"schema": EXPORT_SCHEMA_TAG, "mode": mode}
    if app_version:
        payload["app_version"] = app_version
    if params:
        payload["params"] = params
    text = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    # "]]>" 只可能出現在 JSON 字串值內；> 是合法 escape。
    return text.replace("]]>", "]]\\u003e")


def embed_export_envelope(svg: str, *, mode: str,
                          app_version: str | None = None,
                          params: dict | None = None) -> str:
    """在 SVG 開標籤後插入信封 metadata。

    冪等：已含信封的 SVG 原樣返回（不重複嵌、不覆寫）。
    找不到 ``<svg>`` 開標籤時原樣返回（防禦；不該發生）。
    """
    if not mode:
        raise ValueError("envelope mode 不可為空")
    if f"<{ENVELOPE_ELEMENT}" in svg:
        return svg
    body = build_envelope_json(mode, app_version=app_version, params=params)
    block = (f"<metadata><{ENVELOPE_ELEMENT}><![CDATA[{body}]]>"
             f"</{ENVELOPE_ELEMENT}></metadata>")
    return _SVG_OPEN_RE.sub(lambda m: m.group(1) + block, svg, count=1)


def parse_export_envelope(svg_text: str) -> dict | None:
    """抽出並解析信封 JSON；無信封或 JSON 壞掉回 ``None``。

    只負責「有沒有、長怎樣」；schema/mode 的准入判斷屬 5fw 收件側。
    """
    m = _ENVELOPE_RE.search(svg_text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


__all__ = [
    "EXPORT_SCHEMA_TAG",
    "ENVELOPE_ELEMENT",
    "build_envelope_json",
    "embed_export_envelope",
    "parse_export_envelope",
]
