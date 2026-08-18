#!/bin/bash
# Price the cohort weighting against the fixed engine.
#
# Two things have to be measured together, because the previous reading was the sum of them:
# the gain, and whether the fix actually removed the throughput cost that was cancelling it.
#
#   throughput  P5 completes its beams inside the budget -- both arms were deterministic
#               there -- so the wall clock of one beam is a clean read on what the weighting
#               costs.  If the malloc-per-candidate mattered, cohort=0.3 should now finish in
#               about the time cohort=0.0 does.
#   gain        Three interleaved pairs at 300s on P6, then one pair at P5's real limit.
#               Interleaved, not blocked, so a slow stretch of machine cannot land on one arm.
#
# 300s rather than 900s on P6: the container has reset twice tonight and the mirror only saves
# runs that finished.  Three short pairs survive where two long ones do not, and the earlier
# 300s screen already resolved a tie, so the budget is enough to see a real effect.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect)\.py' >/dev/null; }
while busy; do sleep 20; done

for f in 0.0 0.3 0.0 0.3; do
  python3.12 harness/beam2.py myalg_base 5 240 $f >> _n/thru.log 2>&1
done

for r in 1 2 3; do
  python3.12 harness/run1.py myalg_orig 6 300 "ctl-r$r"  >> _n/cohfix.log 2>&1
  python3.12 harness/run1.py myalg_base 6 300 "coh-r$r"  >> _n/cohfix.log 2>&1
done
python3.12 harness/run1.py myalg_orig 5 600 "ctl"  >> _n/cohfix.log 2>&1
python3.12 harness/run1.py myalg_base 5 600 "coh"  >> _n/cohfix.log 2>&1
echo COHFIX-DONE >> _n/cohfix.log
