#!/bin/bash
# queue14 done properly: every arm paired against a brk-DEFAULT control in the same queue.
#
# WHY THIS EXISTS.  queue14 compares brk+conw0, brk nout=80 and brk step=3 -- and has no
# brk-default arm of its own, so its numbers can only be read against queue12's and queue16's.
# That is exactly the comparison this session has already been burned by: the six brk-default
# runs split cleanly by queue with no value in common,
#
#     queue12  82,180 / 86,550 / 86,550
#     queue16  90,545 / 88,720 / 91,670
#
# with the code diffed across the interval (only a no-op env override) and no contention found.
# Whatever causes that, an arm measured in one queue cannot be scored against a control measured
# in another.  queue16's verdict survived because it ran its own control; queue14's cannot.
#
# ALSO A REAL PROBLEM TO CHASE.  q14_wide_r1 took 260 s against a 240 s budget.  cranepack does
# not respect its deadline, and bayrepack's answer is to size the problem to an observed
# took/asked ratio -- but the ratio adapts from the PREVIOUS call, so a final call that lands
# near the end of the budget overruns before the estimate can react.  At the grader's hard limit
# that is a truncated or rejected answer, not a slow one.  NOUT=80 makes it worse by enlarging
# the problem, so this queue measures the overrun as carefully as the objective: run1.py already
# prints the wall clock, and any arm that exceeds its budget is disqualified whatever it scored.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_brk as A
s = inspect.getsource(A)
assert 'import bayrepack as _brk' in s and '_ogc_fast_engine' in s
assert all(x.get('conw', 1.0) == 1.0 for x in A._AXES)
print('brk arm verified')" || exit 1

run () {  # tag outfile  env...
    [ -s "results/$2" ] && return
    echo "=== $2  ($1)  $(date -u +%H:%M:%S)"
    env "${@:3}" python3.12 harness/run1.py myalg_brk 3 240 "$1" > "results/$2" 2>&1
    tail -1 "results/$2"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$2" >/dev/null 2>&1 \
      && git commit -q -m "result: $1" >/dev/null 2>&1 )
}

# Interleaved, so a drift in machine state over the queue's lifetime hits every arm rather than
# accumulating in whichever ran last.
for rep in 1 2; do
    run "brk default r$rep"  "q17_def_r${rep}.log"
    run "brk nout=80 r$rep"  "q17_wide_r${rep}.log"  BRK_NOUT=80
    run "brk step=3 r$rep"   "q17_fine_r${rep}.log"  BRK_STEP=3
done
echo "queue17done  $(date -u +%H:%M:%S)"
