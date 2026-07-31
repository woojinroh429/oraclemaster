#!/bin/bash
# Does making the anchor BIND improve the full pipeline, or only a single regrow?
#
# Measured on a single regrow, anchoring on the incumbent's own assignment now improves
# monotonically with the weight -- 152,485 -> 140,335 -> 115,515 as stay goes 0.25x, 1x, 4x w3 --
# where before the fix every weight returned the same answer.  But _regrow is one operator inside
# a portfolio that also runs fresh beams, balance and preference passes and keeps the best of all
# of them, so a better regrow is not automatically a better pipeline.  That is what this measures.
#
# Paired and sequential: each arm gets the whole machine and the real per-instance time limit, and
# the two arms differ in exactly four lines of ogc_fast.cpp (CBState::ganch and its use in the
# beam's pruning key).  The engine is swapped by mv, never written over in place -- copying onto a
# live .so SIGBUSes any process holding it.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
EXT="cpython-312-x86_64-linux-gnu.so"
NEW="/tmp/ogc_new.$EXT"
OLD="/tmp/ogc_old.$EXT"
INC="$(python3.12 -m pybind11 --includes)"

[ -f "$NEW" ] || g++ -O3 -shared -std=c++17 -fPIC -w -fopenmp $INC ogc_fast.cpp -o "$NEW" || exit 1
[ -f "$OLD" ] || g++ -O3 -shared -std=c++17 -fPIC -w -fopenmp $INC /tmp/ogc_fast_old.cpp -o "$OLD" || exit 1
echo "both engines built  $(date -u +%H:%M:%S)"

declare -A LIM=([3]=240 [4]=480 [5]=600)
for rep in 1 2; do
  for arm in new old; do
    src=$NEW; [ "$arm" = old ] && src=$OLD
    cp "$src" "/tmp/stage.$EXT" && mv "/tmp/stage.$EXT" "ogc_fast.$EXT"
    for p in 3 4 5; do
      out="results/ab_anchor_p${p}_${arm}_r${rep}.log"
      [ -s "$out" ] && continue
      echo "=== rep$rep $arm P$p (${LIM[$p]}s)  $(date -u +%H:%M:%S)"
      python3.12 harness/run1.py myalg_base "$p" "${LIM[$p]}" > "$out" 2>&1
      tail -2 "$out"
    done
  done
done
echo "done  $(date -u +%H:%M:%S)"
