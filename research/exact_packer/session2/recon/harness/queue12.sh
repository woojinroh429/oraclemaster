#!/bin/bash
# The exact bay repack, as a real operator, measured against its own control.
#
# WHY.  The capacity-aware bound on P3 is 36,765 and the best anything has produced is 87,560 --
# 138% above it -- and area is not what blocks the difference: bay 0's first-choice demand is
# 0.48 of its cells x horizon.  What separates them is packing efficiency under the crane rule.
# Bay 0 runs at 54% peak area occupancy where the bound assumed 100%, and the blocks that would
# fix Z3 are refused because the columns they need are fragmented, not because there is no room.
#
# No existing operator can touch that.  _balance moves ONE block, and p3max proved that
# neighbourhood empty here -- evicting from bay 0 needs gap/workload under 0.0948 and the
# cheapest resident is 0.145.  _z3_improve reassigns without re-placing.  The beam places
# greedily in dispatch order and never revisits.  All three take the arrangement as given.
#
# brk lifts every block out of the contested bay, adds the outsiders that would most improve the
# objective, and lets cranepack seat maximum VALUE under the descent rule -- residents weighted
# by what evicting them would cost, outsiders by what admitting them gains.  It enters as an
# ordinary roster entry, so the allocator prices it against the other five and it earns its
# budget or gets none.  A repack that cannot re-seat every resident is discarded rather than
# patched, and the rebuilt solution is verified with the real grader before it is returned.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
OGC_DK=0 OGC_FASTOBJ=1          python3.12 harness/mkbase.py 0.3 myalg_brkctl.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_brk as A, myalg_brkctl as C
a, c = inspect.getsource(A), inspect.getsource(C)
assert 'import bayrepack as _brk' in a and '(\"brk\"' in a, 'brk arm not wired'
assert 'bayrepack' not in c, 'control must not carry the operator'
assert 'def _fast_obj' in a and 'def _fast_obj' in c, 'both arms on the fastobj base'
print('brk arm and its control verified')" || exit 1

run () {  # module tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "result: $2" >/dev/null 2>&1 )
}

for rep in 1 2 3; do
    run myalg_brk    "brk on r$rep"  "q12_brk_r${rep}.log"
    run myalg_brkctl "brk off r$rep" "q12_ctl_r${rep}.log"
done
echo "queue12done  $(date -u +%H:%M:%S)"
