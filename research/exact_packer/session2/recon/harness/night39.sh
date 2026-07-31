#!/bin/bash
# Split P5's tardiness into the crane's share and the shapes' share.
#
# P5 scores 9,044,458 with Z1 = 639.  The area-only relaxation -- blocks as pure area, no shape,
# no crane -- schedules the same instance with Z1 = 8.  So 631 tardiness units are "geometry",
# but that word covers two different costs with opposite fixes:
#
#   the descent rule   a block's layer k may not pass through an existing block's layer j>=k, so
#                      whatever is already placed sterilises its footprint for later arrivals.
#                      Fixing this means a flatter skyline and co-locating tall blocks.
#   the shapes         real footprints do not tile a rectangle.  Fixing this means better
#                      orientation choice and nesting.
#
# OGC_NOCRANE=1 drops ONLY the descent rule and keeps real shapes, real overlap, real containment
# and real time windows, so:
#
#   Z1 with crane      639        what we ship
#   Z1 without crane    ?         <- this run
#   Z1 area only         8        the cumulative relaxation
#
# The middle number splits it.  Close to 639 means the descent rule is nearly free and the
# shapes are the problem; close to 8 means the descent rule is almost the whole cost.
#
# Solutions produced here are INFEASIBLE by construction -- they are a bound, like the
# cumulative relaxation, and are never shipped.  P4 and P6 run too: if the split differs across
# them, any fix aimed at one is overfitting, and that is worth knowing before building it.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
EXT="cpython-312-x86_64-linux-gnu.so"
NC="/tmp/ogc_nocrane.$EXT"
OLD="/tmp/ogc_old.$EXT"
[ -f "$NC" ] || { echo "diagnostic engine missing"; exit 1; }

declare -A LIM=([4]=480 [5]=600 [6]=900)
for p in 5 4 6; do
  for arm in crane nocrane; do
    out="results/crane_p${p}_${arm}.log"
    [ -s "$out" ] && continue
    src=$OLD; env=""
    if [ "$arm" = nocrane ]; then src=$NC; env="1"; fi
    cp "$src" "/tmp/stage4.$EXT" && mv "/tmp/stage4.$EXT" "ogc_fast.$EXT"
    echo "=== P$p $arm (${LIM[$p]}s)  $(date -u +%H:%M:%S)"
    OGC_NOCRANE="$env" python3.12 harness/run1.py myalg_base "$p" "${LIM[$p]}" > "$out" 2>&1
    tail -1 "$out"
    ( cd .. && git add -f "session2/recon/$out" >/dev/null 2>&1 )
  done
done
# never leave the diagnostic engine installed
cp "$OLD" "/tmp/stage4.$EXT" && mv "/tmp/stage4.$EXT" "ogc_fast.$EXT"
echo "done  $(date -u +%H:%M:%S)"
