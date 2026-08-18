#!/bin/bash
# Per-axis draws in the pipeline, A/B at the real limits.
#
# The worker cycles axes[gen % L], so after one pass every further visit re-runs a beam whose
# dispatch order is fixed -- and the beam is deterministic in it, so the answer is identical and
# that budget is discarded.  A 600s P5 worker fits about ten beams over six axes: four exact
# repeats.  dk makes an axis's first visit keep its fixed order (so the first pass is
# byte-identical to today, and best-of makes the whole thing never-worse) and every later visit
# draw from the top-k of what remains.
#
# Verified firing: on P5 axis 1, visit 1 gave 10,513,332 with the fixed order and visits 2 and 3
# gave 11,436,963 and 11,495,356 with drawn ones.  Both draws lost, which costs nothing -- today
# those visits return 10,513,332 again -- but it is why this needs the pipeline A/B rather than
# an assumption.
cd "$(dirname "$0")/.."
while ! grep -q MASTER-PLAN-COMPLETE _n/master.log 2>/dev/null; do sleep 60; done
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|grasp|grasp2|bgrasp|base345)\.py' >/dev/null; }
while busy; do sleep 20; done
for p in 5 4 3; do
  python3.12 harness/base345.py $p myalg_dk0 >> _n/dkab.log 2>&1
  python3.12 harness/base345.py $p myalg_dk3 >> _n/dkab.log 2>&1
done
echo DKAB-DONE >> _n/dkab.log
for p in 5 4 3; do
  python3.12 harness/base345.py $p myalg_dk3 >> _n/dkab.log 2>&1
done
echo DKAB2-DONE >> _n/dkab.log
