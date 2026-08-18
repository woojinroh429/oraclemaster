#!/bin/bash
# STOP REWARDING AN OPERATOR FOR FAILING, and re-take P6 with the sweep direction that won.
#
# THE DEFECT.  In the operator loop:
#
#     elif ops[k][3]:
#         if s is None:
#             slot[k] = min(budget * 0.45, slot[k] * 1.3)
#
# Field 3 means "starves without budget".  For a beam that is true -- handed too little time it
# returns nothing and wants more.  brk carries the same flag, but its None almost always means a
# displaced block could not be rehomed: infeasible, not starved.  So failing GROWS its share, to
# as much as 45% of the run, and P6 is where brk fails most -- on a 900 s run, up to 405 s to an
# operator that just came back empty.
#
# THE FIX asks everybody the same question, from behaviour rather than registration: an operator
# that SPENT its slice and returned nothing was starved; one that returned nothing cheaply was
# exhausted, and more time will not change that.  No per-operator exception, no instance test.
#
#     if s is None and (not _SLICEFIX or el >= 0.6 * slot[k]):  grow
#
# WHY THIS QUEUE ALSO CARRIES swx.  sweepdir finished and arm C -- every worker filling x-major
# -- came in at 29,285,474 against 29,651,637.  366,163 better, nothing else regressed (P3
# 80,795, P4 1,781,181, P5 9,044,458 all unchanged under the half-and-half arm).  It is small
# next to GRASP's 2.4M and I was wrong to call the direction axis the route to 27M, but a
# measured improvement that costs nothing elsewhere is worth carrying, and testing it together
# with the slice rule is how they get scored as the combination that would actually ship.
#
# BASELINES: P6 29,651,637 | P3 80,795 | P4 1,781,181 | P5 9,044,458
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 \
    python3.12 harness/mkbase.py 0.3 myalg_slf.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 OGC_WDIV='swy:0.01;swx:1.0' \
    python3.12 harness/mkbase.py 0.3 myalg_slx.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1

python3.12 -c "
import inspect, myalg_slf as M, myalg_slx as X
s = inspect.getsource(M)
assert 'el >= 0.6 * slot[k]' in s, 'slice rule not generated'
assert '_SLICEFIX = os.environ.get' in s, 'flag not generated'
assert \"[0.01]\" in inspect.getsource(X), 'x-major override missing from the swx arm'
print('arms built: slice rule present, default off; swx arm carries the worker override')" || exit 1

run () {  # tag outfile module prob secs slicefix
    [ -s "results/$2" ] && return
    echo "=== $2 ($1) $(date -u +%H:%M:%S)"
    env CRANEPACK_NOBITS=1 OGC_SLICEFIX="$6" BRK_DEBUG=1 timeout $(( $5 * 5 + 300 )) \
        python3.12 harness/run1.py "$3" "$4" "$5" "$1" > "results/$2" 2>&1
    tail -1 "results/$2"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$2" >/dev/null 2>&1 \
      && git commit -q -m "slicefix: $1" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

# the paired question first, on the instance the defect is supposed to be hurting
run "slice on P6"      "sf2_on_p6.log"   myalg_slf 6 900 1
run "slice off P6"     "sf2_off_p6.log"  myalg_slf 6 900 0
# then the combination that would ship, and the three that must not regress
run "slice+swx P6"     "sf2_sx_p6.log"   myalg_slx 6 900 1
run "slice on P3"      "sf2_on_p3.log"   myalg_slf 3 240 1
run "slice on P4"      "sf2_on_p4.log"   myalg_slf 4 480 1
run "slice on P5"      "sf2_on_p5.log"   myalg_slf 5 600 1
echo "slicefix done $(date -u +%H:%M:%S)"
