#!/bin/bash
# Six hours on P3, P4 and P5, targets 80,000 / 22,000,000 / 8,000,000.  Start by pinning the
# baselines at the real limits, because the last numbers for these three are scattered across a
# night of logs and half of them predate the engine fixes.
#
# What the floors already say about where to look:
#   Z1's lower bound is 0 on every instance -- no deadline is physically impossible, so all
#   tardiness is congestion.
#   P3 needs 17,135 and Z3 alone holds 62,550 of recoverable cost (551 against a floor of 134).
#   Its Z1 is 0, so P3 is purely preference plus balance.
#   P5 needs 1,044,458 and Z3 holds 458,185 of it -- 44%.  The rest has to come from Z1, which
#   is 94% of its objective.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|grasp|grasp2|base345)\.py' >/dev/null; }
while busy; do sleep 20; done
for p in 3 4 5; do
  for m in myalg_orig myalg_base myalgorithm; do
    python3.12 harness/base345.py $p $m >> _n/base345.log 2>&1
  done
done
echo BASE-DONE >> _n/base345.log
python3.12 harness/headroom.py >> _n/base345.log 2>&1
echo HEADROOM-DONE >> _n/base345.log
