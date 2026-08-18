#!/bin/bash
# The exact bay repack as a real operator -- smoke test first, then measured against its control.
#
# WHY.  harness/p3bay0.py freed bay 0 on P3's base solution and let cranepack reseat everything:
#
#     residents re-seated  50 of 53      outsiders admitted  6 of 17
#     objective 96,990 -> 82,175  (-15.27%),  Z3 543 -> 446
#
# Bay 0 was not full, it was BADLY PACKED.  Every earlier check -- p3time, p3swap, p3max --
# asked whether an outsider fits around the residents AT THE POSITIONS THE PIPELINE GAVE THEM,
# and all said no; none of them could have found this, because a block that does not fit around
# one arrangement has been told nothing about a different one.
#
# No existing operator can reach it either.  _balance moves ONE block and p3max proved that
# neighbourhood empty here (evicting from bay 0 needs gap/workload under 0.0948, cheapest
# resident 0.145).  _z3_improve reassigns without re-placing.  The beam places greedily in
# dispatch order and never revisits.
#
# ONE THING THE DIAGNOSTIC DID NOT DO.  It priced the three displaced residents at their
# next-best bay instead of finding them a seat there -- the same assumption every earlier P3
# diagnostic made, and the assumption this night proved unsafe.  The operator asks the engine
# for a real seat for each displaced block and abandons the repack if any cannot be placed, so
# it is strictly harder than the -15.27% above.  brksmoke.py checks it still fires, and tells a
# "found nothing" apart from a "returned something the grader rejects" -- a None inside a 240 s
# arm is silent, which is how a broken operator reads as a neutral result.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

if [ ! -s results/q12_smoke.log ]; then
    echo "=== q12_smoke  $(date -u +%H:%M:%S)"
    python3.12 harness/brksmoke.py 3 240 60 myalg_base > results/q12_smoke.log 2>&1
    ( cd ../../.. && git add -f research/exact_packer/session2/recon/results/q12_smoke.log >/dev/null 2>&1 \
      && git commit -q -m "result: brk smoke test" >/dev/null 2>&1 )
fi
cat results/q12_smoke.log

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
OGC_DK=0 OGC_FASTOBJ=1          python3.12 harness/mkbase.py 0.3 myalg_brkctl.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_brk as A, myalg_brkctl as C
a, c = inspect.getsource(A), inspect.getsource(C)
assert 'import bayrepack as _brk' in a and '(\"brk\"' in a, 'brk arm not wired'
assert '_build_operations, _ogc_fast_engine' in a, 'engine not passed -- displaced cannot rehome'
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
