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

[ -f /tmp/ogc_fast_old.cpp ] || git -C "$(pwd)" show 7eb4f34:research/exact_packer/session2/recon/ogc_fast.cpp > /tmp/ogc_fast_old.cpp || exit 1
[ -f "$NEW" ] || g++ -O3 -shared -std=c++17 -fPIC -w -fopenmp $INC ogc_fast.cpp -o "$NEW" || exit 1
[ -f "$OLD" ] || g++ -O3 -shared -std=c++17 -fPIC -w -fopenmp $INC /tmp/ogc_fast_old.cpp -o "$OLD" || exit 1
echo "both engines built  $(date -u +%H:%M:%S)"

# P4 FIRST.  The new-engine arm returned 1,981,906 against a 2,531,937 record, and until its
# control runs that is one number with nothing to compare it to -- P4 has drifted between runs
# before.  Everything else waits until that question is settled.
declare -A LIM=([3]=240 [4]=480 [5]=600)
for spec in "1 4" "1 3" "1 5" "2 4" "2 3" "2 5"; do
  set -- $spec
  rep=$1; p=$2
  for arm in old new; do
    out="results/ab_anchor_p${p}_${arm}_r${rep}.log"
    [ -s "$out" ] && continue
    src=$NEW; [ "$arm" = old ] && src=$OLD
    cp "$src" "/tmp/stage.$EXT" && mv "/tmp/stage.$EXT" "ogc_fast.$EXT"
    echo "=== rep$rep $arm P$p (${LIM[$p]}s)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py myalg_base "$p" "${LIM[$p]}" > "$out" 2>&1
    tail -1 "$out"
    ( cd .. && git add -f "session2/recon/$out" >/dev/null 2>&1 )
  done
done
# leave the FIXED engine installed, never the control
cp "$NEW" "/tmp/stage.$EXT" && mv "/tmp/stage.$EXT" "ogc_fast.$EXT"
echo "done  $(date -u +%H:%M:%S)"
