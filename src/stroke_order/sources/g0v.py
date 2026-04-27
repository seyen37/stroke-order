"""
g0v/zh-stroke-data adapter.

Reads per-character JSON from either a local cache folder or fetches from
http://g0v.github.io/zh-stroke-data/json/{hex}.json on demand.

JSON schema (verified via REF_ANALYSIS_G0V.md):

    [
      {
        "outline": [{"type": "M", "x":..., "y":...}, ...],
        "track":   [{"x":..., "y":...}, ...]
      },
      ...   # one object per stroke, array order = stroke order
    ]

Coordinate system is 2048×2048 em square (already canonical), Y-down.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from ..ir import Character, Point, Stroke, OutlineCommand

log = logging.getLogger(__name__)

#: g0v hosted JSON base URL. Hex codepoint (lowercase) + .json appended.
G0V_BASE_URL = "http://g0v.github.io/zh-stroke-data/json/"


class CharacterNotFound(Exception):
    """Raised when the requested character is not in g0v dataset."""


class G0VSource:
    """
    Loader for g0v/zh-stroke-data per-character JSONs.

    Parameters
    ----------
    cache_dir
        Directory to look in first / write fetched files to. Default is
        the project's ``data/g0v_cache/`` folder resolved relative to this
        source file.
    allow_network
        If ``False``, never make HTTP requests; cache-only mode.
    user_agent
        Value for HTTP User-Agent header (some CDNs reject empty UAs).
    """

    def __init__(
        self,
        cache_dir: Optional[str | Path] = None,
        allow_network: bool = True,
        user_agent: str = "stroke-order/0.1 (+https://github.com/seyen37)",
        timeout: float = 10.0,
    ) -> None:
        if cache_dir is None:
            # default: <project-root>/data/g0v_cache/
            cache_dir = Path(__file__).resolve().parents[3] / "data" / "g0v_cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.allow_network = allow_network
        self.user_agent = user_agent
        self.timeout = timeout

    # ---------- public API -------------------------------------------------

    def get_character(self, char: str) -> Character:
        """
        Fetch the Character IR for a single char. Raises CharacterNotFound
        if the char is missing from g0v and cannot be retrieved.
        """
        if len(char) != 1:
            raise ValueError(f"expected a single character, got {char!r}")

        hex_code = f"{ord(char):x}"  # lowercase hex, no prefix
        raw = self._load_json(hex_code)
        return self._parse(char, hex_code, raw)

    # ---------- internals --------------------------------------------------

    def _cache_path(self, hex_code: str) -> Path:
        return self.cache_dir / f"{hex_code}.json"

    def _load_json(self, hex_code: str) -> list[dict]:
        """Return the parsed JSON array of strokes, hitting cache or network."""
        path = self._cache_path(hex_code)
        if path.is_file():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)

        if not self.allow_network:
            raise CharacterNotFound(
                f"U+{hex_code.upper()} not in cache and network disabled"
            )

        data = self._fetch(hex_code)
        # persist to cache for next time
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError as e:
            log.warning("could not write cache %s: %s", path, e)
        return data

    def _fetch(self, hex_code: str) -> list[dict]:
        url = f"{G0V_BASE_URL}{hex_code}.json"
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise CharacterNotFound(
                    f"U+{hex_code.upper()} not in g0v dataset (HTTP 404)"
                ) from e
            raise
        except urllib.error.URLError as e:
            raise CharacterNotFound(
                f"network error fetching U+{hex_code.upper()}: {e}"
            ) from e
        return json.loads(body.decode("utf-8"))

    def _parse(self, char: str, hex_code: str, raw: list[dict]) -> Character:
        """Convert the raw JSON array into Character/Stroke objects."""
        strokes: list[Stroke] = []
        for i, entry in enumerate(raw):
            track_raw = entry.get("track", [])
            outline_raw = entry.get("outline", [])

            track = [Point(float(p["x"]), float(p["y"])) for p in track_raw]
            # outline: copy as-is; downstream exporters can walk M/L/Q commands
            outline: list[OutlineCommand] = []
            for cmd in outline_raw:
                outline.append(dict(cmd))  # shallow-copy so we own it

            # optional size field (pen width, not always present)
            pen_size = entry.get("size")
            if pen_size is not None:
                pen_size = float(pen_size)

            strokes.append(
                Stroke(
                    index=i,
                    raw_track=track,
                    outline=outline,
                    pen_size=pen_size,
                )
            )

        return Character(
            char=char,
            unicode_hex=hex_code,
            strokes=strokes,
            data_source="g0v",
        )


__all__ = ["G0VSource", "CharacterNotFound", "G0V_BASE_URL"]
