"""
Zhang-Suen skeletonization for CNS-font glyphs (Phase 5al).

Takes a glyph's outline (filled polygons) and produces a single-pixel-wide
centreline approximation, then traces it as a polyline list. Used to
convert a TTF outline into a "best-effort" set of writing tracks for
characters that aren't in the g0v / MMH stroke databases.

Pipeline
--------
1. **Rasterise** outline commands to a 128×128 binary bitmap with PIL.
2. **Thin** with the Zhang-Suen algorithm (numpy-vectorised; ~30 ms / glyph
   on a typical CPU).
3. **Trace** the skeleton into one or more polylines via greedy walks
   from endpoint pixels.
4. **Scale** the polylines back to the canonical 2048 em frame.

Honest caveats
--------------
- The output is a single connected centreline, **not** segmented into
  individual strokes. Stroke order, kind classification, and hooks are
  lost. This is alpha-quality.
- For complex glyphs (10+ strokes), junction points are ambiguous and
  the trace may zig-zag. Manual cleanup or g0v stroke data is preferred
  when available.
"""
from __future__ import annotations

from typing import Optional

import numpy as np


_DEFAULT_RASTER_SIZE = 128


# ---------------------------------------------------------------------------
# Rasterisation
# ---------------------------------------------------------------------------


def _sample_quadratic(p0, p1, p2, n=8):
    """Sample n+1 points along a quadratic Bezier from p0 (start) to p2."""
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1.0 - t
        x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
        y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
        out.append((x, y))
    return out


def _sample_cubic(p0, p1, p2, p3, n=12):
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1.0 - t
        x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
        out.append((x, y))
    return out


