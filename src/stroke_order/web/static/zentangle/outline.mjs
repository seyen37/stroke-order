// Phase 6z-1C — Pure outline geometry helpers.
//
// Kept ESM (.mjs) so Node `node:test` can import without a bundler — see
// PRINCIPLES.md §4.1 (pure logic abstracted to .mjs for unit tests) and
// the existing toast.mjs / hash.mjs / avatar.mjs precedent.
//
// Exports (all pure, no DOM):
//   computeBbox(contours)            -> {minX, minY, maxX, maxY, width, height}
//   mapContourToTile(contours, bbox, tileSize, margin) -> contours in tile-local px
//   contoursAreClosed(contours)      -> bool (all polylines have ≥3 points)
//
// Data shape: contours = [[[x, y], [x, y], ...], ...]   (array of polylines)
// Input coords: EM-scaled Y-down (from /api/zentangle/outline)
// Output coords: tile-local px (origin = tile top-left)

/**
 * Compute axis-aligned bounding box across all polyline points.
 * Returns null when contours is empty / has no points.
 */
export function computeBbox(contours) {
  if (!Array.isArray(contours) || contours.length === 0) return null;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  let count = 0;
  for (const poly of contours) {
    if (!Array.isArray(poly)) continue;
    for (const pt of poly) {
      if (!Array.isArray(pt) || pt.length < 2) continue;
      const [x, y] = pt;
      if (typeof x !== "number" || typeof y !== "number") continue;
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
      count++;
    }
  }
  if (count === 0) return null;
  return {
    minX, minY, maxX, maxY,
    width: maxX - minX,
    height: maxY - minY,
  };
}

/**
 * Map EM-coords contours to tile-local px, centered with uniform scale.
 *
 * @param {Array} contours - input polylines in EM coords
 * @param {Object} bbox    - precomputed bbox (or pass null to recompute)
 * @param {number} tileSize - tile canvas px (square assumed; e.g. 600)
 * @param {number} margin  - inset margin in px (e.g. 60 = ~10% of 600)
 * @returns {Array} contours in tile-local px coords (origin = top-left)
 *
 * Uses uniform scaling (longest bbox axis fits into tileSize - 2*margin) so
 * glyph proportions are preserved. The character is centered horizontally
 * AND vertically inside the inner box.
 */
export function mapContourToTile(contours, bbox, tileSize, margin) {
  if (!Array.isArray(contours) || contours.length === 0) return [];
  const bb = bbox || computeBbox(contours);
  if (!bb) return [];
  if (typeof tileSize !== "number" || tileSize <= 0) {
    throw new RangeError(`tileSize must be > 0; got ${tileSize}`);
  }
  if (typeof margin !== "number" || margin < 0 || margin * 2 >= tileSize) {
    throw new RangeError(
      `margin must be in [0, tileSize/2); got margin=${margin}, tileSize=${tileSize}`
    );
  }
  const inner = tileSize - 2 * margin;
  // Avoid division by zero for degenerate bbox (single point glyphs).
  const w = bb.width > 0 ? bb.width : 1;
  const h = bb.height > 0 ? bb.height : 1;
  const scale = Math.min(inner / w, inner / h);
  // Scaled width/height of the glyph after applying uniform scale.
  const scaledW = bb.width * scale;
  const scaledH = bb.height * scale;
  // Center inside the inner box.
  const offsetX = margin + (inner - scaledW) / 2;
  const offsetY = margin + (inner - scaledH) / 2;
  const out = [];
  for (const poly of contours) {
    if (!Array.isArray(poly) || poly.length === 0) continue;
    const mapped = [];
    for (const pt of poly) {
      if (!Array.isArray(pt) || pt.length < 2) continue;
      const [x, y] = pt;
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
      mapped.push([
        offsetX + (x - bb.minX) * scale,
        offsetY + (y - bb.minY) * scale,
      ]);
    }
    if (mapped.length >= 2) out.push(mapped);
  }
  return out;
}

/**
 * Validate that every contour has ≥3 distinct points (i.e. could form a
 * closed polygon). Used by frontend defence before rendering.
 */
export function contoursAreClosed(contours) {
  if (!Array.isArray(contours) || contours.length === 0) return false;
  for (const poly of contours) {
    if (!Array.isArray(poly) || poly.length < 3) return false;
  }
  return true;
}
