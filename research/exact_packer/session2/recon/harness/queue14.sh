#!/bin/bash
# Push brk under 80,000.  Everything here starts from the arm that is already validated.
#
# WHERE IT STANDS.  Paired against its own control, three reps against two:
#
#     brk   82,180 / 86,550 / 86,550     width 4,370
#     ctl   96,990 / 106,700             width 9,710
#
# The bands do not overlap, brk's worst run is 10,440 under the control's best, and all three
# are under the 87,560 that every scoring knob this session could reach at its luckiest.  r2 and
# r3 agree to the digit on Z2 and Z3, so the operator converges rather than drifts.
#
# THREE WAYS FURTHER, each testing a different reason 82,180 is not lower.
#
#   A  stack     conw=0.0 is the best thing the scoring knobs found (87,560) and brk is the best
#                thing the operators found.  They act on different stages -- conw flattens the
#                packing as it is BUILT, brk re-solves it after the fact -- so they might add, or
#                conw's looser layout might simply give brk less to repair.  Untested either way,
#                and the answer decides whether the knob work was wasted or merely early.
#
#   B  wider     the operator considers the 40 most valuable outsiders per call.  The diagnostic
#                found only 17 profitable at all on its base, so 40 was never binding there --
#                but brk's own output has a different set, and after two repacks the third call
#                may be choosing from a list its cap has trimmed.  80 says whether the cap binds.
#
#   C  finer     grid step 4 is what both diagnostics used.  Step 2 admitted FEWER blocks (4 vs
#                6) on its own base, which reads as a worse setting -- but it also ran 18 minutes
#                against a 120 s ask, so what it really showed is that step 2 does not fit in a
#                slice.  Step 3 is the untried middle, and the operator now measures its own
#                overrun, so a setting that does not fit will shrink itself rather than hang.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 python3.12 harness/mkbase.py 0.3 myalg_brk.py   0 "" 0 1.0 "" 0 ""  >/dev/null || exit 1
OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 python3.12 harness/mkbase.py 0.3 myalg_brkc0.py 0 "" 0 1.0 "" 0 0.0 >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_brk as A, myalg_brkc0 as B
a, b = inspect.getsource(A), inspect.getsource(B)
for nm, s in (('brk', a), ('brkc0', b)):
    assert 'import bayrepack as _brk' in s and '_ogc_fast_engine' in s, nm
assert all(x.get('conw', 1.0) == 1.0 for x in A._AXES), 'brk arm must keep contact at full'
assert all(x.get('conw') == 0.0 for x in B._AXES), 'brkc0 arm must have contact off'
print('brk and brk+conw0 arms verified')" || exit 1

run () {  # module tag outfile  env...
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    env "${@:4}" python3.12 harness/run1.py "$1" 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "result: $2" >/dev/null 2>&1 )
}

for rep in 1 2; do
    run myalg_brkc0 "brk+conw0 r$rep"  "q14_stack_r${rep}.log"
    run myalg_brk   "brk nout=80 r$rep" "q14_wide_r${rep}.log"  BRK_NOUT=80
    run myalg_brk   "brk step=3 r$rep"  "q14_fine_r${rep}.log"  BRK_STEP=3
done
echo "queue14done  $(date -u +%H:%M:%S)"
