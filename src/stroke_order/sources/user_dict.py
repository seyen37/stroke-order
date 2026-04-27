"""
User-authored character dictionary (Phase 5ak).

Lets users supply their own stroke data for characters not covered by
g0v / MMH / KanjiVG (rare chars, place names, coined characters, PUA
glyphs) — or to override the built-in glyph for characters they want to
re-style.

Storage layout
--------------
One JSON file per character at::

    ~/.stroke-order/user-dict/{unicode_hex}.json

The path is overridable via the ``STROKE_ORDER_USER_DICT_DIR`` environment
variable (kept simple for tests, single-user local installs, and CI).

JSON schema (subset of g0v Character IR — only the fields that matter
for rendering)::

    {
      "char": "鱻",
      "unicode_hex": "9c7b",
      "data_source": "user",
      "created_at": "2026-04-25T15:30:00",
      "strokes": [
        {
          "track": [[x, y], [x, y], ...],
          "kind_code": 9,
          "kind_name": "其他",
          "has_hook": false
        },
        ...
      ]
    }

Coordinates are in the canonical 2048 em frame, Y-down, identical to
g0v / MMH / PunctuationSource. Two-or-more points per stroke required.

Source-chain placement
----------------------
``UserDictSource`` always sits at the **top** of ``AutoSource`` /
``RegionAutoSource`` so user characters override built-in ones — useful
when you don't like the MOE standard glyph and want your own version.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from ..ir import Character, Point, Stroke
from .g0v import CharacterNotFound


_ENV_DIR = "STROKE_ORDER_USER_DICT_DIR"
_DEFAULT_DIR = Path.home() / ".stroke-order" / "user-dict"


def default_user_dict_dir() -> Path:
    """Resolve the directory once per call. The env var wins."""
    env = os.environ.get(_ENV_DIR)
    return Path(env).expanduser() if env else _DEFAULT_DIR


# ---------------------------------------------------------------------------
# Source adapter
# ---------------------------------------------------------------------------


class UserDictSource:
    """Load characters authored by the user into the source-chain pipeline.

    Cheap to construct (no I/O) — actual files are read lazily on first
    ``get_character(ch)`` and then memoised in ``self._cache``. Call
    :meth:`invalidate` if files change underneath it (the API CRUD
    handlers do this after writes/deletes).
    """

    def __init__(self, dict_dir: Optional[Path] = None) -> None:
        self.dict_dir = Path(dict_dir) if dict_dir else default_user_dict_dir()
        self._cache: dict[str, Character] = {}

    def __repr__(self) -> str:
        return f"UserDictSource(dir={self.dict_dir!s})"

    # ---------- core read path -------------------------------------------

    def _path_for(self, char: str) -> Path:
        return self.dict_dir / f"{ord(char):04x}.json"

    def has(self, char: str) -> bool:
        return self._path_for(char).exists()

    def get_character(self, char: str) -> Character:
        if char in self._cache:
            return self._cache[char]
        path = self._path_for(char)
        if not path.exists():
            raise CharacterNotFound(
                f"no user-dict entry for U+{ord(char):04X} ({char!r}); "
                f"checked {path}"
            )
        c = self._load_from_file(path)
        self._cache[char] = c
        return c

    def list_chars(self) -> list[str]:
        """Return every character currently stored, sorted by Unicode codepoint."""
        if not self.dict_dir.is_dir():
            return []
        chars: list[str] = []
        for p in self.dict_dir.glob("*.json"):
            try:
                chars.append(chr(int(p.stem, 16)))
            except (ValueError, OverflowError):
                # Ignore malformed filenames.
                continue
        chars.sort(key=ord)
        return chars

    def invalidate(self, char: Optional[str] = None) -> None:
        """Drop the cache entry for ``char`` (or everything when None).
        Call after writing / deleting a JSON file so subsequent reads
        pick up the new state without restarting the process."""
        if char is None:
            self._cache.clear()
        else:
            self._cache.pop(char, None)

    # ---------- mutation path (used by /api/user-dict POST/DELETE) -------

    def save_character(
        self, char: str,
        strokes: Iterable[dict],
    ) -> Path:
        """Persist a character to ``{dict_dir}/{hex}.json`` and return the path.

        ``strokes`` is an iterable of dicts with at least a ``track`` field
        (list of (x, y) tuples or 2-element lists in 2048 em coords).
        Other fields (``kind_code`` / ``kind_name`` / ``has_hook``) are
        optional and default to "其他" (9).
        """
        if len(char) != 1:
            raise ValueError(f"char must be a single character, got {char!r}")
        cleaned = []
        for i, s in enumerate(strokes):
            track = s.get("track") or []
            if len(track) < 2:
                raise ValueError(
                    f"stroke {i} must have ≥2 points, got {len(track)}"
                )
            cleaned.append({
                "track": [[float(p[0]), float(p[1])] for p in track],
                "kind_code": int(s.get("kind_code", 9)),
                "kind_name": str(s.get("kind_name", "其他")),
                "has_hook": bool(s.get("has_hook", False)),
            })
        if not cleaned:
            raise ValueError("character must have ≥1 stroke")
        payload = {
            "char": char,
            "unicode_hex": f"{ord(char):04x}",
            "data_source": "user",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "strokes": cleaned,
        }
        self.dict_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(char)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        self.invalidate(char)
        return path

    def delete_character(self, char: str) -> bool:
        """Return True when a file was actually removed."""
        path = self._path_for(char)
        if not path.exists():
            return False
        path.unlink()
        self.invalidate(char)
        return True

    # ---------- Phase 5ar: bulk export / import --------------------------

    def export_zip_bytes(self) -> bytes:
        """Bundle every character JSON in the dict dir into one ZIP.

        Returned as bytes so the web layer can stream it without
        materialising a temp file. Files are stored at the root of the
        archive using their on-disk filename (``{hex}.json``); empty
        archive when no characters exist.
        """
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            if self.dict_dir.is_dir():
                for p in sorted(self.dict_dir.glob("*.json")):
                    zf.write(p, arcname=p.name)
        return buf.getvalue()

    def import_zip_bytes(
        self,
        zip_bytes: bytes,
        policy: str = "skip",
    ) -> dict:
        """Restore characters from a ZIP archive built by :meth:`export_zip_bytes`.

        ``policy``:
        - ``"skip"`` (default) — keep any character already in the dict;
          silently leave its file untouched.
        - ``"replace"`` — overwrite existing files when an incoming
          payload has the same hex codepoint.

        Returns a summary dict::

            {
              "added":    N,   # newly written
              "skipped":  M,   # already present, policy=skip
              "replaced": K,   # already present, policy=replace
              "errors":  [...] # malformed entries (filename + reason)
            }

        The archive may contain only ``{hex}.json`` files at the root;
        anything else (subdirs, non-JSON files) is reported under
        ``errors`` and not written.
        """
        import io
        import zipfile

        if policy not in ("skip", "replace"):
            raise ValueError(
                f"unknown policy {policy!r}; expected 'skip' or 'replace'"
            )

        summary = {"added": 0, "skipped": 0, "replaced": 0,
                   "errors": []}   # type: dict
        try:
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
        except zipfile.BadZipFile as e:
            raise ValueError(f"not a valid ZIP archive: {e}") from e

        with zf:
            for info in zf.infolist():
                name = info.filename
                # Reject path traversal / nested dirs / non-JSON outright.
                if "/" in name or "\\" in name or not name.endswith(".json"):
                    summary["errors"].append({
                        "name": name,
                        "reason": "must be a top-level *.json entry",
                    })
                    continue
                hex_part = name[:-5]   # strip .json
                try:
                    cp = int(hex_part, 16)
                    char = chr(cp)
                except (ValueError, OverflowError):
                    summary["errors"].append({
                        "name": name,
                        "reason": f"filename {hex_part!r} is not a valid hex codepoint",
                    })
                    continue

                # Validate the JSON payload by round-tripping it through
                # save_character. That gives us schema enforcement for
                # free (track length, integer kind_codes, etc).
                try:
                    payload = json.loads(zf.read(info).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as e:
                    summary["errors"].append({
                        "name": name, "reason": f"unreadable JSON: {e}",
                    })
                    continue

                strokes = payload.get("strokes")
                if not isinstance(strokes, list):
                    summary["errors"].append({
                        "name": name,
                        "reason": "missing 'strokes' array",
                    })
                    continue

                already = self.has(char)
                if already and policy == "skip":
                    summary["skipped"] += 1
                    continue

                try:
                    self.save_character(char, strokes)
                except (ValueError, KeyError) as e:
                    summary["errors"].append({
                        "name": name, "reason": str(e),
                    })
                    continue

                if already:
                    summary["replaced"] += 1
                else:
                    summary["added"] += 1

        return summary

    # ---------- helpers ---------------------------------------------------

    @staticmethod
    def _load_from_file(path: Path) -> Character:
        raw = json.loads(path.read_text(encoding="utf-8"))
        ch = raw["char"]
        strokes: list[Stroke] = []
        for idx, s in enumerate(raw.get("strokes", [])):
            pts = [Point(float(p[0]), float(p[1])) for p in s["track"]]
            strokes.append(Stroke(
                index=idx,
                raw_track=pts,
                outline=[],   # user dict only provides tracks
                kind_code=int(s.get("kind_code", 9)),
                kind_name=str(s.get("kind_name", "其他")),
                has_hook=bool(s.get("has_hook", False)),
            ))
        return Character(
            char=ch,
            unicode_hex=raw.get("unicode_hex", f"{ord(ch):04x}"),
            strokes=strokes,
            data_source="user",
        )


# ---------------------------------------------------------------------------
# Input format helpers — convert SVG / canvas-coord handwriting into the
# normalised stroke-track format expected by ``UserDictSource.save_character``.
# ---------------------------------------------------------------------------


def handwriting_to_strokes(
    raw_strokes: list[list[list[float]]],
    canvas_width: float,
    canvas_height: float,
    em_size: int = 2048,
) -> list[dict]:
    """Normalise canvas-coord pointer captures into em-frame strokes.

    Each ``raw_strokes[i]`` is a list of ``[x, y]`` pairs in canvas
    pixel coords. We scale them so the canvas's bbox fills a centred
    em_size × em_size square (preserving aspect ratio so circular
    drawing doesn't get squashed).
    """
    if canvas_width <= 0 or canvas_height <= 0:
        raise ValueError("canvas dimensions must be positive")
    if not raw_strokes:
        raise ValueError("no strokes captured")
    # Uniform scale that fits the longer canvas side into em_size.
    scale = em_size / max(canvas_width, canvas_height)
    # Centre on the em square.
    offset_x = (em_size - canvas_width * scale) / 2.0
    offset_y = (em_size - canvas_height * scale) / 2.0
    out: list[dict] = []
    for s in raw_strokes:
        if len(s) < 2:
            continue   # ignore single-tap clicks; meaningless strokes
        track = [
            [float(p[0]) * scale + offset_x,
             float(p[1]) * scale + offset_y]
            for p in s
        ]
        out.append({
            "track": track,
            "kind_code": 9,
            "kind_name": "其他",
            "has_hook": False,
        })
    if not out:
        raise ValueError("all strokes had <2 points (taps don't count)")
    return out


def svg_to_strokes(
    svg_text: str,
    em_size: int = 2048,
    samples_per_curve: int = 24,
) -> list[dict]:
    """Parse an SVG document and convert its drawable elements into a
    list of stroke-tracks ready for :meth:`UserDictSource.save_character`.

    Recognised elements: ``<path>``, ``<polyline>``, ``<line>``. Each one
    becomes one stroke. Coordinates are normalised so the union bbox of
    all elements fits into a centred ``em_size`` square (uniform scale,
    aspect-ratio preserved). Bezier curves on ``<path>`` are sampled with
    ``samples_per_curve`` evenly-spaced points.

    Raises ``ValueError`` on malformed SVG or no drawable elements.
    """
    import xml.etree.ElementTree as ET
    try:
        from svgpathtools import parse_path
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "svgpathtools is required to parse SVG; install with `pip install svgpathtools`"
        ) from e

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as e:
        raise ValueError(f"invalid SVG: {e}") from e

    # Drawable elements may live under default SVG namespace; tolerate both.
    ns = {"svg": "http://www.w3.org/2000/svg"}

    def _iter(tag: str):
        for el in root.iter():
            local = el.tag.split("}", 1)[-1]   # strip namespace
            if local == tag:
                yield el

    raw_tracks: list[list[tuple[float, float]]] = []

    # <path d="..."> — sample bezier segments
    for el in _iter("path"):
        d = el.get("d")
        if not d:
            continue
        try:
            path = parse_path(d)
        except Exception:
            continue
        for seg in path:
            track: list[tuple[float, float]] = []
            for i in range(samples_per_curve + 1):
                t = i / samples_per_curve
                p = seg.point(t)
                track.append((p.real, p.imag))
            if len(track) >= 2:
                raw_tracks.append(track)

    # <polyline points="x,y x,y ...">
    for el in _iter("polyline"):
        pts_text = el.get("points") or ""
        track = []
        for tok in pts_text.replace(",", " ").split():
            try:
                track.append(float(tok))
            except ValueError:
                continue
        # pair into (x, y)
        coords = list(zip(track[0::2], track[1::2]))
        if len(coords) >= 2:
            raw_tracks.append(coords)

    # <line x1 y1 x2 y2>
    for el in _iter("line"):
        try:
            x1 = float(el.get("x1", 0))
            y1 = float(el.get("y1", 0))
            x2 = float(el.get("x2", 0))
            y2 = float(el.get("y2", 0))
        except ValueError:
            continue
        raw_tracks.append([(x1, y1), (x2, y2)])

    if not raw_tracks:
        raise ValueError(
            "SVG had no recognised <path>/<polyline>/<line> elements"
        )

    # Compute union bbox for uniform-scale fit into em_size square.
    xs = [p[0] for tr in raw_tracks for p in tr]
    ys = [p[1] for tr in raw_tracks for p in tr]
    bx_min, bx_max = min(xs), max(xs)
    by_min, by_max = min(ys), max(ys)
    span = max(bx_max - bx_min, by_max - by_min, 1e-6)
    scale = em_size / span
    # Centre.
    offset_x = (em_size - (bx_max - bx_min) * scale) / 2.0 - bx_min * scale
    offset_y = (em_size - (by_max - by_min) * scale) / 2.0 - by_min * scale

    out: list[dict] = []
    for track in raw_tracks:
        em_track = [
            [x * scale + offset_x, y * scale + offset_y]
            for (x, y) in track
        ]
        out.append({
            "track": em_track,
            "kind_code": 9,
            "kind_name": "其他",
            "has_hook": False,
        })
    return out


__all__ = [
    "UserDictSource",
    "default_user_dict_dir",
    "handwriting_to_strokes",
    "svg_to_strokes",
]
