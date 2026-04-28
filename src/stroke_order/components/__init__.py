"""
Component-level analysis for Chinese characters.

This subpackage implements VISION.md Phase A: 組件覆蓋分析器.

Provides:
- `ids` — IDS (Ideographic Description Sequence) loader and decomposition data
  from CHISE/cjkvi-ids
- `decompose` — recursive leaf component extraction
- `coverset` — bundled cover-sets (中日韓共用 808、教育部 4808 等) for "minimum
  set of chars that cover the most components"
- `algorithm` — greedy set-cover recommender for "next char to write"

Design rationale: see ``docs/VISION.md`` (Layer 1: 標註層) and
``docs/decisions/2026-04-27_808_analysis.md`` (empirical validation).
"""
from __future__ import annotations

from .algorithm import (
    Recommendation,
    coverage_status,
    greedy_full_cover,
    recommend_next,
)
from .coverset import (
    CoverSet,
    list_coversets,
    load_coverset,
    load_coverset_from_path,
)
from .decompose import (
    collect_components,
    covers,
    decompose,
    get_leaf_components,
    is_atomic,
)
from .ids import default_ids_map, parse_ids_file

__all__ = [
    "CoverSet",
    "Recommendation",
    "collect_components",
    "coverage_status",
    "covers",
    "decompose",
    "default_ids_map",
    "get_leaf_components",
    "greedy_full_cover",
    "is_atomic",
    "list_coversets",
    "load_coverset",
    "load_coverset_from_path",
    "parse_ids_file",
    "recommend_next",
]
