#!/bin/bash
# DIRECTED brk: does taking the target and the outsider list from an exact reassignment beat
# taking them from pressure and single-move gain?
#
# WHY THE OPERATOR NEEDS DIRECTING.  Outsiders are ranked by their own SINGLE-move gain, which
# is the right price for one block and the wrong price for a SET, because Z2 is a RANGE: moving
# one block off the extreme bay only helps until another bay becomes the extreme.  Individually
# profitable moves stop paying together, and jointly profitable ones can each look worthless
# alone.  masterprobe3 priced what that costs, from an incumbent of 86,665:
#
#     K=1  79,492     K=2  72,438     K=3  65,426     K=4  59,292     K=16  36,759
#
# K=16 is the capacity-aware bound to six digits, and masterprobe2 showed the refusal is the
# PACKER's rather than the model's -- which is this operator's whole job description.
#
# WHY THIS IS MEASURED IN THE PIPELINE AND NOT IN A PROBE.  wishprobe called the operator
# directly on a saved 86,665 incumbent and both variants returned None.  That was the wrong
# place to look and the trace says why: 86,665 is already brk-CONVERGED -- brk ran inside the
# pipeline that produced it -- so re-running it re-derives its own answer whichever way the
# outsiders are chosen.  Both arms reported tgt=0, res=55, outs=15, 55 of 70 columns seated,
# zero outsiders admitted.  Direction can only pay where brk is called from states it has not
# already settled, which is everywhere inside a real run.
#
# THE COMPARISON.  Same module, same bytes, one environment variable apart.  There is no arm
# generation to drift between the two, which is how arm levels diverged twice tonight.
#
# NOT A P3 SPECIAL CASE.  _wish runs wherever there are two or more bays and solves the same
# objective the operator already scores against.  Where the incumbent is already the best
# assignment at those times it returns it unchanged, the wish is empty, and the pressure path
# runs exactly as before.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 \
    python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_brk as A, bayrepack as R
a = inspect.getsource(A); r = inspect.getsource(R)
assert 'import bayrepack as _brk' in a and 'hard=budget - (time.time() - t0)' in a
assert 'BRK_WISH' in r and 'def _wish(' in r, 'directed path missing from the operator'
assert '_WISH_CACHE' in r, 'the wish must be cached or it re-solves every call'
print('arm and directed operator verified')" || exit 1

run () {  # BRK_WISH tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    BRK_WISH="$1" python3.12 harness/run1.py myalg_brk 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "result: $2" >/dev/null 2>&1 )
}

for rep in 1 2 3; do
    run 1 "wish r$rep" "q28_wish_r${rep}.log"
    run 0 "ctl  r$rep" "q28_ctl_r${rep}.log"
done
echo "queue28done  $(date -u +%H:%M:%S)"
