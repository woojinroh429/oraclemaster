#!/bin/bash
# P4 and P5, properly compared.  Every number I have for these two came from a different build
# under different conditions, so the ranking I have been reasoning from is not a measurement:
#
#   P4   myalg_orig 2,641,820 | "baseline" 2,531,937 | myalg_base 1,780,253-1,981,906
#   P5   myalgorithm 8,972,672 | myalg_base 9,044,458 | ctl 9,299,083
#
# myalg_base wins P4 by a wide margin and LOSES P5 to the deployed build.  Both cannot be the
# base to build on, and picking wrong wastes whatever comes next.  So: three builds, both
# instances, real time limits, sequential so each gets the whole machine, repeated so a single
# lucky run cannot decide it.
#
#   myalgorithm  the deployed build
#   myalg_base   our experimental base (c80551b + the arms mkbase.py generates)
#   myalg_orig   c80551b verbatim, the common ancestor
#
# The engine is pinned to ONE build for the whole sweep -- the anchor A/B showed the .so matters
# (P4 1,780,253 old vs 1,981,906 new), so leaving it to whatever was last installed would
# confound every row here.  The control engine is the one that wins P4, so that is what runs.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
EXT="cpython-312-x86_64-linux-gnu.so"
OLD="/tmp/ogc_old.$EXT"
if [ -f "$OLD" ]; then
    cp "$OLD" "/tmp/stage3.$EXT" && mv "/tmp/stage3.$EXT" "ogc_fast.$EXT"
    echo "engine pinned to the control build  $(date -u +%H:%M:%S)"
fi

declare -A LIM=([4]=480 [5]=600)
for rep in 1 2; do
  for p in 4 5; do
    for mod in myalgorithm myalg_base myalg_orig; do
      out="results/cmp_p${p}_${mod}_r${rep}.log"
      [ -s "$out" ] && continue
      echo "=== rep$rep P$p $mod (${LIM[$p]}s)  $(date -u +%H:%M:%S)"
      python3.12 harness/run1.py "$mod" "$p" "${LIM[$p]}" > "$out" 2>&1
      tail -1 "$out"
      ( cd .. && git add -f "session2/recon/$out" >/dev/null 2>&1 )
    done
  done
done
echo "done  $(date -u +%H:%M:%S)"
