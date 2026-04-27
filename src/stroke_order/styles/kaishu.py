"""Kaishu (original) style — identity transform."""
from __future__ import annotations

from ..ir import Character


class KaishuStyle:
    name = "kaishu"
    description = "楷書（原始筆畫，無變換）"

    def apply(self, c: Character) -> Character:
        return c
