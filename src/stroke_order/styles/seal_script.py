"""Phase 5at: 篆書 (seal script) — real-font swap, not a stroke filter.

Unlike :mod:`stroke_order.styles.mingti` / ``lishu`` which morph kaishu
strokes into a vague "feel" of another script, seal script differs
*structurally* from kaishu (different glyph composition, fewer strokes,
no hooks). A purely stroke-level filter cannot fake it.

So this style is intentionally an **identity transform** at the filter
layer. The real swap happens earlier in the pipeline — see
``server._upgrade_to_seal``: if the user picks ``style="seal_script"``
and the 崇羲篆體 font is installed, the original kaishu Character is
replaced wholesale with the seal-script Character. By the time
``apply_style("seal_script")`` runs, the Character already carries
``data_source = "chongxi_seal"`` (or one of its skeleton variants), so
this filter has nothing to do.

If the seal font is *not* installed, ``_upgrade_to_seal`` returns the
original kaishu Character untouched — and this filter again does
nothing. The user then sees kaishu with a console warning, rather
than a crash.
"""
from __future__ import annotations

from ..ir import Character


class SealScriptStyle:
    name = "seal_script"
    description = "篆書（崇羲篆體；需另裝字型）"

    def apply(self, c: Character) -> Character:
        # Identity. Real work happens in server._upgrade_to_seal.
        return c
