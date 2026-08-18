#!/bin/bash
# shadoww: the position-dependent overhang penalty, measured against its own control.
#
# Why this and not shad_lam.  A block descending to its layer 0 is blocked by every layer j >= 0
# of what is already there, so a placed block denies its whole UNION footprint to later arrivals,
# not just the layer 0 it visually occupies.  Counted on a shipped P5 solution, that costs a
# third of each block's legal positions in its own bay and half across all bays.
#
# shad_lam was supposed to address it and cannot: shadow_excess is cached on (block, orientation)
# and takes no position, so it only picks orientations.  P5 confirmed it -- shadow 0.0 and 0.5
# returned identical objectives to the digit.
#
# shadoww scores the placement instead: of the cells this block's overhang will sterilise, how
# many are currently FREE.  Over already-occupied space the overhang is free; over free space it
# kills cells for everyone who comes later.  Charged in space-time (x stay / mean_proc) to match
# how shad_lam already scaled.
#
# P4 runs at every level too.  A term that only helps where it was tuned is overfitting, and P4
# is the one settled score (1,780,253), so it is the one that can least afford a regression.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
EXT="cpython-312-x86_64-linux-gnu.so"
[ -f /tmp/ogc_shadw.$EXT ] || { echo "engine with shadoww missing"; exit 1; }
cp "/tmp/ogc_shadw.$EXT" "/tmp/st5.$EXT" && mv "/tmp/st5.$EXT" "ogc_fast.$EXT"
echo "engine with shadoww installed  $(date -u +%H:%M:%S)"

for SW in 0.0 0.5 2.0 8.0; do
    python3.12 harness/mkbase.py 0.3 "myalg_sw${SW/./_}.py" 0 "" 0 1.0 "" "$SW" > /dev/null || exit 1
done
echo "arms built  $(date -u +%H:%M:%S)"

declare -A LIM=([5]=600 [4]=480)
for p in 5 4; do
  for SW in 0.0 0.5 2.0 8.0; do
    mod="myalg_sw${SW/./_}"
    out="results/shadw_p${p}_${SW}.log"
    [ -s "$out" ] && continue
    echo "=== P$p shadoww=$SW (${LIM[$p]}s)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$mod" "$p" "${LIM[$p]}" "shadoww=$SW" > "$out" 2>&1
    tail -1 "$out"
    ( cd .. && git add -f "session2/recon/$out" >/dev/null 2>&1 )
  done
done
echo "done  $(date -u +%H:%M:%S)"
