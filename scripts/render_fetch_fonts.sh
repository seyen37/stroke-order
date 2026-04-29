#!/usr/bin/env bash
# =====================================================================
# Render.com build-phase font fetcher — stroke-order
#
# Downloads the 10 third-party font files into ~/.stroke-order/<type>/
# during Render build, so the deployed app can serve seal / lishu /
# mingti / kaishu / CNS-fallback styles instead of falling back to
# fonts-not-loaded warnings.
#
# Hosted as GitHub Release assets on the canonical repo:
#   https://github.com/seyen37/stroke-order/releases/tag/fonts-v1
#
# All five font sources are redistributable under their respective
# licenses (CNS = Taiwan Open Data Lic 1.0; chongxi_seal = CC BY-ND;
# MOE 楷/隸/宋 = Taiwan government public works). LICENSE末段 carries
# the full attribution block.
#
# Design: graceful per-font failure
# ---------------------------------
# Each font is downloaded in its own try-block. A failed download
# (network blip, GitHub temporarily 503ing, missing release asset)
# logs a warning but does NOT abort the build — the app's existing
# fallback path (5aj filter, kaishu-as-fallback) keeps the site
# functional, just with that one style unavailable.
#
# Re-runs are cheap: existing files are skipped (curl -z timestamp).
# =====================================================================

set -u   # Treat unset vars as errors. Do NOT set -e — we want graceful
         # per-font failure, not whole-build abort.

REL_BASE="${STROKE_ORDER_FONTS_REL_BASE:-https://github.com/seyen37/stroke-order/releases/download/fonts-v1}"

# Destination directory — defaults to ./.fonts/ (relative to git checkout
# root, which is Render's build artifact path /opt/render/project/src/).
# Build phase writes here, runtime reads from here via the
# STROKE_ORDER_*_FONT_DIR / _FILE env vars set in render.yaml.
#
# Why not $HOME/.stroke-order? Because Render's build user home is
# ephemeral — files written there during build do NOT survive into the
# runtime container. /opt/render/project/src/ is the git checkout path
# and IS preserved across the build → runtime handoff.
#
# Local dev (where $HOME/.stroke-order is the long-standing convention)
# keeps working: STROKE_ORDER_FONTS_DEST is just unset and we fall back.
FONT_BASE="${STROKE_ORDER_FONTS_DEST:-$HOME/.stroke-order}"

mkdir -p \
  "$FONT_BASE/cns-fonts"    \
  "$FONT_BASE/seal-fonts"   \
  "$FONT_BASE/lishu-fonts"  \
  "$FONT_BASE/song-fonts"   \
  "$FONT_BASE/kaishu-fonts"

ok=0
fail=0

# ---------------------------------------------------------------------
# fetch_one: download a single font with retry + size sanity check
#
# Args:
#   $1 = relative URL path (after REL_BASE/)
#   $2 = absolute target path
#   $3 = minimum expected size in bytes (sanity check)
#
# Behavior:
#   - skip if file already exists with size >= min
#   - retry up to 3 times with 5s backoff
#   - on success: increment $ok
#   - on persistent failure: increment $fail and continue (no abort)
# ---------------------------------------------------------------------
fetch_one() {
  local rel="$1"
  local out="$2"
  local min_size="$3"

  if [ -f "$out" ]; then
    local cur_size
    cur_size=$(stat -c %s "$out" 2>/dev/null || stat -f %z "$out" 2>/dev/null || echo 0)
    if [ "$cur_size" -ge "$min_size" ]; then
      echo "[fetch_fonts] SKIP $out (already $cur_size bytes)"
      ok=$((ok + 1))
      return 0
    fi
  fi

  local url="$REL_BASE/$rel"
  echo "[fetch_fonts] FETCH $rel  →  $out"

  local attempt
  for attempt in 1 2 3; do
    if curl -fsSL --retry 2 --retry-delay 3 --max-time 120 \
         "$url" -o "$out.tmp"; then
      local got_size
      got_size=$(stat -c %s "$out.tmp" 2>/dev/null || stat -f %z "$out.tmp" 2>/dev/null || echo 0)
      if [ "$got_size" -ge "$min_size" ]; then
        mv "$out.tmp" "$out"
        echo "[fetch_fonts] OK    $out  ($got_size bytes)"
        ok=$((ok + 1))
        return 0
      else
        echo "[fetch_fonts] WARN  $out got $got_size bytes (< min $min_size); attempt $attempt failed"
        rm -f "$out.tmp"
      fi
    else
      echo "[fetch_fonts] WARN  curl failed for $url (attempt $attempt/3)"
    fi
    [ "$attempt" -lt 3 ] && sleep 5
  done

  echo "[fetch_fonts] FAIL  $out after 3 attempts — falling back to skip-this-style"
  fail=$((fail + 1))
  return 0   # never propagate the error — graceful fallback
}

# ---------------------------------------------------------------------
# Per-font download list. min_size = 50% of typical real size, to
# detect truncated or HTML-error-page downloads.
# ---------------------------------------------------------------------

# CNS 全字庫 (6 TTFs, ~50-100 MB each)
fetch_one "TW-Kai-98_1.ttf"           "$FONT_BASE/cns-fonts/TW-Kai-98_1.ttf"           20000000
fetch_one "TW-Kai-Ext-B-98_1.ttf"     "$FONT_BASE/cns-fonts/TW-Kai-Ext-B-98_1.ttf"     20000000
fetch_one "TW-Kai-Plus-98_1.ttf"      "$FONT_BASE/cns-fonts/TW-Kai-Plus-98_1.ttf"       1000000
fetch_one "TW-Sung-98_1.ttf"          "$FONT_BASE/cns-fonts/TW-Sung-98_1.ttf"          20000000
fetch_one "TW-Sung-Ext-B-98_1.ttf"    "$FONT_BASE/cns-fonts/TW-Sung-Ext-B-98_1.ttf"    20000000
fetch_one "TW-Sung-Plus-98_1.ttf"     "$FONT_BASE/cns-fonts/TW-Sung-Plus-98_1.ttf"      1000000

# 崇羲篆體 (CC BY-ND, ~5 MB)
fetch_one "chongxi_seal.otf"          "$FONT_BASE/seal-fonts/chongxi_seal.otf"           500000

# 教育部隸書 (~5 MB)
fetch_one "MoeLI.ttf"                 "$FONT_BASE/lishu-fonts/MoeLI.ttf"                 500000

# 教育部宋體 (~10 MB)
fetch_one "edusong_Unicode.ttf"       "$FONT_BASE/song-fonts/edusong_Unicode.ttf"       1000000

# 教育部楷書 (~10 MB)
fetch_one "edukai.ttf"                "$FONT_BASE/kaishu-fonts/edukai.ttf"              1000000

# ---------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------
total=$((ok + fail))
echo ""
echo "[fetch_fonts] ============================================="
echo "[fetch_fonts] Summary: $ok ok / $fail fail / $total total"
echo "[fetch_fonts] Font tree:"
ls -lh "$FONT_BASE"/*/ 2>/dev/null | sed 's/^/[fetch_fonts]   /'
echo "[fetch_fonts] ============================================="

# Exit 0 even when some fonts failed — Render build should succeed
# and let the app run with degraded font coverage. The /api/fonts
# health endpoint reports which styles are actually loaded, so the
# UI's existing 字型載入狀態 dialog stays the source of truth.
exit 0