def rasterize_outline(
    outline_cmds: list[dict],
    em_size: int = 2048,
    raster_size: int = _DEFAULT_RASTER_SIZE,
) -> np.ndarray:
    """Render a list of outline commands to a binary HxW bool numpy array.

    Multi-contour outlines (multiple ``M`` commands) are filled with PIL's
    polygon fill — non-zero winding by default, which is correct for the
    vast majority of CJK glyphs that have no nested holes.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Pillow is required for skeletonization; "
            "install with `pip install Pillow`"
        ) from e
    img = Image.new("L", (raster_size, raster_size), 0)
    draw = ImageDraw.Draw(img)
    scale = raster_size / em_size

    polys: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    for cmd in outline_cmds:
        t = cmd["type"]
        if t == "M":
            if cur:
                polys.append(cur)
            cur = [(cmd["x"] * scale, cmd["y"] * scale)]
        elif t == "L":
            cur.append((cmd["x"] * scale, cmd["y"] * scale))
        elif t == "Q":
            if not cur:
                continue
            p0 = cur[-1]
            p1 = (cmd["begin"]["x"] * scale, cmd["begin"]["y"] * scale)
            p2 = (cmd["end"]["x"]   * scale, cmd["end"]["y"]   * scale)
            cur.extend(_sample_quadratic(p0, p1, p2))
        elif t == "C":
            if not cur:
                continue
            p0 = cur[-1]
            p1 = (cmd["begin"]["x"] * scale, cmd["begin"]["y"] * scale)
            p2 = (cmd["mid"]["x"]   * scale, cmd["mid"]["y"]   * scale)
            p3 = (cmd["end"]["x"]   * scale, cmd["end"]["y"]   * scale)
            cur.extend(_sample_cubic(p0, p1, p2, p3))
    if cur:
        polys.append(cur)

    for poly in polys:
        if len(poly) >= 3:
            draw.polygon(poly, fill=1)

    return np.array(img, dtype=bool)


# ---------------------------------------------------------------------------
# Zhang-Suen thinning (numpy-vectorised)
# ---------------------------------------------------------------------------


def _step(img: np.ndarray, sub_iter: int) -> np.ndarray:
    """Return a mask of pixels that should be removed in this sub-iteration."""
    # 8-connected neighbours, ordered P2..P9 clockwise from north.
    P2 = np.roll(img, 1, axis=0)
    P3 = np.roll(np.roll(img, 1, axis=0), -1, axis=1)
    P4 = np.roll(img, -1, axis=1)
    P5 = np.roll(np.roll(img, -1, axis=0), -1, axis=1)
    P6 = np.roll(img, -1, axis=0)
    P7 = np.roll(np.roll(img, -1, axis=0), 1, axis=1)
    P8 = np.roll(img, 1, axis=1)
    P9 = np.roll(np.roll(img, 1, axis=0), 1, axis=1)

    # B(P1): count of black neighbours (must be 2..6).
    B = (P2.astype(np.uint8) + P3 + P4 + P5
         + P6 + P7 + P8 + P9)
    cond_B = (B >= 2) & (B <= 6)

    # A(P1): number of 0→1 transitions in P2,P3,...,P9,P2.
    A = (
        ((~P2) & P3).astype(np.uint8)
        + ((~P3) & P4)
        + ((~P4) & P5)
        + ((~P5) & P6)
        + ((~P6) & P7)
        + ((~P7) & P8)
        + ((~P8) & P9)
        + ((~P9) & P2)
    )
    cond_A = (A == 1)

    if sub_iter == 1:
        cond_M = ~(P2 & P4 & P6) & ~(P4 & P6 & P8)
    else:
        cond_M = ~(P2 & P4 & P8) & ~(P2 & P6 & P8)

    # Only existing foreground pixels are candidates.
    return img & cond_B & cond_A & cond_M


def zhang_suen(binary: np.ndarray, max_passes: int = 100) -> np.ndarray:
    """Apply Zhang-Suen thinning until convergence or ``max_passes``.

    ``binary`` must be HxW bool. Returns a HxW bool ndarray of the
    skeleton (1-pixel wide).
    """
    img = binary.copy()
    for _ in range(max_passes):
        rm1 = _step(img, 1)
        if rm1.any():
            img[rm1] = False
        rm2 = _step(img, 2)
        if rm2.any():
            img[rm2] = False
        if not rm1.any() and not rm2.any():
            break
    return img


# ---------------------------------------------------------------------------
# Skeleton tracing — bitmap → polyline list
# ---------------------------------------------------------------------------


def _neighbours(y: int, x: int, H: int, W: int):
    """Yield 8-connected neighbour coords inside the image."""
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W:
                yield ny, nx


def trace_skeleton(skel: np.ndarray) -> list[list[tuple[int, int]]]:
    """Walk the skeleton into one or more pixel polylines.

    Strategy: find endpoint pixels (degree 1), walk greedily to depletion;
    after all endpoints are exhausted, treat any remaining loop pixels by
    starting from any remaining pixel and walking until back to start.
    Returns list of (y, x) pixel paths in raster coords.
    """
    H, W = skel.shape
    visited = np.zeros_like(skel)
    polylines: list[list[tuple[int, int]]] = []

    # Compute degree map (number of skeleton neighbours per pixel).
    degree = np.zeros_like(skel, dtype=np.uint8)
    ys, xs = np.where(skel)
    for y, x in zip(ys, xs):
        degree[y, x] = sum(1 for ny, nx in _neighbours(y, x, H, W) if skel[ny, nx])

    # Seed walks from endpoints first (degree == 1).
    endpoints = list(zip(*np.where((degree == 1) & skel)))
    for sy, sx in endpoints:
        if visited[sy, sx]:
            continue
        path = [(sy, sx)]
        visited[sy, sx] = True
        cur = (sy, sx)
        while True:
            cands = [
                (ny, nx) for ny, nx in _neighbours(cur[0], cur[1], H, W)
                if skel[ny, nx] and not visited[ny, nx]
            ]
            if not cands:
                break
            # Prefer 4-connected neighbour over diagonal for smoother path.
            cands.sort(key=lambda c: 0 if (c[0] == cur[0] or c[1] == cur[1]) else 1)
            nxt = cands[0]
            visited[nxt] = True
            path.append(nxt)
            cur = nxt
        if len(path) >= 2:
            polylines.append(path)

    # Pick up any unvisited skeleton pixels (loops or junction-island remainders).
    while True:
        remain = np.where(skel & ~visited)
        if remain[0].size == 0:
            break
        sy, sx = remain[0][0], remain[1][0]
        path = [(sy, sx)]
        visited[sy, sx] = True
        cur = (sy, sx)
        while True:
            cands = [
                (ny, nx) for ny, nx in _neighbours(cur[0], cur[1], H, W)
                if skel[ny, nx] and not visited[ny, nx]
            ]
            if not cands:
                break
            cands.sort(key=lambda c: 0 if (c[0] == cur[0] or c[1] == cur[1]) else 1)
            nxt = cands[0]
            visited[nxt] = True
            path.append(nxt)
            cur = nxt
        if len(path) >= 2:
            polylines.append(path)
    return polylines


# ---------------------------------------------------------------------------
# Top-level: outline → list of em-coord polylines (= stroke tracks)
# ---------------------------------------------------------------------------


def outline_to_skeleton_tracks(
    outline_cmds: list[dict],
    em_size: int = 2048,
    raster_size: int = _DEFAULT_RASTER_SIZE,
    simplify_step: int = 2,
) -> list[list[tuple[float, float]]]:
    """Full pipeline: outline → rasterise → thin → trace → em coords.

    ``simplify_step`` keeps every Nth pixel along the path to reduce
    polyline length (writing-robot G-code is bandwidth-limited).
    Returns a list of tracks, each a list of ``(x, y)`` em-frame floats.
    """
    bitmap = rasterize_outline(outline_cmds, em_size=em_size,
                               raster_size=raster_size)
    if not bitmap.any():
        return []
    skel = zhang_suen(bitmap)
    if not skel.any():
        return []
    pixel_paths = trace_skeleton(skel)
    # Convert (y, x) pixel coords → (x, y) em coords (and downsample).
    scale = em_size / raster_size
    out: list[list[tuple[float, float]]] = []
    for path in pixel_paths:
        if simplify_step > 1:
            kept = path[::simplify_step]
            if kept[-1] != path[-1]:
                kept.append(path[-1])
        else:
            kept = path
        em_path = [(x * scale + scale / 2.0, y * scale + scale / 2.0)
                   for (y, x) in kept]
        if len(em_path) >= 2:
            out.append(em_path)
    return out


# ---------------------------------------------------------------------------
# Phase 5aq Path 2 — junction-aware splitting
#
# v1 pipeline (above) walks the skeleton from endpoints and treats
# junctions implicitly, often merging or fragmenting CJK strokes that
# share a junction (十's cross, 王's three horizontals tied to the
# vertical, etc). v2 splits the skeleton AT every junction, then
# greedily merges colinear segments back so straight strokes that pass
# through a junction stay intact while right-angle corners stay split.
# ---------------------------------------------------------------------------


def _crossing_number(skel: np.ndarray, y: int, x: int) -> int:
    """Number of 0→1 transitions in the 8-neighbourhood ring (P2..P9,P2).

    Standard topological branch-point metric used in skeleton analysis:

    - 0 → isolated pixel
    - 1 → endpoint OR pixel sitting on the convex side of a turn
    - 2 → curve interior (most pixels)
    - ≥3 → true branch point (T/Y/X junction)

    Diagonal staircase artefacts from Zhang-Suen produce degree ≥ 3 in
    the naive sense but crossing_number == 2, which is what we want.
    """
    H, W = skel.shape
    # P2..P9 going CLOCKWISE from north (matches the Zhang-Suen step).
    ring_offsets = [(-1, 0), (-1, 1), (0, 1), (1, 1),
                    (1, 0), (1, -1), (0, -1), (-1, -1)]
    ring = []
    for dy, dx in ring_offsets:
        ny, nx = y + dy, x + dx
        ring.append(bool(skel[ny, nx])
                    if 0 <= ny < H and 0 <= nx < W else False)
    transitions = 0
    for i in range(8):
        a = ring[i]
        b = ring[(i + 1) % 8]
        if (not a) and b:
            transitions += 1
    return transitions


def detect_junctions(skel: np.ndarray) -> set[tuple[int, int]]:
    """Return ``{(y, x), ...}`` of pixels whose crossing number ≥ 3.

    Uses topological crossing number (number of 0→1 transitions in the
    clockwise 8-neighbour ring) instead of raw degree, so diagonal
    staircase artefacts from Zhang-Suen aren't mistaken for branches.
    """
    H, W = skel.shape
    junctions: set[tuple[int, int]] = set()
    ys, xs = np.where(skel)
    for y, x in zip(ys, xs):
        if _crossing_number(skel, int(y), int(x)) >= 3:
            junctions.add((int(y), int(x)))
    return junctions


def prune_spurs(skel: np.ndarray, max_length: int = 3) -> np.ndarray:
    """Iteratively remove short branches (≤ ``max_length`` pixels).

    Zhang-Suen on rasterised diagonals leaves "staircase" artefacts:
    short 2-3 pixel spurs hanging off a longer line. They show up as
    extra endpoints/junctions and explode the count of atomic segments.
    Pruning them once before splitting at junctions gives a much
    cleaner segmentation.
    """
    H, W = skel.shape
    out = skel.copy()
    for _ in range(max_length):
        deg = _degree_map(out)
        endpoints = list(zip(*np.where((deg == 1) & out)))
        # An "endpoint" pixel is part of a spur if walking inward for
        # ≤ max_length steps reaches a junction (degree ≥ 3).
        to_remove: list[tuple[int, int]] = []
        for ey, ex in endpoints:
            ey, ex = int(ey), int(ex)
            path = [(ey, ex)]
            cur = (ey, ex)
            prev = None
            for _step in range(max_length):
                nxts = [(ny, nx) for ny, nx in _neighbours(cur[0], cur[1], H, W)
                        if out[ny, nx] and (ny, nx) != prev]
                if not nxts:
                    break
                if len(nxts) >= 2:
                    # Reached a junction-ish pixel — every pixel walked
                    # so far is spur and should go.
                    to_remove.extend(path)
                    break
                prev = cur
                cur = nxts[0]
                path.append(cur)
        if not to_remove:
            break
        for y, x in to_remove:
            out[y, x] = False
    return out


def _coalesce_junction_clusters(
    skel: np.ndarray,
    junctions: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    """Collapse touching junctions into one representative pixel each.

    A diagonal that thins to staircase pixels often produces 2-3 adjacent
    degree-3 pixels — they're really a single conceptual junction. Pick
    one representative per cluster (top-left of the cluster) so the
    splitter doesn't emit zero-length segments between them.
    """
    H, W = skel.shape
    if not junctions:
        return junctions
    visited: set[tuple[int, int]] = set()
    representatives: set[tuple[int, int]] = set()
    for j in junctions:
        if j in visited:
            continue
        # BFS through adjacent junction pixels.
        cluster = [j]
        stack = [j]
        visited.add(j)
        while stack:
            cur = stack.pop()
            for ny, nx in _neighbours(cur[0], cur[1], H, W):
                p = (ny, nx)
                if p in junctions and p not in visited:
                    visited.add(p)
                    cluster.append(p)
                    stack.append(p)
        # Representative = top-left of cluster (deterministic).
        rep = min(cluster, key=lambda p: (p[0], p[1]))
        representatives.add(rep)
    return representatives


def _degree_map(skel: np.ndarray) -> np.ndarray:
    H, W = skel.shape
    deg = np.zeros_like(skel, dtype=np.uint8)
    ys, xs = np.where(skel)
    for y, x in zip(ys, xs):
        deg[y, x] = sum(1 for ny, nx in _neighbours(int(y), int(x), H, W)
                        if skel[ny, nx])
    return deg


def split_at_junctions(
    skel: np.ndarray,
) -> list[list[tuple[int, int]]]:
    """Split the skeleton into atomic segments delimited by node pixels.

    A node is any pixel that is an endpoint (degree 1) or junction
    (degree ≥ 3). Returns a list of segments, each being a sequence of
    ``(y, x)`` pixel coords. Single-pixel segments are dropped.

    Properties:
    - Junction pixels themselves appear at most as endpoints of the
      adjacent segments (one copy per outgoing branch) so subsequent
      merging can stitch segments back together.
    - Pure cycles with no junction (rare in CJK) are picked up after the
      node-driven walks so we don't lose closed loops.
    """
    H, W = skel.shape
    deg = _degree_map(skel)
    # Endpoints stay degree-based (degree 1 = single neighbour, period).
    # Junction detection uses crossing number to ignore diagonal staircase
    # noise that would otherwise inflate node count by 50-100×.
    is_endpoint = (deg == 1) & skel
    is_junction = np.zeros_like(skel, dtype=bool)
    junctions = detect_junctions(skel)
    for jy, jx in junctions:
        is_junction[jy, jx] = True
    is_node = is_endpoint | is_junction
    visited_edges: set[frozenset[tuple[int, int]]] = set()
    segments: list[list[tuple[int, int]]] = []

    def _walk_from(start: tuple[int, int],
                   first_step: tuple[int, int]) -> list[tuple[int, int]]:
        """Walk from ``start`` through ``first_step`` until we hit any node."""
        path = [start, first_step]
        cur = first_step
        prev = start
        while not is_node[cur]:
            # exactly degree 2 here — pick the neighbour that isn't prev
            nxt = None
            for ny, nx in _neighbours(cur[0], cur[1], H, W):
                if not skel[ny, nx]:
                    continue
                if (ny, nx) == prev:
                    continue
                nxt = (ny, nx)
                break
            if nxt is None:
                break   # defensive: stranded interior pixel
            path.append(nxt)
            prev = cur
            cur = nxt
        return path

    # Seed walks from every node in every outgoing direction.
    nodes = list(zip(*np.where(is_node)))
    for ny_, nx_ in nodes:
        node = (int(ny_), int(nx_))
        for n2y, n2x in _neighbours(node[0], node[1], H, W):
            if not skel[n2y, n2x]:
                continue
            edge = frozenset({node, (n2y, n2x)})
            if edge in visited_edges:
                continue
            seg = _walk_from(node, (n2y, n2x))
            if len(seg) < 2:
                continue
            # Mark the first and last edges to avoid re-walking from the
            # other end. Only the first/last steps need recording — interior
            # edges are unambiguous (degree-2 pixels can't be re-entered).
            visited_edges.add(frozenset({seg[0], seg[1]}))
            visited_edges.add(frozenset({seg[-2], seg[-1]}))
            segments.append(seg)

    # Pick up any nodeless cycle (degree-2-only loop). Rare in CJK glyphs
    # but possible (e.g. a perfectly clean 口 with no junction).
    visited_pixels = {p for seg in segments for p in seg}
    leftover = np.where(skel & ~_pixels_to_mask(visited_pixels, H, W))
    if leftover[0].size > 0:
        sy, sx = int(leftover[0][0]), int(leftover[1][0])
        cycle = [(sy, sx)]
        prev = (sy, sx)
        cur = None
        for ny, nx in _neighbours(sy, sx, H, W):
            if skel[ny, nx]:
                cur = (ny, nx)
                break
        if cur is not None:
            cycle.append(cur)
            while cur != (sy, sx):
                nxt = None
                for ny, nx in _neighbours(cur[0], cur[1], H, W):
                    if not skel[ny, nx]:
                        continue
                    if (ny, nx) == prev:
                        continue
                    nxt = (ny, nx)
                    break
                if nxt is None:
                    break
                cycle.append(nxt)
                prev = cur
                cur = nxt
            if len(cycle) >= 3:
                segments.append(cycle)

    return segments


def _pixels_to_mask(pixels: set[tuple[int, int]], H: int, W: int) -> np.ndarray:
    m = np.zeros((H, W), dtype=bool)
    for y, x in pixels:
        if 0 <= y < H and 0 <= x < W:
            m[y, x] = True
    return m


def _segment_tangent(seg: list[tuple[int, int]],
                     at_start: bool,
                     n_pixels: int = 5) -> tuple[float, float]:
    """Unit-ish tangent vector pointing AWAY from one end of the segment.

    Looking at ``n_pixels`` from the chosen end so the tangent isn't
    dominated by single-pixel staircase noise.
    """
    if len(seg) < 2:
        return (0.0, 0.0)
    n = min(n_pixels, len(seg) - 1)
    if at_start:
        a = seg[0]
        b = seg[n]
    else:
        a = seg[-1]
        b = seg[-1 - n]
    dy = b[0] - a[0]
    dx = b[1] - a[1]
    norm = (dy * dy + dx * dx) ** 0.5 or 1.0
    return (dy / norm, dx / norm)


def merge_collinear(
    segments: list[list[tuple[int, int]]],
    angle_threshold_deg: float = 35.0,
    max_passes: int = 200,
) -> list[list[tuple[int, int]]]:
    """At each shared junction, greedily merge the two segments whose
    tangent vectors continue most smoothly through the junction.

    A pair only merges when the angle between (incoming tangent) and
    (continuation of outgoing tangent) is below ``angle_threshold_deg``.
    Right-angle corners (e.g. the bottom-left of 口) stay split — that
    is the point: they're separate strokes in CJK.

    Greedy: each segment endpoint is matched at most once per pass; we
    repeat until no more merges happen.
    """
    import math
    cos_threshold = math.cos(math.radians(angle_threshold_deg))

    # Index segments by their endpoints. A segment may be merged into
    # another, in which case its entry is set to None and we skip it.
    segs: list[Optional[list[tuple[int, int]]]] = [list(s) for s in segments]

    def _all_junction_pixels() -> dict[tuple[int, int], list[tuple[int, bool]]]:
        """Map junction pixel → list of (segment_index, at_start_endpoint)."""
        idx: dict[tuple[int, int], list[tuple[int, bool]]] = {}
        for i, s in enumerate(segs):
            if s is None:
                continue
            idx.setdefault(s[0], []).append((i, True))
            idx.setdefault(s[-1], []).append((i, False))
        return idx

    pass_count = 0
    while pass_count < max_passes:
        pass_count += 1
        merged_any = False
        end_index = _all_junction_pixels()
        # Only consider pixels that are shared by ≥ 2 segments — these
        # are the actual junctions to merge across.
        for pixel, owners in end_index.items():
            if len(owners) < 2:
                continue
            # Compute outgoing tangents (always pointing AWAY from junction).
            tangents = []
            for seg_i, at_start in owners:
                s = segs[seg_i]
                if s is None:
                    continue
                tangents.append(((seg_i, at_start),
                                 _segment_tangent(s, at_start=at_start)))
            if len(tangents) < 2:
                continue
            # Find the pair with the most-collinear continuation. Two
            # tangents (a) and (b) "continue smoothly" when -a · b ≈ 1
            # (segment 1 ends pointing one way, segment 2 leaves the
            # opposite way through the junction → straight line).
            best_score = cos_threshold
            best_pair: Optional[tuple] = None
            for i in range(len(tangents)):
                (si, sai), ti = tangents[i]
                for j in range(i + 1, len(tangents)):
                    (sj, saj), tj = tangents[j]
                    # smooth continuation = anti-parallel tangents
                    score = -(ti[0] * tj[0] + ti[1] * tj[1])
                    if score > best_score:
                        best_score = score
                        best_pair = (si, sai, sj, saj)
            if best_pair is None:
                continue
            si, sai, sj, saj = best_pair
            a = segs[si]
            b = segs[sj]
            if a is None or b is None:
                continue
            # Splice b onto a; skip the duplicated junction pixel.
            if sai and saj:
                merged = list(reversed(a))[:-1] + b
            elif sai and not saj:
                merged = list(reversed(b))[:-1] + a   # reverse a's start
            elif not sai and saj:
                merged = a[:-1] + b
            else:  # not sai and not saj
                merged = a[:-1] + list(reversed(b))
            segs[si] = merged
            segs[sj] = None
            merged_any = True
            break  # restart scan with fresh index
        if not merged_any:
            break

    return [s for s in segs if s is not None]


def sort_writing_order(
    tracks: list[list[tuple[float, float]]],
) -> list[list[tuple[float, float]]]:
    """Sort tracks by CJK writing convention: top-to-bottom then
    left-to-right based on each track's bbox top-left corner.

    This is a coarse approximation — it doesn't know about radicals,
    "outside-before-inside" rules, or specific kind-code priorities.
    Sufficient for G-code where any consistent ordering beats none.
    """
    def _key(t: list[tuple[float, float]]) -> tuple[float, float]:
        ys = [p[1] for p in t]
        xs = [p[0] for p in t]
        return (min(ys), min(xs))
    return sorted(tracks, key=_key)


def outline_to_skeleton_tracks_v2(
    outline_cmds: list[dict],
    em_size: int = 2048,
    raster_size: int = _DEFAULT_RASTER_SIZE,
    simplify_step: int = 2,
    angle_threshold_deg: float = 35.0,
    spur_max_length: int = 4,
) -> list[list[tuple[float, float]]]:
    """Phase 5aq Path 2 pipeline.

    Same rasterise + thin as v1, then:

    1. Prune short spurs (Zhang-Suen staircase artefacts that masquerade
       as extra strokes).
    2. Split at junctions into atomic segments.
    3. Greedily merge collinear continuations so right-angle corners
       survive but straight strokes through a junction (十's horizontal)
       stay whole.
    4. Sort tracks into rough CJK writing order.
    """
    bitmap = rasterize_outline(outline_cmds, em_size=em_size,
                               raster_size=raster_size)
    if not bitmap.any():
        return []
    skel = zhang_suen(bitmap)
    if not skel.any():
        return []
    if spur_max_length > 0:
        skel = prune_spurs(skel, max_length=spur_max_length)
        if not skel.any():
            return []
    segments = split_at_junctions(skel)
    if not segments:
        return []
    merged = merge_collinear(segments, angle_threshold_deg=angle_threshold_deg)

    # Convert (y, x) pixel coords → (x, y) em coords with optional downsample.
    scale = em_size / raster_size
    em_tracks: list[list[tuple[float, float]]] = []
    for path in merged:
        if simplify_step > 1:
            kept = path[::simplify_step]
            if kept[-1] != path[-1]:
                kept.append(path[-1])
        else:
            kept = path
        em_path = [(x * scale + scale / 2.0, y * scale + scale / 2.0)
                   for (y, x) in kept]
        if len(em_path) >= 2:
            em_tracks.append(em_path)

    return sort_writing_order(em_tracks)


__all__ = [
    "rasterize_outline",
    "zhang_suen",
    "trace_skeleton",
    "outline_to_skeleton_tracks",
    # Phase 5aq
    "detect_junctions",
    "prune_spurs",
    "split_at_junctions",
    "merge_collinear",
    "sort_writing_order",
    "outline_to_skeleton_tracks_v2",
]
