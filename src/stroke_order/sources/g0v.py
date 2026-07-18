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

import gzip
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

#: 隨 repo 部署的預抓 bundle（單一 gzip 檔，hex codepoint → strokes 陣列）。
#: 由 scripts/prefetch_g0v.py 產生；W1-D（架構健檢 2026-07-18）：讓常用字
#: 零網路命中，消除線上冷路徑（實測冷 82s vs 暖 48ms）。
G0V_BUNDLE_FILENAME = "g0v_bundle.json.gz"


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

    #: per-process bundle 快取：path str → dict[hex, strokes]（懶載一次）
    _bundle_cache: dict[str, dict] = {}

    def __init__(
        self,
        cache_dir: Optional[str | Path] = None,
        allow_network: bool = True,
        user_agent: str = "stroke-order/0.1 (+https://github.com/seyen37)",
        timeout: float = 3.0,
        bundle_path: Optional[str | Path] = None,
    ) -> None:
        if cache_dir is None:
            # default: <project-root>/data/g0v_cache/
            cache_dir = Path(__file__).resolve().parents[3] / "data" / "g0v_cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if bundle_path is None:
            # default: cache_dir 旁的 data/g0v_bundle.json.gz
            bundle_path = self.cache_dir.parent / G0V_BUNDLE_FILENAME
        self.bundle_path = Path(bundle_path)
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

        bundled = self._bundle().get(hex_code)
        if bundled is not None:
            return bundled

        if not self.allow_network:
            raise CharacterNotFound(
                f"U+{hex_code.upper()} not in cache/bundle and network disabled"
            )

        data = self._fetch(hex_code)
        # persist to cache for next time
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError as e:
            log.warning("could not write cache %s: %s", path, e)
        return data

    def _bundle(self) -> dict:
        """懶載入 bundle（每 process 每路徑一次）；缺檔/壞檔靜默降級為空。"""
        key = str(self.bundle_path)
        cached = G0VSource._bundle_cache.get(key)
        if cached is None:
            cached = {}
            if self.bundle_path.is_file():
                try:
                    with gzip.open(self.bundle_path, "rt", encoding="utf-8") as f:
                        cached = json.load(f)
                    log.info("g0v bundle loaded: %d chars", len(cached))
                except (OSError, ValueError) as e:
                    log.warning("could not read g0v bundle %s: %s", self.bundle_path, e)
            G0VSource._bundle_cache[key] = cached
        return cached

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
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            # W1-D 修：socket 讀取逾時（連線成功、讀取停滯）丟的是裸
            # TimeoutError（⊄ URLError），先前會炸穿到路由層。
            # URLError ⊂ OSError，一併涵蓋連線重設等其餘網路層錯誤。
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
