"""容量預檢共用尾段（W3-R2／架構健檢 Wave 3）。

七個 ``/api/*/capacity`` 端點的參數與版面構造各屬其模式（合約不動），
但「算容量 → 補 total_chars → 估頁數」的組裝尾段完全相同——收斂於此。
"""
from __future__ import annotations

from ..layouts import estimate_pages, layout_capacity


def capacity_summary(text: str, layout, *, direction: str) -> dict:
    """回傳 capacity dict：layout_capacity ＋ total_chars ＋ pages_estimated。"""
    cap = layout_capacity(layout, direction=direction)
    cap["total_chars"] = sum(1 for c in text if not c.isspace())
    cap["pages_estimated"] = estimate_pages(text, layout, direction=direction)
    return cap
