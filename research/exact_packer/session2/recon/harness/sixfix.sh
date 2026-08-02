#!/bin/bash
# ALL SIX, at their real budgets, with the two corrections in and the self-timing build compiled.
#
# WHAT CHANGED SINCE THE LAST SIX-WAY.
#
#   1. total_s.  cranepack bounds build + search against its OWN measured build, so no caller
#      has to predict the build to keep a deadline.
#   2. The ask is the cap.  Subtracting a predicted build from it charged for the build twice.
#      Measured on P3, two reps each, interleaved:
#          ask = cap                    80,795  80,795
#          ask = cap - predicted build  87,990  87,990
#          tier 0 forced                80,795  80,795
#      7,195 of objective, six figures reproducible.
#   3. The build watches its own clock.  After a rows it has visited a*ncol - a^2/2 pairs of
#      ncol^2/2, so it projects its own completion every 256 rows and stops if the projection
#      exceeds the cap.  An unaffordable tier costs the fraction spent, not the whole overrun,
#      and the aborted result is DISCARDED rather than verified -- its graph is missing edges.
#
# WHY ALL SIX AND NOT JUST P3.  A change to the operator's budget is not allowed to be checked
# only where it helps.  P1/P2 are short-budget instances where brk barely fires and the risk is
# an abort that throws away a call that would have finished; P5 has four bays and has not been
# measured at all since the tier predictor was rewritten.  The scoring server runs all six.
#
# BASELINES to beat, and what counts as a regression:
#     P1        11,280   60 s      unchanged is the result; brk is not expected to fire
#     P2        31,368  120 s      unchanged
#     P3        80,795  240 s      must settle here, not at 87,990
#     P4     1,781,181  480 s      must hold, and inside 480
#     P5             ?  600 s      no recent number -- this run establishes it
#     P6    30,425,588  900 s      must hold, and inside 900
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

echo "== rebuild cranepack (total_s + self-timing build) $(date -u +%H:%M:%S)"
g++ -O3 -shared -std=c++17 -fPIC -w $(python3.12 -m pybind11 --includes) \
    cranepack.cpp -o cranepack.cpython-312-x86_64-linux-gnu.so || exit 1

python3.12 -c "
import inspect, bayrepack as R, cranepack as CP
r = inspect.getsource(R)
assert '_ask = max(_MINASK, _cap)' in r, 'the ask is not the cap'
assert '_cap - _PAIRRATE' not in r, 'the double charge is still there'
assert 'BRK_NOSUB' not in r, 'the knob was supposed to be deleted, not defaulted'
assert 'int(r[9]) == 1' in r, 'abort not handled'
c = inspect.getsource if False else open('cranepack.cpp').read()
assert 'projected > build_cap' in c, 'build does not watch its clock'
assert 'aborted ? 1 : 0' in c, 'abort not returned'
print('ask = cap, no double charge, no knob, abort handled, build self-timing')" || exit 1

run () {  # prob secs tag outfile
    [ -s "results/$4" ] && return
    echo "=== $4 ($3) $(date -u +%H:%M:%S)"
    CRANEPACK_NOBITS=1 BRK_DEBUG=1 timeout $(( $2 * 5 + 300 )) \
        python3.12 harness/run1.py myalg_brk "$1" "$2" "$3" > "results/$4" 2>&1
    tail -1 "results/$4"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$4" >/dev/null 2>&1 \
      && git commit -q -m "sixfix: $3" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

# P3 first: it is the claim.  Then the two deadline risks, then the three unexamined.
run 3 240 "sixfix P3" "sf_p3.log"
run 6 900 "sixfix P6" "sf_p6.log"
run 4 480 "sixfix P4" "sf_p4.log"
run 5 600 "sixfix P5" "sf_p5.log"
run 1  60 "sixfix P1" "sf_p1.log"
run 2 120 "sixfix P2" "sf_p2.log"
run 3 240 "sixfix P3 r2" "sf_p3_r2.log"
echo "sixfix done $(date -u +%H:%M:%S)"
