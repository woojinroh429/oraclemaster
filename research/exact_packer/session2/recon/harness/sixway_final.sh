#!/bin/bash
# THE SIX-WAY, on the algorithm as it will actually ship.
#
# Everything below this line is what myalgorithm.py + bayrepack.py now are:
#
#   * brk shipped, as a separate module (P3 96,990 -> 80,795)
#   * the ask is the cap, not the cap minus a predicted build (the double charge, 7,195 on P3)
#   * cranepack takes total_s and bounds build + search against its OWN measured build
#   * the build projects its own completion every 256 rows and aborts a tier it cannot afford
#   * nent derived from each instance's entry-time ceiling instead of a fitted 6/3/2/1
#   * bayrepack pruned of four closed experiments, proved equivalent on every deterministic
#     decision (real_ncol, target bay, resident and outsider counts, accept/reject)
#   * NO free-column bitset: proved identical, then measured 1.6-1.9x SLOWER and reverted
#
# WHY EVERY EARLIER NUMBER HAS TO BE RE-TAKEN.  The baselines in this session were measured
# across a moving codebase, and three of them were taken while I was compiling or solving on the
# same four cores.  A table assembled from those is not a table.  This one is measured on one
# tree, one binary, with nothing else running.
#
# WHAT COUNTS AS A REGRESSION, from the best clean number for each instance:
#
#     P1        11,280   60 s
#     P2        31,368  120 s
#     P3        80,795  240 s
#     P4     1,781,181  480 s
#     P5     9,044,458  600 s
#     P6    29,651,637  900 s        run-to-run spread on P6 is ~112,000, so anything inside
#                                    that band is noise, not a result
#
# The last stage re-takes slice-on P6.  Its earlier arm was contaminated -- I ran five g++
# compiles and a smoke solve during it -- so OGC_SLICEFIX is still undecided, and it is sitting
# in the shipped file as a branch that defaults to the OLD behaviour.  That is a gate, and it
# does not survive this queue in either direction: if it wins it becomes unconditional, if it
# loses it comes out.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

python3.12 -c "
import inspect, cranepack as CP, bayrepack as R, myalgorithm as M
c = open('cranepack.cpp').read()
assert 'USEBITS' not in c and 'freeb' not in c, 'the bitset is still in the source'
assert 'projected > build_cap' in c, 'the build does not watch its clock'
assert 'total_s' in CP.pack.__doc__ and 'max_iters' in CP.pack.__doc__, 'binary is behind source'
r = inspect.getsource(R)
assert '_ask = max(_MINASK, _cap)' in r, 'the double charge is back'
assert 'def _ne_of(_frac)' in r, 'nent is not derived'
assert 'int(r[9]) == 1' in r, 'abort not handled'
for dead in ('BRK_WISH', 'BRK_LINW', 'BRK_OLDTIER', 'BRK_TARGET'):
    assert dead not in r, dead
m = inspect.getsource(M)
assert 'import bayrepack' in m and '\"brk\"' in m, 'brk is not in the shipped file'
print('verified: brk shipped, ask=cap, total_s, self-timing build, derived nent, pruned, no bitset')" || exit 1

run () {  # prob secs tag outfile [env...]
    [ -s "results/$4" ] && return
    echo "=== $4 ($3) $(date -u +%H:%M:%S)"
    env "${@:5}" BRK_DEBUG=1 timeout $(( $2 * 5 + 300 )) \
        python3.12 harness/run1.py myalgorithm "$1" "$2" "$3" > "results/$4" 2>&1
    tail -1 "results/$4"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$4" >/dev/null 2>&1 \
      && git commit -q -m "final six-way: $3" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

run 3 240 "six P3"    "fx_p3.log"
run 6 900 "six P6"    "fx_p6.log"
run 4 480 "six P4"    "fx_p4.log"
run 5 600 "six P5"    "fx_p5.log"
run 1  60 "six P1"    "fx_p1.log"
run 2 120 "six P2"    "fx_p2.log"
run 3 240 "six P3 r2" "fx_p3_r2.log"
run 6 900 "six P6 slice-on" "fx_p6_slice.log" OGC_SLICEFIX=1
echo "sixway done $(date -u +%H:%M:%S)"
